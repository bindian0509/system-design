"""
API Documentation and examples.
"""

# Scheduler Platform API Documentation

## Authentication

All API requests require a Bearer token in the Authorization header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

JWT token should contain:
- `user_id`: User identifier
- `email`: User email
- `teams`: List of team IDs user belongs to
- `roles`: Dictionary mapping team_id to role (admin, editor, viewer)

## Example: Create a Job

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "quarterly_crm_review",
    "description": "Generate quarterly CRM reports",
    "team_id": "team-001",
    "payload": {
      "crm_system": "salesforce",
      "date_range": "2026-Q1"
    },
    "execution_type": "on_demand",
    "timeout_seconds": 3600,
    "retry": {
      "max_attempts": 3,
      "backoff_multiplier": 2,
      "backoff_base_seconds": 60
    }
  }'
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "team_id": "team-001",
  "name": "quarterly_crm_review",
  "status": "queued",
  "created_at": "2026-05-21T10:00:00Z",
  "execution_history": []
}
```

## Example: Get Job Status

**Request:**
```bash
curl http://localhost:8000/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "team_id": "team-001",
  "name": "quarterly_crm_review",
  "status": "completed",
  "created_at": "2026-05-21T10:00:00Z",
  "started_at": "2026-05-21T10:05:00Z",
  "completed_at": "2026-05-21T10:25:30Z",
  "result_url": "s3://bucket/results/job-id/result.json",
  "result_size_bytes": 1024000,
  "execution_history": [
    {
      "attempt": 1,
      "started_at": "2026-05-21T10:05:00Z",
      "status": "completed",
      "duration_seconds": 1230
    }
  ]
}
```

## Example: Create a Schedule

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "daily_health_score",
    "team_id": "team-001",
    "cron": "0 2 * * *",
    "timezone": "UTC",
    "job_template": {
      "name": "daily_health_score_job",
      "payload": {
        "data_sources": ["crm", "analytics", "support"]
      },
      "timeout_seconds": 1800
    },
    "max_concurrent": 1
  }'
```

**Response:**
```json
{
  "schedule_id": "660e8400-e29b-41d4-a716-446655440001",
  "team_id": "team-001",
  "name": "daily_health_score",
  "cron": "0 2 * * *",
  "timezone": "UTC",
  "is_active": true,
  "created_at": "2026-05-21T10:00:00Z",
  "next_run": "2026-05-22T02:00:00Z"
}
```

## Error Responses

**Unauthorized (401):**
```json
{
  "detail": "Missing Authorization header"
}
```

**Forbidden (403):**
```json
{
  "detail": "User not a member of this team"
}
```

**Not Found (404):**
```json
{
  "detail": "Job not found"
}
```

**Conflict (409):**
```json
{
  "detail": "Team quota exceeded: 1000/1000 jobs today"
}
```

## Rate Limits

- API: 1000 requests/minute per user
- Job creation: 10 jobs/second per team (burst: 20)

## Webhook Events (Phase 2)

The platform will emit events via webhooks:
- `job.created`
- `job.started`
- `job.completed`
- `job.failed`

## Batch Operations (Phase 2)

- Batch create jobs
- Batch cancel jobs
- Bulk update team quotas

## Advanced Queries (Phase 2)

- Search jobs by name, payload, results
- Filter by date range, tags
- Export job history
"""
