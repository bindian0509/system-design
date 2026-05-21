"""
Worker service - executes jobs from the queue.
"""
import logging
import json
import time
import random
from datetime import datetime, timedelta

from common.config import settings
from common.database import get_db_context
from common.queue import get_queue, MessageQueue
from common.models import JobStatus
from common.storage import get_storage
from common.quota import RetryScheduler
from api.services import JobOrchestrator

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class JobWorker:
    """Worker process that executes jobs from the queue."""

    def __init__(self, worker_id: str, concurrency: int = 1):
        """
        Initialize worker.

        Args:
            worker_id: Unique worker identifier
            concurrency: Number of concurrent jobs to process
        """
        self.worker_id = worker_id
        self.concurrency = concurrency
        self.queue = get_queue()
        self.running = True
        logger.info(f"Initialized worker {worker_id} with concurrency {concurrency}")

    def process_job(self, job_id: str, team_id: str, payload: dict, timeout_seconds: int):
        """
        Execute a job.

        This is a mock implementation. In production, this would:
        1. Download job code/config
        2. Execute in isolated environment
        3. Stream results to object storage
        4. Handle timeouts and interrupts

        Args:
            job_id: Job ID
            team_id: Team ID
            payload: Job payload
            timeout_seconds: Execution timeout
        """
        execution_id = None
        try:
            # Update job status to running
            with get_db_context() as db:
                job = JobOrchestrator.get_job(db, job_id, team_id)
                if not job:
                    logger.warning(f"Job {job_id} not found")
                    return

                # Create execution record
                execution = JobOrchestrator.create_execution(
                    db,
                    job_id,
                    attempt_number=1,
                    worker_pod_id=self.worker_id,
                )
                execution_id = execution.execution_id

            # Update job status
            with get_db_context() as db:
                JobOrchestrator.update_job_status(
                    db,
                    job_id,
                    JobStatus.RUNNING,
                )

            logger.info(f"Started executing job {job_id} (execution {execution_id})")

            # Simulate job execution
            start_time = time.time()
            execution_duration = random.uniform(1, 5)  # Simulate 1-5 second execution

            # Simulate occasional failures for testing retry logic
            if random.random() < 0.1:  # 10% failure rate
                raise Exception("Simulated job failure for testing retry logic")

            time.sleep(execution_duration)

            # Simulate job result
            result = {
                "status": "success",
                "output": f"Mock execution of job {job_id}",
                "payload_echo": payload,
                "duration_seconds": execution_duration,
            }

            # Upload result to storage
            storage = get_storage()
            result_json = json.dumps(result).encode('utf-8')
            result_url = storage.upload(job_id, result_json)
            result_size = len(result_json)

            # Mark as completed
            duration = int(time.time() - start_time)
            with get_db_context() as db:
                JobOrchestrator.complete_execution(
                    db,
                    execution_id,
                    JobStatus.COMPLETED,
                    duration,
                    logs_url=f"/logs/{job_id}/{execution_id}",
                )

                job = JobOrchestrator.get_job(db, job_id, team_id)
                job.result_url = result_url
                job.result_size_bytes = result_size

                JobOrchestrator.update_job_status(
                    db,
                    job_id,
                    JobStatus.COMPLETED,
                )

            logger.info(f"Completed job {job_id} (duration: {duration}s, result: {result_url}")

        except Exception as e:
            logger.error(f"Error executing job {job_id}: {e}", exc_info=True)

            # Get retry configuration
            with get_db_context() as db:
                job = JobOrchestrator.get_job(db, job_id, team_id)
                if not job:
                    return

                retry_config = job.retry_config or {
                    "max_attempts": 3,
                    "backoff_multiplier": 2.0,
                    "backoff_base_seconds": 60
                }
                max_attempts = retry_config.get("max_attempts", 3)

                # Get current attempt number
                from common.models import JobExecution
                executions_count = db.query(JobExecution).filter(
                    JobExecution.job_id == job_id
                ).count()

                attempt = executions_count

                # Check if should retry
                if attempt < max_attempts:
                    logger.info(f"Scheduling retry for job {job_id} (attempt {attempt}/{max_attempts})")

                    # Update execution status
                    if execution_id:
                        JobOrchestrator.complete_execution(
                            db,
                            execution_id,
                            JobStatus.FAILED,
                            int(time.time() - time.time()),  # 0 duration
                            error_details={"message": str(e), "type": type(e).__name__}
                        )

                    # Schedule retry
                    RetryScheduler.schedule_retry(
                        db,
                        job_id,
                        attempt,
                        retry_config
                    )

                    # Publish to retry queue
                    queue = get_queue()
                    queue.publish_job(
                        MessageQueue.QUEUE_JOB_RETRY,
                        {
                            "job_id": job_id,
                            "team_id": team_id,
                            "payload": payload,
                            "timeout_seconds": job.timeout_seconds,
                            "retry_config": retry_config,
                            "attempt": attempt + 1,
                            "scheduled_at": datetime.utcnow().isoformat(),
                        }
                    )
                else:
                    # Max retries exceeded - move to DLQ
                    logger.error(f"Job {job_id} failed after {max_attempts} attempts, moving to DLQ")

                    if execution_id:
                        JobOrchestrator.complete_execution(
                            db,
                            execution_id,
                            JobStatus.FAILED,
                            int(time.time() - time.time()),
                            error_details={
                                "message": str(e),
                                "type": type(e).__name__,
                                "max_retries_exceeded": True
                            }
                        )

                    JobOrchestrator.move_to_dlq(
                        db,
                        job_id,
                        f"Job failed after {max_attempts} attempts: {str(e)}",
                        {"error": str(e), "attempts": max_attempts}
                    )
            payload = message.get("payload", {})
            timeout_seconds = message.get("timeout_seconds", 3600)

            logger.debug(f"Processing job: {job_id}")

            # Process the job
            self.process_job(job_id, team_id, payload, timeout_seconds)

            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.debug(f"Acknowledged job {job_id}")

        except Exception as e:
            logger.error(f"Error in job callback: {e}", exc_info=True)
            # Nack message and requeue
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def run(self):
        """Start consuming jobs from queue."""
        try:
            logger.info(f"Worker {self.worker_id} starting to consume jobs...")

            self.queue.consume(
                queue_name=MessageQueue.QUEUE_JOB_PENDING,
                callback=self.callback_process_job,
                prefetch_count=self.concurrency,
            )

        except KeyboardInterrupt:
            logger.info("Worker interrupted by user")
        except Exception as e:
            logger.error(f"Error in worker loop: {e}", exc_info=True)
        finally:
            self.queue.close()
            logger.info(f"Worker {self.worker_id} stopped")


def main():
    """Entry point for worker service."""
    import os

    worker_id = os.getenv("WORKER_ID", f"worker-{os.getpid()}")
    concurrency = settings.worker_concurrency

    worker = JobWorker(worker_id, concurrency)
    worker.run()


if __name__ == "__main__":
    main()
