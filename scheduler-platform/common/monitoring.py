"""
Monitoring and metrics collection for the scheduler platform.
"""
import logging
from datetime import datetime
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from sqlalchemy.orm import Session
from sqlalchemy import func

from common.models import Job, JobStatus, Team

logger = logging.getLogger(__name__)

# Create registry for metrics
registry = CollectorRegistry()

# Job submission metrics
job_submissions = Counter(
    'job_submissions_total',
    'Total number of job submissions',
    ['team_id', 'execution_type'],
    registry=registry
)

# Job completion metrics
job_completions = Counter(
    'job_completions_total',
    'Total number of job completions',
    ['team_id', 'status'],
    registry=registry
)

# Job execution duration
job_duration = Histogram(
    'job_duration_seconds',
    'Job execution duration in seconds',
    ['team_id'],
    registry=registry
)

# Job retry attempts
job_retries = Counter(
    'job_retries_total',
    'Total number of job retries',
    ['team_id'],
    registry=registry
)

# Queue depth
queue_depth = Gauge(
    'queue_depth',
    'Number of pending jobs in queue',
    ['queue_name'],
    registry=registry
)

# Team quota utilization
team_quota_usage = Gauge(
    'team_quota_usage_percent',
    'Team resource quota usage percentage',
    ['team_id', 'quota_type'],
    registry=registry
)


class MetricsCollector:
    """Collects and updates system metrics."""

    @staticmethod
    def record_job_submission(team_id: str, execution_type: str):
        """Record job submission metric."""
        job_submissions.labels(team_id=team_id, execution_type=execution_type).inc()

    @staticmethod
    def record_job_completion(team_id: str, status: JobStatus, duration_seconds: int = 0):
        """Record job completion metric."""
        job_completions.labels(team_id=team_id, status=status.value).inc()
        if duration_seconds > 0:
            job_duration.labels(team_id=team_id).observe(duration_seconds)

    @staticmethod
    def record_retry(team_id: str):
        """Record job retry."""
        job_retries.labels(team_id=team_id).inc()

    @staticmethod
    def update_queue_depth(queue_name: str, depth: int):
        """Update queue depth metric."""
        queue_depth.labels(queue_name=queue_name).set(depth)

    @staticmethod
    def update_team_quotas(db: Session):
        """
        Update team quota utilization metrics.

        Args:
            db: Database session
        """
        teams = db.query(Team).all()

        for team in teams:
            # Daily job quota
            today = datetime.utcnow().date()
            jobs_today = db.query(Job).filter(
                Job.team_id == team.team_id,
                Job.created_at >= datetime(today.year, today.month, today.day),
                Job.status != JobStatus.CANCELLED
            ).count()

            daily_quota_pct = (jobs_today / team.quota_jobs_per_day * 100) if team.quota_jobs_per_day > 0 else 0
            team_quota_usage.labels(
                team_id=team.team_id,
                quota_type="daily_jobs"
            ).set(min(100, daily_quota_pct))

            # Concurrent job quota
            concurrent_jobs = db.query(Job).filter(
                Job.team_id == team.team_id,
                Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED])
            ).count()

            concurrent_quota_pct = (concurrent_jobs / team.quota_concurrent_jobs * 100) if team.quota_concurrent_jobs > 0 else 0
            team_quota_usage.labels(
                team_id=team.team_id,
                quota_type="concurrent_jobs"
            ).set(min(100, concurrent_quota_pct))

            # Storage quota
            storage_used = db.query(
                func.sum(Job.result_size_bytes)
            ).filter(
                Job.team_id == team.team_id,
                Job.result_size_bytes.isnot(None),
                Job.status == JobStatus.COMPLETED
            ).scalar() or 0

            storage_quota_pct = (storage_used / team.quota_storage_bytes * 100) if team.quota_storage_bytes > 0 else 0
            team_quota_usage.labels(
                team_id=team.team_id,
                quota_type="storage"
            ).set(min(100, storage_quota_pct))


class AlertingService:
    """Handles alerting for critical events."""

    ALERT_CHANNELS = {
        "slack": None,  # Would be webhook URL
        "email": None,  # Would be email address
        "pagerduty": None,  # Would be integration key
    }

    @staticmethod
    def send_alert(alert_type: str, message: str, severity: str = "warning"):
        """
        Send alert through configured channels.

        Args:
            alert_type: Type of alert (failure_rate, quota_exceeded, etc.)
            message: Alert message
            severity: Severity level (info, warning, critical)
        """
        logger.warning(f"Alert [{alert_type}] [{severity}]: {message}")

        # In production, integrate with Slack, PagerDuty, email, etc.
        # Example: send_to_slack(f"[{severity.upper()}] {alert_type}: {message}")

    @staticmethod
    def check_failure_rate(db: Session, team_id: str, threshold_pct: float = 5.0):
        """
        Check if job failure rate exceeds threshold.

        Args:
            db: Database session
            team_id: Team ID
            threshold_pct: Failure threshold percentage
        """
        # Get jobs from last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        total_jobs = db.query(Job).filter(
            Job.team_id == team_id,
            Job.created_at >= one_hour_ago,
            Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED])
        ).count()

        if total_jobs == 0:
            return

        failed_jobs = db.query(Job).filter(
            Job.team_id == team_id,
            Job.created_at >= one_hour_ago,
            Job.status == JobStatus.FAILED
        ).count()

        failure_rate = (failed_jobs / total_jobs * 100)

        if failure_rate > threshold_pct:
            AlertingService.send_alert(
                "high_failure_rate",
                f"Team {team_id}: {failure_rate:.1f}% job failure rate (threshold: {threshold_pct}%)",
                severity="critical"
            )

    @staticmethod
    def check_queue_depth(queue_depth: int, threshold: int = 10000):
        """
        Check if queue depth exceeds threshold.

        Args:
            queue_depth: Current queue depth
            threshold: Queue depth threshold
        """
        if queue_depth > threshold:
            AlertingService.send_alert(
                "high_queue_depth",
                f"Queue depth {queue_depth} exceeds threshold {threshold}",
                severity="critical"
            )

    @staticmethod
    def check_quota_exceeded(db: Session, team_id: str):
        """
        Check if team has exceeded quotas.

        Args:
            db: Database session
            team_id: Team ID
        """
        from common.quota import QuotaManager

        allowed, message = QuotaManager.check_all_quotas(db, team_id)

        if not allowed:
            AlertingService.send_alert(
                "quota_exceeded",
                f"Team {team_id}: {message}",
                severity="warning"
            )
