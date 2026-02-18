# Event Sourcing — Deep Dive

In traditional systems, the database stores **current state**. When you update a record, the previous value is overwritten and gone forever. Event Sourcing inverts this: instead of storing what the data **is**, you store every **change that ever happened** to it. Current state is derived by replaying the history.

This distinction has profound consequences for auditability, debugging, scalability, and temporal reasoning — which is why it is the foundation of systems at LinkedIn, Netflix, Walmart, and large financial platforms.

---

## The Core Idea

```mermaid
flowchart TB
    subgraph traditional [Traditional CRUD]
        direction TB
        T1["INSERT user (name='Alice', email='a@x.com')"]
        T2["UPDATE user SET email='alice@y.com'"]
        T3["UPDATE user SET name='Alice Smith'"]
        T4["Current state: {name: 'Alice Smith', email: 'alice@y.com'}"]
        T1 --> T2 --> T3 --> T4
        LOST["Previous states are LOST<br/>Why did the email change?<br/>When? By whom?<br/>❌ No answers"]
    end

    subgraph eventsourced [Event Sourced]
        direction TB
        E1["UserCreated {name: 'Alice', email: 'a@x.com', by: admin, at: T1}"]
        E2["EmailChanged {old: 'a@x.com', new: 'alice@y.com', by: user, at: T2}"]
        E3["NameChanged {old: 'Alice', new: 'Alice Smith', by: user, at: T3}"]
        E4["Current state = replay(E1, E2, E3)<br/>{name: 'Alice Smith', email: 'alice@y.com'}"]
        E1 --> E2 --> E3 --> E4
        KEPT["Full history preserved<br/>Every change, when, why, by whom<br/>✅ Complete audit trail"]
    end

    style traditional fill:#ffebee
    style eventsourced fill:#e8f5e9
```

**Event Sourcing stores facts.** A fact is something that happened — it cannot be changed or deleted. The current state is just a **left fold** over the event history.

```
currentState = events.reduce(applyEvent, initialState)
```

---

## Fundamental Concepts

### The Event

An event is an **immutable record** of something that happened in the past. It is always named in **past tense** because it represents a fact that already occurred.

| Field | Description | Example |
|-------|-------------|---------|
| `event_id` | Globally unique identifier | `evt-a7f3b2c1` |
| `aggregate_id` | Entity this event belongs to | `order-12345` |
| `aggregate_type` | Type of aggregate | `Order` |
| `event_type` | What happened | `OrderPlaced` |
| `data` | Event payload | `{items: [...], total: 149.99}` |
| `metadata` | Context: who, why, correlation | `{user_id: "U1", correlation_id: "req-789"}` |
| `version` | Sequence number for this aggregate | `3` |
| `timestamp` | When it happened | `2025-01-15T10:30:00Z` |

```mermaid
flowchart LR
    subgraph event [Anatomy of an Event]
        HEADER["event_id: evt-001<br/>aggregate_id: order-123<br/>aggregate_type: Order<br/>event_type: OrderPlaced<br/>version: 1<br/>timestamp: 2025-01-15T10:30:00Z"]
        DATA["data: {<br/>  items: [{sku: 'P1', qty: 2}],<br/>  total: 149.99,<br/>  currency: 'USD'<br/>}"]
        META["metadata: {<br/>  user_id: 'U42',<br/>  correlation_id: 'req-789',<br/>  causation_id: 'cmd-456'<br/>}"]
    end

    HEADER --- DATA --- META
```

### The Aggregate

An aggregate is the **consistency boundary** — the entity whose event stream you are managing. All events for one aggregate are stored together and ordered by version.

```mermaid
flowchart TB
    subgraph aggregate [Aggregate: Order-12345]
        E1["v1: OrderPlaced"]
        E2["v2: PaymentReceived"]
        E3["v3: ItemShipped"]
        E4["v4: ItemDelivered"]
        E1 --> E2 --> E3 --> E4
    end

    subgraph state [Current State — derived by replay]
        S["Order {<br/>  id: 12345,<br/>  status: DELIVERED,<br/>  paid: true,<br/>  shipped_at: ...,<br/>  delivered_at: ...<br/>}"]
    end

    E4 --> S
```

### The Event Store

The event store is the **append-only** database that holds all events. It is the single source of truth.

```mermaid
flowchart TB
    subgraph eventstore [Event Store]
        direction TB
        STREAM1["Stream: Order-123<br/>v1: OrderPlaced<br/>v2: PaymentReceived<br/>v3: ItemShipped"]
        STREAM2["Stream: Order-456<br/>v1: OrderPlaced<br/>v2: OrderCancelled"]
        STREAM3["Stream: Cart-789<br/>v1: CartCreated<br/>v2: ItemAdded<br/>v3: ItemAdded<br/>v4: ItemRemoved"]
    end

    WRITE["Append Only<br/>Never UPDATE<br/>Never DELETE"] --> eventstore

    eventstore --> READ1["Read stream for one aggregate<br/>(reconstruct state)"]
    eventstore --> READ2["Read all streams by event type<br/>(build projections)"]
    eventstore --> READ3["Subscribe to new events<br/>(real-time consumers)"]
```

---

## Event Store Schema Design

### Relational (PostgreSQL)

```
events
├── event_id         UUID PRIMARY KEY
├── aggregate_id     VARCHAR NOT NULL
├── aggregate_type   VARCHAR NOT NULL
├── event_type       VARCHAR NOT NULL
├── version          INT NOT NULL              ← per-aggregate sequence number
├── data             JSONB NOT NULL            ← event payload
├── metadata         JSONB                     ← correlation, causation, user
├── created_at       TIMESTAMP NOT NULL
│
├── UNIQUE (aggregate_id, version)             ← optimistic concurrency guard
└── INDEX  (aggregate_type, created_at)        ← for projections / subscriptions
```

The `UNIQUE (aggregate_id, version)` constraint is critical — it prevents two concurrent writes from appending the same version number, providing **optimistic concurrency control**.

### Purpose-Built Event Stores

| Store | Type | Strengths |
|-------|------|-----------|
| **EventStoreDB** | Purpose-built | Native projections, subscriptions, built for event sourcing |
| **PostgreSQL** | Relational | Familiar, ACID, good enough for most scales |
| **DynamoDB** | NoSQL | Infinite scale, partition by aggregate_id, sort by version |
| **Kafka** | Distributed log | High throughput, natural append-only, but limited querying |
| **MongoDB** | Document | Flexible schema, good for nested event data |
| **Cassandra** | Wide-column | Write-optimized, partition by aggregate, cluster by version |

### DynamoDB Event Store Design

```
Table: events
├── PK (Partition Key):  aggregate_id        ← "Order-12345"
├── SK (Sort Key):       version             ← 1, 2, 3, ...
├── event_type:          "OrderPlaced"
├── data:                { ... }
├── metadata:            { ... }
├── created_at:          "2025-01-15T10:30:00Z"
│
└── GSI: event_type + created_at             ← query all events of a type
```

```mermaid
flowchart LR
    subgraph dynamo [DynamoDB Event Store]
        subgraph partition1 ["PK: Order-123"]
            R1["SK:1 OrderPlaced"]
            R2["SK:2 PaymentReceived"]
            R3["SK:3 ItemShipped"]
        end
        subgraph partition2 ["PK: Order-456"]
            R4["SK:1 OrderPlaced"]
            R5["SK:2 OrderCancelled"]
        end
    end

    QUERY1["Get all events for Order-123<br/>→ Query PK='Order-123'<br/>→ Ordered by SK (version)"]
    QUERY2["Get all OrderPlaced events<br/>→ Query GSI event_type='OrderPlaced'<br/>→ For projections"]

    dynamo --> QUERY1
    dynamo --> QUERY2
```

---

## State Reconstruction (Rehydration)

To get the current state of an aggregate, read all its events from the store and replay them through a state-building function.

```mermaid
sequenceDiagram
    participant Client
    participant Service as Order Service
    participant ES as Event Store

    Client->>Service: GET /orders/12345

    Service->>ES: Read all events for Order-12345

    ES-->>Service: [OrderPlaced v1, PaymentReceived v2,<br/>ItemShipped v3, ItemDelivered v4]

    Note over Service: Replay events to build state

    rect rgb(230, 245, 255)
    Note over Service: state = {}
    Note over Service: apply(OrderPlaced) →<br/>{status: PLACED, items: [...], total: 149.99}
    Note over Service: apply(PaymentReceived) →<br/>{status: PAID, paid: true, ...}
    Note over Service: apply(ItemShipped) →<br/>{status: SHIPPED, tracking: 'TRK-001', ...}
    Note over Service: apply(ItemDelivered) →<br/>{status: DELIVERED, delivered_at: '...', ...}
    end

    Service-->>Client: {id: 12345, status: DELIVERED, ...}
```

### The Apply Function (Fold)

Each event type has a pure function that takes the current state and the event, and returns the new state. No side effects. No I/O.

```
function apply(state, event):
    switch event.type:
        case "OrderPlaced":
            return { ...state,
                     id: event.data.order_id,
                     items: event.data.items,
                     total: event.data.total,
                     status: "PLACED" }

        case "PaymentReceived":
            return { ...state,
                     paid: true,
                     payment_id: event.data.payment_id,
                     status: "PAID" }

        case "ItemShipped":
            return { ...state,
                     tracking_id: event.data.tracking_id,
                     shipped_at: event.timestamp,
                     status: "SHIPPED" }

        case "OrderCancelled":
            return { ...state,
                     cancelled_reason: event.data.reason,
                     status: "CANCELLED" }
```

---

## Snapshots — Solving the Replay Performance Problem

For an aggregate with thousands of events, replaying from the beginning on every read is expensive. **Snapshots** store periodic checkpoints of the materialized state.

```mermaid
flowchart LR
    subgraph without_snap [❌ Without Snapshots]
        E1[v1] --> E2[v2] --> E3[v3] --> E4["..."] --> E500[v500]
        E500 --> REPLAY1["Replay 500 events<br/>on every read 🐌"]
    end

    subgraph with_snap [✅ With Snapshots]
        S1[v1] --> S2[v2] --> S3["..."] --> S100[v100]
        S100 --> SNAP["📸 Snapshot at v100<br/>{full state at v100}"]
        SNAP -.-> S101[v101] --> S102[v102] --> S103["..."] --> S150[v150]
        S150 --> REPLAY2["Replay only 50 events<br/>from snapshot ⚡"]
    end

    style without_snap fill:#ffebee
    style with_snap fill:#e8f5e9
```

### Snapshot Strategy

```mermaid
sequenceDiagram
    participant Service
    participant ES as Event Store
    participant SS as Snapshot Store

    Service->>SS: Get latest snapshot for Order-12345
    SS-->>Service: Snapshot at v100: {state...}

    Service->>ES: Get events for Order-12345 WHERE version > 100
    ES-->>Service: [v101, v102, ..., v150]

    Note over Service: apply(snapshot_state, events[101..150])
    Note over Service: Current state at v150

    opt Every N events (e.g., every 100)
        Service->>SS: Save new snapshot at v150
    end
```

| Snapshot Strategy | When to Snapshot | Trade-off |
|------------------|-----------------|-----------|
| **Every N events** | After every 100 events | Simple, predictable |
| **Time-based** | Every hour / day | Good for infrequently updated aggregates |
| **On read** | Snapshot after rebuilding if stale | Lazy, amortizes cost |
| **On write** | Snapshot after every write | Always fresh, extra write overhead |

### Snapshot Storage

| Store | Approach |
|-------|----------|
| **Same event store** | Special `Snapshot` event type at the end of the stream |
| **Separate table** | `snapshots(aggregate_id, version, state, created_at)` |
| **Cache (Redis)** | Fast reads, rebuild from events on cache miss |
| **S3 / Blob store** | For very large aggregate states |

---

## Projections — Building Read Models

Events are optimized for writing (append-only, ordered). But reading patterns are different — you need indexes, aggregations, search, joins. **Projections** transform the event stream into read-optimized views.

```mermaid
flowchart TB
    subgraph event_store [Event Store — Source of Truth]
        ES[(All Events)]
    end

    subgraph projections [Projection Handlers]
        P1[Order History<br/>Projector]
        P2[Search Index<br/>Projector]
        P3[Analytics<br/>Projector]
        P4[User Dashboard<br/>Projector]
    end

    subgraph read_models [Read Models — Query Optimized]
        RM1[(DynamoDB<br/>Orders by user_id)]
        RM2[(Elasticsearch<br/>Full-text search)]
        RM3[(ClickHouse<br/>Aggregations)]
        RM4[(PostgreSQL<br/>Dashboard view)]
    end

    ES --> P1 --> RM1
    ES --> P2 --> RM2
    ES --> P3 --> RM3
    ES --> P4 --> RM4
```

### Types of Projections

```mermaid
flowchart TB
    subgraph live [Live / Subscription Projection]
        ES1[Event Store] -->|Subscribe to new events| LP[Projector]
        LP -->|Update in real-time| RM1[(Read Model)]
        Note1["Low latency<br/>Runs continuously<br/>Must track position (offset)"]
    end

    subgraph catchup [Catch-Up Projection]
        ES2[Event Store] -->|Read from beginning<br/>or last checkpoint| CP[Projector]
        CP -->|Rebuild from scratch| RM2[(Read Model)]
        Note2["For new projections<br/>or rebuilding after bug fix<br/>Replays entire history"]
    end
```

| Projection Type | When Used | Characteristics |
|----------------|-----------|-----------------|
| **Live (subscription)** | Normal operation | Real-time, low-latency, tracks offset |
| **Catch-up (replay)** | New read model, bug fix, schema change | Replays from beginning, can take hours for large stores |
| **One-time** | Analytics, reports, ad-hoc queries | Run once, no ongoing subscription |

### Projection Example: Order Dashboard

```mermaid
flowchart LR
    subgraph events [Event Stream]
        E1["OrderPlaced<br/>{order_id: 1, user: U1, total: 50}"]
        E2["OrderPlaced<br/>{order_id: 2, user: U2, total: 100}"]
        E3["PaymentReceived<br/>{order_id: 1}"]
        E4["OrderCancelled<br/>{order_id: 2}"]
        E5["OrderPlaced<br/>{order_id: 3, user: U1, total: 75}"]
    end

    subgraph projector [Dashboard Projector Logic]
        LOGIC["On OrderPlaced → total_orders++, revenue += total<br/>On OrderCancelled → cancelled_orders++, revenue -= total<br/>On PaymentReceived → paid_orders++"]
    end

    subgraph view [Materialized Dashboard View]
        DASH["total_orders: 3<br/>paid_orders: 1<br/>cancelled_orders: 1<br/>active_orders: 2<br/>total_revenue: $125"]
    end

    events --> projector --> view
```

### Projection Rebuild (The Superpower)

One of the most powerful aspects of event sourcing: **you can build entirely new read models from existing events, without changing anything upstream.**

```mermaid
flowchart TB
    subgraph day1 [Day 1: System Launch]
        ES1[Event Store] --> PROJ1[Order List Projection]
        PROJ1 --> RM1[(Orders by date)]
    end

    subgraph month6 [Month 6: New requirement — need search]
        ES2[Same Event Store<br/>No changes needed] --> PROJ2[New: Search Projector]
        PROJ2 -->|Replay all historical events| RM2[(Elasticsearch<br/>Full-text search)]
        Note1["Replay builds search index<br/>from day 1 data —<br/>zero data loss"]
    end

    subgraph year2 [Year 2: ML team needs features]
        ES3[Same Event Store] --> PROJ3[New: Feature Store Projector]
        PROJ3 -->|Replay| RM3[(ML Feature Store<br/>User behavior vectors)]
    end
```

---

## Event Sourcing + CQRS — The Natural Pairing

Event Sourcing (how data is stored) and CQRS (how reads/writes are separated) complement each other perfectly.

```mermaid
flowchart TB
    subgraph command_side [Command Side — Write]
        CMD[Command:<br/>PlaceOrder] --> HANDLER[Command Handler]
        HANDLER --> LOAD[Load aggregate<br/>from Event Store]
        LOAD --> VALIDATE[Validate business rules<br/>against current state]
        VALIDATE --> APPEND[Append new event<br/>to Event Store]
        APPEND --> ES[(Event Store<br/>Source of Truth)]
    end

    subgraph bridge [Event Bus]
        ES --> KAFKA[Kafka / Subscription]
    end

    subgraph query_side [Query Side — Read]
        KAFKA --> P1[Projector 1]
        KAFKA --> P2[Projector 2]
        KAFKA --> P3[Projector 3]
        P1 --> RM1[(Read Model 1)]
        P2 --> RM2[(Read Model 2)]
        P3 --> RM3[(Read Model 3)]
        Q1[Query: GetOrderHistory] --> RM1
        Q2[Query: SearchOrders] --> RM2
        Q3[Query: OrderMetrics] --> RM3
    end
```

### Command Processing Flow

```mermaid
sequenceDiagram
    participant Client
    participant Handler as Command Handler
    participant ES as Event Store
    participant Bus as Event Bus / Kafka
    participant Proj as Projectors

    Client->>Handler: Command: PlaceOrder {items, user_id}

    Handler->>ES: Load events for cart aggregate
    ES-->>Handler: [CartCreated, ItemAdded, ItemAdded]

    Note over Handler: Replay → current state<br/>Validate: items in stock? user valid?

    alt Validation passes
        Handler->>ES: Append: OrderPlaced {order_id, items, total}
        ES-->>Handler: OK (version 4)
        Handler-->>Client: 201 Created {order_id}

        ES->>Bus: Publish: OrderPlaced
        Bus->>Proj: Project to read models
    else Validation fails
        Handler-->>Client: 400 Bad Request {reason}
    end
```

---

## Concurrency Control

What happens when two concurrent requests try to modify the same aggregate?

### Optimistic Concurrency with Version Numbers

```mermaid
sequenceDiagram
    participant Req1 as Request 1
    participant Req2 as Request 2
    participant ES as Event Store

    par Both load same aggregate
        Req1->>ES: Load Order-123 events
        ES-->>Req1: Events [v1, v2, v3] → state at v3
        Req2->>ES: Load Order-123 events
        ES-->>Req2: Events [v1, v2, v3] → state at v3
    end

    Req1->>ES: Append PaymentReceived<br/>expected_version: 3
    ES-->>Req1: ✅ Stored as v4

    Req2->>ES: Append OrderCancelled<br/>expected_version: 3
    ES-->>Req2: ❌ Conflict! Current version is 4

    Note over Req2: Must reload events [v1..v4]<br/>Rebuild state, re-validate<br/>Then retry with expected_version: 4
```

**Implementation (PostgreSQL):**

```sql
INSERT INTO events (aggregate_id, version, event_type, data, created_at)
VALUES ('Order-123', 4, 'PaymentReceived', '{"payment_id": "..."}', NOW());

-- The UNIQUE(aggregate_id, version) constraint ensures
-- only one writer can claim version 4.
-- Concurrent writer gets: ERROR: duplicate key value violates unique constraint
```

**Implementation (DynamoDB):**

```json
{
  "TableName": "events",
  "Item": { "aggregate_id": "Order-123", "version": 4, ... },
  "ConditionExpression": "attribute_not_exists(version)"
}
```

---

## Event Versioning and Schema Evolution

Events are immutable — you cannot change old events. But business requirements evolve. How do you handle schema changes?

### Strategy 1: Upcasting (Recommended)

Transform old event formats to new formats **at read time** using an upcaster pipeline.

```mermaid
flowchart LR
    subgraph store [Event Store — Immutable]
        V1["OrderPlaced v1<br/>{total: 149.99}"]
        V2["OrderPlaced v2<br/>{total: 149.99, currency: 'USD'}"]
        V3["OrderPlaced v3<br/>{amount: {value: 149.99, currency: 'USD'}}"]
    end

    subgraph upcaster [Upcaster Pipeline — At Read Time]
        U1["v1 → v2: add currency='USD'"]
        U2["v2 → v3: wrap in amount object"]
    end

    subgraph handler [Event Handler — Only Knows v3]
        H["Handle OrderPlaced v3<br/>{amount: {value, currency}}"]
    end

    V1 --> U1 --> U2 --> H
    V2 --> U2 --> H
    V3 --> H
```

### Strategy 2: New Event Type

When the change is semantically different, introduce a new event type.

```
-- Original
OrderPlaced { items, total, shipping_address }

-- New requirement: split shipping
OrderPlacedV2 { items, total, shipping_address, billing_address }

-- Handler supports both
handle(OrderPlaced)   → use shipping_address as billing_address (backward compat)
handle(OrderPlacedV2) → use both addresses
```

### Strategy 3: Event Wrapper with Schema Version

```json
{
  "event_type": "OrderPlaced",
  "schema_version": 3,
  "data": { ... }
}
```

The consumer checks `schema_version` and routes to the appropriate handler or upcaster.

### Comparison

| Strategy | Pros | Cons | Best For |
|----------|------|------|----------|
| **Upcasting** | Old events untouched, handler only knows latest | Upcaster chain can grow long | Most cases — incremental field additions |
| **New event type** | Clean separation | Must support old + new type forever | Semantically different events |
| **Schema version field** | Explicit versioning | Handler complexity | Large-scale with many versions |
| **Copy-transform (migration)** | Clean store after migration | Breaks immutability — last resort | Major rewrites (rare) |

---

## Temporal Queries — Time Travel

Event sourcing gives you something no CRUD system can: **the ability to query the state of any entity at any point in time.**

```mermaid
flowchart TB
    subgraph timeline [Order-12345 Event Timeline]
        E1["Jan 1: OrderPlaced<br/>total: $149.99"]
        E2["Jan 2: ItemAdded<br/>total: $199.99"]
        E3["Jan 5: DiscountApplied<br/>total: $179.99"]
        E4["Jan 8: PaymentReceived"]
        E5["Jan 12: ItemShipped"]

        E1 --> E2 --> E3 --> E4 --> E5
    end

    Q1["What was the order state on Jan 3?<br/>→ Replay E1, E2<br/>→ {total: $199.99, status: PLACED}"] --> E2
    Q2["What was the total before discount?<br/>→ Replay E1, E2<br/>→ $199.99"] --> E2
    Q3["Current state?<br/>→ Replay E1..E5<br/>→ {status: SHIPPED, total: $179.99}"] --> E5

    style Q1 fill:#e3f2fd
    style Q2 fill:#e3f2fd
    style Q3 fill:#e3f2fd
```

### Use Cases for Temporal Queries

| Use Case | Query | Business Value |
|----------|-------|---------------|
| **Dispute resolution** | "What was the price when the customer ordered?" | Resolve pricing complaints with facts |
| **Regulatory compliance** | "What was the account state at end-of-quarter?" | Auditable point-in-time reporting |
| **Debugging** | "What events led to this inconsistent state?" | Root cause analysis from event history |
| **Retroactive analytics** | "What would revenue be if we hadn't given discount X?" | What-if analysis by selective replay |
| **Undo / Replay** | "Rebuild state after fixing a bug in event handler" | Correct read models without data loss |

---

## Practical Example: E-Commerce Order Lifecycle

### Event Stream for a Complete Order

```mermaid
flowchart TB
    subgraph stream [Event Stream: Order-7890]
        E1["v1: OrderPlaced<br/>{user: U42, items: [{sku: P1, qty: 2, price: 29.99},<br/>{sku: P2, qty: 1, price: 89.99}], total: 149.97}"]
        E2["v2: InventoryReserved<br/>{items: [{sku: P1, qty: 2}, {sku: P2, qty: 1}]}"]
        E3["v3: PaymentAuthorized<br/>{payment_id: PAY-001, amount: 149.97, method: 'VISA ****4242'}"]
        E4["v4: PaymentCaptured<br/>{payment_id: PAY-001, captured_amount: 149.97}"]
        E5["v5: OrderConfirmed<br/>{estimated_delivery: '2025-01-22'}"]
        E6["v6: ShipmentCreated<br/>{shipment_id: SHP-001, carrier: 'FedEx', tracking: 'TRK123'}"]
        E7["v7: ItemShipped<br/>{shipment_id: SHP-001, shipped_at: '2025-01-18T14:00:00Z'}"]
        E8["v8: ItemDelivered<br/>{shipment_id: SHP-001, delivered_at: '2025-01-21T09:30:00Z',<br/>signed_by: 'Alice Smith'}"]

        E1 --> E2 --> E3 --> E4 --> E5 --> E6 --> E7 --> E8
    end
```

### Multiple Projections from Same Events

```mermaid
flowchart TB
    ES[Event Stream: Order-7890<br/>8 events] --> P1 & P2 & P3 & P4 & P5

    subgraph projections [Different Projections — Same Source]
        P1[Customer Order<br/>Status View]
        P2[Warehouse<br/>Fulfillment View]
        P3[Finance<br/>Revenue View]
        P4[Carrier<br/>Shipping View]
        P5[Analytics<br/>Funnel View]
    end

    P1 --> V1["Shows: status, tracking,<br/>estimated delivery"]
    P2 --> V2["Shows: items to pick,<br/>packing details"]
    P3 --> V3["Shows: revenue, payment<br/>method breakdown"]
    P4 --> V4["Shows: package dimensions,<br/>delivery address"]
    P5 --> V5["Shows: time between steps,<br/>conversion funnel"]
```

---

## Practical Example: Bank Account

Banking is one of the most natural fits for event sourcing — regulators literally require a complete, immutable audit trail.

```mermaid
flowchart TB
    subgraph account_stream [Event Stream: Account-A100]
        E1["v1: AccountOpened {holder: 'Alice', type: 'checking', opened_by: 'branch-42'}"]
        E2["v2: MoneyDeposited {amount: 1000.00, source: 'cash', teller: 'T5'}"]
        E3["v3: MoneyWithdrawn {amount: 200.00, channel: 'ATM', location: 'ATM-NYC-01'}"]
        E4["v4: MoneyDeposited {amount: 3500.00, source: 'direct_deposit', employer: 'Acme'}"]
        E5["v5: TransferSent {amount: 500.00, to_account: 'A200', reference: 'rent'}"]
        E6["v6: InterestApplied {amount: 2.15, rate: 0.05, period: '2025-01'}"]

        E1 --> E2 --> E3 --> E4 --> E5 --> E6
    end

    subgraph state [Current State at v6]
        S["Account A100<br/>Balance: $3,802.15<br/>Holder: Alice<br/>Type: Checking<br/>Status: Active"]
    end

    subgraph audit [Regulatory Audit]
        A["Complete trail:<br/>Every deposit, withdrawal, transfer<br/>Who, when, where, why<br/>Cannot be altered ✅"]
    end

    E6 --> S
    E6 --> audit
```

**State derivation:**

```
v1: balance = 0         (account opened)
v2: balance = 1000      (+1000 deposit)
v3: balance = 800       (-200 withdrawal)
v4: balance = 4300      (+3500 deposit)
v5: balance = 3800      (-500 transfer)
v6: balance = 3802.15   (+2.15 interest)
```

---

## Event Sourcing with Kafka

Kafka's append-only, immutable log is architecturally similar to an event store, making it a common infrastructure choice.

```mermaid
flowchart TB
    subgraph write [Write Path]
        SVC[Service] -->|Append events| KAFKA[Kafka Topic:<br/>order-events<br/>Key: order_id]
    end

    subgraph kafka_internals [Kafka — Acts as Event Store]
        KAFKA --> PART0["Partition 0<br/>Order-1 events<br/>Order-7 events"]
        KAFKA --> PART1["Partition 1<br/>Order-2 events<br/>Order-8 events"]
        KAFKA --> PART2["Partition 2<br/>Order-3 events<br/>Order-9 events"]
    end

    subgraph consumers [Read Path — Projections]
        PART0 & PART1 & PART2 --> CG1[Consumer Group:<br/>Search Projector]
        PART0 & PART1 & PART2 --> CG2[Consumer Group:<br/>Analytics Projector]
        PART0 & PART1 & PART2 --> CG3[Consumer Group:<br/>State Rebuilder]
    end

    CG1 --> ES[(Elasticsearch)]
    CG2 --> CH[(ClickHouse)]
    CG3 --> CACHE[(Redis State Cache)]
```

### Kafka as Event Store — Limitations

| Capability | Dedicated Event Store | Kafka |
|-----------|----------------------|-------|
| Append events | ✅ | ✅ |
| Read single aggregate's stream | ✅ Efficient (by aggregate_id) | ❌ Must scan partition — events for many aggregates mixed |
| Optimistic concurrency (version check) | ✅ Native | ❌ Not supported — no conditional append |
| Infinite retention | ✅ Designed for it | ⚠️ Possible but expensive — Kafka optimized for throughput, not storage |
| Subscriptions / projections | ✅ Native | ✅ Consumer groups |
| Global ordering | ✅ Per-stream | ✅ Per-partition only |
| Event replay | ✅ By stream | ✅ By resetting consumer offset |

**Verdict:** Use Kafka as the **event bus** (publishing events to consumers/projections), but use a **dedicated event store** (EventStoreDB, PostgreSQL, DynamoDB) as the source-of-truth write store — especially if you need per-aggregate reads and optimistic concurrency.

```mermaid
flowchart LR
    SVC[Service] -->|1. Append| ES[(Event Store<br/>PostgreSQL / EventStoreDB<br/>Source of Truth)]
    ES -->|2. Publish via CDC<br/>or outbox| KAFKA[Kafka<br/>Distribution Bus]
    KAFKA --> P1[Projector 1]
    KAFKA --> P2[Projector 2]
    KAFKA --> P3[Projector 3]

    style ES fill:#4CAF50,color:#fff
    style KAFKA fill:#2196F3,color:#fff
```

---

## Event Sourcing in SAGA

Event sourcing provides a natural audit trail for every SAGA step, and the event store acts as the SAGA log.

```mermaid
sequenceDiagram
    participant ORCH as SAGA Orchestrator
    participant ES as Event Store
    participant OS as Order Service
    participant PS as Payment Service

    ORCH->>ES: Append: SagaStarted {saga_id, order_id}

    ORCH->>OS: CreateOrder
    OS-->>ORCH: OrderCreated
    ORCH->>ES: Append: OrderStepCompleted {saga_id}

    ORCH->>PS: ChargePayment
    PS-->>ORCH: PaymentFailed

    ORCH->>ES: Append: PaymentStepFailed {saga_id, reason}
    ORCH->>ES: Append: CompensationStarted {saga_id}

    ORCH->>OS: CancelOrder (compensate)
    OS-->>ORCH: OrderCancelled
    ORCH->>ES: Append: CompensationCompleted {saga_id}
    ORCH->>ES: Append: SagaFailed {saga_id}

    Note over ES: Complete SAGA history<br/>available for debugging,<br/>replay, and audit
```

---

## Common Pitfalls

### Pitfall 1: Treating the Event Store as a Database

```mermaid
flowchart LR
    subgraph wrong [❌ Querying the Event Store Directly]
        CLIENT1[Client] -->|"Find all orders > $100<br/>placed in January"| ES1[Event Store]
        Note1["Event stores are not query engines<br/>This is slow and painful"]
    end

    subgraph right [✅ Query the Projection]
        ES2[Event Store] --> PROJ[Projector]
        PROJ --> RM[(Read Model<br/>indexed, optimized)]
        CLIENT2[Client] -->|"SELECT * WHERE total > 100<br/>AND placed_at >= '2025-01-01'"| RM
    end

    style wrong fill:#ffebee
    style right fill:#e8f5e9
```

### Pitfall 2: Enormous Aggregates

An aggregate with millions of events is unmanageable even with snapshots.

**Fix:** Model smaller aggregates. Instead of one `User` aggregate with every event, use `UserProfile`, `UserPreferences`, `UserOrderHistory` as separate aggregates.

### Pitfall 3: Events Containing Derived Data

```mermaid
flowchart LR
    subgraph bad [❌ Derived Data in Event]
        E1["OrderPlaced {<br/>  items: [...],<br/>  subtotal: 120.00,<br/>  tax: 10.80,<br/>  total: 130.80<br/>}"]
        Note1["If tax rate changes,<br/>historical replay gives<br/>wrong totals"]
    end

    subgraph good [✅ Only Source Data in Event]
        E2["OrderPlaced {<br/>  items: [...],<br/>  tax_rate_id: 'TX-CA-2025'<br/>}"]
        Note2["Compute subtotal, tax, total<br/>at projection time with<br/>correct historical rate"]
    end

    style bad fill:#ffebee
    style good fill:#e8f5e9
```

### Pitfall 4: Not Handling Projection Failure

Projections can fail or fall behind. You need:

| Mechanism | Purpose |
|-----------|---------|
| **Checkpoint / offset tracking** | Resume from where projection stopped |
| **Rebuild capability** | Drop and rebuild projection from scratch |
| **Monitoring / alerting** | Alert when projection lag exceeds threshold |
| **Idempotent projectors** | Handle redelivered events without corruption |

### Pitfall 5: Exposing Internal Events to External Consumers

Internal events leak domain internals. Expose **integration events** instead.

```mermaid
flowchart LR
    subgraph internal [Internal Events — Private]
        IE1[OrderValidationPassed]
        IE2[InventoryLockAcquired]
        IE3[PaymentGatewayResponseReceived]
        IE4[FraudScoreCalculated]
    end

    subgraph transform [Event Transformer]
        T[Map internal → integration]
    end

    subgraph external [Integration Events — Public API]
        EE1[OrderConfirmed]
        EE2[OrderShipped]
    end

    internal --> transform --> external

    style internal fill:#ffebee
    style external fill:#e8f5e9
```

---

## Pros and Cons

### Pros

| Advantage | Detail |
|-----------|--------|
| **Complete audit trail** | Every change is recorded — who, when, what, why |
| **Temporal queries** | Query state at any point in time |
| **Projection rebuild** | Build new read models from existing events without data migration |
| **Debugging superpower** | Replay events to reproduce any bug |
| **No data loss** | Nothing is ever overwritten or deleted |
| **Natural fit for CQRS** | Events bridge write model to multiple read models |
| **Domain-driven** | Events capture business intent, not just data mutations |
| **Retroactive fixes** | Fix a projection bug and replay — corrected data appears automatically |
| **Decoupled consumers** | New downstream systems consume historical + live events |

### Cons

| Disadvantage | Detail |
|--------------|--------|
| **Complexity** | Fundamentally different mental model — steep learning curve |
| **Eventual consistency** | Read models lag behind the event store |
| **Event schema evolution** | Changing event schemas requires upcasting — can't ALTER old events |
| **Storage growth** | Events accumulate forever — need retention and archival strategy |
| **Replay time** | Rebuilding projections from scratch can take hours for large stores |
| **Query limitations** | Event store is not queryable — must build projections for every access pattern |
| **Framework maturity** | Fewer off-the-shelf solutions compared to CRUD frameworks |
| **GDPR / right to deletion** | Immutable events conflict with "right to be forgotten" — needs crypto-shredding |
| **Testing complexity** | Must test event handlers, projections, upcasters, and snapshot logic |

---

## When to Use Event Sourcing

```mermaid
flowchart TB
    Q1{Do you need a complete<br/>audit trail of every change?}
    Q1 -->|No| Q2{Do you need to query<br/>historical state at any<br/>point in time?}
    Q2 -->|No| Q3{Do you need to build<br/>multiple read models from<br/>the same data?}
    Q3 -->|No| CRUD[Stick with CRUD<br/>Event sourcing is overkill]
    Q3 -->|Yes| MAYBE[Consider CQRS<br/>without full event sourcing]

    Q1 -->|Yes| USE[✅ Strong candidate<br/>for Event Sourcing]
    Q2 -->|Yes| USE

    Q4{Is your domain inherently<br/>event-driven?}
    Q4 -->|Yes, e.g., trading,<br/>logistics, workflows| USE
    Q4 -->|No, simple CRUD| CRUD

    Q5{Can your team handle<br/>the complexity?}
    Q5 -->|Yes| USE
    Q5 -->|No, limited experience| START[Start with CRUD +<br/>event publishing.<br/>Migrate later if needed]

    style USE fill:#4CAF50,color:#fff
    style CRUD fill:#9E9E9E,color:#fff
    style MAYBE fill:#FF9800,color:#fff
    style START fill:#2196F3,color:#fff
```

### Use Event Sourcing When

- **Audit and compliance are mandatory** — financial systems, healthcare, regulated industries
- **The domain is inherently event-driven** — order lifecycle, supply chain, trading, IoT telemetry
- **You need temporal queries** — "what was the state on date X?"
- **Multiple teams need different views of the same data** — projection rebuild is invaluable
- **Debugging production issues** by replaying events is a priority
- **You're already using CQRS** — event sourcing is a natural complement
- **Undo/redo capabilities** are a product requirement

### Do NOT Use Event Sourcing When

- **Simple CRUD with no audit needs** — a todo app, a blog, basic settings page
- **Your team is unfamiliar** — the learning curve is real; get CRUD right first
- **Strict GDPR deletion requirements** without a crypto-shredding strategy in place
- **Low entity count, infrequent changes** — the overhead is not justified
- **You need strong consistency on reads** — eventual consistency from projections may not be acceptable
- **The domain has no meaningful events** — if "UserUpdated" is your only event, you're doing it wrong

---

## Real-World Implementations

| System | Domain | Implementation Details |
|--------|--------|----------------------|
| **LinkedIn** | Activity feed | Event-sourced user activity — replayed to build feed projections |
| **Netflix** | Content metadata | Event-sourced content catalog for multi-region consistency |
| **Walmart** | Inventory | Event-sourced stock movements across 4,700+ stores |
| **Capital One** | Banking | Transaction history as immutable event log — regulatory requirement |
| **Lego** | E-commerce | Order lifecycle event-sourced with Axon Framework |
| **EventStoreDB** | Infrastructure | Purpose-built database for event sourcing (used by many) |
| **Axon Framework** | Java framework | Full event sourcing + CQRS + SAGA support |
| **Marten** | .NET library | Event sourcing on PostgreSQL with JSONB |
| **Temporal.io** | Workflow engine | Durable execution built on event-sourced workflow state |

---

## GDPR and the Right to Be Forgotten

Immutable events conflict with GDPR's requirement to delete personal data. The solution: **crypto-shredding**.

```mermaid
flowchart TB
    subgraph write_time [At Write Time]
        EVENT["OrderPlaced {<br/>  order_id: 123,<br/>  user_pii: ENCRYPTED(name, email, address)<br/>  encryption_key_ref: 'user-U42-key'<br/>}"]
        KEYSTORE["Key Store:<br/>user-U42-key → AES-256 key"]
    end

    subgraph normal_read [Normal Read — Key Exists]
        READ1[Read event] --> DECRYPT["Decrypt user_pii<br/>with user-U42-key"]
        DECRYPT --> FULL["Full event data visible"]
    end

    subgraph gdpr_delete [GDPR Deletion Request]
        DELETE["Delete user-U42-key<br/>from Key Store"] --> READ2[Read event]
        READ2 --> UNDECRYPT["Cannot decrypt user_pii<br/>Key destroyed"]
        UNDECRYPT --> REDACTED["Event exists but PII<br/>is permanently unreadable<br/>= effectively deleted"]
    end

    style gdpr_delete fill:#e3f2fd
```

**Events remain immutable.** Only the encryption key is deleted. Without the key, the personal data in the events is cryptographically unrecoverable — satisfying GDPR without breaking the event log.

---

## Key Takeaways for System Design Interviews

1. **"Store events, derive state"** — this is the one-sentence summary. Everything else follows from this.
2. **Events are immutable facts in past tense** — `OrderPlaced`, not `PlaceOrder`. The naming matters.
3. **Current state = fold over events** — the apply function is pure, deterministic, no side effects.
4. **Projections are the read side** — you never query the event store directly for user-facing reads.
5. **Snapshots solve the replay performance problem** — without them, aggregates with thousands of events are impractical.
6. **Optimistic concurrency via version numbers** — the UNIQUE(aggregate_id, version) constraint prevents write conflicts.
7. **Event schema evolution requires upcasting** — you cannot ALTER old events. Plan for this from day one.
8. **Kafka is the bus, not the store** — use Kafka to distribute events to projections, but use a dedicated event store for the write side.
9. **Projection rebuild is the superpower** — "we can build any new read model from historical events" is a powerful interview answer.
10. **GDPR + immutability = crypto-shredding** — encrypt PII in events, delete the key on erasure request.
11. **Don't use it for everything** — event sourcing adds significant complexity. Use it where the audit trail and temporal queries justify the cost.
12. **Pair with CQRS** — event sourcing without CQRS forces you to query the event store directly, which is painful. Always pair them.

---

## Related Concepts

- **[Kafka Communication Patterns](./kafka-communication-patterns.md)** — Kafka as the event distribution bus for projections
- **[SAGA Pattern](./saga-pattern.md)** — SAGAs benefit from event-sourced step logging
- **[Idempotency](./idempotency.md)** — Projection handlers must be idempotent for replay safety
- **[Two-Phase Commit](./two-phase-commit.md)** — The transactional alternative when you need strong consistency
- **CQRS** — The natural architectural companion to event sourcing
- **Outbox Pattern** — Reliable event publishing from the event store to Kafka
- **Domain-Driven Design** — Aggregates, bounded contexts, and domain events align with event sourcing
