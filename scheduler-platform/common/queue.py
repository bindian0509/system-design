"""
Message queue client for RabbitMQ.
Handles job publishing and consumption.
"""
import pika
import json
import logging
from typing import Dict, Any, Callable
from functools import wraps

from common.config import settings

logger = logging.getLogger(__name__)


class MessageQueue:
    """RabbitMQ message queue client."""

    # Queue names
    QUEUE_JOB_PENDING = "job.pending"
    QUEUE_JOB_RETRY = "job.retry"
    QUEUE_JOB_SCHEDULED = "job.scheduled"
    QUEUE_JOB_COMPLETED = "job.completed"
    QUEUE_JOB_FAILED = "job.failed"

    # Exchange for fanout (monitoring, alerts)
    EXCHANGE_JOB_EVENTS = "job.events"

    def __init__(self):
        """Initialize RabbitMQ connection."""
        self.connection = None
        self.channel = None
        self._connect()

    def _connect(self):
        """Establish connection to RabbitMQ."""
        try:
            credentials = pika.PlainCredentials("guest", "guest")
            parameters = pika.ConnectionParameters(
                host="localhost",
                port=5672,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declare queues and exchange
            self._declare_queues()

            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def _declare_queues(self):
        """Declare queues and exchanges."""
        # Declare durable queues (survive broker restart)
        for queue_name in [
            self.QUEUE_JOB_PENDING,
            self.QUEUE_JOB_RETRY,
            self.QUEUE_JOB_SCHEDULED,
            self.QUEUE_JOB_COMPLETED,
            self.QUEUE_JOB_FAILED,
        ]:
            self.channel.queue_declare(
                queue=queue_name,
                durable=True,
                auto_delete=False,
            )

        # Declare fanout exchange for events
        self.channel.exchange_declare(
            exchange=self.EXCHANGE_JOB_EVENTS,
            exchange_type="fanout",
            durable=True,
        )

        # Bind event queues to exchange
        self.channel.queue_declare(queue="job.events.monitoring", durable=True)
        self.channel.queue_declare(queue="job.events.alerts", durable=True)

        self.channel.queue_bind(
            exchange=self.EXCHANGE_JOB_EVENTS,
            queue="job.events.monitoring"
        )
        self.channel.queue_bind(
            exchange=self.EXCHANGE_JOB_EVENTS,
            queue="job.events.alerts"
        )

    def publish_job(self, queue_name: str, job_data: Dict[str, Any]):
        """
        Publish a job to the queue.

        Args:
            queue_name: Queue to publish to (e.g., QUEUE_JOB_PENDING)
            job_data: Job payload with job_id, team_id, payload, etc.
        """
        try:
            message = json.dumps(job_data)
            self.channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE,
                    content_type="application/json",
                )
            )
            logger.debug(f"Published job {job_data.get('job_id')} to {queue_name}")
        except Exception as e:
            logger.error(f"Failed to publish job: {e}")
            raise

    def publish_event(self, event_type: str, event_data: Dict[str, Any]):
        """
        Publish an event to the fanout exchange (for monitoring/alerts).

        Args:
            event_type: Type of event (job.completed, job.failed, etc.)
            event_data: Event payload
        """
        try:
            message = json.dumps({
                "event_type": event_type,
                "data": event_data,
            })
            self.channel.basic_publish(
                exchange=self.EXCHANGE_JOB_EVENTS,
                routing_key="",
                body=message,
                properties=pika.BasicProperties(
                    content_type="application/json",
                )
            )
            logger.debug(f"Published event: {event_type}")
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            raise

    def consume(
        self,
        queue_name: str,
        callback: Callable,
        prefetch_count: int = 1,
    ):
        """
        Consume messages from a queue.

        Args:
            queue_name: Queue to consume from
            callback: Function to process each message (ch, method, properties, body)
            prefetch_count: QoS - max messages to process concurrently
        """
        try:
            self.channel.basic_qos(prefetch_count=prefetch_count)
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=callback,
                auto_ack=False,
            )
            logger.info(f"Starting to consume from {queue_name}...")
            self.channel.start_consuming()
        except Exception as e:
            logger.error(f"Error consuming from {queue_name}: {e}")
            raise

    def close(self):
        """Close connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("Closed RabbitMQ connection")

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()


# Global queue instance
_queue_instance = None


def get_queue() -> MessageQueue:
    """Get or create the global message queue instance."""
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = MessageQueue()
    return _queue_instance


def close_queue():
    """Close the global message queue instance."""
    global _queue_instance
    if _queue_instance:
        _queue_instance.close()
        _queue_instance = None
