# Testing Guide - Phase 2

## End-to-End Testing Scenarios

### Scenario 1: Successful Job Execution

**Steps:**
1. Create a job
2. Monitor status (should be queued → running → completed)
3. Verify result stored in storage backend
4. Check execution history

**Script:**
```bash
# Create job
JOB_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "successful-job",
    "team_id": "team-001",
    "payload": {"success": true}
  }')

JOB_ID=$(echo $JOB_RESPONSE | jq -r '.job_id')

# Poll for completion
for i in {1..60}; do
  STATUS=$(curl -s http://localhost:8000/api/v1/jobs/$JOB_ID \
    -H "Authorization: Bearer $TOKEN" | jq -r '.status')

  echo "Attempt $i: Status = $STATUS"

  if [ "$STATUS" = "completed" ]; then
    echo "Job completed successfully!"
    break
  fi

  sleep 1
done
```

### Scenario 2: Job Failure and Retry

**Steps:**
1. Create job with retry config
2. First execution fails (simulated in worker)
3. Job automatically retried
4. Second attempt succeeds
5. Final status: completed

**Expected Flow:**
```
Job created (status: queued)
  ↓
Execution 1 starts (status: running)
  ↓
Execution 1 fails (error: simulated failure)
  ↓
Scheduled for retry in 5 seconds
  ↓
Execution 2 starts (status: running)
  ↓
Execution 2 succeeds
  ↓
Job completed (status: completed)
  ↓
Executions table has 2 records
```

**Script:**
```bash
# Keep running jobs until we get a failure then retry
python3 << 'PYTHON'
import requests
import time
import json

TOKEN = "bearer-token-here"
BASE_URL = "http://localhost:8000"

for attempt in range(10):
    # Create job with 3 retry attempts
    response = requests.post(
        f"{BASE_URL}/api/v1/jobs",
        json={
            "name": f"retry-test-{attempt}",
            "team_id": "team-001",
            "payload": {"test": True},
            "retry": {
                "max_attempts": 3,
                "backoff_base_seconds": 5,
                "backoff_multiplier": 2
            }
        },
        headers={"Authorization": f"Bearer {TOKEN}"}
    )

    job_id = response.json()["job_id"]
    print(f"Created job {job_id}")

    # Poll until complete
    for i in range(120):
        status_response = requests.get(
            f"{BASE_URL}/api/v1/jobs/{job_id}",
            headers={"Authorization": f"Bearer {TOKEN}"}
        )

        job = status_response.json()
        status = job["status"]
        num_executions = len(job["execution_history"])

        print(f"  {i}: Status={status}, Executions={num_executions}")

        if status in ["completed", "failed"]:
            if num_executions > 1:
                print(f"✓ Job had {num_executions} attempts (retry worked!)")
                break
            time.sleep(1)

    time.sleep(5)
PYTHON
```

### Scenario 3: Quota Exceeded

**Steps:**
1. Set low quota on team (e.g., 5 jobs/day)
2. Create 5 jobs successfully
3. 6th job returns 429 error

**Script:**
```bash
# Create 6 jobs quickly
for i in {1..6}; do
  echo "Creating job $i..."
  RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    http://localhost:8000/api/v1/jobs \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"quota-test-$i\",
      \"team_id\": \"team-001\",
      \"payload\": {}
    }")

  HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
  BODY=$(echo "$RESPONSE" | head -n -1)

  if [ "$HTTP_CODE" = "201" ]; then
    echo "  ✓ Job created"
  elif [ "$HTTP_CODE" = "429" ]; then
    echo "  ✗ Quota exceeded (expected)"
    echo "  Message: $(echo $BODY | jq -r '.detail')"
  else
    echo "  ✗ Unexpected error: $HTTP_CODE"
  fi
done
```

### Scenario 4: Result Storage

**Steps:**
1. Create and complete a job
2. Verify result uploaded to storage
3. Retrieve result from storage
4. Verify content matches expected output

**Script:**
```bash
# Complete a job first
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"storage-test","team_id":"team-001","payload":{}}' \
  | jq -r '.job_id')

# Wait for completion
sleep 10

# Get job details with result URL
JOB=$(curl -s http://localhost:8000/api/v1/jobs/$JOB_ID \
  -H "Authorization: Bearer $TOKEN")

RESULT_URL=$(echo $JOB | jq -r '.result_url')
echo "Result URL: $RESULT_URL"

# For local storage:
if [[ $RESULT_URL == local://* ]]; then
  FILE_PATH=${RESULT_URL#local://}
  echo "Result file exists: $([ -f $FILE_PATH ] && echo 'yes' || echo 'no')"
  echo "Result content:"
  cat $FILE_PATH | jq .
fi

# For S3:
if [[ $RESULT_URL == s3://* ]]; then
  BUCKET=$(echo $RESULT_URL | cut -d/ -f3)
  KEY=$(echo $RESULT_URL | cut -d/ -f4-)
  aws s3 cp s3://$BUCKET/$KEY - | jq .
fi
```

### Scenario 5: Monitoring Metrics

**Steps:**
1. Create multiple jobs
2. Check metrics endpoint
3. Verify metrics are being collected

**Script:**
```bash
# Create some jobs
for i in {1..5}; do
  curl -s -X POST http://localhost:8000/api/v1/jobs \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"metric-test-$i\",\"team_id\":\"team-001\",\"payload\":{}}" &
done

wait

# Get metrics
curl -s http://localhost:8000/metrics | grep -E "job_|queue_" | head -20

# Example output:
# job_submissions_total{execution_type="on_demand",team_id="team-001"} 5.0
# job_completions_total{status="completed",team_id="team-001"} 3.0
# job_duration_seconds_bucket{team_id="team-001",le="1.0"} 2.0
# job_retries_total{team_id="team-001"} 0.0
# queue_depth{queue_name="job.pending"} 2.0
```

### Scenario 6: DLQ (Permanent Failure)

**Note:** DLQ is triggered when retries are exhausted. In current mock implementation with 10% failure rate, this is hard to trigger reliably. In production with real failure modes, this would be tested by intentionally breaking a service.

**Steps:**
1. Simulate a job that fails permanently
2. Allow all retries to be exhausted
3. Verify job ends up in DLQ
4. Check DLQ queue has message

**Future Test (Phase 3):**
```python
# Trigger a job with explicit failure (requires code modification)
# Current: Worker has 10% random failure rate
# Future: Add test mode that forces failure after N retries
```

---

## Performance Testing

### Load Test: Concurrent Job Submissions

```python
import concurrent.futures
import requests
import time
from statistics import mean, median

TOKEN = "bearer-token"
BASE_URL = "http://localhost:8000"
NUM_JOBS = 100
WORKERS = 10

def create_job(i):
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/api/v1/jobs",
        json={
            "name": f"load-test-{i}",
            "team_id": "team-001",
            "payload": {"index": i}
        },
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    latency = (time.time() - start) * 1000
    return response.status_code, latency

print(f"Creating {NUM_JOBS} jobs with {WORKERS} workers...")

start_time = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
    futures = [executor.submit(create_job, i) for i in range(NUM_JOBS)]
    results = [f.result() for f in futures]

total_time = time.time() - start_time
latencies = [r[1] for r in results]
success_count = sum(1 for status, _ in results if status == 201)

print(f"\nResults:")
print(f"  Total time: {total_time:.2f}s")
print(f"  Throughput: {NUM_JOBS/total_time:.1f} jobs/sec")
print(f"  Success: {success_count}/{NUM_JOBS}")
print(f"  Latency (ms):")
print(f"    Min: {min(latencies):.1f}")
print(f"    Median: {median(latencies):.1f}")
print(f"    Mean: {mean(latencies):.1f}")
print(f"    Max: {max(latencies):.1f}")
```

### Database Query Performance

```sql
-- Check query performance
SELECT COUNT(*) FROM jobs WHERE team_id = 'team-001' AND status = 'completed';

-- With index, should be < 50ms
-- Without index, could be > 1s

-- Verify indexes exist
\d jobs
-- Should show: idx_job_team_status, idx_job_created_at, etc.
```

---

## Reliability Testing

### Test: Worker Failure Recovery

```bash
# Stop a worker while job is running
# Then restart it
# Job should eventually complete

docker ps | grep scheduler-worker
WORKER_ID=$(docker ps | grep scheduler-worker | awk '{print $1}')

# Create a job
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs ... | jq -r '.job_id')

# Stop worker during execution
sleep 2
docker stop $WORKER_ID

# Wait
sleep 5

# Restart worker
docker start $WORKER_ID

# Job should still complete (RabbitMQ redelivers)
curl http://localhost:8000/api/v1/jobs/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"
```

### Test: Message Queue Durability

```bash
# Verify RabbitMQ is persisting messages
# Stop RabbitMQ while jobs are queued
docker stop scheduler_rabbitmq

# Create jobs while RabbitMQ is down
# This should fail gracefully

# Restart RabbitMQ
docker start scheduler_rabbitmq

# Messages should be recovered and processed
docker logs scheduler_rabbitmq
```

---

## Verification Checklist for Phase 2

- [ ] Retry logic activates on job failure
- [ ] Exponential backoff delay increases with each retry
- [ ] Max retries enforced (job moves to DLQ)
- [ ] DLQ messages are stored and accessible
- [ ] Quota enforcement returns 429 error
- [ ] Team quotas are applied correctly
- [ ] Results stored in configured storage backend
- [ ] Result URLs are correct for storage type
- [ ] Metrics collected and exposed on /metrics
- [ ] Multiple workers can scale horizontally
- [ ] Worker crashes don't lose jobs (RabbitMQ redelivery)
- [ ] Concurrent requests don't corrupt database
- [ ] Performance meets targets (100+ jobs/sec)
- [ ] Error handler processes retries correctly
- [ ] DLQ processor handles failed jobs gracefully

---
