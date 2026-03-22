# System Architecture

## Overview

The Notification Service is a **Hub-and-Spoke** system that provides a single REST entry point for all internal e-commerce services to send SMS, Email, and Push notifications. It handles 500M+ notifications/day across three priority tiers, enforcing per-service quotas, deduplication, and user DND preferences before dispatching to third-party providers via independent per-channel workers.

---

## High-Level Component Diagram

```mermaid
flowchart TB
    subgraph Callers["Calling Services (Internal)"]
        OS[Order Service]
        AS[Auth Service]
        MS[Marketing Service]
        PS[Payment Service]
        XS[... N Services]
    end

    subgraph Gateway["Notification Gateway (Stateless, Horizontally Scaled)"]
        direction TB
        AUTH[Auth & Rate Limiter]
        QUOTA[Quota Enforcer]
        DEDUP[Deduplication Check]
        DND[DND / Opt-out Resolver]
        ROUTER[Priority Router]
    end

    subgraph Queues["Priority Queues (Kafka, RF=3)"]
        P1["notif.critical\n(P1 — OTP, Security)"]
        P2["notif.transactional\n(P2 — Orders, Payments)"]
        P3["notif.marketing\n(P3 — Promos, Recs)"]
        DLQ["notif.dlq\n(Failed after retries)"]
    end

    subgraph Workers["Channel Workers (Independent, Horizontally Scaled)"]
        SMSWorker[SMS Worker]
        EmailWorker[Email Worker]
        PushWorker[Push Worker]
    end

    subgraph Providers["Third-Party Providers"]
        Twilio[Twilio / AWS SNS]
        SES[AWS SES / SendGrid]
        FCM[FCM / APNs]
    end

    subgraph DataStores["Data Stores"]
        Redis[(Redis Cluster\nQuota + Dedup)]
        PG[(PostgreSQL\nNotif DB + Config)]
        PGRead[(PostgreSQL\nRead Replica)]
    end

    Callers -->|POST /notify| AUTH
    AUTH --> QUOTA
    QUOTA -->|check Redis| Redis
    QUOTA --> DEDUP
    DEDUP -->|SET NX Redis| Redis
    DEDUP --> DND
    DND -->|read preferences| PGRead
    DND --> ROUTER

    ROUTER -->|priority=CRITICAL| P1
    ROUTER -->|priority=TRANSACTIONAL| P2
    ROUTER -->|priority=MARKETING| P3

    P1 --> SMSWorker
    P1 --> EmailWorker
    P1 --> PushWorker
    P2 --> SMSWorker
    P2 --> EmailWorker
    P2 --> PushWorker
    P3 --> SMSWorker
    P3 --> EmailWorker
    P3 --> PushWorker

    SMSWorker --> Twilio
    EmailWorker --> SES
    PushWorker --> FCM

    SMSWorker -->|failed| DLQ
    EmailWorker -->|failed| DLQ
    PushWorker -->|failed| DLQ

    SMSWorker -->|status update| PG
    EmailWorker -->|status update| PG
    PushWorker -->|status update| PG

    Gateway -->|write notification record| PG
```

---

## Happy Path: Data Flow Sequence

```mermaid
sequenceDiagram
    participant Caller as Calling Service
    participant GW as Notification Gateway
    participant Redis as Redis
    participant PG as PostgreSQL
    participant Kafka as Kafka
    participant Worker as Channel Worker
    participant Provider as Third-Party Provider

    Caller->>GW: POST /notify {service_id, user_id, channel, template, priority}

    GW->>Redis: INCR quota:{service_id}:{channel}:{window}
    Redis-->>GW: count=142 (under limit)

    GW->>Redis: SET NX dedup:{idempotency_key} TTL=300s
    Redis-->>GW: OK (not duplicate)

    GW->>PG: SELECT opted_out FROM user_preferences WHERE user_id=? AND channel=?
    PG-->>GW: opted_out=false, dnd=inactive

    GW->>PG: INSERT INTO notifications (id, status=QUEUED, ...)
    GW->>Kafka: Produce → notif.critical | notif.transactional | notif.marketing
    GW-->>Caller: 202 Accepted {notification_id}

    Kafka->>Worker: Consume message (at-least-once)
    Worker->>Provider: Send SMS / Email / Push
    Provider-->>Worker: 200 OK {provider_message_id}

    Worker->>PG: UPDATE notifications SET status=DELIVERED, delivered_at=NOW()
    Worker->>Kafka: ACK (commit offset)
```

---

## Rejection Flows

```mermaid
sequenceDiagram
    participant Caller as Calling Service
    participant GW as Notification Gateway
    participant Redis as Redis
    participant PG as PostgreSQL

    Note over GW: Quota exceeded
    Caller->>GW: POST /notify
    GW->>Redis: INCR quota:{service_id}:{channel}:{window}
    Redis-->>GW: count=10001 (over limit=10000)
    GW-->>Caller: 429 Too Many Requests {reason: QUOTA_EXCEEDED}

    Note over GW: Duplicate suppressed
    Caller->>GW: POST /notify (same idempotency_key)
    GW->>Redis: SET NX dedup:{key}
    Redis-->>GW: nil (key exists)
    GW-->>Caller: 200 OK {notification_id: original_id, status: DUPLICATE_SUPPRESSED}

    Note over GW: User opted out
    Caller->>GW: POST /notify
    GW->>PG: SELECT opted_out FROM user_preferences
    PG-->>GW: opted_out=true
    GW-->>Caller: 200 OK {notification_id: new_id, status: OPTED_OUT}
```

---

## Deployment & Scaling

```mermaid
flowchart TB
    subgraph Internet["Internal Network"]
        LB[Internal Load Balancer]
    end

    subgraph GWTier["Gateway Tier (Stateless — Auto-Scale)"]
        GW1[Gateway Pod 1]
        GW2[Gateway Pod 2]
        GWN[Gateway Pod N]
    end

    subgraph WorkerTier["Worker Tier (Scale per Channel)"]
        subgraph SMS["SMS Workers"]
            S1[SMS Pod 1]
            S2[SMS Pod 2]
        end
        subgraph Email["Email Workers"]
            E1[Email Pod 1]
            E2[Email Pod 2]
            EN[Email Pod N]
        end
        subgraph Push["Push Workers"]
            P1[Push Pod 1]
            P2[Push Pod 2]
            PN[Push Pod N]
        end
    end

    subgraph Kafka["Kafka Cluster (RF=3, min ISR=2)"]
        KA[Broker 1]
        KB[Broker 2]
        KC[Broker 3]
    end

    subgraph RedisCluster["Redis Cluster (6 nodes, 3 shards)"]
        RA[Shard 1 Primary + Replica]
        RB[Shard 2 Primary + Replica]
        RC[Shard 3 Primary + Replica]
    end

    subgraph DBTier["PostgreSQL"]
        Primary[(Primary)]
        Replica1[(Read Replica 1)]
        Replica2[(Read Replica 2)]
    end

    LB --> GW1
    LB --> GW2
    LB --> GWN

    GW1 & GW2 & GWN --> Kafka
    GW1 & GW2 & GWN --> RedisCluster
    GW1 & GW2 & GWN --> Primary

    Kafka --> SMS
    Kafka --> Email
    Kafka --> Push

    SMS & Email & Push --> Primary
    Primary --> Replica1
    Primary --> Replica2
```

### Scaling Targets

| Component | Strategy | Scale Trigger |
|-----------|----------|---------------|
| Gateway | Stateless horizontal scale | CPU > 70% or p99 latency > 50ms |
| SMS Worker | Scale by Kafka partition count | Consumer lag > 10K messages |
| Email Worker | Scale by Kafka partition count | Consumer lag > 50K messages |
| Push Worker | Scale by Kafka partition count | Consumer lag > 100K messages |
| Kafka | Add partitions per topic | Sustained throughput > 80% capacity |
| Redis | Cluster resharding | Memory > 75% per shard |
| PostgreSQL | Add read replicas | Read IOPS > 80% capacity |

### Kafka Topic Partition Configuration

| Topic | Partitions | Key | Rationale |
|-------|-----------|-----|-----------|
| notif.critical | 60 | user_id | Ordering per user; OTP must not arrive out of order |
| notif.transactional | 120 | user_id | High volume, loose ordering acceptable |
| notif.marketing | 240 | round-robin | Pure throughput, no ordering required |
| notif.dlq | 12 | notification_id | Low volume, needs inspection |

---

## Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **Notification Gateway** | Auth, quota check, dedup, DND resolution, priority routing, enqueue, return 202 |
| **SMS Worker** | Consume from all topics (P1 first), call Twilio/SNS, retry with backoff, update status |
| **Email Worker** | Consume from all topics, call SES/SendGrid, retry with backoff, update status |
| **Push Worker** | Consume from all topics, call FCM/APNs, retry with backoff, update status |
| **Redis Cluster** | Quota counters (INCR+TTL), dedup keys (SET NX+TTL), rate limiting |
| **PostgreSQL** | Notification records, service config, quota config, user preferences, audit log |
| **Kafka** | Priority-ordered durable message passing, replay, DLQ |
