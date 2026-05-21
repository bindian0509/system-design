"""
Configuration management for the scheduler platform.
Loads environment variables with defaults.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://scheduler:scheduler@localhost:5432/scheduler"
    )

    # Message Queue (RabbitMQ)
    rabbitmq_url: str = os.getenv(
        "RABBITMQ_URL",
        "amqp://guest:guest@localhost:5672/"
    )

    # Redis Cache
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Worker Configuration
    worker_concurrency: int = int(os.getenv("WORKER_CONCURRENCY", "10"))
    job_timeout_seconds: int = int(os.getenv("JOB_TIMEOUT_SECONDS", "3600"))

    # Scheduler Configuration
    scheduler_check_interval_seconds: int = int(
        os.getenv("SCHEDULER_CHECK_INTERVAL_SECONDS", "60")
    )

    # API Configuration
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    api_workers: int = int(os.getenv("API_WORKERS", "4"))

    # Monitoring
    prometheus_port: int = int(os.getenv("PROMETHEUS_PORT", "8001"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Security
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")
    jwt_algorithm: str = "HS256"

    # S3/GCS Configuration (for Phase 2)
    result_storage_type: str = os.getenv("RESULT_STORAGE_TYPE", "local")  # local, s3, gcs
    result_storage_bucket: str = os.getenv("RESULT_STORAGE_BUCKET", "/tmp/job_results")

    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
