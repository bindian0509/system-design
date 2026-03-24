# Notification Service — System Design

A greenfield notification service for an Amazon-scale e-commerce platform, supporting **SMS, Email, and Push** channels at 500M+ notifications/day.

---

## Problem Statement

Internal services (Order, Auth, Marketing, Payment, etc.) need a unified way to send notifications to users. Requirements:

- Three priority tiers: **Critical** (OTP, security) / **Transactional** (orders, delivery) / **Marketing** (promos)
- Per-service **quota enforcement** to control third-party provider billing
- **Deduplication** to suppress duplicate sends within configurable windows
- Basic **DND and opt-out** per channel per user
- **Retry with exponential backoff** on provider failures
- Integration via **REST API** — callers POST and get 202 Accepted; delivery is async

---

## Architecture at a Glance

```
Calling Services
      │
      │ POST /notify {template_id, vars, channel, priority}
      ▼
┌─────────────────────────────────────────┐
│        Notification Gateway             │
│  Auth → Quota → Dedup → DND → Route    │
└──────────────┬──────────────────────────┘
               │ enqueue {template_id, vars}  ← tiny message, no rendered content
               ▼
      ┌─────────────────┐
      │   Kafka Topics   │
      │  P1: critical    │
      │  P2: transactional│
      │  P3: marketing   │
      └────────┬─────────┘
               │
    ┌──────────┼───────────┐
    ▼          ▼           ▼
 SMS         Email       Push
Worker      Worker      Worker
    │          │           │
    │     ┌────┘           │
    └────►│  Template  ◄───┘
          │  Service
          │  (render + cache)
          │
          ├─ Twilio / SNS
          ├─ SES / SendGrid  ──► S3 (if email > 256KB)
          └─ FCM / APNs
```

**Key design decisions:**
- Separate Kafka topics per priority tier (not tags) — P1 workers always drain critical first, marketing floods never starve OTP
- Template rendering happens at the **worker** (not the gateway) — Kafka messages stay under 4KB regardless of email size
- **Template Service** is independent — marketing teams manage content without touching delivery infrastructure
- Large email HTML (> 256KB) staged in **S3**, streamed directly to SES — Kafka never carries email bodies

---

## Design Documents

### Start Here

| Doc | What it covers |
|-----|---------------|
| [System Architecture](design/system-architecture.md) | Full component diagram, happy-path sequence, rejection flows, deployment and scaling topology |
| [Non-Functional Requirements](design/non-functional-requirements.md) | Availability targets, Kafka sizing, rate limiting layers, observability and alerting |

### Core Components

| Doc | What it covers |
|-----|---------------|
| [API Contracts](design/api-contracts.md) | All REST endpoints — `POST /notify`, status polling, user preferences, quota check — with request/response schemas and sequence diagrams |
| [Data Models](design/data-models.md) | ER diagram, PostgreSQL table DDLs, Redis key schemas, notification lifecycle state machine, retention policy |
| [Priority Queuing](design/priority-queuing.md) | Kafka topic design, partition strategy, priority-aware consumer polling, Kafka message schema, consumer lag alerting |
| [Channel Workers](design/channel-workers.md) | Per-channel worker design (SMS/Email/Push), retry policy, circuit breaker state machine, large email S3 path, provider-specific handling |
| [Template Service](design/template-service.md) | Template CRUD + versioning, two-phase rendering (Mjml compile → cache → user interpolation), A/B testing, fault tolerance fallback chain |

### Cross-Cutting Concerns

| Doc | What it covers |
|-----|---------------|
| [Quota & Deduplication](design/quota-and-dedup.md) | Redis INCR fixed-window quota enforcement, idempotency key derivation, dedup windows per priority tier, combined cost-control flow |
| [Fault Tolerance](design/fault-tolerance.md) | DLQ design, retry sequences, multi-AZ HA for each data store, failure scenario table, RPO/RTO targets |
| [Integration Patterns](design/integration-patterns.md) | REST API vs SDK vs Event-Driven vs Webhook — trade-off comparison, decision tree, code examples for how other services onboard |

---

## Component Summary

| Component | Tech | Role |
|-----------|------|------|
| Notification Gateway | Stateless pods, multi-AZ | Auth, quota, dedup, DND, priority routing, enqueue |
| Kafka | RF=3, min ISR=2 | Durable priority queues; P1 (60 partitions), P2 (120), P3 (240) |
| SMS Worker | Kafka consumer + Twilio | Render → dispatch SMS, retry, DLQ |
| Email Worker | Kafka consumer + SES | Render → S3 if large → dispatch email, retry, DLQ |
| Push Worker | Kafka consumer + FCM/APNs | Render → dispatch push, retry, DLQ |
| Template Service | Stateless pods + Redis + PG | Template CRUD, Mjml rendering, Redis skeleton cache (60s TTL), A/B variants |
| Redis Cluster | 6-node, 3 shards | Quota counters (INCR+TTL), dedup keys (SET NX+TTL), template render cache |
| PostgreSQL | Primary + 2 read replicas | Notification records, config, user preferences, template definitions, audit logs |
| S3 | Object storage | Rendered email HTML > 256KB; streamed directly from S3 to SES |
| DLQ | Kafka topic (30-day retention) | Permanently failed notifications; alerts to PagerDuty on CRITICAL DLQ growth |

---

## Priority Tiers

| Tier | Examples | Kafka Topic | Dedup Window | OTP Rate Limit |
|------|----------|-------------|-------------|----------------|
| CRITICAL | OTP, security alerts, password reset | `notif.critical` | 5 minutes | 1 per user per 60s |
| TRANSACTIONAL | Order shipped, payment confirmed, delivery update | `notif.transactional` | 1 hour | — |
| MARKETING | Promos, recommendations, newsletters | `notif.marketing` | 24 hours | 3 per user per 24h |

CRITICAL notifications bypass DND and cannot be sent by services without explicit allowlist authorization.

---

## Cost Control Mechanisms

Three independent gates prevent unnecessary third-party provider charges, all enforced at the gateway **before** any message hits Kafka:

1. **Per-service quota** — hourly and daily limits per service per channel, enforced via Redis INCR with TTL. Returns 429 on breach.
2. **Deduplication** — idempotency key (`SHA256(service_id + user_id + template_id + time_window)`) stored in Redis SET NX. Suppresses duplicates silently.
3. **User opt-out / DND** — opt-out is permanent per channel; DND is a time window (e.g. 22:00–08:00 local time). Neither applies to CRITICAL priority.

Every suppressed/rejected notification is recorded in `notifications` with a status (QUOTA_EXCEEDED, DUPLICATE_SUPPRESSED, OPTED_OUT, DND_SUPPRESSED) — full audit trail for cost reconciliation.

---

## How Other Services Integrate

```python
# Minimal REST example (Order Service sending a shipment notification)
requests.post(
    "https://notification-service.internal/v1/notify",
    headers={"X-Service-API-Key": NOTIF_API_KEY},
    json={
        "user_id": order.customer_id,
        "channel": "PUSH",
        "priority": "TRANSACTIONAL",
        "template_id": "order_shipped_v3",
        "template_vars": {"order_id": order.id, "tracking_url": order.tracking_url},
        "idempotency_key": f"order-shipped-{order.id}"
    }
)
# Returns 202 Accepted immediately. Delivery is async.
```

See [Integration Patterns](design/integration-patterns.md) for REST vs SDK vs Event-Driven trade-off analysis and a decision tree for choosing the right integration approach.

---

## Non-Functional Targets (Summary)

| Dimension | Target |
|-----------|--------|
| Gateway availability | 99.99% |
| OTP delivery SLA | p95 < 5 seconds end-to-end |
| Transactional delivery SLA | p95 < 30 seconds |
| Peak throughput | 50,000 notifications/second (10× Black Friday) |
| Kafka message size | < 4KB (template_id + vars only, no rendered content) |
| Gateway acceptance latency | p99 < 50ms (CRITICAL), < 200ms (MARKETING) |
| Template render latency (cache hit) | p99 < 5ms |
| DLQ alert (CRITICAL channel) | Page on-call if > 10 messages in 5 minutes |
