# SAGA Pattern — Deep Dive

The SAGA pattern is the go-to approach for managing **distributed transactions in microservices** without the drawbacks of [Two-Phase Commit (2PC)](./two-phase-commit.md). Instead of locking resources across services, a SAGA breaks a transaction into a sequence of **local transactions**, each with a corresponding **compensating transaction** to undo its effect if something goes wrong downstream.

---

## The Problem SAGA Solves

In a microservices architecture, each service owns its database. There is **no shared transaction manager**. You cannot use `BEGIN ... COMMIT` across service boundaries.

```mermaid
flowchart TB
    subgraph problem [The Problem]
        direction TB
        A[Order Service<br/>Orders DB] -.-|No shared TX| B[Inventory Service<br/>Inventory DB]
        B -.-|No shared TX| C[Payment Service<br/>Payments DB]
        C -.-|No shared TX| D[Shipping Service<br/>Shipping DB]
    end

    subgraph question [How do you ensure...]
        Q1[All succeed together?]
        Q2[All rollback on failure?]
        Q3[No inconsistent intermediate state lingers?]
    end

    problem --> question
```

**2PC could solve this**, but it requires:
- All services to support XA
- Long-held distributed locks
- A centralized coordinator (SPOF)
- Low-latency networking (same datacenter)

**SAGA provides an alternative:** no distributed locks, no blocking, eventual consistency.

---

## What is a SAGA?

A SAGA is a sequence of **local transactions** where:

1. Each local transaction updates a single service's database and publishes an event/message
2. Each local transaction has a **compensating transaction** that semantically undoes its effect
3. If any step fails, previously completed steps are compensated **in reverse order**

```mermaid
flowchart LR
    T1[T1: Create Order] --> T2[T2: Reserve Inventory]
    T2 --> T3[T3: Process Payment]
    T3 --> T4[T4: Ship Order]

    T4 -.->|On failure| C3[C3: Refund Payment]
    C3 -.-> C2[C2: Release Inventory]
    C2 -.-> C1[C1: Cancel Order]

    style T1 fill:#4CAF50,color:#fff
    style T2 fill:#4CAF50,color:#fff
    style T3 fill:#4CAF50,color:#fff
    style T4 fill:#4CAF50,color:#fff
    style C1 fill:#f44336,color:#fff
    style C2 fill:#f44336,color:#fff
    style C3 fill:#f44336,color:#fff
```

### The Three Types of SAGA Steps

| Step Type | Description | Example | Can it be compensated? |
|-----------|-------------|---------|----------------------|
| **Compensatable** | Has a compensating transaction that can undo it | Reserve inventory → Release inventory | ✅ Yes |
| **Pivot** | The go/no-go decision point. If it succeeds, the SAGA will commit | Process payment | ⚠️ It's the decision boundary |
| **Retriable** | Guaranteed to eventually succeed (idempotent, retried on failure) | Send shipping notification | ❌ Not needed (always succeeds) |

```mermaid
flowchart LR
    subgraph compensatable [Compensatable Steps]
        T1[Create Order]
        T2[Reserve Inventory]
    end

    subgraph pivot [Pivot Step]
        T3[Process Payment]
    end

    subgraph retriable [Retriable Steps]
        T4[Update Order Status]
        T5[Send Notification]
    end

    T1 --> T2 --> T3 --> T4 --> T5

    style compensatable fill:#fff3e0
    style pivot fill:#e3f2fd
    style retriable fill:#e8f5e9
```

**Design rule:** Structure your SAGA so that compensatable steps come first, then the pivot, then retriable steps. This minimizes the number of compensations needed on failure.

---

## Two Coordination Approaches

### 1. Choreography (Event-Driven)

Each service listens for events and decides locally what to do next. There is **no central coordinator** — the workflow emerges from event reactions.

```mermaid
sequenceDiagram
    participant OS as Order Service
    participant IS as Inventory Service
    participant PS as Payment Service
    participant SS as Shipping Service

    Note over OS: T1: Create Order
    OS->>IS: Event: OrderCreated

    Note over IS: T2: Reserve Inventory
    IS->>PS: Event: InventoryReserved

    Note over PS: T3: Process Payment
    PS->>SS: Event: PaymentProcessed

    Note over SS: T4: Ship Order
    SS->>OS: Event: OrderShipped

    Note over OS: Update order status: COMPLETED
```

**Failure with compensation (choreography):**

```mermaid
sequenceDiagram
    participant OS as Order Service
    participant IS as Inventory Service
    participant PS as Payment Service

    Note over OS: T1: Create Order
    OS->>IS: Event: OrderCreated

    Note over IS: T2: Reserve Inventory
    IS->>PS: Event: InventoryReserved

    Note over PS: T3: Process Payment
    PS->>PS: 💥 Payment Failed!

    PS->>IS: Event: PaymentFailed
    Note over IS: C2: Release Inventory
    IS->>OS: Event: InventoryReleased

    Note over OS: C1: Cancel Order (mark as FAILED)
```

#### Choreography — Pros and Cons

| Pros | Cons |
|------|------|
| Simple for 3-4 step workflows | Hard to understand as steps grow (>5) |
| Loose coupling — services are independent | **Cyclic dependencies** — services must know about each other's events |
| No single point of failure | **Difficult to track** — no single place shows SAGA status |
| Easy to add new steps | **Testing is hard** — must simulate entire event chain |
| Good for small teams | **Risk of event storms** — cascading reactions |

---

### 2. Orchestration (Command-Driven)

A central **SAGA Orchestrator** tells each service what to do and when. The orchestrator maintains the state machine and drives the workflow.

```mermaid
sequenceDiagram
    participant Client
    participant Orch as SAGA Orchestrator
    participant OS as Order Service
    participant IS as Inventory Service
    participant PS as Payment Service
    participant SS as Shipping Service

    Client->>Orch: Place Order

    Orch->>OS: Command: Create Order
    OS-->>Orch: Reply: Order Created

    Orch->>IS: Command: Reserve Inventory
    IS-->>Orch: Reply: Inventory Reserved

    Orch->>PS: Command: Process Payment
    PS-->>Orch: Reply: Payment Processed

    Orch->>SS: Command: Ship Order
    SS-->>Orch: Reply: Order Shipped

    Orch->>OS: Command: Mark Order Complete
    Orch-->>Client: Order Confirmed
```

**Failure with compensation (orchestration):**

```mermaid
sequenceDiagram
    participant Orch as SAGA Orchestrator
    participant OS as Order Service
    participant IS as Inventory Service
    participant PS as Payment Service

    Orch->>OS: Command: Create Order
    OS-->>Orch: ✅ Order Created

    Orch->>IS: Command: Reserve Inventory
    IS-->>Orch: ✅ Inventory Reserved

    Orch->>PS: Command: Process Payment
    PS-->>Orch: ❌ Payment Failed

    Note over Orch: Payment failed → start compensation

    Orch->>IS: Command: Release Inventory (C2)
    IS-->>Orch: ✅ Inventory Released

    Orch->>OS: Command: Cancel Order (C1)
    OS-->>Orch: ✅ Order Cancelled

    Note over Orch: SAGA completed with FAILURE
```

#### Orchestrator State Machine

```mermaid
stateDiagram-v2
    [*] --> OrderPending: Start SAGA

    OrderPending --> InventoryReserving: Order created
    OrderPending --> OrderCancelling: Order creation failed

    InventoryReserving --> PaymentProcessing: Inventory reserved
    InventoryReserving --> OrderCancelling: Inventory insufficient

    PaymentProcessing --> ShippingInitiated: Payment success
    PaymentProcessing --> InventoryReleasing: Payment failed

    ShippingInitiated --> Completed: Shipped
    ShippingInitiated --> PaymentRefunding: Shipping failed

    PaymentRefunding --> InventoryReleasing: Refund complete
    InventoryReleasing --> OrderCancelling: Inventory released
    OrderCancelling --> Failed: Order cancelled

    Completed --> [*]
    Failed --> [*]
```

#### Orchestration — Pros and Cons

| Pros | Cons |
|------|------|
| **Easy to understand** — workflow in one place | Orchestrator can become a **single point of failure** |
| **Easy to test** — test the orchestrator's state machine | Risk of **centralizing too much logic** in orchestrator |
| No cyclic dependencies | Orchestrator must be highly available |
| Easy to add/modify steps | Additional infrastructure component to maintain |
| Good observability — track SAGA state | Slight coupling to orchestrator |
| Complex workflows manageable | Design discipline needed to keep orchestrator thin |

---

## Choreography vs. Orchestration — Decision Guide

```mermaid
flowchart TB
    Q1{How many services<br/>in the SAGA?}
    Q1 -->|2-4 services| Q2{Are the interactions<br/>straightforward?}
    Q1 -->|5+ services| ORCH[Use Orchestration]

    Q2 -->|Yes, linear flow| CHOREO[Use Choreography]
    Q2 -->|No, branching/conditions| ORCH

    Q3{Do you need<br/>SAGA status tracking?}
    Q3 -->|Yes| ORCH
    Q3 -->|No| Q1

    style CHOREO fill:#4CAF50,color:#fff
    style ORCH fill:#2196F3,color:#fff
```

| Factor | Choreography | Orchestration |
|--------|-------------|---------------|
| **# of steps** | 2-4 | 5+ |
| **Workflow complexity** | Linear | Branching, conditions, parallel |
| **Team structure** | Independent teams per service | Central platform team |
| **Observability needs** | Low | High |
| **Coupling tolerance** | Event coupling acceptable | Prefer command coupling |
| **Failure handling** | Simple rollback | Complex compensation logic |

---

## Compensating Transactions — Design Principles

Compensating transactions are the heart of the SAGA pattern. They require careful design.

### Semantic Undo, Not Physical Undo

A compensating transaction does **not** rollback the database to a previous state. It applies a **new transaction** that semantically reverses the effect.

```mermaid
flowchart TB
    subgraph not_this [❌ NOT physical undo]
        A1[INSERT order] -.->|Compensate| A2[DELETE order]
    end

    subgraph do_this [✅ Semantic undo]
        B1[INSERT order<br/>status=CREATED] -.->|Compensate| B2[UPDATE order<br/>status=CANCELLED]
    end

    style not_this fill:#ffebee
    style do_this fill:#e8f5e9
```

### Compensation Design Rules

| Rule | Rationale | Example |
|------|-----------|---------|
| **Compensations must be idempotent** | May be retried on failure | Refund should check if already refunded |
| **Compensations must be commutative** | Order of execution may vary | Release inventory should work regardless of current state |
| **Never delete data** | Need audit trail and debugging | Mark as CANCELLED, don't DELETE |
| **Include the SAGA ID** | For correlation and deduplication | Every event/command carries saga_id |
| **Handle the "already compensated" case** | Duplicate events are possible | Return success if already compensated |

### Example: E-Commerce Compensation Table

| Step | Forward Transaction | Compensating Transaction |
|------|-------------------|--------------------------|
| 1. Order | `INSERT order (status=PENDING)` | `UPDATE order SET status=CANCELLED` |
| 2. Inventory | `UPDATE stock SET qty = qty - N` | `UPDATE stock SET qty = qty + N` |
| 3. Payment | `POST /payments/charge` (auth + capture) | `POST /payments/refund` |
| 4. Shipping | `POST /shipments/create` | `POST /shipments/cancel` (if not yet shipped) |

---

## Handling the Lack of Isolation

Unlike 2PC, SAGA does **not** provide isolation. Intermediate states are visible to other transactions. This creates anomalies:

### Anomaly Types

```mermaid
flowchart TB
    subgraph anomalies [SAGA Isolation Anomalies]
        LU[Lost Updates<br/>Another tx overwrites<br/>SAGA's uncommitted change]
        DR[Dirty Reads<br/>Another tx reads data<br/>that SAGA will compensate]
        FR[Fuzzy Reads<br/>Same data read differently<br/>at different SAGA steps]
    end
```

| Anomaly | Scenario | Impact |
|---------|----------|--------|
| **Lost Update** | SAGA reserves inventory, another transaction also modifies the same row | One update is silently lost |
| **Dirty Read** | Payment service reads an order that is later cancelled by compensation | Payment processed for a cancelled order |
| **Fuzzy/Non-repeatable Read** | Order service reads inventory at step 1 (available) but it changes by step 3 | Decision made on stale data |

### Countermeasures

| Countermeasure | How it Works | Trade-off |
|----------------|-------------|-----------|
| **Semantic Lock** | Set a flag (e.g., `status=PENDING`) to warn other transactions | Other txns must check the flag |
| **Commutative Updates** | Design operations so order doesn't matter (e.g., `qty += N` instead of `qty = N`) | Limits operation types |
| **Pessimistic View** | Reorder SAGA steps to minimize dirty read risk | May not always be possible |
| **Reread Value** | Re-check the value before committing a step | Extra read, possible race |
| **Version File** | Record operations, apply in correct order later | Complex bookkeeping |
| **By Value (Risk-Based)** | Use SAGA for low-risk, 2PC for high-risk transactions | Dual mechanism complexity |

```mermaid
flowchart LR
    subgraph semantic_lock [Semantic Lock Pattern]
        A[Create Order<br/>status = PENDING] --> B[Reserve Inventory<br/>reservation_status = HELD]
        B --> C[Process Payment]
        C --> D[Update Order<br/>status = CONFIRMED]
        D --> E[Release lock:<br/>reservation_status = COMMITTED]
    end

    Note[Other transactions see<br/>PENDING/HELD status and<br/>know not to interfere]
```

---

## Practical Architecture: Order Service SAGA (Orchestration)

A complete real-world orchestration example:

```mermaid
flowchart TB
    Client[Client] --> API[API Gateway]
    API --> Orch[Order SAGA<br/>Orchestrator]

    Orch --> MQ[(Message Broker<br/>Kafka / RabbitMQ)]

    MQ --> OS[Order Service]
    MQ --> IS[Inventory Service]
    MQ --> PS[Payment Service]
    MQ --> NS[Notification Service]
    MQ --> SS[Shipping Service]

    OS --> OSDB[(Orders DB)]
    IS --> ISDB[(Inventory DB)]
    PS --> PSDB[(Payments DB)]
    SS --> SSDB[(Shipping DB)]

    Orch --> SLOG[(SAGA Log<br/>State Store)]

    style Orch fill:#2196F3,color:#fff
    style SLOG fill:#FF9800,color:#fff
```

### SAGA Log — Why it Matters

The orchestrator persists its state at every step. If it crashes and restarts, it resumes from the last logged state.

| SAGA Log Entry | Fields |
|---------------|--------|
| `saga_id` | Unique identifier for the SAGA instance |
| `current_step` | Which step is currently executing |
| `status` | `RUNNING`, `COMPENSATING`, `COMPLETED`, `FAILED` |
| `step_results[]` | Success/failure of each completed step |
| `created_at` | When the SAGA started |
| `updated_at` | Last state change timestamp |

---

## SAGA with Event Sourcing and CQRS

SAGA works particularly well alongside Event Sourcing and CQRS:

```mermaid
flowchart TB
    subgraph write_side [Write Side]
        Orch[Orchestrator] --> CMD[Command Handler]
        CMD --> ES[(Event Store)]
        ES --> PUB[Event Publisher]
    end

    subgraph read_side [Read Side]
        PUB --> PROJ[Projections]
        PROJ --> VIEWS[(Read Models / Views)]
    end

    PUB --> SAGA[SAGA Step Handler]
    SAGA --> CMD

    style ES fill:#FF9800,color:#fff
```

**Benefits of combining:**
- Event store provides a natural SAGA log
- Events are the source of truth — no dual-write problem
- Easy replay and debugging
- Natural fit for choreography-style SAGAs

---

## Real-World SAGA Implementations

| Company/System | Pattern | Details |
|---------------|---------|---------|
| **Netflix** | Orchestration | Custom Conductor orchestration engine for microservice workflows |
| **Uber** | Orchestration | Cadence/Temporal workflow engine — SAGAs as workflows with compensation |
| **Airbnb** | Choreography + Orchestration | Mix of event-driven and orchestrated flows for booking pipeline |
| **Amazon** | Choreography | Order pipeline uses event-driven SAGAs across 100+ services |
| **Axon Framework** | Orchestration | Java framework with built-in SAGA support and event sourcing |
| **Temporal.io** | Orchestration | Durable execution platform — models SAGAs as workflows with automatic retry |
| **MassTransit** | Both | .NET library with built-in SAGA state machines |

---

## Pros and Cons

### Pros

| Advantage | Detail |
|-----------|--------|
| **No distributed locks** | Each step uses only local transactions — no cross-service locking |
| **High availability** | No blocking; failure of one service doesn't freeze others |
| **Works across heterogeneous systems** | REST APIs, gRPC, message queues — anything can participate |
| **Scales horizontally** | Each service scales independently |
| **Resilient to network partitions** | Async communication tolerates transient failures |
| **Long-running transactions** | Can span minutes, hours, or days (e.g., travel booking) |
| **Fits microservices naturally** | Respects service autonomy and database-per-service pattern |

### Cons

| Disadvantage | Detail |
|--------------|--------|
| **No isolation** | Intermediate states are visible (dirty reads, lost updates) |
| **Eventual consistency** | System is temporarily inconsistent during SAGA execution |
| **Complex compensating logic** | Every step needs a carefully designed undo operation |
| **Difficult to debug** | Distributed tracing required to follow the flow |
| **Compensation may fail** | What if the refund API is down? Need retry + dead letter queue |
| **Ordering challenges** | Events may arrive out of order in choreography |
| **Testing complexity** | Must test every failure path and compensation chain |
| **Not suitable for all domains** | Some operations can't be compensated (e.g., sending an email) |

---

## When to Use SAGA

```mermaid
flowchart TB
    Q1{Does your transaction span<br/>multiple services/databases?}
    Q1 -->|No| LOCAL[Use local ACID transaction]
    Q1 -->|Yes| Q2{Can all participants<br/>use XA/2PC?}

    Q2 -->|Yes, and same DC| Q3{Is lock contention<br/>acceptable?}
    Q3 -->|Yes| USE_2PC[Consider 2PC/XA]
    Q3 -->|No| USE_SAGA[✅ Use SAGA]

    Q2 -->|No| USE_SAGA

    Q4{Is the transaction<br/>long-running?}
    Q4 -->|Yes| USE_SAGA
    Q4 -->|No| Q1

    Q5{Do you need high<br/>availability?}
    Q5 -->|Yes| USE_SAGA
    Q5 -->|No| Q2

    style USE_SAGA fill:#4CAF50,color:#fff
    style USE_2PC fill:#2196F3,color:#fff
    style LOCAL fill:#9E9E9E,color:#fff
```

### Use SAGA When

- **Microservices architecture** with database-per-service
- **Cross-service transactions** involving heterogeneous systems (REST, gRPC, third-party APIs)
- **Long-running business processes** (travel booking, insurance claims, order fulfillment)
- **High availability is critical** — cannot afford blocking
- **Horizontal scalability** — services must scale independently
- **Eventual consistency is acceptable** — business can tolerate brief inconsistency
- **Cross-datacenter operations** — 2PC latency would be prohibitive

### Do NOT Use SAGA When

- **Strong isolation is required** — e.g., financial ledger debits/credits that must never show intermediate states
- **Operations cannot be compensated** — e.g., launching a missile, sending an irreversible physical action
- **Simple, few-service transactions** — overhead of SAGA outweighs benefits if you can use local TX or 2PC
- **Team lacks distributed systems experience** — compensating logic is hard to get right
- **Regulatory requirements demand strict ACID** — some compliance frameworks require 2PC-level guarantees

---

## SAGA vs. 2PC — Head-to-Head

| Aspect | SAGA | 2PC |
|--------|------|-----|
| **Consistency** | Eventual | Strong (atomic) |
| **Isolation** | None (anomalies possible) | Full (locks held) |
| **Availability** | High | Low (blocking on coordinator failure) |
| **Latency** | Low per step | High (2 RTT + sync) |
| **Lock duration** | Per-step only (milliseconds) | Entire transaction (can be seconds+) |
| **Scalability** | Horizontal | Limited |
| **Failure recovery** | Compensating transactions | Coordinator-driven rollback |
| **Complexity** | Business logic (compensations) | Protocol/infrastructure |
| **Long-running TX** | ✅ Supported | ❌ Impractical |
| **Heterogeneous systems** | ✅ Any service can participate | ❌ All must support XA |
| **Network partitions** | Tolerant (async messaging) | Blocking |
| **Debugging** | Harder (distributed traces) | Easier (centralized coordinator logs) |

---

## Key Takeaways for System Design Interviews

1. **SAGA is the standard answer for distributed transactions in microservices** — mention it whenever the interviewer asks about cross-service consistency.
2. **Know both choreography and orchestration** — and articulate when to use each.
3. **Compensating transactions are the hard part** — stress that designing correct compensations requires domain expertise.
4. **Lack of isolation is the main trade-off** — explain the anomalies and countermeasures (semantic locks, commutative updates).
5. **Pair SAGA with idempotency** — every handler must be idempotent because retries are inevitable.
6. **Mention real tooling** — Temporal, Conductor, Axon, MassTransit show practical depth.
7. **Distinguish step types** — compensatable → pivot → retriable. This ordering minimizes compensations.
8. **SAGA log is essential** — the orchestrator must persist its state for crash recovery.
9. **Contrast with 2PC** — always compare SAGA to [2PC](./two-phase-commit.md) and explain why SAGA is preferred for microservices.
10. **Not everything can be compensated** — know the limitations and have a plan (e.g., human intervention, circuit breakers).

---

## Related Concepts

- **[Two-Phase Commit (2PC)](./two-phase-commit.md)** — The blocking alternative that provides strong consistency
- **Event Sourcing** — Natural complement to choreography-based SAGAs
- **CQRS** — Separates read/write models, works well with SAGA's eventual consistency
- **Outbox Pattern** — Reliable event publishing to avoid dual-write problem within each SAGA step
- **Idempotency** — Critical for reliable SAGA step execution with retries
- **Dead Letter Queue** — For handling compensation failures that exhaust retries
- **Distributed Tracing** — Essential for debugging SAGAs across services (Jaeger, Zipkin)
