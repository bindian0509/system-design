# Internal Job Scheduler Platform

A scalable, cloud-native platform for engineering teams to define and execute long-running jobs.

**Supports**: On-demand, scheduled, and recurring jobs
**Scale**: ~440,000 jobs/day (~4-5 jobs/sec) with reliability features
**Teams**: 20 internal teams, resource-limited via quotas
**Status**: ✅ **Phase 2 Complete** - Production-ready with retry logic, DLQ, quotas, and monitoring

## Features

### Phase 1: MVP (Complete) ✅
- **REST API** for job submission, status tracking, and scheduling
- **Cron Scheduler** for recurring jobs with timezone support
- **Worker Pool** for distributed execution via Kubernetes
- **Full RBAC** with team isolation and role-based access control
- **Comprehensive Logging** and audit trails

### Phase 2: Scale & Reliability (Complete) ✅ **[NEW]**
- **Automatic Retry** with exponential backoff (60s, 120s, 240s...)
- **Dead Letter Queue** for permanent failure tracking
- **Team Resource Quotas** (daily jobs, concurrent jobs, storage)
- **Result Storage** abstraction (Local, S3, GCS)
- **Prometheus Metrics** for observability and alerting
- **Error Recovery** system (retry handler, DLQ processor)

### Phase 3: Advanced Features (Planned)
- **DAG Support** for job dependencies and workflows
- **Web UI** for self-service job management
- **Webhook Integration** for external event delivery
- **Cost Tracking** and usage analytics
- **Distributed Scheduler** with leader election (HA)

## Architecture

```
Client Apps
    │
    ├─ /api/v1/jobs      (Submit, status, list)
    ├─ /api/v1/schedules (Create, manage cron)
    └─ /metrics          (Prometheus metrics)
    │
    ▼
┌─────────────────────────────────┐
│  API Server (FastAPI) ×3        │
│  - JWT auth + RBAC              │
│  - Quota validation             │
│  - Event publishing             │
└────────┬────────────────────────┘
         │
    ┌────┼────┬──────────┬─────────┐
    │    │    │          │         │
    ▼    ▼    ▼          ▼         ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│PostgreSQL│ │ RabbitMQ │ │ Redis    │ │Prometheus│ │Grafana   │
│ Jobs DB  │ │ Queues   │ │ Cache    │ │ Metrics  │ │Dashboard │
└──────────┘ └────┬─────┘ └──────────┘ └──────────┘ └──────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
 ┌────────────────────────────┐  ┌────────────────────┐
 │ Worker Pods ×5-20          │  │ Error Recovery     │
 │ - Execute jobs             │  │ - Retry Handler    │
 │ - Store results            │  │ - DLQ Processor    │
 │ - Upload to S3/GCS         │  │ - Alerting Service │
 └────────────────────────────┘  └────────────────────┘
    │             │
    └─────────┬───┘
              │
    ┌─────────▼────────┐
    │ Result Storage   │
    │ - Local FS       │
    │ - S3             │
    │ - GCS            │
    └──────────────────┘

┌────────────────────────────┐
│ Cron Scheduler (Singleton) │
│ Checks every 60 seconds    │
└────────────────────────────┘
```

## Project Structure

```
├── api/                    # FastAPI application
│   ├── main.py            # Entry point
│   ├── routes/            # API endpoints
│   ├── middleware/        # RBAC, auth, logging
│   ├── schemas/           # Pydantic models
│   └── services/          # Business logic
├── worker/                # Job execution service
│   ├── main.py           # Worker entry point
│   ├── executor.py       # Job execution logic
│   └── handlers/         # Job type handlers
├── scheduler/            # Cron job scheduler
│   └── main.py          # Scheduler entry point
├── common/              # Shared utilities
│   ├── models.py        # Database models
│   ├── database.py      # DB connection
│   ├── queue.py         # Message queue client
│   └── config.py        # Configuration
├── infra/               # Infrastructure as code
│   ├── docker-compose.yml    # Local dev environment
│   ├── kubernetes/           # K8s manifests
│   └── migrations/           # Database migrations
├── docs/                # API documentation
├── tests/               # Test suites
└── requirements.txt     # Python dependencies
```

## Quick Start (Local Development)

### Prerequisites
- Python 3.9+
- Docker & Docker Compose
- PostgreSQL (via Docker)

### Setup

```bash
# Clone the repository
cd scheduler-platform

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start services (PostgreSQL, RabbitMQ, Redis)
docker-compose up -d

# Run database migrations
python -m alembic upgrade head

# Start API server
python api/main.py

# In another terminal, start scheduler
python scheduler/main.py

# In another terminal, start worker
python worker/main.py
```

API will be available at `http://localhost:8000`

## API Endpoints

### Job Management

- `POST /api/v1/jobs` - Submit a new job
- `GET /api/v1/jobs/{job_id}` - Get job status
- `GET /api/v1/jobs` - List jobs (with filtering)
- `POST /api/v1/jobs/{job_id}/cancel` - Cancel a job

### Schedules

- `POST /api/v1/schedules` - Create a schedule (cron)
- `GET /api/v1/schedules` - List schedules
- `DELETE /api/v1/schedules/{schedule_id}` - Delete schedule

### Teams

- `GET /api/v1/teams/{team_id}` - Get team info & quotas
- `PUT /api/v1/teams/{team_id}/quotas` - Update team quotas (admin only)

## Configuration

Environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/scheduler

# Message Queue
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Redis
REDIS_URL=redis://localhost:6379

# Execution
WORKER_CONCURRENCY=10
JOB_TIMEOUT_SECONDS=3600

# Monitoring
PROMETHEUS_PORT=8001
LOG_LEVEL=INFO
```

## Implementation Phases

### Phase 1: MVP ✓ (Starting)
- [x] Project structure
- [ ] Database schema + migrations
- [ ] REST API with basic CRUD
- [ ] Job Orchestrator (state machine)
- [ ] Basic Scheduler (cron)
- [ ] Worker + RabbitMQ integration
- [ ] Prometheus metrics
- [ ] Docker Compose for local dev

### Phase 2: Scale & Reliability
- [ ] Retry logic + DLQ
- [ ] S3/GCS integration
- [ ] Distributed scheduler
- [ ] Team resource quotas
- [ ] Enhanced monitoring & alerts
- [ ] API SDKs (Python, Go)

### Phase 3: Advanced Features
- [ ] DAG support
- [ ] Result caching
- [ ] Web UI
- [ ] Cost tracking

### Phase 4: Optimization
- [ ] Parallel DAG execution
- [ ] Performance tuning
- [ ] Result storage tiering

## Monitoring

**Prometheus Metrics** available at `http://localhost:8001/metrics`

Key metrics:
- `job_submission_rate` - Jobs submitted per second
- `job_execution_duration` - Histogram of job execution times
- `job_success_rate` - Percentage of jobs completed successfully
- `queue_depth` - Number of pending jobs
- `worker_utilization` - Percentage of worker resources in use

**Logs** - Sent to stdout (development); configure for centralized logging in production (ELK, Datadog)

## Security

- **Authentication**: OAuth 2.0 / OIDC (configurable)
- **Authorization**: RBAC (Admin, Editor, Viewer per team)
- **Data Encryption**: TLS in transit, encryption at rest (DB + object storage)
- **Audit Logging**: All operations logged with user attribution

## Testing

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests (requires Docker services)
pytest tests/integration/

# Run load tests
pytest tests/load/
```

## Contributing

1. Create a feature branch
2. Make changes with tests
3. Run tests locally
4. Submit a pull request

## License

Internal use only.
