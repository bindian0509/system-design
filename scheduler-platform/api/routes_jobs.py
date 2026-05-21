"""
API routes for job management.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from common.database import SessionLocal
from common.models import JobStatus, ExecutionType
from api.schemas import (
    JobCreateRequest, JobResponse, JobListResponse,
    JobExecutionHistoryItem, ErrorResponse
)
from api.services import JobOrchestrator
from api.middleware import get_user_info
from common.quota import QuotaManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def get_db():
    """Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    request: JobCreateRequest,
    db: Session = Depends(get_db),
    user_info: dict = Depends(get_user_info),
):
    """
    Create a new job.

    **Request Body:**
    - `name`: Job name
    - `team_id`: Team ID
    - `payload`: Job-specific parameters
    - `execution_type`: on_demand, scheduled, or recurring
    - `timeout_seconds`: Job timeout (default: 3600)
    - `retry`: Retry configuration
    - `dag_config`: Optional DAG structure

    **Response:** Created job details with job_id

    **Errors:**
    - 400: Invalid request
    - 401: Unauthorized
    - 403: Insufficient permissions
    - 409: Team quota exceeded
    """
    try:
        # Verify user is part of the team and has editor or admin role
        if request.team_id not in user_info.get("teams", []):
            raise HTTPException(
                status_code=403,
                detail="User not a member of this team"
            )

        user_role = user_info.get("roles", {}).get(request.team_id)
        if user_role not in ["editor", "admin"]:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions. Requires editor or admin role"
            )

        # Verify quotas before creating job
        allowed, message = QuotaManager.check_all_quotas(db, request.team_id)
        if not allowed:
            raise HTTPException(
                status_code=429,  # Too Many Requests
                detail=message
            )

        # Create job
        job = JobOrchestrator.create_job(
            db=db,
            team_id=request.team_id,
            job_data=request.dict(exclude_unset=True),
            created_by=user_info.get("user_id"),
        )

        return JobResponse.from_orm(job)

    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    user_info: dict = Depends(get_user_info),
):
    """
    Get job details by ID.

    **Response:** Job details including status, execution history, and results

    **Errors:**
    - 401: Unauthorized
    - 404: Job not found
    """
    try:
        job = JobOrchestrator.get_job(db, job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Check user is part of job's team
        if job.team_id not in user_info.get("teams", []):
            raise HTTPException(
                status_code=403,
                detail="User not authorized to view this job"
            )

        # Build execution history
        execution_history = [
            JobExecutionHistoryItem(
                attempt=exe.attempt_number,
                started_at=exe.started_at,
                status=JobStatus(exe.status.value),
                error=exe.error_details.get("message") if exe.error_details else None,
                duration_seconds=exe.duration_seconds,
            )
            for exe in job.executions
        ]

        response = JobResponse.from_orm(job)
        response.execution_history = execution_history

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=JobListResponse)
async def list_jobs(
    team_id: str,
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user_info: dict = Depends(get_user_info),
):
    """
    List jobs for a team.

    **Query Parameters:**
    - `team_id`: Team ID (required)
    - `status`: Filter by status (queued, running, completed, failed, cancelled)
    - `limit`: Results per page (default: 20, max: 100)
    - `offset`: Pagination offset (default: 0)

    **Response:** Paginated list of jobs

    **Errors:**
    - 401: Unauthorized
    - 403: Not a team member
    """
    try:
        # Check user is part of the team
        if team_id not in user_info.get("teams", []):
            raise HTTPException(
                status_code=403,
                detail="User not a member of this team"
            )

        # Parse status filter
        status_filter = None
        if status:
            try:
                status_filter = JobStatus(status.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}"
                )

        # List jobs
        jobs, total = JobOrchestrator.list_jobs(
            db=db,
            team_id=team_id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )

        job_responses = [JobResponse.from_orm(job) for job in jobs]

        return JobListResponse(
            jobs=job_responses,
            total=total,
            page=offset // limit + 1,
            page_size=limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{job_id}/cancel", status_code=204)
async def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    user_info: dict = Depends(get_user_info),
):
    """
    Cancel a job.

    **Errors:**
    - 401: Unauthorized
    - 403: Insufficient permissions
    - 404: Job not found
    - 409: Job cannot be cancelled (already completed/failed)
    """
    try:
        job = JobOrchestrator.get_job(db, job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Check permissions
        if job.team_id not in user_info.get("teams", []):
            raise HTTPException(status_code=403, detail="Unauthorized")

        user_role = user_info.get("roles", {}).get(job.team_id)
        if user_role not in ["editor", "admin"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Cancel job
        JobOrchestrator.cancel_job(db, job_id, job.team_id)

    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
