"""
Pydantic schemas for API request/response models.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class ExecutionType(str, Enum):
    ON_DEMAND = "on_demand"
    SCHEDULED = "scheduled"
    RECURRING = "recurring"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RetryConfig(BaseModel):
    """Retry configuration for jobs."""
    max_attempts: int = 3
    backoff_multiplier: float = 2.0
    backoff_base_seconds: int = 60


class DAGNode(BaseModel):
    """DAG node definition."""
    id: str
    type: str
    params: Dict[str, Any] = {}


class DAGEdge(BaseModel):
    """DAG edge (dependency) definition."""
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")


class DAGConfig(BaseModel):
    """DAG configuration for job workflows."""
    nodes: List[DAGNode]
    edges: List[DAGEdge] = []

    class Config:
        populate_by_name = True


class JobCreateRequest(BaseModel):
    """Request model for creating a job."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    team_id: str
    payload: Dict[str, Any]
    execution_type: ExecutionType = ExecutionType.ON_DEMAND

    # DAG support
    dag_config: Optional[DAGConfig] = None

    # Execution constraints
    timeout_seconds: int = 3600
    retry: RetryConfig = Field(default_factory=RetryConfig)


class JobExecutionHistoryItem(BaseModel):
    """Single execution attempt in history."""
    attempt: int
    started_at: datetime
    status: JobStatus
    error: Optional[str] = None
    duration_seconds: Optional[int] = None
    next_retry_at: Optional[datetime] = None


class JobResponse(BaseModel):
    """Response model for job details."""
    job_id: str
    team_id: str
    name: str
    description: Optional[str]
    execution_type: ExecutionType
    status: JobStatus

    created_at: datetime
    created_by: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    # Progress and results
    progress: Optional[Dict[str, int]] = None
    result_url: Optional[str] = None
    result_size_bytes: Optional[int] = None
    error_message: Optional[str] = None

    # Execution history
    execution_history: List[JobExecutionHistoryItem] = []

    # Logs
    logs_url: Optional[str] = None

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Paginated list of jobs."""
    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int


class ScheduleCreateRequest(BaseModel):
    """Request model for creating a schedule."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    team_id: str

    # Cron definition
    cron: str = Field(..., min_length=5)  # Cron expression
    timezone: str = "UTC"

    # Job template (base config)
    job_template: Dict[str, Any]

    # Constraints
    max_concurrent: int = 1


class ScheduleResponse(BaseModel):
    """Response model for schedule details."""
    schedule_id: str
    team_id: str
    name: str
    description: Optional[str]
    cron: str
    timezone: str

    is_active: bool
    created_at: datetime
    last_triggered_at: Optional[datetime]
    next_run: Optional[datetime]

    class Config:
        from_attributes = True


class TeamQuotaUpdate(BaseModel):
    """Request model for updating team quotas."""
    quota_jobs_per_day: Optional[int] = None
    quota_concurrent_jobs: Optional[int] = None
    quota_max_duration_seconds: Optional[int] = None
    quota_storage_bytes: Optional[int] = None


class TeamResponse(BaseModel):
    """Response model for team details."""
    team_id: str
    name: str
    description: Optional[str]

    quota_jobs_per_day: int
    quota_concurrent_jobs: int
    quota_max_duration_seconds: int
    quota_storage_bytes: int

    created_at: datetime

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
