"""
SQLAlchemy database models for the scheduler platform.
"""
from datetime import datetime
from enum import Enum
import json
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Text,
    ForeignKey, JSON, Enum as SQLEnum, Index, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class JobStatus(str, Enum):
    """Job execution status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY_PENDING = "retry_pending"


class ExecutionType(str, Enum):
    """Type of job execution."""
    ON_DEMAND = "on_demand"
    SCHEDULED = "scheduled"
    RECURRING = "recurring"


class UserRole(str, Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class Team(Base):
    """Team model - represents an engineering team."""
    __tablename__ = "teams"

    team_id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)

    # Resource quotas
    quota_jobs_per_day = Column(Integer, default=1000)
    quota_concurrent_jobs = Column(Integer, default=100)
    quota_max_duration_seconds = Column(Integer, default=86400)  # 24 hours
    quota_storage_bytes = Column(Integer, default=1_073_741_824)  # 1 GB

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    jobs = relationship("Job", back_populates="team")
    schedules = relationship("Schedule", back_populates="team")
    team_members = relationship("TeamMember", back_populates="team")

    __table_args__ = (
        Index("idx_team_name", "name"),
    )


class TeamMember(Base):
    """Team member model - users and their roles within teams."""
    __tablename__ = "team_members"

    member_id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.team_id"), nullable=False)
    user_id = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.VIEWER, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    team = relationship("Team", back_populates="team_members")

    __table_args__ = (
        Index("idx_team_member_user", "team_id", "user_id"),
    )


class Job(Base):
    """Job model - represents a scheduled or on-demand job."""
    __tablename__ = "jobs"

    job_id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.team_id"), nullable=False)
    schedule_id = Column(String(36), ForeignKey("schedules.schedule_id"), nullable=True)

    name = Column(String(255), nullable=False)
    description = Column(Text)
    execution_type = Column(SQLEnum(ExecutionType), nullable=False)
    status = Column(SQLEnum(JobStatus), default=JobStatus.QUEUED, nullable=False)

    # Job payload and configuration
    payload = Column(JSON, nullable=False)
    dag_config = Column(JSON)  # DAG structure (if applicable)

    # Execution metadata
    timeout_seconds = Column(Integer, default=3600)
    retry_config = Column(JSON, default={
        "max_attempts": 3,
        "backoff_multiplier": 2,
        "backoff_base_seconds": 60
    })

    # Job results and status
    result_url = Column(String(512))  # S3/GCS path or local path
    result_size_bytes = Column(Integer)
    error_message = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String(255))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # For DAG relationships
    parent_job_id = Column(String(36), ForeignKey("jobs.job_id"), nullable=True)

    # Metadata for tracking
    metadata = Column(JSON, default={})

    # Relationships
    team = relationship("Team", back_populates="jobs")
    schedule = relationship("Schedule", back_populates="jobs")
    executions = relationship("JobExecution", back_populates="job")

    __table_args__ = (
        Index("idx_job_team_status", "team_id", "status"),
        Index("idx_job_created_at", "created_at"),
        Index("idx_job_schedule_id", "schedule_id"),
    )


class JobExecution(Base):
    """Job execution model - tracks execution history and attempts."""
    __tablename__ = "job_executions"

    execution_id = Column(String(36), primary_key=True)
    job_id = Column(String(36), ForeignKey("jobs.job_id"), nullable=False)

    attempt_number = Column(Integer, nullable=False)
    status = Column(SQLEnum(JobStatus), nullable=False)

    # Worker information
    worker_pod_id = Column(String(255))

    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)

    # Duration and logs
    duration_seconds = Column(Integer)
    logs_url = Column(String(512))  # S3/GCS/local path to logs

    # Error tracking
    error_details = Column(JSON)

    # Performance metrics
    metrics = Column(JSON, default={})  # CPU, memory, etc.

    # Relationships
    job = relationship("Job", back_populates="executions")

    __table_args__ = (
        Index("idx_execution_job_id", "job_id"),
        Index("idx_execution_started_at", "started_at"),
    )


class Schedule(Base):
    """Schedule model - represents scheduled/recurring jobs."""
    __tablename__ = "schedules"

    schedule_id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.team_id"), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(Text)
    cron_expression = Column(String(255), nullable=False)
    timezone = Column(String(63), default="UTC")

    # Job template (base config for jobs created from this schedule)
    job_template = Column(JSON, nullable=False)

    is_active = Column(Boolean, default=True)

    # Execution constraints
    max_concurrent_executions = Column(Integer, default=1)

    # Scheduling metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String(255))
    last_triggered_at = Column(DateTime)
    next_scheduled_run = Column(DateTime)

    # Relationships
    team = relationship("Team", back_populates="schedules")
    jobs = relationship("Job", back_populates="schedule")

    __table_args__ = (
        Index("idx_schedule_team_active", "team_id", "is_active"),
        Index("idx_schedule_next_run", "next_scheduled_run"),
    )


class AuditLog(Base):
    """Audit log model - tracks all operations for security/compliance."""
    __tablename__ = "audit_logs"

    log_id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.team_id"))
    user_id = Column(String(255))

    resource_type = Column(String(50))  # job, schedule, team, etc.
    resource_id = Column(String(36))
    action = Column(String(50))  # create, update, delete, etc.

    changes = Column(JSON)  # Before/after values

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_audit_team_timestamp", "team_id", "timestamp"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )
