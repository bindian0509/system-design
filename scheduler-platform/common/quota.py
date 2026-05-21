"""
Quota management - enforce resource limits per team.
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from common.models import Job, JobStatus, Team

logger = logging.getLogger(__name__)


class QuotaManager:
    """Manages team resource quotas."""

    @staticmethod
    def check_job_creation_quota(db: Session, team_id: str) -> tuple[bool, str]:
        """
        Check if team can create another job today.

        Args:
            db: Database session
            team_id: Team ID

        Returns:
            Tuple of (allowed: bool, message: str)
        """
        # Get team and their quota
        team = db.query(Team).filter(Team.team_id == team_id).first()
        if not team:
            return False, f"Team {team_id} not found"

        # Count jobs created today (exclude cancelled)
        today = datetime.utcnow().date()
        jobs_today = db.query(Job).filter(
            and_(
                Job.team_id == team_id,
                Job.created_at >= datetime(today.year, today.month, today.day),
                Job.status != JobStatus.CANCELLED
            )
        ).count()

        if jobs_today >= team.quota_jobs_per_day:
            return False, (
                f"Daily quota exceeded: {jobs_today}/{team.quota_jobs_per_day} "
                f"jobs created today"
            )

        return True, ""

    @staticmethod
    def check_concurrent_quota(db: Session, team_id: str) -> tuple[bool, str]:
        """
        Check if team can run another concurrent job.

        Args:
            db: Database session
            team_id: Team ID

        Returns:
            Tuple of (allowed: bool, message: str)
        """
        team = db.query(Team).filter(Team.team_id == team_id).first()
        if not team:
            return False, f"Team {team_id} not found"

        # Count running/queued jobs
        running_jobs = db.query(Job).filter(
            and_(
                Job.team_id == team_id,
                Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED])
            )
        ).count()

        if running_jobs >= team.quota_concurrent_jobs:
            return False, (
                f"Concurrent job quota exceeded: {running_jobs}/"
                f"{team.quota_concurrent_jobs} concurrent jobs"
            )

        return True, ""

    @staticmethod
    def check_storage_quota(db: Session, team_id: str, additional_bytes: int) -> tuple[bool, str]:
        """
        Check if team has storage quota for job results.

        Args:
            db: Database session
            team_id: Team ID
            additional_bytes: Additional storage needed

        Returns:
            Tuple of (allowed: bool, message: str)
        """
        team = db.query(Team).filter(Team.team_id == team_id).first()
        if not team:
            return False, f"Team {team_id} not found"

        # Sum up storage used by completed jobs
        storage_used = db.query(
            db.func.sum(Job.result_size_bytes)
        ).filter(
            and_(
                Job.team_id == team_id,
                Job.result_size_bytes.isnot(None),
                Job.status == JobStatus.COMPLETED
            )
        ).scalar() or 0

        if storage_used + additional_bytes > team.quota_storage_bytes:
            return False, (
                f"Storage quota exceeded: {storage_used + additional_bytes}/"
                f"{team.quota_storage_bytes} bytes"
            )

        return True, ""

    @staticmethod
    def check_all_quotas(db: Session, team_id: str) -> tuple[bool, str]:
        """
        Check all quotas for team.

        Args:
            db: Database session
            team_id: Team ID

        Returns:
            Tuple of (allowed: bool, message: str)
        """
        # Check creation quota
        allowed, message = QuotaManager.check_job_creation_quota(db, team_id)
        if not allowed:
            return False, message

        # Check concurrent quota
        allowed, message = QuotaManager.check_concurrent_quota(db, team_id)
        if not allowed:
            return False, message

        return True, ""


class RetryScheduler:
    """Manages job retry logic with exponential backoff."""

    @staticmethod
    def calculate_retry_delay(
        attempt: int,
        backoff_base_seconds: int,
        backoff_multiplier: float
    ) -> int:
        """
        Calculate delay for next retry using exponential backoff.

        Args:
            attempt: Current attempt number (1-indexed)
            backoff_base_seconds: Base delay in seconds
            backoff_multiplier: Multiplier for exponential growth

        Returns:
            Delay in seconds for next retry
        """
        # delay = base * (multiplier ^ attempt)
        delay = int(backoff_base_seconds * (backoff_multiplier ** (attempt - 1)))

        # Add jitter (±10%) to prevent thundering herd
        import random
        jitter = delay * random.uniform(-0.1, 0.1)

        return max(1, int(delay + jitter))

    @staticmethod
    def should_retry(
        db: Session,
        job_id: str,
        max_attempts: int
    ) -> tuple[bool, Optional[int]]:
        """
        Determine if job should be retried and calculate next retry time.

        Args:
            db: Database session
            job_id: Job ID
            max_attempts: Maximum retry attempts

        Returns:
            Tuple of (should_retry: bool, next_retry_timestamp: Optional[int])
        """
        from common.models import JobExecution

        # Get executions for this job
        executions = db.query(JobExecution).filter(
            JobExecution.job_id == job_id
        ).order_by(JobExecution.attempt_number.desc()).all()

        if not executions:
            return True, 0  # First attempt

        last_execution = executions[0]
        attempt_number = last_execution.attempt_number

        # Check if max attempts reached
        if attempt_number >= max_attempts:
            return False, None

        # Schedule next retry
        return True, None

    @staticmethod
    def schedule_retry(
        db: Session,
        job_id: str,
        attempt: int,
        retry_config: dict
    ) -> datetime:
        """
        Schedule job for retry.

        Args:
            db: Database session
            job_id: Job ID
            attempt: Current attempt number
            retry_config: Retry configuration

        Returns:
            Scheduled retry time
        """
        from common.models import Job

        backoff_base = retry_config.get("backoff_base_seconds", 60)
        backoff_multiplier = retry_config.get("backoff_multiplier", 2.0)

        delay = RetryScheduler.calculate_retry_delay(
            attempt,
            backoff_base,
            backoff_multiplier
        )

        next_retry_time = datetime.utcnow() + timedelta(seconds=delay)

        # Update job status to retry_pending
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            job.status = JobStatus.RETRY_PENDING
            db.commit()

        logger.info(
            f"Scheduled retry for job {job_id}: attempt {attempt + 1} "
            f"in {delay} seconds"
        )

        return next_retry_time
