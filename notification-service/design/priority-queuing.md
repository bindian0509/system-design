# Priority Queuing

## Overview

The notification service uses three separate Kafka topics — one per priority tier — rather than a single topic with priority tags. This provides true priority isolation: a flood of marketing messages cannot starve OTP delivery, because consumer workers always drain the critical topic first.

---

## Topic Design

```mermaid
flowchart LR
    GW[Notification Gateway]

    GW -->|priority=CRITICAL| T1["notif.critical\n60 partitions\nKey: user_id"]
    GW -->|priority=TRANSACTIONAL| T2["notif.transactional\n120 partitions\nKey: user_id"]
    GW -->|priority=MARKETING| T3["notif.marketing\n240 partitions\nKey: round-robin"]

    T1 --> SMSGroup["sms-workers\nconsumer group"]
    T2 --> SMSGroup
    T3 --> SMSGroup

    T1 --> EmailGroup["email-workers\nconsumer group"]
    T2 --> EmailGroup
    T3 --> EmailGroup

    T1 --> PushGroup["push-workers\nconsumer group"]
    T2 --> PushGroup
    T3 --> PushGroup

    SMSGroup --> DLQ["notif.dlq"]
    EmailGroup --> DLQ
    PushGroup --> DLQ
```

### Topic Configuration

| Topic | Partitions | Partition Key | Retention | RF | Min ISR |
|-------|-----------|---------------|-----------|-----|---------|
| `notif.critical` | 60 | `user_id` | 24h | 3 | 2 |
| `notif.transactional` | 120 | `user_id` | 7 days | 3 | 2 |
| `notif.marketing` | 240 | round-robin | 3 days | 3 | 2 |
| `notif.dlq` | 12 | `notification_id` | 30 days | 3 | 2 |

**Why separate topics (not priority tags)?**
- Kafka has no native priority queue semantics; a single topic requires consumers to reorder in memory
- Separate topics allow independent consumer scaling, offset management, and lag monitoring per tier
- Critical topic stays small → poll latency is minimal; worker always finds OTP messages first

**Partition key rationale**:
- `user_id` for critical + transactional: ensures all notifications for a user go to the same partition → preserves ordering (user sees OTP before the "login success" push)
- Round-robin for marketing: pure throughput, no ordering requirement, avoids hot partitions from power users

---

## Priority Assignment Logic

The gateway assigns priority based on a two-level check:

```mermaid
flowchart TD
    IN[Incoming POST /notify\npriority field in request] --> CHECK1{priority == CRITICAL?}

    CHECK1 -->|yes| VERIFY[Verify caller is\nauthorized for CRITICAL]
    VERIFY -->|authorized| CRITICAL[Enqueue → notif.critical]
    VERIFY -->|not authorized| REJECT[400 FORBIDDEN_PRIORITY]

    CHECK1 -->|no| CHECK2{priority == TRANSACTIONAL?}
    CHECK2 -->|yes| TRANS[Enqueue → notif.transactional]
    CHECK2 -->|no| MARKETING[Enqueue → notif.marketing]
```

**CRITICAL authorization**: Only allowlisted services (e.g., `auth-service`, `payment-service`) may submit CRITICAL priority. This prevents a misconfigured marketing service from bypassing queues. Enforced by a `critical_senders` set in Redis, populated from config.

---

## Consumer Group Configuration

Each channel has its own consumer group subscribed to all three topics. Workers implement **priority-aware polling**: they poll the critical topic first, drain it (up to a configurable batch), then move to transactional, then marketing.

```mermaid
sequenceDiagram
    participant Worker as SMS Worker Pod
    participant KafkaC as notif.critical
    participant KafkaT as notif.transactional
    participant KafkaM as notif.marketing

    loop Poll cycle (every 50ms)
        Worker->>KafkaC: poll(max_records=50, timeout=50ms)
        alt critical messages available
            KafkaC-->>Worker: [msg1, msg2, ...]
            Worker->>Worker: Process critical batch
        else no critical messages
            Worker->>KafkaT: poll(max_records=100, timeout=50ms)
            alt transactional messages available
                KafkaT-->>Worker: [msg3, msg4, ...]
                Worker->>Worker: Process transactional batch
            else no transactional messages
                Worker->>KafkaM: poll(max_records=200, timeout=100ms)
                KafkaM-->>Worker: [msg5, ...]
                Worker->>Worker: Process marketing batch
            end
        end
    end
```

### Consumer Group Settings

| Setting | SMS Workers | Email Workers | Push Workers |
|---------|------------|---------------|--------------|
| `group.id` | `sms-workers` | `email-workers` | `push-workers` |
| `auto.offset.reset` | `earliest` | `earliest` | `earliest` |
| `enable.auto.commit` | `false` | `false` | `false` |
| `max.poll.records` | 50 (critical), 100 (trans), 200 (mktg) | same | same |
| `session.timeout.ms` | 30000 | 30000 | 30000 |
| Commit strategy | Manual after ACK from provider | same | same |

**Manual offset commit** (no auto-commit): Workers only commit the offset after the provider confirms delivery or the message is moved to DLQ. This ensures at-least-once delivery — if the worker crashes mid-dispatch, the message is re-delivered.

---

## Kafka Message Schema

```json
{
  "notification_id": "notif_a1b2c3d4",
  "service_id": "svc-auth",
  "user_id": "usr_abc123",
  "channel": "SMS",
  "priority": "CRITICAL",
  "template_id": "otp_verification_v2",
  "rendered_content": {
    "body": "Your OTP is 847291. Expires in 5 minutes. Do not share."
  },
  "recipient": {
    "phone_number": "+919876543210"
  },
  "metadata": {
    "order_id": null,
    "trace_id": "trace_abc"
  },
  "enqueued_at": "2026-03-23T10:00:00.045Z",
  "attempt_count": 0,
  "max_attempts": 3
}
```

Note: `rendered_content` is pre-rendered by the gateway at enqueue time using the template + vars. Workers do not need to re-fetch the template — this makes workers stateless with respect to template config.

---

## Consumer Lag Monitoring & Scaling

```mermaid
flowchart LR
    Kafka --> LagMonitor[Consumer Lag Monitor\nprometheus-kafka-exporter]
    LagMonitor --> Prometheus[Prometheus]
    Prometheus --> AlertManager[AlertManager]
    AlertManager -->|lag > threshold| HPA[Kubernetes HPA\nScale up workers]
    AlertManager -->|lag > critical threshold| PagerDuty[PagerDuty Alert]
```

### Lag Thresholds

| Topic | Scale-out trigger | Critical alert |
|-------|------------------|----------------|
| `notif.critical` | lag > 1,000 messages | lag > 5,000 messages |
| `notif.transactional` | lag > 10,000 messages | lag > 50,000 messages |
| `notif.marketing` | lag > 100,000 messages | lag > 500,000 messages |

Critical topic lag triggers immediate scale-out (OTP SLA: delivery < 2s p99). Marketing lag is expected during peak and can tolerate delay.

---

## End-to-End Sequence: Gateway Enqueue → Worker Dispatch

```mermaid
sequenceDiagram
    participant GW as Notification Gateway
    participant Kafka as Kafka (notif.critical)
    participant Worker as SMS Worker
    participant Twilio as Twilio
    participant PG as PostgreSQL

    GW->>PG: INSERT notifications (status=QUEUED)
    GW->>Kafka: Produce {notification_id, rendered_content, recipient, ...}
    Kafka-->>GW: ack (offset committed by producer)
    GW-->>Caller: 202 Accepted

    Kafka->>Worker: Poll → deliver message
    Worker->>PG: UPDATE status=DISPATCHING, attempt_count=1
    Worker->>Twilio: POST /Messages {To, Body}

    alt Success
        Twilio-->>Worker: 201 Created {sid: SM...}
        Worker->>PG: UPDATE status=DELIVERED, provider_message_id=SM..., delivered_at=NOW()
        Worker->>Kafka: Commit offset
    else Twilio error (retryable)
        Twilio-->>Worker: 503 / 429
        Worker->>Worker: Wait backoff (2^attempt × 1s, max 30s)
        Worker->>Twilio: Retry POST /Messages
    else All retries exhausted
        Worker->>PG: UPDATE status=FAILED, failed_at=NOW()
        Worker->>Kafka: Produce to notif.dlq
        Worker->>Kafka: Commit offset on source topic
    end
```
