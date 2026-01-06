# Payment Flow

This document details the end-to-end payment processing flows, from order completion to successful seller payout.

## High-Level Flow Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Order     │    │  Balance    │    │   Payout    │    │  Gateway    │
│ Completed   │───▶│  Updated    │───▶│  Scheduled  │───▶│  Payment    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
   Pending           Available           Processing        Completed
   Balance           Balance             Status            Status
```

## Flow 1: Order to Balance

When an order is completed, the seller's balance is credited.

### Sequence Diagram

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Order   │     │  Event   │     │ Balance  │     │ Payment  │     │  Audit   │
│ Service  │     │  Queue   │     │ Service  │     │    DB    │     │   Log    │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │ Publish Event  │                │                │                │
     │───────────────▶│                │                │                │
     │                │                │                │                │
     │                │ Consume Event  │                │                │
     │                │───────────────▶│                │                │
     │                │                │                │                │
     │                │                │ Check Duplicate│                │
     │                │                │───────────────▶│                │
     │                │                │◀───────────────│                │
     │                │                │                │                │
     │                │                │  BEGIN TXN     │                │
     │                │                │───────────────▶│                │
     │                │                │                │                │
     │                │                │ Update Balance │                │
     │                │                │───────────────▶│                │
     │                │                │                │                │
     │                │                │ Create Mapping │                │
     │                │                │───────────────▶│                │
     │                │                │                │                │
     │                │                │  COMMIT TXN    │                │
     │                │                │───────────────▶│                │
     │                │                │                │                │
     │                │                │                │  Log Event    │
     │                │                │                │───────────────▶│
     │                │                │                │                │
     │                │   ACK Event    │                │                │
     │                │◀───────────────│                │                │
     │                │                │                │                │
```

### Processing Steps

**Step 1: Event Publication (OrderService)**
```json
{
  "eventId": "EVT-20260106-001",
  "eventType": "ORDER_COMPLETED",
  "orderId": "ORD-123",
  "products": [
    {
      "productId": "P789",
      "sellerId": "S001",
      "sellerPrice": 45.00,
      "quantity": 2
    }
  ],
  "orderTimestamp": "2026-01-06T10:30:00Z"
}
```

**Step 2: Idempotency Check**
```sql
-- Check if order already processed for this seller
SELECT 1 FROM order_payout_mapping
WHERE order_id = 'ORD-123' AND seller_id = 'S001';

-- If exists, skip processing (idempotent)
```

**Step 3: Calculate Seller Amount**
```
For each product in order:
  seller_amount = sellerPrice × quantity

Total for S001 = 45.00 × 2 = 90.00
```

**Step 4: Update Balance (Atomic Transaction)**
```sql
BEGIN TRANSACTION;

-- Update seller balance
UPDATE seller_balance
SET pending_balance = pending_balance + 90.00,
    version = version + 1,
    last_updated = NOW()
WHERE seller_id = 'S001';

-- Create order mapping
INSERT INTO order_payout_mapping
  (order_id, seller_id, seller_amount, status, order_timestamp)
VALUES
  ('ORD-123', 'S001', 90.00, 'PENDING', '2026-01-06T10:30:00Z');

COMMIT;
```

**Step 5: Audit Log**
```json
{
  "auditId": "AUD-20260106-001",
  "eventType": "BALANCE_CREDITED",
  "sellerId": "S001",
  "previousState": {"pending_balance": 250.00},
  "newState": {"pending_balance": 340.00},
  "metadata": {"order_id": "ORD-123", "amount": 90.00}
}
```

---

## Flow 2: Settlement Window

Orders go through a settlement window before becoming available for payout.

### Settlement Window Process

```
Day 0: Order completed → pending_balance += amount
Day 1-6: Settlement window (cancellation possible)
Day 7: Settlement complete → available_balance += amount, pending_balance -= amount
```

### Scheduled Job: Settlement Processor

**Frequency**: Runs every hour

```sql
-- Find orders past settlement window
SELECT opm.order_id, opm.seller_id, opm.seller_amount
FROM order_payout_mapping opm
WHERE opm.status = 'PENDING'
  AND opm.order_timestamp < NOW() - INTERVAL '7 days';

-- For each eligible order:
BEGIN TRANSACTION;

UPDATE seller_balance
SET available_balance = available_balance + :amount,
    pending_balance = pending_balance - :amount,
    version = version + 1
WHERE seller_id = :sellerId
  AND pending_balance >= :amount;

UPDATE order_payout_mapping
SET status = 'SETTLED',
    settlement_date = NOW()
WHERE order_id = :orderId AND seller_id = :sellerId;

COMMIT;
```

---

## Flow 3: Payout Scheduling

The scheduler determines which sellers are eligible for payout.

### Eligibility Determination

```
┌─────────────────────────────────────────────────────────────────┐
│                    PAYOUT ELIGIBILITY CHECK                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  DAILY Schedule:                                                │
│    eligible = (current_time == 22:00) AND (available > 0)       │
│                                                                 │
│  WEEKLY Schedule:                                               │
│    eligible = (day_of_week == preferred_day)                    │
│               AND (current_time == 22:00)                       │
│               AND (available > 0)                               │
│                                                                 │
│  THRESHOLD Schedule:                                            │
│    eligible = (available >= threshold_amount)                   │
│                                                                 │
│  ON_DEMAND Schedule:                                            │
│    eligible = (payout_request_exists) AND (available > 0)       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Scheduler Query Examples

**Daily Payout (runs at 22:00)**:
```sql
SELECT sb.seller_id, sb.available_balance, spp.payment_method
FROM seller_balance sb
JOIN seller_payout_preference spp ON sb.seller_id = spp.seller_id
WHERE spp.payout_schedule = 'DAILY'
  AND sb.available_balance > 0
  AND NOT EXISTS (
    SELECT 1 FROM payout_record pr
    WHERE pr.seller_id = sb.seller_id
      AND pr.status IN ('PENDING', 'PROCESSING')
  );
```

**Weekly Payout (runs at 22:00 on configured day)**:
```sql
SELECT sb.seller_id, sb.available_balance, spp.payment_method
FROM seller_balance sb
JOIN seller_payout_preference spp ON sb.seller_id = spp.seller_id
WHERE spp.payout_schedule = 'WEEKLY'
  AND spp.preferred_day = EXTRACT(DOW FROM CURRENT_DATE)
  AND sb.available_balance > 0;
```

**Threshold Payout (runs every 15 minutes)**:
```sql
SELECT sb.seller_id, sb.available_balance, spp.payment_method, spp.threshold_amount
FROM seller_balance sb
JOIN seller_payout_preference spp ON sb.seller_id = spp.seller_id
WHERE spp.payout_schedule = 'THRESHOLD'
  AND sb.available_balance >= spp.threshold_amount;
```

### Payout Record Creation

```sql
-- Generate idempotency key
payout_id = 'PO-' || DATE || '-' || seller_id || '-' || MD5(period_start || period_end)

-- Create payout record
INSERT INTO payout_record (
  payout_id, seller_id, amount, payment_method, status,
  period_start, period_end, created_at
)
VALUES (
  :payoutId, :sellerId, :amount, :paymentMethod, 'PENDING',
  :periodStart, :periodEnd, NOW()
)
ON CONFLICT (payout_id) DO NOTHING;  -- Idempotent
```

---

## Flow 4: Payment Processing

The payment processor executes the actual payment through the gateway.

### Processing Sequence

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│Processor │     │ Payment  │     │  Seller  │     │ Gateway  │     │  Audit   │
│          │     │    DB    │     │ Service  │     │          │     │   Log    │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │ Get PENDING    │                │                │                │
     │───────────────▶│                │                │                │
     │◀───────────────│                │                │                │
     │                │                │                │                │
     │ Acquire Lock   │                │                │                │
     │───────────────▶│                │                │                │
     │◀───────────────│ (optimistic)   │                │                │
     │                │                │                │                │
     │ Set PROCESSING │                │                │                │
     │───────────────▶│                │                │                │
     │                │                │                │                │
     │                │                │                │ Log SUBMITTED  │
     │                │                │                │───────────────▶│
     │                │                │                │                │
     │ Get Payment Details             │                │                │
     │────────────────────────────────▶│                │                │
     │◀────────────────────────────────│                │                │
     │                │                │                │                │
     │ sendWire/sendCheck              │                │                │
     │─────────────────────────────────────────────────▶│                │
     │                │                │                │                │
     │                │  (~1 minute processing)        │                │
     │                │                │                │                │
     │◀─────────────────────────────────────────────────│                │
     │                │    transactionId or error      │                │
     │                │                │                │                │
     │ Update Status  │                │                │                │
     │───────────────▶│                │                │                │
     │                │                │                │                │
     │ Deduct Balance │                │                │                │
     │───────────────▶│                │                │                │
     │                │                │                │                │
     │                │                │                │ Log COMPLETED  │
     │                │                │                │───────────────▶│
     │                │                │                │                │
```

### Payment Processor Pseudocode

```python
def process_payout(payout: PayoutRecord):
    # Step 1: Acquire optimistic lock
    result = db.execute("""
        UPDATE payout_record
        SET status = 'PROCESSING',
            processed_at = NOW(),
            version = version + 1
        WHERE payout_id = :payout_id
          AND status = 'PENDING'
          AND version = :current_version
        RETURNING *
    """, payout_id=payout.id, current_version=payout.version)

    if not result:
        log.warn(f"Payout {payout.id} already being processed")
        return

    # Step 2: Log submission
    audit_log.log(
        event_type='PAYOUT_SUBMITTED',
        payout_id=payout.id,
        seller_id=payout.seller_id
    )

    # Step 3: Get payment details from SellerService
    try:
        payment_details = seller_service.get_payment_details(payout.seller_id)
    except Exception as e:
        mark_failed(payout, 'SELLER_SERVICE_ERROR', str(e))
        return

    # Step 4: Call payment gateway
    try:
        if payout.payment_method == 'WIRE':
            txn_id = gateway.send_wire(
                wire_details=payment_details.wire_details,
                amount=payout.amount
            )
        else:
            txn_id = gateway.send_check(
                check_details=payment_details.check_details,
                amount=payout.amount
            )
    except GatewayError as e:
        handle_gateway_error(payout, e)
        return

    # Step 5: Mark completed and deduct balance
    with db.transaction():
        db.execute("""
            UPDATE payout_record
            SET status = 'COMPLETED',
                gateway_txn_id = :txn_id,
                completed_at = NOW()
            WHERE payout_id = :payout_id
        """, txn_id=txn_id, payout_id=payout.id)

        db.execute("""
            UPDATE seller_balance
            SET available_balance = available_balance - :amount,
                version = version + 1
            WHERE seller_id = :seller_id
        """, amount=payout.amount, seller_id=payout.seller_id)

        db.execute("""
            UPDATE order_payout_mapping
            SET status = 'PAID', payout_id = :payout_id
            WHERE seller_id = :seller_id
              AND status = 'SETTLED'
              AND payout_id IS NULL
        """, payout_id=payout.id, seller_id=payout.seller_id)

    # Step 6: Log completion
    audit_log.log(
        event_type='PAYOUT_COMPLETED',
        payout_id=payout.id,
        seller_id=payout.seller_id,
        metadata={'gateway_txn_id': txn_id}
    )
```

---

## Flow 5: Order Cancellation

Handling order cancellations within the settlement window.

### Cancellation Scenarios

| Scenario | Action |
|----------|--------|
| Order in PENDING state | Deduct from pending_balance |
| Order already SETTLED | Deduct from available_balance |
| Order already PAID | Clawback from next payout |

### Cancellation Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Order   │     │ Balance  │     │ Payment  │     │  Audit   │
│ Service  │     │ Service  │     │    DB    │     │   Log    │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ ORDER_CANCELLED│                │                │
     │───────────────▶│                │                │
     │                │                │                │
     │                │ Get Mapping    │                │
     │                │───────────────▶│                │
     │                │◀───────────────│                │
     │                │                │                │
     │                │ [PENDING]      │                │
     │                │ Deduct pending │                │
     │                │───────────────▶│                │
     │                │                │                │
     │                │ [SETTLED]      │                │
     │                │ Deduct avail   │                │
     │                │───────────────▶│                │
     │                │                │                │
     │                │ [PAID]         │                │
     │                │ Create clawback│                │
     │                │───────────────▶│                │
     │                │                │                │
     │                │ Update mapping │                │
     │                │───────────────▶│                │
     │                │                │                │
     │                │                │  Log Event    │
     │                │                │───────────────▶│
     │                │                │                │
```

### Cancellation Pseudocode

```python
def handle_order_cancellation(order_id: str, seller_id: str):
    # Get current mapping status
    mapping = db.get_order_mapping(order_id, seller_id)

    if not mapping:
        log.warn(f"No mapping found for {order_id}/{seller_id}")
        return

    with db.transaction():
        if mapping.status == 'PENDING':
            # Deduct from pending balance
            db.execute("""
                UPDATE seller_balance
                SET pending_balance = pending_balance - :amount
                WHERE seller_id = :seller_id
                  AND pending_balance >= :amount
            """, amount=mapping.seller_amount, seller_id=seller_id)

        elif mapping.status == 'SETTLED':
            # Deduct from available balance
            db.execute("""
                UPDATE seller_balance
                SET available_balance = available_balance - :amount
                WHERE seller_id = :seller_id
                  AND available_balance >= :amount
            """, amount=mapping.seller_amount, seller_id=seller_id)

        elif mapping.status == 'PAID':
            # Create clawback record for next payout
            db.execute("""
                INSERT INTO clawback_record
                  (order_id, seller_id, amount, reason, created_at)
                VALUES
                  (:order_id, :seller_id, :amount, 'ORDER_CANCELLED', NOW())
            """, order_id=order_id, seller_id=seller_id,
                 amount=mapping.seller_amount)

        # Update mapping status
        db.execute("""
            UPDATE order_payout_mapping
            SET status = 'CANCELLED'
            WHERE order_id = :order_id AND seller_id = :seller_id
        """, order_id=order_id, seller_id=seller_id)

    # Audit log
    audit_log.log(
        event_type='ORDER_CANCELLED',
        seller_id=seller_id,
        metadata={
            'order_id': order_id,
            'previous_status': mapping.status,
            'amount': mapping.seller_amount
        }
    )
```

---

## Flow 6: On-Demand Payout

When a seller requests an immediate payout.

### Request Validation

```python
def validate_on_demand_request(seller_id: str, requested_amount: float):
    # Get current balance
    balance = db.get_seller_balance(seller_id)

    # Check available balance
    if requested_amount > balance.available_balance:
        raise InsufficientBalanceError(
            requested=requested_amount,
            available=balance.available_balance
        )

    # Check minimum payout amount
    MIN_PAYOUT = 10.00
    if requested_amount < MIN_PAYOUT:
        raise MinimumNotMetError(minimum=MIN_PAYOUT)

    # Check for in-progress payouts
    in_progress = db.exists("""
        SELECT 1 FROM payout_record
        WHERE seller_id = :seller_id
          AND status IN ('PENDING', 'PROCESSING')
    """, seller_id=seller_id)

    if in_progress:
        raise PayoutInProgressError()

    return True
```

### On-Demand Processing

```python
def process_on_demand_payout(seller_id: str, amount: float):
    # Validate request
    validate_on_demand_request(seller_id, amount)

    # Create payout record
    payout_id = generate_payout_id(seller_id, 'ON_DEMAND')

    payout = db.execute("""
        INSERT INTO payout_record
          (payout_id, seller_id, amount, payment_method, status,
           period_start, period_end, created_at)
        SELECT
          :payout_id, :seller_id, :amount, spp.payment_method, 'PENDING',
          NOW(), NOW(), NOW()
        FROM seller_payout_preference spp
        WHERE spp.seller_id = :seller_id
        RETURNING *
    """, payout_id=payout_id, seller_id=seller_id, amount=amount)

    # Queue for immediate processing
    message_queue.publish('payout-requests', {
        'payout_id': payout_id,
        'priority': 'HIGH'
    })

    return payout
```

---

## Concurrency Handling

### Optimistic Locking

All balance updates use optimistic locking to prevent race conditions:

```sql
UPDATE seller_balance
SET available_balance = available_balance - :amount,
    version = version + 1
WHERE seller_id = :seller_id
  AND version = :expected_version
  AND available_balance >= :amount;

-- Check rows affected
-- If 0 rows: Retry with fresh data
```

### Distributed Locks

For operations requiring cross-service coordination:

```python
def acquire_seller_lock(seller_id: str, timeout_seconds: int = 60):
    lock_key = f"seller_payout_lock:{seller_id}"
    lock_value = str(uuid.uuid4())

    acquired = redis.set(
        lock_key,
        lock_value,
        nx=True,  # Only if not exists
        ex=timeout_seconds
    )

    if not acquired:
        raise LockNotAcquiredError(seller_id)

    return Lock(key=lock_key, value=lock_value)

def release_seller_lock(lock: Lock):
    # Only release if we own the lock
    script = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    else
        return 0
    end
    """
    redis.eval(script, 1, lock.key, lock.value)
```

---

## Performance Optimization

### Batch Processing

For high volume, process payouts in batches:

```python
BATCH_SIZE = 100
PARALLEL_WORKERS = 10

def process_payouts_batch():
    # Fetch batch of pending payouts
    payouts = db.fetch("""
        SELECT * FROM payout_record
        WHERE status = 'PENDING'
        ORDER BY created_at
        LIMIT :batch_size
        FOR UPDATE SKIP LOCKED
    """, batch_size=BATCH_SIZE)

    # Process in parallel with thread pool
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = [
            executor.submit(process_payout, payout)
            for payout in payouts
        ]

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                log.error(f"Payout processing failed: {e}")
```

### Connection Pooling

Gateway connections should be pooled and reused:

```python
gateway_pool = ConnectionPool(
    max_connections=20,
    timeout=120,  # 2 minutes for gateway calls
    retry_on_timeout=True
)
```

