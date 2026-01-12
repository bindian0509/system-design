# Messaging and Async Patterns

Asynchronous communication is fundamental to building scalable, resilient distributed systems. This guide covers message queues, event-driven architecture, and common async patterns.

## Why Async Communication?

```mermaid
flowchart TB
    subgraph sync [Synchronous - Problems]
        A[Service A] -->|Blocked| B[Service B]
        B -->|Blocked| C[Service C]
        Note1[Tight coupling<br/>Cascading failures<br/>Limited scale]
    end

    subgraph async [Asynchronous - Benefits]
        D[Service A] -->|Publish| Queue[Message Queue]
        Queue -->|Subscribe| E[Service B]
        Queue -->|Subscribe| F[Service C]
        Note2[Loose coupling<br/>Fault isolation<br/>Better scale]
    end
```

| Aspect | Synchronous | Asynchronous |
|--------|-------------|--------------|
| **Coupling** | Tight | Loose |
| **Response Time** | Wait for completion | Immediate acknowledgment |
| **Scaling** | Both must scale together | Independent scaling |
| **Failure Handling** | Cascading failures | Isolated failures |
| **Load Handling** | Overflow = failure | Queue absorbs spikes |

---

## Message Queue Fundamentals

### Core Concepts

```mermaid
flowchart LR
    subgraph producer [Producers]
        P1[Producer 1]
        P2[Producer 2]
    end

    subgraph queue [Message Queue]
        Q[(Queue)]
        M1[Msg 1]
        M2[Msg 2]
        M3[Msg 3]
    end

    subgraph consumer [Consumers]
        C1[Consumer 1]
        C2[Consumer 2]
    end

    P1 --> Q
    P2 --> Q
    Q --> C1
    Q --> C2
```

| Term | Definition |
|------|------------|
| **Producer** | Sends messages to queue |
| **Consumer** | Receives messages from queue |
| **Message** | Data packet with payload and metadata |
| **Topic** | Named channel for messages |
| **Partition** | Ordered subset of topic (for parallelism) |
| **Offset** | Position of message in partition |
| **Consumer Group** | Set of consumers sharing work |

### Queue vs Topic (Pub/Sub)

```mermaid
flowchart TB
    subgraph queue [Point-to-Point Queue]
        PQ[Producer] --> Q[(Queue)]
        Q --> CQ1[Consumer 1]
        Q --> CQ2[Consumer 2]
        Note1[Each message to ONE consumer]
    end

    subgraph pubsub [Publish-Subscribe Topic]
        PT[Producer] --> T[(Topic)]
        T --> CT1[Subscriber 1<br/>Gets ALL messages]
        T --> CT2[Subscriber 2<br/>Gets ALL messages]
        Note2[Each message to ALL subscribers]
    end
```

| Model | Behavior | Use Case |
|-------|----------|----------|
| **Queue** | One consumer per message | Task distribution, work queues |
| **Topic** | All subscribers get all messages | Event broadcasting, notifications |

---

## Delivery Guarantees

### The Three Guarantees

```mermaid
flowchart LR
    subgraph guarantees [Delivery Guarantees]
        AtMost[At-Most-Once<br/>May lose messages]
        AtLeast[At-Least-Once<br/>May duplicate]
        Exactly[Exactly-Once<br/>No loss, no duplicates]
    end

    AtMost -->|Easier| AtLeast -->|Harder| Exactly
```

| Guarantee | Behavior | Trade-off | Use Case |
|-----------|----------|-----------|----------|
| **At-most-once** | Fire and forget | Fast, may lose | Metrics, logs |
| **At-least-once** | Retry until ACK | Safe, may duplicate | Most systems |
| **Exactly-once** | Deduplicate + ACK | Slow, complex | Financial transactions |

### Achieving At-Least-Once

```mermaid
sequenceDiagram
    participant Producer
    participant Queue
    participant Consumer

    Producer->>Queue: Send message
    Queue->>Consumer: Deliver message
    Consumer->>Consumer: Process message
    Consumer->>Queue: ACK
    Queue->>Queue: Remove message

    Note over Consumer,Queue: If no ACK, message redelivered
```

### Achieving Exactly-Once

```mermaid
sequenceDiagram
    participant Producer
    participant Queue
    participant Consumer
    participant DB

    Producer->>Queue: Send message (idempotency_key=abc)
    Queue->>Consumer: Deliver message

    Consumer->>DB: Check: processed abc?

    alt Already processed
        Consumer->>Queue: ACK (skip processing)
    else Not processed
        Consumer->>DB: Process + record abc
        Consumer->>Queue: ACK
    end
```

**Key Technique: Idempotent Consumers**
```python
def process_message(message):
    idempotency_key = message.headers['idempotency_key']

    # Check if already processed
    if db.exists(f"processed:{idempotency_key}"):
        return  # Already done

    # Process the message
    result = do_business_logic(message.body)

    # Record completion (atomically with processing if possible)
    db.set(f"processed:{idempotency_key}", result)
```

---

## Message Queue Comparison

### Kafka

```mermaid
flowchart TB
    subgraph kafka [Kafka Architecture]
        subgraph topic [Topic: orders]
            P0[Partition 0]
            P1[Partition 1]
            P2[Partition 2]
        end

        subgraph cg1 [Consumer Group: order-processor]
            C1[Consumer 1 → P0]
            C2[Consumer 2 → P1]
            C3[Consumer 3 → P2]
        end

        subgraph cg2 [Consumer Group: analytics]
            C4[Consumer 4 → P0, P1, P2]
        end
    end
```

**Key Features:**
- Distributed commit log
- High throughput (millions/sec)
- Message retention (replay capability)
- Partitions for parallelism
- Consumer groups for scaling

**Best For:**
- Event streaming
- Log aggregation
- High-throughput pipelines
- Event sourcing

### RabbitMQ

```mermaid
flowchart TB
    subgraph rabbitmq [RabbitMQ Architecture]
        Producer[Producer] --> Exchange{Exchange}

        Exchange -->|routing key: order.*| Q1[Queue: new-orders]
        Exchange -->|routing key: payment.*| Q2[Queue: payments]
        Exchange -->|fanout| Q3[Queue: notifications]

        Q1 --> C1[Consumer]
        Q2 --> C2[Consumer]
        Q3 --> C3[Consumer]
    end
```

**Exchange Types:**
| Type | Routing |
|------|---------|
| **Direct** | Exact routing key match |
| **Topic** | Pattern matching (*.order.#) |
| **Fanout** | Broadcast to all queues |
| **Headers** | Match on headers |

**Best For:**
- Complex routing
- Traditional message queuing
- Request-reply patterns
- Smaller scale

### AWS SQS

```mermaid
flowchart LR
    Producer[Producer] --> SQS[(SQS Queue)]
    SQS --> Consumer1[Consumer 1]
    SQS --> Consumer2[Consumer 2]

    SQS -.->|DLQ| DLQ[(Dead Letter Queue)]
```

**Key Features:**
- Fully managed
- Automatic scaling
- No infrastructure to manage
- Standard and FIFO queues

**Best For:**
- AWS-native applications
- Serverless (Lambda integration)
- Simple queue needs

### Comparison Table

| Feature | Kafka | RabbitMQ | SQS |
|---------|-------|----------|-----|
| **Throughput** | Very High | Medium | Medium |
| **Latency** | Low | Very Low | Medium |
| **Ordering** | Per partition | Per queue | FIFO only |
| **Retention** | Configurable (days) | Until consumed | 14 days max |
| **Replay** | Yes | No | No |
| **Complexity** | High | Medium | Low |
| **Managed Option** | Confluent, MSK | CloudAMQP | Native AWS |

---

## Event-Driven Architecture

### Event Types

```mermaid
flowchart LR
    subgraph events [Event Types]
        Command[Command<br/>CreateOrder]
        Event[Event<br/>OrderCreated]
        Query[Query<br/>GetOrderStatus]
    end
```

| Type | Purpose | Naming | Example |
|------|---------|--------|---------|
| **Command** | Request action | Imperative verb | CreateOrder, SendEmail |
| **Event** | Notify what happened | Past tense | OrderCreated, PaymentReceived |
| **Query** | Request information | Question-like | GetOrderStatus |

### Event Structure

```json
{
  "event_id": "evt_abc123",
  "event_type": "order.created",
  "timestamp": "2024-01-15T10:30:00Z",
  "source": "order-service",
  "correlation_id": "req_xyz789",
  "data": {
    "order_id": "ord_456",
    "customer_id": "cust_789",
    "total": 99.99,
    "items": [...]
  },
  "metadata": {
    "version": "1.0",
    "trace_id": "trace_abc"
  }
}
```

### Choreography vs Orchestration

```mermaid
flowchart TB
    subgraph choreography [Choreography - Decentralized]
        O1[Order Service] -->|OrderCreated| E1((Event Bus))
        E1 --> I1[Inventory Service]
        E1 --> P1[Payment Service]
        E1 --> N1[Notification Service]

        I1 -->|InventoryReserved| E1
        P1 -->|PaymentProcessed| E1
    end

    subgraph orchestration [Orchestration - Centralized]
        Orch[Orchestrator] --> O2[Order Service]
        Orch --> I2[Inventory Service]
        Orch --> P2[Payment Service]
        Orch --> N2[Notification Service]
    end
```

| Aspect | Choreography | Orchestration |
|--------|--------------|---------------|
| **Control** | Decentralized | Central orchestrator |
| **Coupling** | Very loose | Tighter to orchestrator |
| **Visibility** | Harder to trace | Clear workflow |
| **Failure Handling** | Distributed | Centralized |
| **Complexity Growth** | Exponential | Linear |

---

## Event Sourcing

Store events as the source of truth, derive state from events.

### Traditional vs Event Sourcing

```mermaid
flowchart TB
    subgraph traditional [Traditional - Store State]
        T_CMD[UpdateBalance] --> T_DB[(Account: $150)]
    end

    subgraph eventsourcing [Event Sourcing - Store Events]
        E_CMD[Deposit $50] --> E_LOG[(Event Log)]
        E_LOG --> E1[AccountOpened: $100]
        E_LOG --> E2[Deposited: $50]
        E_LOG --> E3[Withdrawn: $30]
        E_LOG --> E4[Deposited: $30]
        E_LOG --> Current[Current State: $150]
    end
```

**Benefits:**
- Complete audit trail
- Can reconstruct any past state
- Natural fit for event-driven systems
- Supports temporal queries

**Challenges:**
- More complex queries
- Event schema evolution
- Eventual consistency

### CQRS (Command Query Responsibility Segregation)

```mermaid
flowchart TB
    subgraph commands [Command Side]
        Write[Write Command] --> CmdHandler[Command Handler]
        CmdHandler --> EventStore[(Event Store)]
    end

    subgraph events [Event Processing]
        EventStore --> Projector[Projector]
        Projector --> ReadDB[(Read Database)]
    end

    subgraph queries [Query Side]
        Query[Read Query] --> QueryHandler[Query Handler]
        QueryHandler --> ReadDB
    end
```

**When to Use:**
- Different read/write patterns
- Complex domain logic
- Event sourcing systems
- Different scaling needs for reads/writes

---

## Saga Pattern

Manage distributed transactions through a sequence of local transactions.

### Choreography-Based Saga

```mermaid
sequenceDiagram
    participant Order
    participant Inventory
    participant Payment
    participant Shipping

    Order->>Order: Create Order
    Order-->>Inventory: OrderCreated
    Inventory->>Inventory: Reserve Stock
    Inventory-->>Payment: StockReserved
    Payment->>Payment: Charge Customer

    alt Payment Success
        Payment-->>Shipping: PaymentCompleted
        Shipping->>Shipping: Create Shipment
    else Payment Failure
        Payment-->>Inventory: PaymentFailed
        Inventory->>Inventory: Release Stock (Compensate)
        Inventory-->>Order: StockReleased
        Order->>Order: Cancel Order (Compensate)
    end
```

### Orchestration-Based Saga

```mermaid
flowchart TB
    Orchestrator[Saga Orchestrator]

    Orchestrator -->|1. Reserve| Inventory[(Inventory)]
    Orchestrator -->|2. Charge| Payment[(Payment)]
    Orchestrator -->|3. Ship| Shipping[(Shipping)]

    Shipping -->|Failure| Orchestrator
    Orchestrator -->|Compensate 2| Payment
    Orchestrator -->|Compensate 1| Inventory
```

### Compensating Transactions

| Action | Compensation |
|--------|--------------|
| Reserve inventory | Release inventory |
| Create order | Cancel order |
| Charge payment | Refund payment |
| Create shipment | Cancel shipment |

---

## Dead Letter Queues

Handle messages that can't be processed.

```mermaid
flowchart TB
    Producer[Producer] --> MainQ[(Main Queue)]
    MainQ --> Consumer[Consumer]

    Consumer -->|Success| Done[Processed]
    Consumer -->|Failure x3| DLQ[(Dead Letter Queue)]

    DLQ --> Alert[Alert/Investigation]
    DLQ --> Retry[Manual Retry]
```

**DLQ Best Practices:**
1. Set max retry attempts before DLQ
2. Include original message + error details
3. Monitor DLQ depth
4. Have process for investigation
5. Implement replay mechanism

```python
def process_with_dlq(message):
    try:
        process_message(message)
        return True
    except TransientError:
        # Retry later
        raise
    except PermanentError as e:
        # Send to DLQ
        dlq.send({
            "original_message": message,
            "error": str(e),
            "failed_at": datetime.now(),
            "retry_count": message.retry_count
        })
        return True  # ACK to remove from main queue
```

---

## Backpressure Handling

Prevent overwhelmed consumers from crashing.

```mermaid
flowchart LR
    subgraph producer [Fast Producer]
        P[1000 msg/sec]
    end

    subgraph queue [Buffer]
        Q[(Queue)]
    end

    subgraph consumer [Slow Consumer]
        C[100 msg/sec]
    end

    P --> Q --> C

    Note[Queue grows 900 msg/sec!]
```

### Backpressure Strategies

| Strategy | How It Works | Trade-off |
|----------|--------------|-----------|
| **Drop Messages** | Discard when queue full | Data loss |
| **Block Producer** | Producer waits | Cascading delays |
| **Buffering** | Queue absorbs spike | Memory/disk limits |
| **Rate Limiting** | Limit producer rate | Slower ingestion |
| **Scaling Consumers** | Add more consumers | Cost, delay |
| **Sampling** | Process subset | Incomplete data |

### Implementation Example

```python
# Rate limiting producer
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=100, period=1)  # 100 msg/sec
def produce_message(message):
    queue.send(message)

# Scaling consumers (Kubernetes HPA example)
# When queue depth > 1000, scale up
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  metrics:
  - type: External
    external:
      metric:
        name: queue_messages_ready
      target:
        type: AverageValue
        averageValue: 1000
```

---

## Message Ordering

### Partition-Based Ordering (Kafka)

```mermaid
flowchart TB
    subgraph producer [Producer]
        M1[Order 1 - User A]
        M2[Order 2 - User B]
        M3[Order 3 - User A]
    end

    subgraph topic [Topic with 3 Partitions]
        P0[Partition 0<br/>User A: Order 1, Order 3]
        P1[Partition 1<br/>User B: Order 2]
        P2[Partition 2<br/>Empty]
    end

    M1 -->|hash user_id| P0
    M2 -->|hash user_id| P1
    M3 -->|hash user_id| P0
```

**Ordering Rule:**
- Order guaranteed **within a partition**
- No ordering across partitions
- Use partition key for related messages

```python
# Kafka producer with ordering
producer.send(
    topic='orders',
    key=user_id.encode(),  # Same user → same partition
    value=order_data
)
```

### FIFO Queues (SQS FIFO)

```python
# SQS FIFO with message group
sqs.send_message(
    QueueUrl='https://sqs.../MyQueue.fifo',
    MessageBody=json.dumps(order),
    MessageGroupId=user_id,  # Orders for same user in order
    MessageDeduplicationId=order_id
)
```

---

## Real-World Use Case: Order Processing

```mermaid
flowchart TB
    subgraph api [API Layer]
        Gateway[API Gateway]
    end

    subgraph services [Services]
        OrderSvc[Order Service]
        InventorySvc[Inventory Service]
        PaymentSvc[Payment Service]
        ShippingSvc[Shipping Service]
        NotificationSvc[Notification Service]
    end

    subgraph messaging [Messaging]
        Kafka[(Kafka)]
    end

    subgraph databases [Data Stores]
        OrderDB[(Order DB)]
        InventoryDB[(Inventory DB)]
        PaymentDB[(Payment DB)]
    end

    Gateway --> OrderSvc
    OrderSvc --> OrderDB
    OrderSvc -->|OrderCreated| Kafka

    Kafka --> InventorySvc
    Kafka --> PaymentSvc
    Kafka --> NotificationSvc

    InventorySvc --> InventoryDB
    InventorySvc -->|StockReserved| Kafka

    PaymentSvc --> PaymentDB
    PaymentSvc -->|PaymentProcessed| Kafka

    Kafka --> ShippingSvc
```

**Event Flow:**
1. `OrderCreated` → Inventory reserves stock, Notification sends confirmation
2. `StockReserved` → Payment processes charge
3. `PaymentProcessed` → Shipping creates shipment
4. `ShipmentCreated` → Notification sends tracking

**Error Handling:**
- `PaymentFailed` → Inventory releases stock, Order marked failed
- `ShipmentFailed` → Retry or manual intervention
- All failures → Logged to DLQ for investigation

---

## Best Practices

### Message Design

```json
// Good: Self-contained, versioned
{
  "event_type": "order.created.v2",
  "event_id": "evt_unique_123",
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req_xyz",
  "data": {
    "order_id": "ord_456",
    // Include necessary data, not just IDs
    "customer_email": "john@example.com",
    "items": [...]
  }
}

// Bad: Missing metadata, requires lookups
{
  "order_id": "ord_456"
}
```

### Consumer Best Practices

1. **Make consumers idempotent**
2. **Process in batches when possible**
3. **Implement proper error handling**
4. **Use dead letter queues**
5. **Monitor consumer lag**
6. **Handle poison messages**

### Producer Best Practices

1. **Include correlation IDs for tracing**
2. **Use proper serialization (Avro, Protobuf)**
3. **Handle send failures gracefully**
4. **Consider message size limits**
5. **Version your events**

---

## Summary

| Pattern | Use Case | Complexity |
|---------|----------|------------|
| **Simple Queue** | Task distribution | Low |
| **Pub/Sub** | Event broadcasting | Low |
| **Event Sourcing** | Audit trail, temporal queries | High |
| **CQRS** | Separate read/write models | Medium |
| **Saga** | Distributed transactions | High |
| **DLQ** | Error handling | Low |

---

**Previous**: [← Caching Strategies](07-caching-strategies.md) | **Next**: [API Design & Gateway →](09-api-design-gateway.md)
