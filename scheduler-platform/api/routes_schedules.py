"""
API routes for schedule management.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import uuid
from datetime import datetime
import logging

from common.database import SessionLocal
from common.models import Schedule, Team
from api.schemas import ScheduleCreateRequest, ScheduleResponse
from api.middleware import get_user_info

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


def get_db():
    """Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    request: ScheduleCreateRequest,
    db: Session = Depends(get_db),
    user_info: dict = Depends(get_user_info),
):
    """
    Create a new schedule (cron-based recurring job).

    **Request Body:**
    - `name`: Schedule name
    - `team_id`: Team ID
    - `cron`: Cron expression (e.g., "0 2 * * *" for daily at 2 AM)
    - `timezone`: Timezone for cron evaluation (default: UTC)
    - `job_template`: Base job configuration
    - `max_concurrent`: Max concurrent jobs from this schedule (default: 1)

    **Response:** Created schedule details

    **Errors:**
    - 400: Invalid cron expression
    - 401: Unauthorized
    - 403: Insufficient permissions
    """
    try:
        # Check permissions
        if request.team_id not in user_info.get("teams", []):
            raise HTTPException(status_code=403, detail="User not a member of this team")

        user_role = user_info.get("roles", {}).get(request.team_id)
        if user_role not in ["editor", "admin"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Verify team exists
        team = db.query(Team).filter(Team.team_id == request.team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Create schedule
        schedule = Schedule(
            schedule_id=str(uuid.uuid4()),
            team_id=request.team_id,
            name=request.name,
            description=request.description,
            cron_expression=request.cron,
            timezone=request.timezone,
            job_template=request.job_template,
            max_concurrent_executions=request.max_concurrent,
            is_active=True,
            created_by=user_info.get("user_id"),
            created_at=datetime.utcnow(),
        )

        db.add(schedule)
        db.commit()
        db.refresh(schedule)

        logger.info(f"Created schedule {schedule.schedule_id} for team {request.team_id}")

        return ScheduleResponse.from_orm(schedule)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating schedule: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    user_info: dict = Depends(get_user_info),
):
    """
    Get schedule details by ID.

    **Errors:**
    - 401: Unauthorized
    - 403: Not a team member
    - 404: Schedule not found
    """
    try:
        schedule = db.query(Schedule).filter(
            Schedule.schedule_id == schedule_id
        ).first()

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Check permissions
        if schedule.team_id not in user_info.get("teams", []):
            raise HTTPException(status_code=403, detail="Unauthorized")

        return ScheduleResponse.from_orm(schedule)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving schedule: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    team_id: str = Query(...),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    user_info: dict = Depends(get_user_info),
):
    """
    List schedules for a team.

    **Query Parameters:**
    - `team_id`: Team ID (required)
    - `active_only`: Filter to active schedules only (default: true)

    **Errors:**
    - 401: Unauthorized
    - 403: Not a team member
    """
    try:
        # Check permissions
        if team_id not in user_info.get("teams", []):
            raise HTTPException(status_code=403, detail="User not a member of this team")

        # List schedules
        query = db.query(Schedule).filter(Schedule.team_id == team_id)

        if active_only:
            query = query.filter(Schedule.is_active == True)

        schedules = query.order_by(Schedule.created_at.desc()).all()

        return [ScheduleResponse.from_orm(s) for s in schedules]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing schedules: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    user_info: dict = Depends(get_user_info),
):
    """
    Delete a schedule (soft delete - mark as inactive).

    **Errors:**
    - 401: Unauthorized
    - 403: Insufficient permissions
    - 404: Schedule not found
    """
    try:
        schedule = db.query(Schedule).filter(
            Schedule.schedule_id == schedule_id
        ).first()

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Check permissions
        if schedule.team_id not in user_info.get("teams", []):
            raise HTTPException(status_code=403, detail="Unauthorized")

        user_role = user_info.get("roles", {}).get(schedule.team_id)
        if user_role not in ["editor", "admin"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Soft delete by marking inactive
        schedule.is_active = False
        db.commit()

        logger.info(f"Deleted schedule {schedule_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting schedule: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
