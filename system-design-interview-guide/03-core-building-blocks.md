# Core Building Blocks of Distributed Systems

Every large-scale system is composed of fundamental building blocks. Understanding these components, when to use them, and how they interact is essential for system design interviews.

## System Architecture Overview

```mermaid
flowchart TB
    subgraph clients [Client Layer]
        Web[Web Browser]
        Mobile[Mobile App]
        API_Client[API Client]
    end

    subgraph edge [Edge Layer]
        DNS[DNS]
        CDN[CDN]
        LB[Load Balancer]
    end

    subgraph gateway [Gateway Layer]
        APIGateway[API Gateway]
        Auth[Auth Service]
        RateLimiter[Rate Limiter]
    end

    subgraph services [Service Layer]
        Svc1[Service A]
        Svc2[Service B]
        Svc3[Service C]
    end

    subgraph data [Data Layer]
        Cache[(Cache)]
        PrimaryDB[(Primary DB)]
        ReplicaDB[(Replica DB)]
        SearchDB[(Search)]
    end

    subgraph async [Async Layer]
        Queue[Message Queue]
        Workers[Workers]
        Scheduler[Scheduler]
    end

    subgraph storage [Storage Layer]
        Blob[Blob Storage]
        FileSystem[Distributed FS]
    end

    clients --> DNS
    DNS --> CDN
    CDN --> LB
    LB --> APIGateway
    APIGateway --> Auth
    APIGateway --> RateLimiter
    APIGateway --> services
    services --> Cache
    services --> PrimaryDB
    PrimaryDB --> ReplicaDB
    services --> SearchDB
    services --> Queue
    Queue --> Workers
    Workers --> Blob
```

---

## 1. DNS (Domain Name System)

### What It Does
Translates domain names to IP addresses. The first step in any web request.

### How It Works

```mermaid
sequenceDiagram
    participant Client
    participant LocalDNS as Local DNS
    participant RootDNS as Root DNS
    participant TLD as TLD DNS
    participant AuthDNS as Authoritative DNS

    Client->>LocalDNS: example.com?
    LocalDNS->>RootDNS: .com nameserver?
    RootDNS-->>LocalDNS: TLD server IP
    LocalDNS->>TLD: example.com nameserver?
    TLD-->>LocalDNS: Auth DNS IP
    LocalDNS->>AuthDNS: example.com IP?
    AuthDNS-->>LocalDNS: 93.184.216.34
    LocalDNS-->>Client: 93.184.216.34
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **A Record** | Maps domain to IPv4 address |
| **AAAA Record** | Maps domain to IPv6 address |
| **CNAME** | Alias to another domain |
| **TTL** | How long to cache the result |
| **DNS Load Balancing** | Return multiple IPs, round-robin |

### Use Cases in System Design
- **Geographic routing**: Route users to nearest datacenter
- **Failover**: Change DNS to backup when primary fails
- **Load distribution**: Spread traffic across multiple IPs

### Limitations
- DNS propagation can take time (TTL-dependent)
- Not suitable for real-time failover
- Limited load balancing intelligence

---

## 2. CDN (Content Delivery Network)

### What It Does
Caches static content at edge locations close to users, reducing latency and origin server load.

### How It Works

```mermaid
flowchart LR
    subgraph users [Users]
        User1[User - NYC]
        User2[User - London]
        User3[User - Tokyo]
    end

    subgraph cdn [CDN Edge Locations]
        Edge1[Edge - NYC]
        Edge2[Edge - London]
        Edge3[Edge - Tokyo]
    end

    subgraph origin [Origin]
        Origin[Origin Server - SF]
    end

    User1 --> Edge1
    User2 --> Edge2
    User3 --> Edge3
    Edge1 -.->|Cache Miss| Origin
    Edge2 -.->|Cache Miss| Origin
    Edge3 -.->|Cache Miss| Origin
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Edge Location** | Server close to users (PoP) |
| **Origin** | Source of truth for content |
| **Cache Hit/Miss** | Whether content is in edge cache |
| **TTL** | How long content is cached |
| **Invalidation** | Forcing cache refresh |
| **Pull vs Push** | On-demand vs pre-populated cache |

### What to Cache

| Content Type | Cache Duration | Example |
|--------------|----------------|---------|
| Static assets | Days to weeks | JS, CSS, images |
| Media files | Days | Videos, audio |
| API responses | Minutes to hours | User profiles, feeds |
| Dynamic HTML | Seconds | Personalized pages |

### Use Cases
- **Static content delivery**: Images, videos, JS, CSS
- **API acceleration**: Cache API responses at edge
- **DDoS protection**: Absorb attack traffic at edge
- **SSL termination**: Offload HTTPS at edge

### Popular CDNs
- Cloudflare, AWS CloudFront, Akamai, Fastly

---

## 3. Load Balancer

### What It Does
Distributes incoming traffic across multiple servers to ensure reliability and performance.

### Types of Load Balancers

```mermaid
flowchart TB
    subgraph l4 [Layer 4 - Transport]
        L4LB[L4 Load Balancer]
        L4LB -->|TCP/UDP| Server1[Server 1]
        L4LB -->|TCP/UDP| Server2[Server 2]
    end

    subgraph l7 [Layer 7 - Application]
        L7LB[L7 Load Balancer]
        L7LB -->|/api/*| APIServer[API Servers]
        L7LB -->|/static/*| StaticServer[Static Servers]
        L7LB -->|/ws/*| WSServer[WebSocket Servers]
    end
```

| Type | Layer | Decisions Based On | Use Case |
|------|-------|-------------------|----------|
| **L4** | Transport | IP, Port | High throughput, simple routing |
| **L7** | Application | URL, Headers, Cookies | Content-based routing, SSL termination |

### Load Balancing Algorithms

| Algorithm | Description | Best For |
|-----------|-------------|----------|
| **Round Robin** | Sequential distribution | Equal capacity servers |
| **Weighted Round Robin** | Based on server capacity | Mixed capacity |
| **Least Connections** | Route to least busy | Varying request duration |
| **IP Hash** | Consistent server per client | Session affinity |
| **Random** | Random selection | Simple, effective |

### Health Checks

```mermaid
sequenceDiagram
    participant LB as Load Balancer
    participant S1 as Server 1
    participant S2 as Server 2

    loop Every 5 seconds
        LB->>S1: Health check
        S1-->>LB: 200 OK
        LB->>S2: Health check
        S2--xLB: Timeout
    end

    Note over LB: Remove S2 from pool

    LB->>S1: All traffic
```

### Use Cases
- **High availability**: Failover when servers die
- **Horizontal scaling**: Add servers transparently
- **SSL termination**: Offload encryption
- **Session management**: Sticky sessions

---

## 4. API Gateway

### What It Does
Single entry point for all client requests. Handles cross-cutting concerns.

### Responsibilities

```mermaid
flowchart LR
    Client[Client] --> Gateway[API Gateway]

    subgraph gateway_functions [Gateway Functions]
        Auth[Authentication]
        RateLimit[Rate Limiting]
        Routing[Routing]
        Transform[Request Transform]
        Cache[Response Cache]
        Logging[Logging]
    end

    Gateway --> gateway_functions
    gateway_functions --> Services[Backend Services]
```

| Function | Description |
|----------|-------------|
| **Authentication** | Validate tokens, API keys |
| **Authorization** | Check permissions |
| **Rate Limiting** | Protect against abuse |
| **Request Routing** | Route to appropriate service |
| **Protocol Translation** | REST to gRPC, etc. |
| **Response Caching** | Cache common responses |
| **Request/Response Transformation** | Modify payloads |
| **Logging & Monitoring** | Centralized observability |

### Patterns

**Backend for Frontend (BFF)**
```mermaid
flowchart TB
    WebApp[Web App] --> WebBFF[Web BFF]
    MobileApp[Mobile App] --> MobileBFF[Mobile BFF]

    WebBFF --> Services[Backend Services]
    MobileBFF --> Services
```

### Use Cases
- **Microservices**: Single entry point for many services
- **Mobile apps**: Aggregate multiple API calls
- **Third-party APIs**: Expose controlled interface

### Popular Options
- Kong, AWS API Gateway, Nginx, Envoy

---

## 5. Databases

### SQL vs NoSQL Decision Tree

```mermaid
flowchart TB
    Start[Start] --> Q1{Need ACID transactions?}
    Q1 -->|Yes| SQL1[Consider SQL]
    Q1 -->|No| Q2{Fixed schema?}

    Q2 -->|Yes| SQL2[Consider SQL]
    Q2 -->|No| NoSQL1[Consider NoSQL]

    SQL1 --> Q3{Need massive scale?}
    SQL2 --> Q3

    Q3 -->|Yes| NewSQL[Consider NewSQL<br/>CockroachDB, Spanner]
    Q3 -->|No| SQL[PostgreSQL, MySQL]

    NoSQL1 --> Q4{Data model?}
    Q4 -->|Key-Value| KV[Redis, DynamoDB]
    Q4 -->|Document| Doc[MongoDB, Couchbase]
    Q4 -->|Column| Col[Cassandra, HBase]
    Q4 -->|Graph| Graph[Neo4j, Neptune]
```

### Database Types

| Type | Data Model | Use Cases | Examples |
|------|------------|-----------|----------|
| **Relational** | Tables, rows | Transactions, complex queries | PostgreSQL, MySQL |
| **Key-Value** | Key → Value | Caching, sessions | Redis, DynamoDB |
| **Document** | JSON documents | Content management, catalogs | MongoDB, Couchbase |
| **Column-Family** | Columns grouped | Time-series, analytics | Cassandra, HBase |
| **Graph** | Nodes, edges | Social networks, recommendations | Neo4j, Neptune |
| **Time-Series** | Timestamp → values | Metrics, IoT | InfluxDB, TimescaleDB |

### When to Use What

| Requirement | Database Choice |
|-------------|-----------------|
| ACID transactions | PostgreSQL, MySQL |
| High write throughput | Cassandra, ScyllaDB |
| Flexible schema | MongoDB |
| Caching | Redis, Memcached |
| Full-text search | Elasticsearch |
| Graph relationships | Neo4j |
| Time-series data | InfluxDB, TimescaleDB |

---

## 6. Cache

### What It Does
Stores frequently accessed data in memory for fast retrieval.

### Caching Layers

```mermaid
flowchart LR
    Client[Client] --> CDN[CDN Cache]
    CDN --> LB[Load Balancer]
    LB --> AppCache[Application Cache]
    AppCache --> DBCache[Database Cache]
    DBCache --> DB[(Database)]

    style CDN fill:#e1f5fe
    style AppCache fill:#e1f5fe
    style DBCache fill:#e1f5fe
```

| Layer | Location | What's Cached |
|-------|----------|---------------|
| **Browser** | Client | Static assets, API responses |
| **CDN** | Edge | Static content, some API |
| **Application** | Server memory | Computed results, sessions |
| **Distributed Cache** | Redis/Memcached | Shared data across servers |
| **Database** | DB buffer pool | Query results, indexes |

### Cache Strategies

| Strategy | How It Works | Use Case |
|----------|--------------|----------|
| **Cache-Aside** | App manages cache manually | General purpose |
| **Read-Through** | Cache loads on miss | Simplicity |
| **Write-Through** | Write to cache and DB | Consistency |
| **Write-Behind** | Write to cache, async to DB | Performance |
| **Refresh-Ahead** | Proactive refresh | Predictable access |

### Cache Eviction Policies

| Policy | Description | Use Case |
|--------|-------------|----------|
| **LRU** | Least Recently Used | General purpose |
| **LFU** | Least Frequently Used | Stable popularity |
| **FIFO** | First In First Out | Simple, time-based |
| **TTL** | Time To Live | Data freshness |

### Redis vs Memcached

| Feature | Redis | Memcached |
|---------|-------|-----------|
| Data Structures | Rich (lists, sets, hashes) | Simple strings |
| Persistence | Yes | No |
| Replication | Yes | No |
| Clustering | Yes | Client-side |
| Memory Efficiency | Lower | Higher |

---

## 7. Message Queue

### What It Does
Enables asynchronous communication between services. Decouples producers and consumers.

### How It Works

```mermaid
flowchart LR
    subgraph producers [Producers]
        P1[Service A]
        P2[Service B]
    end

    subgraph queue [Message Queue]
        Q[Queue/Topic]
    end

    subgraph consumers [Consumers]
        C1[Worker 1]
        C2[Worker 2]
        C3[Worker 3]
    end

    P1 --> Q
    P2 --> Q
    Q --> C1
    Q --> C2
    Q --> C3
```

### Queue vs Topic (Pub/Sub)

| Aspect | Queue | Topic (Pub/Sub) |
|--------|-------|-----------------|
| Consumers | One consumer per message | All subscribers get message |
| Use Case | Task distribution | Event broadcasting |
| Example | Order processing | Price updates |

### Delivery Guarantees

| Guarantee | Description | Trade-off |
|-----------|-------------|-----------|
| **At-most-once** | Message may be lost | Fast, no duplicates |
| **At-least-once** | Message may be duplicated | Safe, needs idempotency |
| **Exactly-once** | Message delivered once | Slow, complex |

### Popular Options

| System | Best For | Key Feature |
|--------|----------|-------------|
| **Kafka** | High throughput streaming | Partitioned log, replay |
| **RabbitMQ** | Complex routing | Flexible exchanges |
| **AWS SQS** | Managed simplicity | Serverless, auto-scaling |
| **Redis Pub/Sub** | Real-time, simple | Low latency |

### Use Cases
- **Order processing**: Decouple order creation from fulfillment
- **Notifications**: Send emails, push notifications async
- **Data pipelines**: Stream processing, ETL
- **Event sourcing**: Store events as source of truth

---

## 8. Search Engine

### What It Does
Enables fast full-text search over large datasets.

### How It Works

```mermaid
flowchart TB
    subgraph indexing [Indexing Pipeline]
        Data[Source Data] --> Analyzer[Analyzer]
        Analyzer --> Tokenizer[Tokenizer]
        Tokenizer --> Index[Inverted Index]
    end

    subgraph search [Search Pipeline]
        Query[Search Query] --> Parser[Query Parser]
        Parser --> Scorer[Scorer]
        Scorer --> Results[Ranked Results]
    end

    Index --> Scorer
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Inverted Index** | Word → Document IDs mapping |
| **Tokenization** | Breaking text into searchable tokens |
| **Analyzers** | Language-specific text processing |
| **Relevance Scoring** | TF-IDF, BM25 algorithms |
| **Facets** | Aggregations for filtering |

### Elasticsearch Architecture

```mermaid
flowchart TB
    subgraph cluster [Elasticsearch Cluster]
        subgraph node1 [Node 1]
            P1[Primary Shard 1]
            R2[Replica Shard 2]
        end

        subgraph node2 [Node 2]
            P2[Primary Shard 2]
            R1[Replica Shard 1]
        end

        subgraph node3 [Node 3]
            P3[Primary Shard 3]
            R3[Replica Shard 3]
        end
    end
```

### Use Cases
- **Product search**: E-commerce catalog
- **Log analysis**: ELK stack
- **Autocomplete**: Type-ahead suggestions
- **Geospatial search**: Location-based queries

---

## 9. Blob Storage

### What It Does
Stores unstructured data (images, videos, files) at massive scale.

### Key Features

| Feature | Description |
|---------|-------------|
| **Durability** | 99.999999999% (11 9s) |
| **Scalability** | Petabytes of data |
| **Cost-effective** | Tiered storage (hot/cold) |
| **CDN Integration** | Direct edge delivery |

### Storage Tiers

| Tier | Access Pattern | Cost | Use Case |
|------|----------------|------|----------|
| **Hot** | Frequent access | $$$ | Active data |
| **Warm** | Occasional access | $$ | 30-day retention |
| **Cold** | Rare access | $ | Archives |
| **Archive** | Near-zero access | ¢ | Compliance |

### Popular Options
- AWS S3, Google Cloud Storage, Azure Blob Storage

### Use Cases
- **Media storage**: Images, videos, audio
- **Backups**: Database dumps, snapshots
- **Static hosting**: Websites, documentation
- **Data lakes**: Raw data for analytics

---

## 10. Coordination Service

### What It Does
Provides distributed synchronization, configuration, and leader election.

### Key Features

| Feature | Description |
|---------|-------------|
| **Distributed Locks** | Prevent concurrent access |
| **Leader Election** | Choose a single leader |
| **Configuration** | Centralized config storage |
| **Service Registry** | Track available services |

### ZooKeeper Use Cases

```mermaid
flowchart TB
    subgraph zk [ZooKeeper Ensemble]
        ZK1[ZK Node 1]
        ZK2[ZK Node 2]
        ZK3[ZK Node 3]
    end

    subgraph services [Services]
        S1[Service 1]
        S2[Service 2]
        S3[Service 3]
    end

    S1 --> zk
    S2 --> zk
    S3 --> zk

    zk --> Config[Config Management]
    zk --> Lock[Distributed Locks]
    zk --> Leader[Leader Election]
    zk --> Registry[Service Registry]
```

### Popular Options
- ZooKeeper, etcd, Consul

---

## Component Selection Cheat Sheet

### By Use Case

| Use Case | Primary Choice | Alternative |
|----------|----------------|-------------|
| **Caching** | Redis | Memcached |
| **Primary Database** | PostgreSQL | MySQL |
| **Document Store** | MongoDB | Couchbase |
| **High Write Throughput** | Cassandra | ScyllaDB |
| **Message Queue** | Kafka | RabbitMQ |
| **Search** | Elasticsearch | Solr |
| **Blob Storage** | S3 | GCS |
| **Coordination** | ZooKeeper | etcd |
| **API Gateway** | Kong | AWS API Gateway |

### By Scale

| Scale | Infrastructure Approach |
|-------|------------------------|
| **MVP** | Monolith, single DB, no cache |
| **Growth** | Add cache, read replicas |
| **Scale** | Microservices, sharding, CDN |
| **Massive** | Multi-region, custom solutions |

---

## Summary

Understanding these building blocks is fundamental to system design:

1. **DNS & CDN**: First line of defense, reduce latency
2. **Load Balancer**: Distribute traffic, enable scaling
3. **API Gateway**: Centralize cross-cutting concerns
4. **Databases**: Choose based on data model and scale
5. **Cache**: Speed up reads, reduce DB load
6. **Message Queue**: Decouple services, enable async
7. **Search Engine**: Fast full-text queries
8. **Blob Storage**: Store unstructured data at scale
9. **Coordination Service**: Distributed synchronization

---

**Previous**: [← Requirements & Estimation](02-requirements-estimation.md) | **Next**: [Scalability Patterns →](04-scalability-patterns.md)
