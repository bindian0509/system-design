"""
Scheduler service - handles cron job triggering.
"""
import logging
import time
from datetime import datetime
from croniter import croniter
import json

from common.config import settings
from common.database import get_db_context
from common.queue import get_queue, MessageQueue
from common.models import Schedule, Job, JobStatus, ExecutionType
from api.services import JobOrchestrator

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class CronScheduler:
    """Scheduler service - triggers scheduled jobs based on cron expressions."""

    def __init__(self, check_interval_seconds: int = 60):
        """
        Initialize scheduler.

        Args:
            check_interval_seconds: How often to check for jobs to trigger
        """
        self.check_interval_seconds = check_interval_seconds
        self.queue = get_queue()
        self.running = True
        logger.info(f"Initialized scheduler with check interval {check_interval_seconds}s")

    def check_schedules(self):
        """
        Check all active schedules and trigger jobs if due.
        """
        with get_db_context() as db:
            # Get all active schedules
            schedules = db.query(Schedule).filter(
                Schedule.is_active == True
            ).all()

            now = datetime.utcnow()

            for schedule in schedules:
                try:
                    # Parse cron expression
                    cron = croniter(schedule.cron_expression, now)

                    # Get next scheduled run
                    next_run = cron.get_next(datetime)

                    # Check if this schedule should be triggered
                    if schedule.next_scheduled_run is None or now >= schedule.next_scheduled_run:
                        logger.info(f"Triggering schedule {schedule.schedule_id}")

                        # Create job from template
                        job_template = schedule.job_template
                        job_data = {
                            "name": job_template.get("name", f"{schedule.name} #{now.timestamp()}"),
                            "description": job_template.get("description", f"Auto-triggered from schedule {schedule.schedule_id}"),
                            "payload": job_template.get("payload", {}),
                            "execution_type": ExecutionType.SCHEDULED.value,
                            "timeout_seconds": job_template.get("timeout_seconds", 3600),
                            "retry": job_template.get("retry", {
                                "max_attempts": 3,
                                "backoff_multiplier": 2,
                                "backoff_base_seconds": 60
                            }),
                        }

                        # Create the job
                        try:
                            job = JobOrchestrator.create_job(
                                db=db,
                                team_id=schedule.team_id,
                                job_data=job_data,
                                created_by="scheduler",
                            )

                            # Update schedule metadata
                            schedule.last_triggered_at = now
                            schedule.next_scheduled_run = next_run
                            db.commit()

                            logger.info(f"Created job {job.job_id} from schedule {schedule.schedule_id}")

                        except Exception as e:
                            logger.error(f"Error creating job from schedule {schedule.schedule_id}: {e}")
                            # Continue with next schedule
                    else:
                        # Update next scheduled run if needed
                        if schedule.next_scheduled_run != next_run:
                            schedule.next_scheduled_run = next_run
                            db.commit()

                except Exception as e:
                    logger.error(f"Error processing schedule {schedule.schedule_id}: {e}")
                    continue

    def run(self):
        """
        Main scheduler loop - continuously check for jobs to trigger.
        """
        try:
            logger.info("Scheduler service started")

            while self.running:
                try:
                    self.check_schedules()

                    # Sleep before next check
                    time.sleep(self.check_interval_seconds)

                except Exception as e:
                    logger.error(f"Error in scheduler check: {e}", exc_info=True)
                    # Continue despite errors
                    time.sleep(self.check_interval_seconds)

        except KeyboardInterrupt:
            logger.info("Scheduler interrupted by user")
        finally:
            self.queue.close()
            logger.info("Scheduler service stopped")


def main():
    """Entry point for scheduler service."""
    check_interval = settings.scheduler_check_interval_seconds
    scheduler = CronScheduler(check_interval)
    scheduler.run()


if __name__ == "__main__":
    main()
