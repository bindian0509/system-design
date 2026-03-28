# Channel Workers

## Overview

Each channel (SMS, Email, Push) has an independent horizontally-scalable worker service. Workers consume from all three priority Kafka topics (polling critical first), call the **Template Service** to render content, dispatch to third-party providers, handle retries with exponential backoff, update delivery status in PostgreSQL, and route permanently-failed messages to the DLQ.

Workers are **stateless** — all state lives in PostgreSQL and Kafka offsets. A worker pod crash results in re-delivery of unacknowledged messages.

Kafka messages carry only `{template_id, template_vars, recipient}` — no rendered content. This keeps messages under 4KB regardless of email size. Large rendered email HTML (> 256KB) is staged in S3; the Email Worker streams it directly to SES.

---

## Worker Architecture

```mermaid
flowchart TB
    subgraph Worker["Email Worker Pod (SMS/Push follow same pattern, minus S3)"]
        direction TB
        Poller["Priority Poller\n(poll critical → trans → marketing)"]
        Renderer["Template Renderer\n(calls Template Service)"]
        PayloadRouter["Payload Router\n(inline vs S3 based on size)"]
        Dispatcher["Provider Dispatcher\n(SES client)"]
        RetryManager["Retry Manager\n(backoff + attempt tracking)"]
        StatusUpdater["Status Updater\n(PostgreSQL writes)"]
    end

    subgraph Kafka["Kafka Topics"]
        KC[notif.critical]
        KT[notif.transactional]
        KM[notif.marketing]
        DLQ[notif.dlq]
    end

    subgraph TemplateSvc["Template Service"]
        TAPI[Render API]
        TCache[(Redis Cache\nTTL=60s)]
    end

    subgraph Storage["Storage"]
        S3[(S3\nLarge payloads > 256KB)]
        PG[(PostgreSQL)]
    end

    subgraph Providers["Third-Party Providers"]
        SES[AWS SES / SendGrid]
    end

    KC --> Poller
    KT --> Poller
    KM --> Poller

    Poller --> Renderer
    Renderer -->|GET /render| TAPI
    TAPI <--> TCache

    Renderer --> PayloadRouter
    PayloadRouter -->|size <= 256KB| Dispatcher
    PayloadRouter -->|size > 256KB| S3
    S3 -->|s3 reference| Dispatcher

    Dispatcher --> SES
    SES --> RetryManager
    RetryManager -->|retry| Dispatcher
    RetryManager -->|exhausted| DLQ

    Dispatcher --> StatusUpdater
    StatusUpdater --> PG
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

### Template Rendering + Large Payload Flow

```mermaid
sequenceDiagram
    participant Worker as Email Worker
    participant TS as Template Service
    participant S3 as S3
    participant SES as AWS SES
    participant PG as PostgreSQL
    participant DLQ as notif.dlq

    Worker->>Worker: Consume notification_id, template_id, template_vars, recipient_email

    Worker->>TS: POST /render with template_id, template_vars, user_id
    Note over TS: Check Redis cache first (key: template_id + segment hash)
    alt Cache hit
        TS-->>Worker: subject, body_html, body_text (cached skeleton)
        Worker->>Worker: Interpolate user-specific vars locally
    else Cache miss
        TS->>TS: Fetch template from DB\nRender full HTML (Mjml/Handlebars)
        TS->>TS: Cache rendered skeleton (TTL=60s)
        TS-->>Worker: subject, body_html, body_text
    end

    Note over Worker: Images are always CDN URLs in template\nNever base64 embedded

    alt body_html size <= 256KB
        Worker->>SES: SendEmail v2 {from, to, subject, body_html, body_text}
    else body_html size > 256KB (large marketing email)
        Worker->>S3: PUT s3://notif-email-payloads/{notification_id}.html
        S3-->>Worker: ETag confirmed
        Worker->>SES: SendRawEmail with S3 reference\n(SES streams from S3 directly)
    end

    alt Delivery success
        SES-->>Worker: MessageId: 0102018...
        Worker->>PG: UPDATE status=DELIVERED, provider_message_id=0102018...
        Worker->>Worker: Commit Kafka offset
    else Hard bounce (invalid address)
        SES-->>Worker: MessageRejected
        Worker->>PG: UPDATE status=FAILED
        Worker->>DLQ: Produce with reason INVALID_ADDRESS
        Worker->>Worker: Commit Kafka offset
    else Throttle (429)
        SES-->>Worker: ThrottlingException
        Worker->>Worker: Backoff + retry (same S3 object reused)
    end
```

**Email-specific handling**:
- **Images**: Always CDN-hosted URLs in templates (`<img src="https://cdn.example.com/...">`). Never base64 — keeps body_html small and enables browser caching
- **Large payloads**: Rendered HTML > 256KB → uploaded to S3 once, reused across retries (S3 object survives worker retries)
- **Rendering cache**: Template Service caches rendered skeletons by `{template_id + user_segment}` for 60s — a 100M-user bulk send renders the template once, not 100M times; only user-specific vars (name, order_id) are interpolated per-user at the worker
- **SES delivery receipts**: Bounces and complaints arrive asynchronously via SNS webhook → update `notifications.status`
- **Soft bounces** (mailbox full) → retry; **hard bounces** (invalid address) → DLQ + mark address invalid in user profile

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
        Worker->>FCM: POST /v1/projects/id/messages:send with token, notification, data
        FCM-->>Worker: 200 OK with message name
        Worker->>PG: UPDATE status=DELIVERED
    else iOS (APNs)
        Worker->>APNs: POST /3/device/token via HTTP/2 JWT auth
        APNs-->>Worker: 200 OK with apns-id
        Worker->>PG: UPDATE status=DELIVERED
    else Token expired/invalid
        FCM-->>Worker: UNREGISTERED token
        Worker->>PG: UPDATE status=FAILED - mark device token as stale
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
