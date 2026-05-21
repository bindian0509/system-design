"""
Job Orchestrator service - handles job state management and orchestration.
"""
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from common.models import Job, JobStatus, ExecutionType, JobExecution, Team
from common.queue import get_queue, MessageQueue
from common.quota import QuotaManager, RetryScheduler

logger = logging.getLogger(__name__)


class JobOrchestrator:
    """Orchestrates job lifecycle and state transitions."""

    @staticmethod
    def create_job(
        db: Session,
        team_id: str,
        job_data: Dict[str, Any],
        created_by: str,
    ) -> Job:
        """
        Create a new job and enqueue it for processing.

        Args:
            db: Database session
            team_id: Team ID
            job_data: Job payload
            created_by: User ID of creator

        Returns:
            Created Job object

        Raises:
            Exception if team doesn't exist or quotas exceeded
        """
        # Verify team exists
        team = db.query(Team).filter(Team.team_id == team_id).first()
        if not team:
            raise ValueError(f"Team {team_id} not found")

        # Check all quotas
        allowed, message = QuotaManager.check_all_quotas(db, team_id)
        if not allowed:
            raise ValueError(message)
            name=job_data.get("name"),
            description=job_data.get("description"),
            execution_type=job_data.get("execution_type", ExecutionType.ON_DEMAND),
            status=JobStatus.QUEUED,
            payload=job_data.get("payload", {}),
            dag_config=job_data.get("dag_config"),
            timeout_seconds=job_data.get("timeout_seconds", 3600),
            retry_config=job_data.get("retry", {
                "max_attempts": 3,
                "backoff_multiplier": 2,
                "backoff_base_seconds": 60
            }),
            created_by=created_by,
            created_at=datetime.utcnow(),
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        logger.info(f"Created job {job.job_id} for team {team_id}")

        # Publish to queue for processing
        JobOrchestrator._enqueue_job(job)

        return job

    @staticmethod
    def get_job(db: Session, job_id: str, team_id: Optional[str] = None) -> Optional[Job]:
        """
        Get job by ID with optional team verification.

        Args:
            db: Database session
            job_id: Job ID
            team_id: Optional team ID for verification

        Returns:
            Job object or None if not found
        """
        query = db.query(Job).filter(Job.job_id == job_id)

        if team_id:
            query = query.filter(Job.team_id == team_id)

        return query.first()

    @staticmethod
    def list_jobs(
        db: Session,
        team_id: str,
        status: Optional[JobStatus] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[Job], int]:
        """
        List jobs for a team with optional filtering.

        Args:
            db: Database session
            team_id: Team ID
            status: Optional status filter
            limit: Page size
            offset: Pagination offset

        Returns:
            Tuple of (jobs list, total count)
        """
        query = db.query(Job).filter(Job.team_id == team_id)

        if status:
            query = query.filter(Job.status == status)

        total = query.count()
        jobs = query.order_by(Job.created_at.desc()).limit(limit).offset(offset).all()

        return jobs, total

    @staticmethod
    def update_job_status(
        db: Session,
        job_id: str,
        new_status: JobStatus,
        error_message: Optional[str] = None,
        result_url: Optional[str] = None,
    ) -> Job:
        """
        Update job status and associated metadata.

        Args:
            db: Database session
            job_id: Job ID
            new_status: New status
            error_message: Optional error details
            result_url: Optional result storage path

        Returns:
            Updated Job object
        """
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        old_status = job.status
        job.status = new_status

        if error_message:
            job.error_message = error_message

        if result_url:
            job.result_url = result_url

        # Update timestamps based on status
        if new_status == JobStatus.RUNNING and not job.started_at:
            job.started_at = datetime.utcnow()
        elif new_status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            job.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(job)

        logger.info(f"Job {job_id} status updated: {old_status} -> {new_status}")

        # Publish event for monitoring/alerts
        queue = get_queue()
        event_type = f"job.{new_status.value}"
        queue.publish_event(event_type, {
            "job_id": job_id,
            "team_id": job.team_id,
            "status": new_status.value,
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return job

    @staticmethod
    def cancel_job(db: Session, job_id: str, team_id: str) -> Job:
        """
        Cancel a job (only if not already running/completed).

        Args:
            db: Database session
            job_id: Job ID
            team_id: Team ID for verification

        Returns:
            Updated Job object

        Raises:
            ValueError if job cannot be cancelled
        """
        job = JobOrchestrator.get_job(db, job_id, team_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            raise ValueError(f"Cannot cancel job in {job.status.value} state")

        return JobOrchestrator.update_job_status(db, job_id, JobStatus.CANCELLED)

    @staticmethod
    def create_execution(
        db: Session,
        job_id: str,
        attempt_number: int,
        worker_pod_id: Optional[str] = None,
    ) -> JobExecution:
        """
        Create an execution record for a job attempt.

        Args:
            db: Database session
            job_id: Job ID
            attempt_number: Attempt number
            worker_pod_id: Optional K8s pod ID

        Returns:
            Created JobExecution object
        """
        execution = JobExecution(
            execution_id=str(uuid.uuid4()),
            job_id=job_id,
            attempt_number=attempt_number,
            status=JobStatus.RUNNING,
            worker_pod_id=worker_pod_id,
            started_at=datetime.utcnow(),
        )

        db.add(execution)
        db.commit()
        db.refresh(execution)

        return execution

    @staticmethod
    def complete_execution(
        db: Session,
        execution_id: str,
        status: JobStatus,
        duration_seconds: int,
        logs_url: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> JobExecution:
        """
        Complete an execution record.

        Args:
            db: Database session
            execution_id: Execution ID
            status: Completion status (COMPLETED or FAILED)
            duration_seconds: Execution duration
            logs_url: Optional logs storage path
            error_details: Optional error details

        Returns:
            Updated JobExecution object
        """
        execution = db.query(JobExecution).filter(
            JobExecution.execution_id == execution_id
        ).first()

        if not execution:
            raise ValueError(f"Execution {execution_id} not found")

        execution.status = status
        execution.completed_at = datetime.utcnow()
        execution.duration_seconds = duration_seconds

        if logs_url:
            execution.logs_url = logs_url

        if error_details:
            execution.error_details = error_details

        db.commit()
        db.refresh(execution)

        return execution

    @staticmethod
    def _enqueue_job(job: Job):
        """Publish job to processing queue."""
        queue = get_queue()
        queue.publish_job(
            MessageQueue.QUEUE_JOB_PENDING,
            {
                "job_id": job.job_id,
                "team_id": job.team_id,
                "payload": job.payload,
                "timeout_seconds": job.timeout_seconds,
                "dag_config": job.dag_config,
                "scheduled_at": datetime.utcnow().isoformat(),
            }
        )
        logger.debug(f"Enqueued job {job.job_id} to {MessageQueue.QUEUE_JOB_PENDING}")
, queue_name: str = MessageQueue.QUEUE_JOB_PENDING):
        """
        Publish job to processing queue.

        Args:
            job: Job to enqueue
            queue_name: Queue to publish to
        """
        queue = get_queue()
        queue.publish_job(
            queue_name,
            {
                "job_id": job.job_id,
                "team_id": job.team_id,
                "payload": job.payload,
                "timeout_seconds": job.timeout_seconds,
                "dag_config": job.dag_config,
                "retry_config": job.retry_config,
                "scheduled_at": datetime.utcnow().isoformat(),
            }
        )
        logger.debug(f"Enqueued job {job.job_id} to {queue_name}")

    @staticmethod
    def move_to_dlq(
        db: Session,
        job_id: str,
        error_message: str,
        final_error_details: Optional[Dict[str, Any]] = None,
    ) -> Job:
        """
        Move job to dead letter queue (permanent failure).

        Args:
            db: Database session
            job_id: Job ID
            error_message: Error message
            final_error_details: Final error details

        Returns:
            Updated Job object
        """
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatus.FAILED
        job.error_message = error_message
        job.completed_at = datetime.utcnow()

        # Publish to DLQ
        queue = get_queue()
        queue.publish_job(
            MessageQueue.QUEUE_JOB_FAILED,
            {
                "job_id": job_id,
                "team_id": job.team_id,
                "error_message": error_message,
                "error_details": final_error_details or {},
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        db.commit()
        logger.warning(f"Moved job {job_id} to DLQ: {error_message}")

        return job
