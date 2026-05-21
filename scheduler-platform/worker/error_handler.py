"""
Error recovery worker - handles retry queue and DLQ processing.
"""
import logging
import json
import time
from datetime import datetime

from common.config import settings
from common.database import get_db_context
from common.queue import get_queue, MessageQueue
from common.models import JobStatus, JobExecution
from api.services import JobOrchestrator

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class RetryHandler:
    """Handles job retry logic."""

    def __init__(self, worker_id: str):
        """Initialize retry handler."""
        self.worker_id = worker_id
        self.queue = get_queue()
        logger.info(f"Initialized retry handler {worker_id}")

    def process_retry(self, job_id: str, team_id: str, payload: dict, timeout_seconds: int, attempt: int):
        """
        Process a job retry.

        Args:
            job_id: Job ID
            team_id: Team ID
            payload: Job payload
            timeout_seconds: Execution timeout
            attempt: Current attempt number
        """
        try:
            with get_db_context() as db:
                job = JobOrchestrator.get_job(db, job_id, team_id)
                if not job:
                    logger.warning(f"Job {job_id} not found for retry")
                    return

                # Create new execution record for this retry
                execution = JobOrchestrator.create_execution(
                    db,
                    job_id,
                    attempt_number=attempt,
                    worker_pod_id=self.worker_id,
                )
                execution_id = execution.execution_id

            logger.info(f"Retrying job {job_id} (attempt {attempt}, execution {execution_id})")

            # Re-publish to main job queue for processing
            self.queue.publish_job(
                MessageQueue.QUEUE_JOB_PENDING,
                {
                    "job_id": job_id,
                    "team_id": team_id,
                    "payload": payload,
                    "timeout_seconds": timeout_seconds,
                    "scheduled_at": datetime.utcnow().isoformat(),
                }
            )

        except Exception as e:
            logger.error(f"Error processing retry for job {job_id}: {e}", exc_info=True)

    def callback_process_retry(self, ch, method, properties, body):
        """Callback for processing retry from RabbitMQ."""
        try:
            message = json.loads(body)

            job_id = message.get("job_id")
            team_id = message.get("team_id")
            payload = message.get("payload", {})
            timeout_seconds = message.get("timeout_seconds", 3600)
            attempt = message.get("attempt", 1)

            logger.debug(f"Processing retry: {job_id}")

            self.process_retry(job_id, team_id, payload, timeout_seconds, attempt)

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            logger.error(f"Error in retry callback: {e}", exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def run(self):
        """Start consuming from retry queue."""
        try:
            logger.info("Retry handler starting...")

            self.queue.consume(
                queue_name=MessageQueue.QUEUE_JOB_RETRY,
                callback=self.callback_process_retry,
                prefetch_count=1,
            )

        except KeyboardInterrupt:
            logger.info("Retry handler interrupted")
        except Exception as e:
            logger.error(f"Error in retry handler: {e}", exc_info=True)
        finally:
            self.queue.close()
            logger.info("Retry handler stopped")


class DLQProcessor:
    """Processes dead letter queue (permanent failures)."""

    def __init__(self, worker_id: str):
        """Initialize DLQ processor."""
        self.worker_id = worker_id
        self.queue = get_queue()
        logger.info(f"Initialized DLQ processor {worker_id}")

    def process_failed_job(self, job_id: str, team_id: str, error_message: str, error_details: dict):
        """
        Process a job that permanently failed.

        Args:
            job_id: Job ID
            team_id: Team ID
            error_message: Error message
            error_details: Error details dict
        """
        try:
            with get_db_context() as db:
                job = JobOrchestrator.get_job(db, job_id, team_id)
                if not job:
                    logger.warning(f"Job {job_id} not found in DLQ processing")
                    return

                logger.warning(
                    f"Job {job_id} permanently failed after all retries: {error_message}"
                )

                # Job is already marked as failed in DLQ by worker
                # Additional processing could happen here:
                # - Send notifications to team
                # - Create incident
                # - Log to audit trail
                # - Trigger remediation workflows

        except Exception as e:
            logger.error(f"Error processing DLQ for job {job_id}: {e}", exc_info=True)

    def callback_process_dlq(self, ch, method, properties, body):
        """Callback for processing DLQ message from RabbitMQ."""
        try:
            message = json.loads(body)

            job_id = message.get("job_id")
            team_id = message.get("team_id")
            error_message = message.get("error_message", "Unknown error")
            error_details = message.get("error_details", {})

            logger.debug(f"Processing DLQ message: {job_id}")

            self.process_failed_job(job_id, team_id, error_message, error_details)

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            logger.error(f"Error in DLQ callback: {e}", exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def run(self):
        """Start consuming from DLQ."""
        try:
            logger.info("DLQ processor starting...")

            self.queue.consume(
                queue_name=MessageQueue.QUEUE_JOB_FAILED,
                callback=self.callback_process_dlq,
                prefetch_count=5,  # Higher prefetch for DLQ processing
            )

        except KeyboardInterrupt:
            logger.info("DLQ processor interrupted")
        except Exception as e:
            logger.error(f"Error in DLQ processor: {e}", exc_info=True)
        finally:
            self.queue.close()
            logger.info("DLQ processor stopped")


def main():
    """Entry point for error recovery worker."""
    import os
    import sys

    # Choose which handler to run
    handler_type = os.getenv("HANDLER_TYPE", "retry")  # retry or dlq
    worker_id = os.getenv("WORKER_ID", f"{handler_type}-{os.getpid()}")

    if handler_type == "retry":
        handler = RetryHandler(worker_id)
        handler.run()
    elif handler_type == "dlq":
        handler = DLQProcessor(worker_id)
        handler.run()
    else:
        logger.error(f"Unknown handler type: {handler_type}")
        sys.exit(1)


if __name__ == "__main__":
    main()
