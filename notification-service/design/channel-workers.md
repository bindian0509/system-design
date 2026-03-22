# Channel Workers

## Overview

Each channel (SMS, Email, Push) has an independent horizontally-scalable worker service. Workers consume from all three priority Kafka topics (polling critical first), render and dispatch notifications to third-party providers, handle retries with exponential backoff, update delivery status in PostgreSQL, and route permanently-failed messages to the DLQ.

Workers are **stateless** — all state lives in PostgreSQL and Kafka offsets. A worker pod crash results in re-delivery of unacknowledged messages.

---

## Worker Architecture

```mermaid
flowchart TB
    subgraph Worker["SMS Worker Pod (same pattern for Email, Push)"]
        direction TB
        Poller["Priority Poller\n(poll critical → trans → marketing)"]
        Dispatcher["Provider Dispatcher\n(Twilio client)"]
        RetryManager["Retry Manager\n(backoff + attempt tracking)"]
        StatusUpdater["Status Updater\n(PostgreSQL writes)"]
    end

    subgraph Kafka["Kafka Topics"]
        KC[notif.critical]
        KT[notif.transactional]
        KM[notif.marketing]
        DLQ[notif.dlq]
    end

    subgraph Providers["Third-Party Providers"]
        Twilio[Twilio / AWS SNS]
    end

    KC --> Poller
    KT --> Poller
    KM --> Poller

    Poller --> Dispatcher
    Dispatcher --> Twilio
    Twilio --> RetryManager
    RetryManager -->|retry| Dispatcher
    RetryManager -->|exhausted| DLQ

    Dispatcher --> StatusUpdater
    StatusUpdater --> PG[(PostgreSQL)]
```

---

## Per-Channel Provider Mapping

| Channel | Primary Provider | SDK/API |
|---------|-----------------|---------|
| SMS | Twilio | REST API v2010 |
| Email | AWS SES | SES v2 SendEmail |
| Push (Android) | Firebase FCM | FCM HTTP v1 |
| Push (iOS) | Apple APNs | APNs HTTP/2 |

Each worker implements a `ProviderClient` interface:

```
interface ProviderClient {
  send(notification: Notification): Result<provider_message_id, ProviderError>
}
```

This abstraction allows swapping providers without changing retry/status logic.

---

## Retry Policy

```mermaid
flowchart TD
    DISPATCH[Dispatch to Provider] --> RESULT{Response?}

    RESULT -->|200/201 Success| DELIVERED[Update status=DELIVERED\nCommit Kafka offset]

    RESULT -->|Retryable error\n429 / 503 / network timeout| RETRY{attempt_count < max_attempts?}

    RETRY -->|yes| BACKOFF["Wait: 2^attempt × 1s\n(cap at 30s)\n1s → 2s → 4s → 8s..."]
    BACKOFF --> DISPATCH

    RETRY -->|no, exhausted| DLQ_ROUTE[Update status=FAILED\nProduce to notif.dlq\nCommit Kafka offset]

    RESULT -->|Non-retryable error\n400 invalid number\n401 bad credentials| FAIL_PERM[Update status=FAILED\nProduce to notif.dlq\nCommit Kafka offset\nAlert on 401]
```

### Retry Configuration

| Priority | Max Attempts | Backoff Base | Max Backoff | Total Max Wait |
|----------|-------------|-------------|-------------|---------------|
| CRITICAL | 3 | 1s | 4s | ~7s |
| TRANSACTIONAL | 3 | 2s | 16s | ~20s |
| MARKETING | 3 | 5s | 30s | ~35s |

CRITICAL retries faster because OTP expiry windows are tight (typically 5 minutes).

### Retryable vs Non-Retryable Errors

| Error | Type | Action |
|-------|------|--------|
| 429 Rate Limited by provider | Retryable | Retry with backoff |
| 503 Provider unavailable | Retryable | Retry with backoff |
| Network timeout | Retryable | Retry with backoff |
| 400 Invalid phone/email | Non-retryable | DLQ immediately |
| 401 Auth failure | Non-retryable | DLQ + alert (credential issue) |
| 404 Unknown recipient | Non-retryable | DLQ |

---

## Circuit Breaker

Each worker maintains a circuit breaker per provider to avoid hammering a failing provider during an outage.

```mermaid
stateDiagram-v2
    [*] --> CLOSED : Normal operation

    CLOSED --> OPEN : Error rate > 50%\nin last 60s window
    OPEN --> HALF_OPEN : After 30s cooldown
    HALF_OPEN --> CLOSED : 3 consecutive successes
    HALF_OPEN --> OPEN : Any failure

    note right of CLOSED
        Requests pass through normally
        Tracking: success/fail counts
    end note

    note right of OPEN
        All requests fail-fast
        No provider calls made
        Messages stay in Kafka (offset not committed)
    end note

    note right of HALF_OPEN
        1 probe request let through
        Tests if provider recovered
    end note
```

**When circuit is OPEN**: Worker does not commit the Kafka offset — messages accumulate (Kafka retains them). Once circuit closes, workers resume processing from where they left off. This is safe because Kafka retention is 7 days (critical: 24h).

**Circuit state is local per pod** (not shared via Redis). Pods independently detect provider failures. This is intentional — a degraded provider may behave differently across network paths, and local circuit state prevents cascading if only some pods are affected.

---

## Notification Lifecycle State Machine

```mermaid
stateDiagram-v2
    direction LR
    [*] --> QUEUED : Gateway accepted

    QUEUED --> DISPATCHING : Worker picked up

    DISPATCHING --> DELIVERED : Provider success
    DISPATCHING --> DISPATCHING : Retry (attempt < max)
    DISPATCHING --> FAILED : Retries exhausted\nor non-retryable error

    FAILED --> [*] : Moved to DLQ\nAlert fired

    note right of DELIVERED
        delivered_at recorded
        provider_message_id stored
        Kafka offset committed
    end note

    note right of FAILED
        failed_at recorded
        error details in audit log
        DLQ message produced
    end note
```

---

## Email Worker Specifics

```mermaid
sequenceDiagram
    participant Worker as Email Worker
    participant SES as AWS SES
    participant PG as PostgreSQL
    participant Kafka as notif.dlq

    Worker->>SES: SendEmail v2\n{from, to, subject, html_body, text_body}

    alt Success
        SES-->>Worker: MessageId: 0102018...
        Worker->>PG: UPDATE status=DELIVERED, provider_message_id=010201...
        Worker->>Worker: Commit Kafka offset
    else SES bounce (permanent — 5xx SMTP)
        SES-->>Worker: Error: MessageRejected (invalid address)
        Worker->>PG: UPDATE status=FAILED
        Worker->>Kafka: Produce DLQ message {reason: INVALID_ADDRESS}
        Worker->>Worker: Commit Kafka offset
    else SES throttle (429)
        SES-->>Worker: ThrottlingException
        Worker->>Worker: Backoff + retry
    end
```

**Email-specific handling**:
- SES delivery receipts (bounces, complaints) arrive via SNS webhook → update `notifications.status` asynchronously
- Soft bounces (mailbox full) → retry; hard bounces (invalid address) → DLQ + mark address invalid in user profile

---

## Push Worker Specifics

```mermaid
sequenceDiagram
    participant Worker as Push Worker
    participant FCM as Firebase FCM
    participant APNs as Apple APNs
    participant PG as PostgreSQL

    Worker->>Worker: Determine platform from\ndevice_token prefix or user profile

    alt Android (FCM)
        Worker->>FCM: POST /v1/projects/{id}/messages:send\n{token, notification, data}
        FCM-->>Worker: {name: projects/.../messages/...}
        Worker->>PG: UPDATE status=DELIVERED
    else iOS (APNs)
        Worker->>APNs: POST /3/device/{token}\n(HTTP/2, JWT auth)
        APNs-->>Worker: 200 OK {apns-id}
        Worker->>PG: UPDATE status=DELIVERED
    else Token expired/invalid
        FCM-->>Worker: UNREGISTERED token
        Worker->>PG: UPDATE status=FAILED\nMark device token as stale
        Note over Worker,PG: Trigger token refresh flow\nvia User Profile Service
    end
```

**Push-specific handling**:
- Device tokens expire — UNREGISTERED errors trigger token invalidation in the user profile system
- FCM supports topic messaging for bulk push (marketing tier), reducing API calls for broadcast notifications

---

## Worker Scaling

```mermaid
flowchart LR
    LagExporter[Kafka Lag Exporter] --> Prometheus
    Prometheus --> HPA[Kubernetes HPA]
    HPA -->|lag > threshold| Scale[Scale worker replicas]
    Scale --> NewPod[New Worker Pod\nauto-assigns Kafka partitions]
```

Kubernetes HPA scales based on **Kafka consumer lag** (custom metric via KEDA or prometheus-kafka-exporter), not CPU. This ensures scaling is driven by actual delivery backlog rather than compute usage.

| Worker | Min Replicas | Max Replicas | Scale Metric |
|--------|-------------|-------------|-------------|
| SMS Worker | 10 | 200 | notif.critical lag > 1K OR notif.transactional lag > 10K |
| Email Worker | 5 | 100 | notif.transactional lag > 50K OR notif.marketing lag > 200K |
| Push Worker | 10 | 500 | notif.critical lag > 1K OR notif.marketing lag > 500K |
