# Seller-Side Payment System

A robust payment system for paying out sellers on an e-commerce platform with configurable payout schedules, minimized gateway fees, comprehensive audit trails, and resilient failure handling.

## Problem Statement

Design a seller-side payment system for a large e-commerce company with three existing microservices:

- **SellerService**: Manages seller information and payment preferences (check/wire)
- **ProductService**: Manages product catalog with seller pricing
- **OrderService**: Manages orders and buyer transactions

The buyer-side payment system already exists. This system focuses exclusively on paying out sellers.

## Key Requirements

| Requirement                                | Solution                                           |
| ------------------------------------------ | -------------------------------------------------- |
| Payment gateway takes ~1 minute to process | Async processing with status tracking              |
| Fixed fee per transfer                     | Aggregate payments per seller per cycle            |
| Audit log of all payments                  | Immutable audit log with full state history        |
| Seller-preferred payment method            | Support CHECK and WIRE based on seller preference  |
| Status visibility for sellers              | REST API for real-time status and issue resolution |
| Minimize gateway fees                      | Batch payments per seller per payout cycle         |
| No dropped payments                        | Persistent queue + retry mechanism                 |
| No duplicate payments                      | Idempotency keys + state machine                   |

## Architecture Overview

```mermaid
flowchart TB
    subgraph Existing [Existing Microservices]
        SellerSvc[SellerService]
        ProductSvc[ProductService]
        OrderSvc[OrderService]
    end

    subgraph PaymentSystem [Seller Payment System]
        Consumer[Order Consumer]
        BalanceSvc[Balance Service]
        Scheduler[Payout Scheduler]
        Processor[Payment Processor]
        StatusAPI[Status API]
        AuditSvc[Audit Service]

        Consumer --> BalanceSvc
        BalanceSvc --> Scheduler
        Scheduler --> Processor
        Processor --> AuditSvc
        BalanceSvc --> StatusAPI
    end

    subgraph Storage [Data Layer]
        DB[(Payment DB)]
        Queue[Message Queue]
        Cache[(Redis)]
    end

    subgraph External [External]
        Gateway[Payment Gateway]
    end

    OrderSvc -->|Order Events| Queue
    Queue --> Consumer
    SellerSvc -.->|Payment Details| Processor
    Processor --> Gateway
    BalanceSvc --> DB
    StatusAPI --> Cache
```

### System Flow

```mermaid
sequenceDiagram
    participant Order as OrderService
    participant Queue as Message Queue
    participant Balance as Balance Service
    participant Scheduler as Payout Scheduler
    participant Processor as Payment Processor
    participant Gateway as Payment Gateway
    participant Seller as Seller

    Order->>Queue: Order Completed Event
    Queue->>Balance: Process Event
    Balance->>Balance: Update Pending Balance

    Note over Balance: Settlement Window (7 days)

    Balance->>Balance: Move to Available Balance
    Scheduler->>Balance: Check Eligibility
    Balance-->>Scheduler: Eligible for Payout
    Scheduler->>Processor: Create Payout
    Processor->>Gateway: Send Payment
    Gateway-->>Processor: Transaction ID
    Processor->>Seller: Payment Notification
```

## Payout Schedule Options

Sellers can configure their preferred payout schedule:

| Schedule      | Description                           | Use Case                              |
| ------------- | ------------------------------------- | ------------------------------------- |
| **DAILY**     | Payout every day at EOD               | High-volume sellers needing cash flow |
| **WEEKLY**    | Payout on preferred day of week       | Standard sellers                      |
| **THRESHOLD** | Payout when balance exceeds threshold | Low-volume sellers                    |
| **ON_DEMAND** | Seller-initiated payout               | Sellers wanting full control          |

```mermaid
flowchart LR
    subgraph Schedules [Payout Schedule Types]
        Daily[DAILY<br/>Every day at 10 PM]
        Weekly[WEEKLY<br/>Preferred day at 10 PM]
        Threshold[THRESHOLD<br/>When balance >= amount]
        OnDemand[ON_DEMAND<br/>Seller-initiated]
    end

    Daily --> Payout[Payout Processing]
    Weekly --> Payout
    Threshold --> Payout
    OnDemand --> Payout
```

## Documentation Structure

```
seller-side-payment-system/
├── README.md                           # This file
├── design/
│   ├── system-architecture.md          # Component details and interactions
│   ├── data-models.md                  # Database schema design
│   ├── api-contracts.md                # REST API specifications
│   ├── payment-flow.md                 # Payment processing workflows
│   └── failure-handling.md             # Failure scenarios and recovery
├── diagrams/
│   └── architecture-diagrams.md        # Visual system diagrams
└── operations/
    └── runbook.md                      # Operational procedures
```

## Quick Links

- [System Architecture](design/system-architecture.md) - Component breakdown and responsibilities
- [Data Models](design/data-models.md) - Database schema and relationships
- [API Contracts](design/api-contracts.md) - REST API specifications
- [Payment Flow](design/payment-flow.md) - End-to-end payment processing
- [Failure Handling](design/failure-handling.md) - Error recovery strategies
- [Architecture Diagrams](diagrams/architecture-diagrams.md) - Visual representations
- [Operations Runbook](operations/runbook.md) - Operational procedures

## Key Design Principles

### 1. Fee Optimization

Aggregate all order earnings for a seller into a single payout per cycle, reducing gateway fees from O(orders) to O(sellers × cycles).

### 2. Exactly-Once Semantics

- Idempotency keys prevent duplicate payments
- State machine ensures each payment progresses correctly
- Reconciliation catches edge cases

### 3. Resilience

- Circuit breaker for gateway failures
- Exponential backoff retry
- Dead letter queue for manual intervention
- Automatic rollover of failed payments

### 4. Auditability

- Immutable audit log of all state changes
- Full traceability from order to payout
- Compliance-ready reporting

### Payout State Machine

```mermaid
stateDiagram-v2
    [*] --> PENDING: Create Payout
    PENDING --> PROCESSING: Start Processing
    PROCESSING --> COMPLETED: Gateway Success
    PROCESSING --> FAILED: Gateway Error
    FAILED --> PENDING: Retry
    FAILED --> CANCELLED: Max Retries
    COMPLETED --> [*]
    CANCELLED --> [*]
```

### Failure Handling Flow

```mermaid
flowchart TD
    Call[Gateway Call] --> Result{Result?}
    Result -->|Success| Complete[Mark Completed]
    Result -->|Failure| Retry{Retry < Max?}
    Retry -->|Yes| Backoff[Exponential Backoff]
    Backoff --> Call
    Retry -->|No| DLQ[Dead Letter Queue]
    DLQ --> Alert[Alert Operations]
```

## Third Party Gateway Interface

```java
interface ThirdPartyPaymentGateway {
    function sendCheck(checkDetails, amount) returns transactionId or error;
    function sendWire(wireDetails, amount) returns transactionId or error;
}
```

## Technology Considerations

| Component     | Recommended Technology | Rationale                        |
| ------------- | ---------------------- | -------------------------------- |
| Message Queue | Kafka / RabbitMQ       | Durability, ordering, replay     |
| Payment DB    | PostgreSQL             | ACID, JSON support, reliability  |
| Audit Log     | Append-only table / S3 | Immutability, compliance         |
| Scheduler     | Temporal / Airflow     | Reliability, visibility, retries |
| Cache         | Redis                  | Balance lookups, status queries  |

## Contact

For questions about this design, refer to the detailed documentation in the `/design` folder.
