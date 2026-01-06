# Architecture Diagrams

This document contains visual representations of the Seller-Side Payment System architecture using Mermaid diagrams.

## System Overview

### High-Level Architecture

```mermaid
flowchart TB
    subgraph ExistingServices [Existing Services]
        OrderSvc[OrderService]
        SellerSvc[SellerService]
        ProductSvc[ProductService]
    end

    subgraph PaymentSystem [Seller Payment System]
        EventConsumer[Order Event Consumer]
        BalanceService[Seller Balance Service]
        PayoutScheduler[Payout Scheduler]
        PaymentProcessor[Payment Processor]
        StatusAPI[Payment Status API]
        AuditService[Audit Log Service]
    end

    subgraph DataStores [Data Stores]
        PaymentDB[(Payment DB)]
        AuditLog[(Audit Log)]
        Cache[(Redis Cache)]
        EventQueue[Message Queue]
    end

    subgraph External [External Systems]
        PaymentGateway[Third Party Payment Gateway]
    end

    OrderSvc -->|Order Events| EventQueue
    EventQueue --> EventConsumer
    EventConsumer --> BalanceService
    BalanceService --> PaymentDB

    PayoutScheduler --> PaymentDB
    PayoutScheduler --> PaymentProcessor

    PaymentProcessor --> PaymentGateway
    PaymentProcessor --> AuditService
    PaymentProcessor --> PaymentDB

    AuditService --> AuditLog

    StatusAPI --> PaymentDB
    StatusAPI --> Cache

    SellerSvc -.->|Payment Details| PaymentProcessor
```

### Component Interaction

```mermaid
flowchart LR
    subgraph Ingestion [Event Ingestion]
        OrderEvents[Order Events]
        Consumer[Event Consumer]
    end

    subgraph Processing [Balance Processing]
        BalanceCalc[Balance Calculator]
        BalanceStore[Balance Store]
    end

    subgraph Scheduling [Payout Scheduling]
        Scheduler[Scheduler]
        EligibilityCheck[Eligibility Check]
    end

    subgraph Execution [Payment Execution]
        Processor[Payment Processor]
        GatewayClient[Gateway Client]
    end

    subgraph Monitoring [Status and Audit]
        StatusAPI[Status API]
        AuditWriter[Audit Writer]
    end

    OrderEvents --> Consumer
    Consumer --> BalanceCalc
    BalanceCalc --> BalanceStore

    BalanceStore --> EligibilityCheck
    Scheduler --> EligibilityCheck
    EligibilityCheck --> Processor

    Processor --> GatewayClient
    Processor --> AuditWriter

    BalanceStore --> StatusAPI
```

---

## Data Flow Diagrams

### Order to Balance Flow

```mermaid
sequenceDiagram
    participant OS as OrderService
    participant MQ as Message Queue
    participant EC as Event Consumer
    participant BS as Balance Service
    participant DB as Payment DB
    participant AL as Audit Log

    OS->>MQ: Publish ORDER_COMPLETED
    MQ->>EC: Deliver event

    EC->>DB: Check duplicate (order_id)
    DB-->>EC: Not found

    EC->>BS: Credit balance request

    BS->>DB: BEGIN TRANSACTION
    BS->>DB: UPDATE seller_balance (pending +amount)
    BS->>DB: INSERT order_payout_mapping
    BS->>DB: COMMIT

    BS->>AL: Log BALANCE_CREDITED
    BS-->>EC: Success

    EC->>MQ: ACK message
```

### Payout Scheduling Flow

```mermaid
sequenceDiagram
    participant Cron as Cron Trigger
    participant Sched as Payout Scheduler
    participant DB as Payment DB
    participant Queue as Payout Queue
    participant AL as Audit Log

    Cron->>Sched: Trigger (22:00 daily)

    Sched->>DB: Acquire leader lock
    DB-->>Sched: Lock acquired

    Sched->>DB: Query eligible sellers (DAILY)
    DB-->>Sched: Seller list

    Sched->>DB: Query eligible sellers (WEEKLY - today)
    DB-->>Sched: Seller list

    Sched->>DB: Query eligible sellers (THRESHOLD)
    DB-->>Sched: Seller list

    loop For each eligible seller
        Sched->>DB: Check existing payout
        DB-->>Sched: None found

        Sched->>DB: INSERT payout_record (PENDING)
        Sched->>AL: Log PAYOUT_CREATED
        Sched->>Queue: Enqueue payout
    end

    Sched->>DB: Release leader lock
```

### Payment Processing Flow

```mermaid
sequenceDiagram
    participant Queue as Payout Queue
    participant PP as Payment Processor
    participant DB as Payment DB
    participant SS as SellerService
    participant GW as Payment Gateway
    participant AL as Audit Log

    Queue->>PP: Dequeue payout

    PP->>DB: UPDATE status = PROCESSING
    PP->>AL: Log PAYOUT_SUBMITTED

    PP->>SS: GET /sellers/{id}/payment-details
    SS-->>PP: Payment details

    alt Wire Transfer
        PP->>GW: sendWire(wireDetails, amount)
    else Check
        PP->>GW: sendCheck(checkDetails, amount)
    end

    Note over GW: ~1 minute processing

    alt Success
        GW-->>PP: transactionId
        PP->>DB: BEGIN TRANSACTION
        PP->>DB: UPDATE status = COMPLETED
        PP->>DB: UPDATE seller_balance (available - amount)
        PP->>DB: UPDATE order_payout_mapping (status = PAID)
        PP->>DB: COMMIT
        PP->>AL: Log PAYOUT_COMPLETED
    else Failure
        GW-->>PP: error
        PP->>DB: UPDATE status = FAILED, error_code
        PP->>AL: Log PAYOUT_FAILED
    end
```

---

## State Diagrams

### Payout Status State Machine

```mermaid
stateDiagram-v2
    [*] --> PENDING: Payout created

    PENDING --> PROCESSING: Processing started

    PROCESSING --> COMPLETED: Gateway success
    PROCESSING --> FAILED: Gateway error
    PROCESSING --> PROCESSING: Timeout (reconcile)

    FAILED --> PENDING: Retry scheduled
    FAILED --> CANCELLED: Manual cancel
    FAILED --> CANCELLED: Max retries exceeded

    COMPLETED --> [*]
    CANCELLED --> [*]

    note right of PROCESSING: Max 2 minutes
    note right of FAILED: Up to 5 retries
```

### Order Payout Mapping State Machine

```mermaid
stateDiagram-v2
    [*] --> PENDING: Order completed

    PENDING --> SETTLED: Settlement window passed
    PENDING --> CANCELLED: Order cancelled

    SETTLED --> PAID: Payout completed
    SETTLED --> CANCELLED: Order cancelled (late)

    PAID --> [*]
    CANCELLED --> [*]

    note right of PENDING: 7 day window
    note right of SETTLED: Available for payout
```

### Circuit Breaker State Machine

```mermaid
stateDiagram-v2
    [*] --> CLOSED: Initial state

    CLOSED --> CLOSED: Success
    CLOSED --> OPEN: Failure threshold reached

    OPEN --> HALF_OPEN: Recovery timeout elapsed

    HALF_OPEN --> CLOSED: Test request succeeds
    HALF_OPEN --> OPEN: Test request fails

    note right of CLOSED: Normal operation
    note right of OPEN: Requests blocked
    note right of HALF_OPEN: Testing recovery
```

---

## Infrastructure Diagrams

### Deployment Architecture

```mermaid
flowchart TB
    subgraph LoadBalancer [Load Balancer]
        ALB[Application LB]
    end

    subgraph APILayer [API Layer]
        API1[Status API Pod 1]
        API2[Status API Pod 2]
        API3[Status API Pod 3]
    end

    subgraph Workers [Background Workers]
        Sched[Scheduler Pod]
        SchedStandby[Scheduler Standby]
        Proc1[Processor Pod 1]
        Proc2[Processor Pod 2]
        Consumer1[Consumer Pod 1]
        Consumer2[Consumer Pod 2]
    end

    subgraph DataLayer [Data Layer]
        PGPrimary[(PostgreSQL Primary)]
        PGReplica[(PostgreSQL Replica)]
        Redis[(Redis Cluster)]
        Kafka[Kafka Cluster]
    end

    subgraph External [External]
        Gateway[Payment Gateway]
    end

    ALB --> API1
    ALB --> API2
    ALB --> API3

    API1 --> PGReplica
    API2 --> PGReplica
    API3 --> PGReplica
    API1 --> Redis
    API2 --> Redis
    API3 --> Redis

    Sched --> PGPrimary
    Sched --> Redis
    SchedStandby --> Redis

    Proc1 --> PGPrimary
    Proc2 --> PGPrimary
    Proc1 --> Gateway
    Proc2 --> Gateway

    Consumer1 --> Kafka
    Consumer2 --> Kafka
    Consumer1 --> PGPrimary
    Consumer2 --> PGPrimary

    PGPrimary --> PGReplica
```

### Database Replication

```mermaid
flowchart LR
    subgraph Primary [Primary Region]
        PG1[(PostgreSQL Primary)]
        App1[Application]
    end

    subgraph DR [DR Region]
        PG2[(PostgreSQL Standby)]
        App2[Application Standby]
    end

    subgraph Backup [Backup Storage]
        S3[S3 Bucket]
        Glacier[Glacier Archive]
    end

    App1 -->|Writes| PG1
    PG1 -->|Sync Replication| PG2
    PG1 -->|WAL Shipping| S3
    S3 -->|Archive| Glacier

    App2 -.->|Failover| PG2
```

---

## Process Flow Diagrams

### Order Cancellation Flow

```mermaid
flowchart TD
    Start([Order Cancellation Event]) --> GetMapping[Get Order Mapping]

    GetMapping --> CheckStatus{Check Status}

    CheckStatus -->|PENDING| DeductPending[Deduct from pending_balance]
    CheckStatus -->|SETTLED| DeductAvailable[Deduct from available_balance]
    CheckStatus -->|PAID| CreateClawback[Create clawback record]
    CheckStatus -->|CANCELLED| AlreadyCancelled[Already cancelled - skip]

    DeductPending --> UpdateMapping[Update mapping status = CANCELLED]
    DeductAvailable --> UpdateMapping
    CreateClawback --> UpdateMapping

    UpdateMapping --> LogAudit[Log to audit]
    AlreadyCancelled --> End
    LogAudit --> End([End])
```

### Reconciliation Flow

```mermaid
flowchart TD
    Start([Reconciliation Job Start]) --> QueryStuck[Query PROCESSING > 10 min]

    QueryStuck --> HasStuck{Found stuck payouts?}

    HasStuck -->|No| End([End])
    HasStuck -->|Yes| Loop[For each stuck payout]

    Loop --> QueryGateway[Query gateway status]

    QueryGateway --> GatewayResult{Gateway response}

    GatewayResult -->|COMPLETED| MarkComplete[Mark COMPLETED, deduct balance]
    GatewayResult -->|FAILED| MarkFailed[Mark FAILED]
    GatewayResult -->|NOT_FOUND| ResetPending[Reset to PENDING for retry]
    GatewayResult -->|ERROR| ManualReview[Move to manual review]

    MarkComplete --> AlertOps[Alert ops team]
    MarkFailed --> NextPayout
    ResetPending --> NextPayout
    ManualReview --> AlertOps

    AlertOps --> NextPayout{More payouts?}
    NextPayout -->|Yes| Loop
    NextPayout -->|No| End
```

### Retry Flow

```mermaid
flowchart TD
    Start([Payment Failed]) --> CheckRetries{Retry count < max?}

    CheckRetries -->|No| MoveToDLQ[Move to Dead Letter Queue]
    CheckRetries -->|Yes| CheckError{Error type?}

    CheckError -->|Transient| CalculateBackoff[Calculate exponential backoff]
    CheckError -->|Recoverable| NotifySeller[Notify seller - action required]
    CheckError -->|Fatal| MoveToDLQ

    CalculateBackoff --> ScheduleRetry[Schedule retry]
    ScheduleRetry --> IncrementCounter[Increment retry count]
    IncrementCounter --> End([Wait for retry])

    NotifySeller --> MarkFailed[Mark as FAILED]
    MarkFailed --> End2([End - awaiting seller action])

    MoveToDLQ --> AlertOps[Alert operations]
    AlertOps --> End3([End - manual intervention])
```

---

## Entity Relationship Diagram

```mermaid
erDiagram
    SELLER_PAYOUT_PREFERENCE ||--|| SELLER_BALANCE : "has"
    SELLER_BALANCE ||--o{ PAYOUT_RECORD : "generates"
    PAYOUT_RECORD ||--o{ ORDER_PAYOUT_MAPPING : "includes"
    PAYOUT_RECORD ||--o{ AUDIT_LOG : "creates"

    SELLER_PAYOUT_PREFERENCE {
        string seller_id PK
        enum payout_schedule
        decimal threshold_amount
        int preferred_day
        enum payment_method
        timestamp created_at
        timestamp updated_at
    }

    SELLER_BALANCE {
        string seller_id PK
        decimal available_balance
        decimal pending_balance
        decimal held_balance
        bigint version
        timestamp last_updated
    }

    PAYOUT_RECORD {
        string payout_id PK
        string seller_id FK
        decimal amount
        enum payment_method
        enum status
        string gateway_txn_id
        string error_code
        string error_message
        int retry_count
        timestamp period_start
        timestamp period_end
        timestamp created_at
        timestamp processed_at
        timestamp completed_at
    }

    ORDER_PAYOUT_MAPPING {
        bigint id PK
        string order_id
        string payout_id FK
        string seller_id FK
        decimal seller_amount
        enum status
        timestamp order_timestamp
        timestamp settlement_date
        timestamp created_at
    }

    AUDIT_LOG {
        string audit_id PK
        string payout_id FK
        string seller_id
        enum event_type
        json previous_state
        json new_state
        string actor
        timestamp timestamp
        json metadata
    }
```

---

## Monitoring Dashboard Layout

```mermaid
flowchart TB
    subgraph Dashboard [Operations Dashboard]
        subgraph Row1 [Key Metrics]
            PayoutRate[Payout Success Rate]
            FailureRate[Failure Rate]
            Latency[Gateway Latency p99]
            QueueDepth[Queue Depth]
        end

        subgraph Row2 [Trends]
            DailyVolume[Daily Payout Volume]
            MethodBreakdown[Payment Method Distribution]
        end

        subgraph Row3 [Alerts]
            ActiveAlerts[Active Alerts]
            RecentIncidents[Recent Incidents]
        end

        subgraph Row4 [Operations]
            StuckPayouts[Stuck Payouts]
            DLQSize[DLQ Size]
            ManualQueue[Manual Review Queue]
        end
    end
```

---

## Scaling Architecture

### Horizontal Scaling

```mermaid
flowchart TB
    subgraph Scaling [Auto-Scaling Groups]
        subgraph APIScale [API Tier - Scale by CPU]
            API1[API Pod]
            API2[API Pod]
            APIMore[...]
        end

        subgraph ConsumerScale [Consumers - Scale by Lag]
            C1[Consumer]
            C2[Consumer]
            CMore[...]
        end

        subgraph ProcessorScale [Processors - Scale by Queue]
            P1[Processor]
            P2[Processor]
            PMore[...]
        end
    end

    subgraph Triggers [Scaling Triggers]
        CPUMetric[CPU > 70%]
        LagMetric[Consumer Lag > 1000]
        QueueMetric[Queue Depth > 500]
    end

    CPUMetric --> APIScale
    LagMetric --> ConsumerScale
    QueueMetric --> ProcessorScale
```

