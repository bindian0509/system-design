# Failure Handling

This document covers failure scenarios, recovery strategies, and resilience patterns for the Seller-Side Payment System.

## Failure Categories

| Category | Examples | Impact | Recovery |
|----------|----------|--------|----------|
| **Transient** | Network timeout, temporary gateway unavailable | Low | Automatic retry |
| **Recoverable** | Invalid payment details, insufficient funds | Medium | User action required |
| **Fatal** | Data corruption, security breach | Critical | Manual intervention |

---

## Payment Gateway Failures

### Gateway Unavailable

When the third-party payment gateway is down or unreachable.

**Detection**:
- Connection timeout (> 5 seconds)
- HTTP 5xx responses
- Circuit breaker trips

**Recovery Strategy**:

```
┌─────────────────────────────────────────────────────────────────┐
│                    GATEWAY FAILURE HANDLING                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. RETRY with exponential backoff:                             │
│     Attempt 1: wait 1 second                                    │
│     Attempt 2: wait 2 seconds                                   │
│     Attempt 3: wait 4 seconds                                   │
│     Attempt 4: wait 8 seconds                                   │
│     Attempt 5: wait 16 seconds                                  │
│     Max attempts: 5                                             │
│                                                                 │
│  2. CIRCUIT BREAKER:                                            │
│     After 3 consecutive failures → OPEN circuit                 │
│     Wait 60 seconds → HALF-OPEN (try one request)              │
│     Success → CLOSED, Failure → OPEN again                      │
│                                                                 │
│  3. DEAD LETTER QUEUE:                                          │
│     After max retries → Move to DLQ                             │
│     Alert operations team                                       │
│     Manual review and retry                                     │
│                                                                 │
│  4. ROLLOVER:                                                   │
│     Failed payouts automatically included in next cycle         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation**:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitOpenError("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise

    def on_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'

    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            alert_ops_team("Circuit breaker OPEN for payment gateway")


def process_with_retry(payout, max_attempts=5):
    for attempt in range(max_attempts):
        try:
            return circuit_breaker.call(gateway.send_payment, payout)
        except (TimeoutError, ConnectionError) as e:
            wait_time = 2 ** attempt  # Exponential backoff
            log.warn(f"Gateway call failed, attempt {attempt + 1}, waiting {wait_time}s")
            time.sleep(wait_time)
        except CircuitOpenError:
            log.error("Circuit breaker open, skipping payout")
            raise

    # Max attempts exceeded
    move_to_dlq(payout)
    raise MaxRetriesExceededError(payout.id)
```

### Gateway Error Responses

Handling specific error codes from the gateway:

| Error Code | Meaning | Action |
|------------|---------|--------|
| `INVALID_ACCOUNT` | Bank account invalid | Mark FAILED, notify seller |
| `INVALID_ROUTING` | Routing number invalid | Mark FAILED, notify seller |
| `ACCOUNT_CLOSED` | Account no longer exists | Mark FAILED, notify seller |
| `INSUFFICIENT_INFO` | Missing required fields | Mark FAILED, notify seller |
| `RATE_LIMITED` | Too many requests | Retry with backoff |
| `MAINTENANCE` | Scheduled downtime | Retry after window |
| `INTERNAL_ERROR` | Gateway internal issue | Retry with backoff |

```python
def handle_gateway_error(payout, error):
    if error.code in ['INVALID_ACCOUNT', 'INVALID_ROUTING', 'ACCOUNT_CLOSED']:
        # Recoverable by seller action
        mark_failed(payout, error.code, error.message)
        notify_seller(payout.seller_id,
            action_required='UPDATE_PAYMENT_DETAILS',
            error_message=error.message
        )

    elif error.code in ['INSUFFICIENT_INFO']:
        mark_failed(payout, error.code, error.message)
        notify_seller(payout.seller_id,
            action_required='COMPLETE_PROFILE',
            error_message=error.message
        )

    elif error.code in ['RATE_LIMITED', 'MAINTENANCE', 'INTERNAL_ERROR']:
        # Transient, retry later
        schedule_retry(payout, delay_minutes=15)

    else:
        # Unknown error, alert and move to DLQ
        log.error(f"Unknown gateway error: {error}")
        move_to_dlq(payout)
        alert_ops_team(f"Unknown gateway error for payout {payout.id}")
```

---

## Scheduled Job Failures

### Job Fails to Start

**Scenario**: The payout scheduler cron job doesn't trigger.

**Prevention**:
- Leader election with multiple scheduler instances
- Heartbeat monitoring
- External job scheduler (Airflow/Temporal) with built-in retries

**Detection**:
- Missing heartbeat alert (no ping for > 5 minutes)
- No payouts created during expected window
- Job execution lag metric

**Recovery**:

```python
# Leader election using Redis
class PayoutSchedulerLeader:
    LOCK_KEY = "payout_scheduler_leader"
    LOCK_TTL = 30  # seconds
    HEARTBEAT_INTERVAL = 10  # seconds

    def __init__(self):
        self.is_leader = False
        self.lock_value = str(uuid.uuid4())

    def try_acquire_leadership(self):
        acquired = redis.set(
            self.LOCK_KEY,
            self.lock_value,
            nx=True,
            ex=self.LOCK_TTL
        )
        if acquired:
            self.is_leader = True
            self.start_heartbeat()
        return acquired

    def start_heartbeat(self):
        while self.is_leader:
            # Extend lock TTL
            redis.expire(self.LOCK_KEY, self.LOCK_TTL)
            time.sleep(self.HEARTBEAT_INTERVAL)

    def run_scheduler(self):
        while True:
            if self.is_leader or self.try_acquire_leadership():
                try:
                    self.execute_payout_cycle()
                except Exception as e:
                    log.error(f"Scheduler error: {e}")
                    alert_ops_team(f"Scheduler error: {e}")
            else:
                log.info("Not leader, standing by...")
            time.sleep(60)
```

### Job Fails After Processing Some Records

**Scenario**: Scheduler crashes after processing 50 of 1000 eligible sellers.

**Prevention**:
- Idempotent processing (check for existing PENDING/PROCESSING payouts)
- Checkpoint progress to database
- Process in small batches with commits

**Recovery**:
- On restart, query for eligible sellers without recent payouts
- Skip sellers with PENDING/PROCESSING status
- Resume from last checkpoint

```python
def execute_payout_cycle_with_checkpoint():
    cycle_id = generate_cycle_id()

    # Get all eligible sellers
    eligible_sellers = get_eligible_sellers()

    for batch in chunk(eligible_sellers, size=100):
        try:
            for seller in batch:
                # Idempotency check
                existing = get_pending_payout(seller.id)
                if existing:
                    log.info(f"Skipping {seller.id}, payout already exists")
                    continue

                # Create payout
                create_payout(seller)

            # Checkpoint after each batch
            update_checkpoint(cycle_id, batch[-1].id)

        except Exception as e:
            log.error(f"Batch failed at {batch[0].id}: {e}")
            # Next run will resume from checkpoint
            raise

def resume_from_checkpoint():
    checkpoint = get_last_checkpoint()
    if checkpoint and checkpoint.age < timedelta(hours=1):
        return get_eligible_sellers(after_id=checkpoint.last_seller_id)
    else:
        return get_eligible_sellers()
```

### Job Fails Mid-Record Processing

**Scenario**: System crashes while calling payment gateway.

**Detection**:
- Payout stuck in PROCESSING state for > 10 minutes
- Reconciliation job finds orphaned records

**Recovery**:

```python
# Reconciliation job (runs every 15 minutes)
def reconcile_stuck_payouts():
    stuck_payouts = db.query("""
        SELECT * FROM payout_record
        WHERE status = 'PROCESSING'
          AND processed_at < NOW() - INTERVAL '10 minutes'
    """)

    for payout in stuck_payouts:
        # Query gateway for actual status
        try:
            gateway_status = gateway.get_transaction_status(
                payout.gateway_txn_id or payout.payout_id
            )

            if gateway_status == 'COMPLETED':
                # Payment went through, update our records
                mark_completed(payout, gateway_status.txn_id)
                deduct_balance(payout)
                alert_ops_team(f"Reconciled stuck payout {payout.id} as COMPLETED")

            elif gateway_status == 'FAILED':
                mark_failed(payout, gateway_status.error_code, gateway_status.error)

            elif gateway_status == 'NOT_FOUND':
                # Payment was never submitted, safe to retry
                reset_to_pending(payout)

        except Exception as e:
            # Can't determine status, needs manual review
            move_to_manual_review(payout)
            alert_ops_team(f"Cannot reconcile payout {payout.id}: {e}")
```

---

## Database Failures

### Primary Database Unavailable

**Impact**: All writes blocked, system effectively down.

**Prevention**:
- Multi-AZ deployment with synchronous replica
- Automatic failover (RDS Multi-AZ, Cloud SQL HA)
- Connection pool health checks

**Recovery**:
- Automatic failover to replica (< 60 seconds)
- Payment processor pauses and retries
- Queue buffers incoming events

```python
class DatabaseConnectionManager:
    def __init__(self, primary_url, replica_url):
        self.primary_pool = create_pool(primary_url)
        self.replica_pool = create_pool(replica_url)
        self.health_check_interval = 5  # seconds

    def get_write_connection(self):
        try:
            return self.primary_pool.getconn()
        except ConnectionError:
            # Primary unavailable, wait for failover
            log.error("Primary database unavailable")
            raise DatabaseUnavailableError()

    def get_read_connection(self):
        # Prefer replica for reads
        try:
            return self.replica_pool.getconn()
        except ConnectionError:
            # Fall back to primary
            return self.primary_pool.getconn()
```

### Data Corruption

**Prevention**:
- Database constraints (CHECK, FOREIGN KEY)
- Application-level validation
- Immutable audit log for recovery

**Detection**:
- Balance mismatch (sum of order earnings ≠ total payouts + current balance)
- Orphaned records
- Checksum failures

**Recovery**:
```sql
-- Detect balance discrepancies
SELECT
    sb.seller_id,
    sb.available_balance + sb.pending_balance + sb.held_balance as recorded_balance,
    COALESCE(SUM(opm.seller_amount) FILTER (WHERE opm.status != 'CANCELLED'), 0)
        - COALESCE(SUM(pr.amount) FILTER (WHERE pr.status = 'COMPLETED'), 0) as calculated_balance
FROM seller_balance sb
LEFT JOIN order_payout_mapping opm ON sb.seller_id = opm.seller_id
LEFT JOIN payout_record pr ON sb.seller_id = pr.seller_id
GROUP BY sb.seller_id, sb.available_balance, sb.pending_balance, sb.held_balance
HAVING sb.available_balance + sb.pending_balance + sb.held_balance !=
    COALESCE(SUM(opm.seller_amount) FILTER (WHERE opm.status != 'CANCELLED'), 0)
    - COALESCE(SUM(pr.amount) FILTER (WHERE pr.status = 'COMPLETED'), 0);
```

---

## Message Queue Failures

### Event Consumer Lag

**Detection**:
- Consumer lag metric > threshold (e.g., 1000 messages)
- Processing time increasing

**Recovery**:
- Scale up consumers
- Increase batch size
- Skip to latest (with data loss acknowledgment)

### Poison Messages

Messages that cause repeated processing failures.

**Handling**:
```python
def consume_with_dlq(message, max_attempts=3):
    attempts = message.headers.get('retry_count', 0)

    try:
        process_order_event(message)
        consumer.commit(message)
    except ValidationError as e:
        # Invalid message, send directly to DLQ
        dlq.publish(message, error=str(e))
        consumer.commit(message)
    except ProcessingError as e:
        if attempts >= max_attempts:
            # Max retries exceeded
            dlq.publish(message, error=str(e))
            consumer.commit(message)
            alert_ops_team(f"Message sent to DLQ: {message.id}")
        else:
            # Retry with incremented counter
            message.headers['retry_count'] = attempts + 1
            retry_topic.publish(message)
            consumer.commit(message)
```

---

## Duplicate Prevention

### Duplicate Payment Detection

Multiple layers of protection against duplicate payments:

**Layer 1: Idempotency Key**
```python
payout_id = f"PO-{date}-{seller_id}-{hash(period_start + period_end)}"

# Insert with ON CONFLICT
INSERT INTO payout_record (payout_id, ...)
VALUES (:payout_id, ...)
ON CONFLICT (payout_id) DO NOTHING;
```

**Layer 2: Status Check**
```python
def can_create_payout(seller_id: str) -> bool:
    existing = db.query("""
        SELECT 1 FROM payout_record
        WHERE seller_id = :seller_id
          AND status IN ('PENDING', 'PROCESSING')
    """, seller_id=seller_id)
    return not existing
```

**Layer 3: Distributed Lock**
```python
with redis_lock(f"payout:{seller_id}", timeout=120):
    if can_create_payout(seller_id):
        create_payout(seller_id)
```

**Layer 4: Gateway Idempotency**
```python
# Include payout_id as reference for gateway
response = gateway.send_wire(
    wire_details=details,
    amount=amount,
    reference_id=payout.payout_id  # Gateway deduplicates on this
)
```

### Duplicate Event Detection

```python
def process_order_event(event):
    # Check if already processed
    existing = db.query("""
        SELECT 1 FROM order_payout_mapping
        WHERE order_id = :order_id AND seller_id = :seller_id
    """, order_id=event.order_id, seller_id=event.seller_id)

    if existing:
        log.info(f"Order {event.order_id} already processed, skipping")
        return  # Idempotent - no error

    # Process the event
    create_order_mapping(event)
```

---

## Alerting Configuration

### Critical Alerts (P1 - Immediate Response)

| Alert | Condition | Action |
|-------|-----------|--------|
| Payment Gateway Down | Circuit breaker OPEN | On-call page |
| Database Unavailable | Connection failures > 3 | On-call page |
| Payment Failure Rate High | > 10% in 15 minutes | On-call page |
| DLQ Growing | > 50 messages | On-call page |

### Warning Alerts (P2 - Response within 1 hour)

| Alert | Condition | Action |
|-------|-----------|--------|
| Stuck Payouts | PROCESSING > 15 min | Slack notification |
| Consumer Lag | > 5000 messages | Slack notification |
| Gateway Latency High | p99 > 90 seconds | Slack notification |
| Job Execution Delayed | > 30 min late | Slack notification |

### Informational Alerts (P3 - Next business day)

| Alert | Condition | Action |
|-------|-----------|--------|
| Balance Discrepancy | Detected in audit | Email to finance |
| Manual Intervention Queue | > 10 items | Email to support |
| Retry Rate High | > 5% of payouts | Email to engineering |

---

## Disaster Recovery

### RPO and RTO Targets

| Metric | Target | Strategy |
|--------|--------|----------|
| RPO (Recovery Point Objective) | < 1 minute | Synchronous replication |
| RTO (Recovery Time Objective) | < 5 minutes | Automated failover |

### Failover Procedure

```
1. Detect primary failure (health check fails 3 times)
2. Promote replica to primary (automatic)
3. Update connection strings (automatic via DNS)
4. Verify data consistency
5. Resume processing from checkpoint
6. Alert operations team
```

### Backup Strategy

| Data | Backup Frequency | Retention | Location |
|------|------------------|-----------|----------|
| Payment DB | Continuous (WAL) | 30 days | Cross-region S3 |
| Audit Log | Daily snapshot | 7 years | Glacier |
| Configuration | On change | 90 days | Git repository |

### Recovery Testing

- Monthly: Failover drill to replica
- Quarterly: Full restore from backup
- Annually: Cross-region disaster recovery test

