# Scalability Patterns

Scalability is the ability of a system to handle increased load by adding resources. This guide covers the fundamental patterns for scaling systems horizontally and vertically.

## Scaling Fundamentals

### Vertical vs Horizontal Scaling

```mermaid
flowchart TB
    subgraph vertical [Vertical Scaling - Scale Up]
        V1[Small Server<br/>2 CPU, 4GB RAM]
        V2[Medium Server<br/>8 CPU, 32GB RAM]
        V3[Large Server<br/>64 CPU, 512GB RAM]
        V1 --> V2 --> V3
    end

    subgraph horizontal [Horizontal Scaling - Scale Out]
        H1[Server 1]
        H2[Server 2]
        H3[Server 3]
        H4[Server 4]
        H5[Server N...]
    end
```

| Aspect | Vertical Scaling | Horizontal Scaling |
|--------|-----------------|-------------------|
| **Approach** | Bigger machine | More machines |
| **Limit** | Hardware ceiling | Theoretically unlimited |
| **Downtime** | Required for upgrade | Zero downtime |
| **Cost** | Expensive at scale | Cost-effective |
| **Complexity** | Simple | Complex (distributed) |
| **Failure** | Single point of failure | Fault tolerant |

### When to Use Which

```mermaid
flowchart TB
    Start[Need to Scale?] --> Q1{Current load<br/>manageable?}
    Q1 -->|Yes| Wait[Wait and Monitor]
    Q1 -->|No| Q2{Quick fix needed?}

    Q2 -->|Yes| Vertical[Vertical Scale<br/>Upgrade hardware]
    Q2 -->|No| Q3{Stateless service?}

    Q3 -->|Yes| Horizontal[Horizontal Scale<br/>Add instances]
    Q3 -->|No| Q4{Can make stateless?}

    Q4 -->|Yes| Refactor[Refactor to Stateless]
    Q4 -->|No| Vertical2[Vertical + Sharding]

    Refactor --> Horizontal
```

---

## Database Scaling Patterns

### 1. Read Replicas

Distribute read traffic across multiple database copies.

```mermaid
flowchart TB
    subgraph app [Application Layer]
        App1[App Server 1]
        App2[App Server 2]
    end

    subgraph db [Database Layer]
        Primary[(Primary DB<br/>Writes)]
        Replica1[(Replica 1<br/>Reads)]
        Replica2[(Replica 2<br/>Reads)]
        Replica3[(Replica 3<br/>Reads)]
    end

    App1 -->|Writes| Primary
    App2 -->|Writes| Primary
    Primary -->|Async Replication| Replica1
    Primary -->|Async Replication| Replica2
    Primary -->|Async Replication| Replica3
    App1 -->|Reads| Replica1
    App1 -->|Reads| Replica2
    App2 -->|Reads| Replica2
    App2 -->|Reads| Replica3
```

**When to Use:**
- Read-heavy workloads (10:1 or higher read:write ratio)
- Geographic distribution needed
- Reporting queries that shouldn't impact production

**Trade-offs:**
- Replication lag (eventual consistency)
- Added complexity
- Doesn't help with write scaling

### 2. Database Sharding

Partition data across multiple database instances.

```mermaid
flowchart TB
    App[Application] --> Router[Shard Router]

    Router -->|user_id % 4 = 0| Shard1[(Shard 1<br/>Users 0-25M)]
    Router -->|user_id % 4 = 1| Shard2[(Shard 2<br/>Users 25-50M)]
    Router -->|user_id % 4 = 2| Shard3[(Shard 3<br/>Users 50-75M)]
    Router -->|user_id % 4 = 3| Shard4[(Shard 4<br/>Users 75-100M)]
```

#### Sharding Strategies

| Strategy | How It Works | Pros | Cons |
|----------|--------------|------|------|
| **Hash-based** | `shard = hash(key) % n` | Even distribution | Resharding is hard |
| **Range-based** | `shard = key_range` | Easy range queries | Hot spots possible |
| **Directory-based** | Lookup table | Flexible | Single point of failure |
| **Geographic** | By region/location | Data locality | Cross-region queries hard |

#### Choosing a Shard Key

| Good Shard Key | Bad Shard Key |
|----------------|---------------|
| `user_id` (even distribution) | `created_at` (time-based hot spot) |
| `customer_id` (for B2B) | `country` (uneven distribution) |
| `order_id` (hash-based) | `status` (few values) |

#### Shard Key Selection Decision Tree

```mermaid
flowchart TB
    Start[Choose Shard Key] --> Q1{High cardinality?}
    Q1 -->|No| Bad1[Bad: Too few values]
    Q1 -->|Yes| Q2{Even distribution?}

    Q2 -->|No| Bad2[Bad: Hot spots]
    Q2 -->|Yes| Q3{Supports query patterns?}

    Q3 -->|No| Bad3[Bad: Cross-shard queries]
    Q3 -->|Yes| Q4{Immutable?}

    Q4 -->|No| Bad4[Bad: Resharding needed]
    Q4 -->|Yes| Good[Good Shard Key!]
```

### 3. Consistent Hashing

Minimizes data movement when adding/removing nodes.

```mermaid
flowchart LR
    subgraph ring [Hash Ring]
        direction TB
        N1[Node 1<br/>0-90°]
        N2[Node 2<br/>90-180°]
        N3[Node 3<br/>180-270°]
        N4[Node 4<br/>270-360°]
    end

    K1[Key A] -.->|hash| N1
    K2[Key B] -.->|hash| N2
    K3[Key C] -.->|hash| N3
```

**How It Works:**
1. Hash both nodes and keys to positions on a ring
2. Each key is assigned to the first node clockwise from its position
3. When a node is added/removed, only keys in that segment move

**Benefits:**
- Adding a node: Only `1/n` keys need to move
- Removing a node: Only that node's keys redistribute
- Virtual nodes prevent uneven distribution

**Use Cases:**
- Distributed caches (Memcached, Redis Cluster)
- Load balancers
- CDN edge selection

---

## Application Scaling Patterns

### 1. Stateless Services

Services that don't store session state locally.

```mermaid
flowchart TB
    LB[Load Balancer] --> S1[Server 1]
    LB --> S2[Server 2]
    LB --> S3[Server 3]

    S1 --> Session[(Session Store<br/>Redis)]
    S2 --> Session
    S3 --> Session

    S1 --> DB[(Database)]
    S2 --> DB
    S3 --> DB
```

**How to Achieve:**
- Store session in external store (Redis, database)
- Use JWT tokens for authentication (stateless)
- Cache results in distributed cache

**Benefits:**
- Any server can handle any request
- Easy horizontal scaling
- Simple deployment (rolling updates)

### 2. Stateful Services

When state must be maintained (e.g., WebSocket connections, game servers).

```mermaid
flowchart TB
    LB[Load Balancer<br/>Sticky Sessions] --> S1[Server 1<br/>Clients A, B]
    LB --> S2[Server 2<br/>Clients C, D]
    LB --> S3[Server 3<br/>Clients E, F]

    S1 -.->|State Sync| Coordinator[(Coordinator<br/>ZooKeeper)]
    S2 -.->|State Sync| Coordinator
    S3 -.->|State Sync| Coordinator
```

**Approaches:**
- Sticky sessions (route same client to same server)
- State synchronization between servers
- Partitioned state (each server owns certain data)

**Use Cases:**
- Real-time collaboration (Google Docs)
- Multiplayer games
- WebSocket connections

### 3. Service Decomposition

Break monolith into independent, scalable services.

```mermaid
flowchart TB
    subgraph before [Monolith]
        Mono[All Features<br/>in One Service]
    end

    subgraph after [Microservices]
        Gateway[API Gateway]
        Auth[Auth Service]
        Users[User Service]
        Orders[Order Service]
        Payments[Payment Service]
        Notifications[Notification Service]

        Gateway --> Auth
        Gateway --> Users
        Gateway --> Orders
        Gateway --> Payments
        Orders --> Payments
        Orders --> Notifications
    end
```

**Benefits:**
- Scale services independently
- Different tech stacks per service
- Independent deployments
- Fault isolation

**When to Decompose:**
- Different scaling needs (CPU vs I/O)
- Different team ownership
- Different release cycles

---

## Caching for Scale

### Multi-Layer Caching

```mermaid
flowchart LR
    Client[Client] --> Browser[Browser Cache]
    Browser --> CDN[CDN Cache]
    CDN --> LB[Load Balancer]
    LB --> App[App Cache<br/>Local Memory]
    App --> Distributed[Distributed Cache<br/>Redis]
    Distributed --> DB[(Database)]

    style Browser fill:#e8f5e9
    style CDN fill:#e8f5e9
    style App fill:#e8f5e9
    style Distributed fill:#e8f5e9
```

### Cache Sizing

```
Cache Hit Rate Formula:
Hit Rate = (Total Requests - Cache Misses) / Total Requests

Cache Size Estimation:
If 20% of data serves 80% of requests (Pareto):
Cache Size = 0.2 × Total Data Size

Example:
Total data: 100 GB
Cache needed: 20 GB for ~80% hit rate
```

### Write Scaling with Caching

| Pattern | Write Path | Read Path | Use Case |
|---------|------------|-----------|----------|
| **Cache-Aside** | DB only | Cache then DB | General purpose |
| **Write-Through** | Cache + DB sync | Cache only | Consistency needed |
| **Write-Behind** | Cache, async DB | Cache only | High write throughput |

---

## Async Processing

### Queue-Based Load Leveling

```mermaid
flowchart LR
    subgraph burst [Burst Traffic]
        R1[Request 1]
        R2[Request 2]
        R3[Request 3]
        R4[Request N]
    end

    burst --> Queue[Message Queue]

    subgraph steady [Steady Processing]
        W1[Worker 1]
        W2[Worker 2]
    end

    Queue --> steady

    Note1[Peak: 10K/sec] -.-> burst
    Note2[Steady: 1K/sec] -.-> steady
```

**Benefits:**
- Absorb traffic spikes
- Workers process at sustainable rate
- Prevents system overload

### Event-Driven Architecture

```mermaid
flowchart TB
    Event[Order Created Event]

    Event --> Inventory[Inventory Service]
    Event --> Shipping[Shipping Service]
    Event --> Analytics[Analytics Service]
    Event --> Email[Email Service]

    Inventory --> InvDB[(Update Stock)]
    Shipping --> ShipDB[(Create Shipment)]
    Analytics --> AnalyDB[(Record Sale)]
    Email --> SMTP[Send Confirmation]
```

**Benefits:**
- Services scale independently
- Loose coupling
- Natural event logging
- Easy to add new consumers

---

## Data Partitioning Patterns

### Functional Partitioning

Split by function/domain, not by data.

```mermaid
flowchart TB
    subgraph partition1 [User Data Partition]
        UserDB[(User DB)]
        ProfileDB[(Profile DB)]
    end

    subgraph partition2 [Order Data Partition]
        OrderDB[(Order DB)]
        PaymentDB[(Payment DB)]
    end

    subgraph partition3 [Analytics Partition]
        EventsDB[(Events DB)]
        ReportsDB[(Reports DB)]
    end
```

### Geographic Partitioning

Route users to nearest data center.

```mermaid
flowchart TB
    subgraph dns [Global DNS]
        DNS[GeoDNS]
    end

    subgraph us [US Region]
        US_LB[Load Balancer]
        US_DB[(US Database)]
    end

    subgraph eu [EU Region]
        EU_LB[Load Balancer]
        EU_DB[(EU Database)]
    end

    subgraph asia [Asia Region]
        Asia_LB[Load Balancer]
        Asia_DB[(Asia Database)]
    end

    DNS -->|US Users| US_LB
    DNS -->|EU Users| EU_LB
    DNS -->|Asia Users| Asia_LB

    US_LB --> US_DB
    EU_LB --> EU_DB
    Asia_LB --> Asia_DB
```

**Considerations:**
- Data sovereignty (GDPR)
- Cross-region queries
- Replication strategy

---

## Auto-Scaling

### Metrics-Based Scaling

```mermaid
flowchart LR
    subgraph metrics [Metrics]
        CPU[CPU Usage]
        Memory[Memory Usage]
        Queue[Queue Length]
        Latency[Response Latency]
    end

    metrics --> Monitor[Auto-Scaler]

    Monitor -->|Scale Up| Add[Add Instances]
    Monitor -->|Scale Down| Remove[Remove Instances]
```

### Scaling Policies

| Metric | Scale Up When | Scale Down When |
|--------|---------------|-----------------|
| CPU | > 70% for 3 min | < 30% for 10 min |
| Memory | > 80% | < 40% for 10 min |
| Queue Length | > 1000 messages | < 100 messages |
| Latency | P99 > 500ms | P99 < 100ms |

### Predictive Scaling

```mermaid
flowchart LR
    Historical[Historical Data] --> ML[ML Model]
    ML --> Prediction[Traffic Prediction]
    Prediction --> PreScale[Pre-Scale<br/>Before Peak]
```

---

## Anti-Patterns to Avoid

### 1. Premature Scaling

```
❌ Wrong: "Let's shard from day one for future scale"
✅ Right: "Let's design for sharding but implement when needed"
```

### 2. Ignoring Data Locality

```
❌ Wrong: Separate user data across random shards
✅ Right: Co-locate related data (user + user's orders)
```

### 3. Cross-Shard Transactions

```
❌ Wrong: Transaction spanning multiple shards
✅ Right: Design to avoid cross-shard transactions
```

### 4. No Circuit Breakers

```mermaid
flowchart LR
    subgraph bad [Without Circuit Breaker]
        A1[Service A] -->|Retry forever| B1[Service B - Down]
        A1 -->|Cascading failure| C1[Service C]
    end

    subgraph good [With Circuit Breaker]
        A2[Service A] -->|Open circuit| CB[Circuit Breaker]
        CB -->|Fail fast| Fallback[Fallback Response]
    end
```

---

## Scaling Checklist

### Before You Scale

- [ ] Profile and identify actual bottlenecks
- [ ] Measure current performance baseline
- [ ] Determine scaling targets (2x? 10x? 100x?)
- [ ] Consider cost implications

### Application Layer

- [ ] Stateless service design
- [ ] Horizontal scaling capability
- [ ] Health checks implemented
- [ ] Graceful shutdown handling

### Data Layer

- [ ] Read replicas for read scaling
- [ ] Caching layer implemented
- [ ] Sharding strategy defined
- [ ] Connection pooling configured

### Infrastructure

- [ ] Load balancer configured
- [ ] Auto-scaling policies set
- [ ] CDN for static content
- [ ] Monitoring and alerting

---

## Use Case: Scaling a Read-Heavy Application

**Scenario**: E-commerce product catalog with 100K QPS reads, 100 QPS writes

```mermaid
flowchart TB
    subgraph clients [Clients - 100K QPS]
        Users[Users]
    end

    subgraph edge [Edge Layer]
        CDN[CDN<br/>Static Assets]
    end

    subgraph app [Application Layer]
        LB[Load Balancer]
        API1[API Server 1]
        API2[API Server 2]
        API3[API Server N]
    end

    subgraph cache [Cache Layer - 90% hit rate]
        Redis1[(Redis 1)]
        Redis2[(Redis 2)]
        Redis3[(Redis 3)]
    end

    subgraph db [Database Layer - 10K QPS]
        Primary[(Primary<br/>Writes)]
        Replica1[(Replica 1)]
        Replica2[(Replica 2)]
        Replica3[(Replica 3)]
    end

    Users --> CDN
    CDN --> LB
    LB --> API1
    LB --> API2
    LB --> API3
    API1 --> Redis1
    API2 --> Redis2
    API3 --> Redis3
    Redis1 -.->|Miss| Replica1
    Redis2 -.->|Miss| Replica2
    Redis3 -.->|Miss| Replica3
    Primary --> Replica1
    Primary --> Replica2
    Primary --> Replica3
```

**Key Decisions:**
1. **CDN**: Cache product images, reduce origin traffic
2. **Distributed Cache**: 90% hit rate means only 10K QPS to DB
3. **Read Replicas**: Distribute 10K read QPS across replicas
4. **Stateless APIs**: Scale horizontally as needed

---

## Summary

| Pattern | When to Use | Key Benefit |
|---------|-------------|-------------|
| **Vertical Scaling** | Quick fix, small scale | Simple |
| **Horizontal Scaling** | Sustainable growth | No ceiling |
| **Read Replicas** | Read-heavy workloads | Easy read scaling |
| **Sharding** | Write scaling needed | Unlimited data |
| **Consistent Hashing** | Dynamic cluster | Minimal resharding |
| **Stateless Services** | Any web service | Easy scaling |
| **Caching** | Repeat reads | Reduce DB load |
| **Async Processing** | Spiky traffic | Level load |

---

**Previous**: [← Core Building Blocks](03-core-building-blocks.md) | **Next**: [Distributed System Concepts →](05-distributed-system-concepts.md)
