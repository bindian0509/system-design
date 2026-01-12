# System Design Quick Reference Cheatsheet

A one-page summary of everything you need for system design interviews. Print this out or keep it handy for quick review.

---

## The Interview Framework (45-60 min)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. REQUIREMENTS (5 min)          │ 2. HIGH-LEVEL DESIGN (15 min)│
│ • Functional requirements        │ • Draw architecture diagram  │
│ • Non-functional (scale, SLAs)   │ • Core components & data flow│
│ • Back-of-envelope estimation    │ • API design (key endpoints) │
│                                  │ • Data model (main entities) │
├─────────────────────────────────────────────────────────────────┤
│ 3. DEEP DIVE (20 min)            │ 4. WRAP UP (5 min)           │
│ • Database design & scaling      │ • Identify bottlenecks       │
│ • Caching strategy               │ • Monitoring & alerting      │
│ • Handle edge cases              │ • Future improvements        │
│ • Discuss trade-offs             │ • Q&A                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Numbers to Remember

### Latency

| Operation | Latency |
|-----------|---------|
| L1 cache | 1 ns |
| L2 cache | 4 ns |
| RAM | 100 ns |
| SSD read | 16 μs |
| HDD seek | 2 ms |
| Datacenter round trip | 500 μs |
| Cross-continent | 150 ms |

### Data Sizes

| Unit | Size | Practical |
|------|------|-----------|
| 1 KB | 1,024 B | Small JSON |
| 1 MB | 1,024 KB | High-res photo |
| 1 GB | 1,024 MB | 1 hour HD video |
| 1 TB | 1,024 GB | 500 hours HD |
| 1 PB | 1,024 TB | Large enterprise |

### Quick Math

```
1 day    = 86,400 sec ≈ 100,000 sec
1 month  = 2.5 million sec
1 year   = 30 million sec

1 million  = 10^6
1 billion  = 10^9
1 trillion = 10^12
```

### Availability

| SLO | Downtime/Year | Downtime/Month |
|-----|---------------|----------------|
| 99% | 3.65 days | 7.3 hours |
| 99.9% | 8.76 hours | 43.2 min |
| 99.99% | 52.6 min | 4.3 min |
| 99.999% | 5.26 min | 26 sec |

---

## Estimation Formulas

```
QPS = (DAU × actions/user) / 86,400
Peak QPS = QPS × 3

Storage/day = Write_QPS × 86,400 × data_size
Storage/year = Storage/day × 365
Total = Storage/year × years × replication_factor

Bandwidth = QPS × response_size
```

---

## Component Selection

### When to Use What

| Need | Choose | Alternative |
|------|--------|-------------|
| Relational + ACID | PostgreSQL | MySQL |
| High write volume | Cassandra | ScyllaDB |
| Document store | MongoDB | Couchbase |
| Caching | Redis | Memcached |
| Search | Elasticsearch | Solr |
| Message queue | Kafka | RabbitMQ |
| Object storage | S3 | GCS |
| Time-series | InfluxDB | TimescaleDB |

### SQL vs NoSQL Decision

```
Need ACID transactions? → SQL
Need flexible schema?   → NoSQL
Need massive scale?     → NoSQL
Need complex queries?   → SQL
Need graph traversal?   → Graph DB
Need text search?       → Search engine
```

---

## Scaling Patterns

### Horizontal vs Vertical

| Vertical | Horizontal |
|----------|------------|
| Bigger machine | More machines |
| Simple | Complex |
| Has ceiling | Unlimited |
| Single point of failure | Fault tolerant |

### Database Scaling

```
1. Add read replicas (10:1 read/write)
2. Add caching layer (80-95% hit rate)
3. Shard when single node can't handle writes
```

### Sharding Strategies

| Strategy | Use When |
|----------|----------|
| Hash | Even distribution needed |
| Range | Range queries needed |
| Geographic | Data locality needed |

---

## Caching

### Cache Patterns

| Pattern | Write Latency | Consistency |
|---------|---------------|-------------|
| Cache-aside | Normal | Eventually |
| Write-through | Higher | Strong |
| Write-behind | Very low | Eventually |

### Cache Eviction

- **LRU**: Evict least recently used (default choice)
- **LFU**: Evict least frequently used
- **TTL**: Expire after time

### Cache Hit Rate Impact

| Hit Rate | DB Load |
|----------|---------|
| 80% | 20% |
| 90% | 10% |
| 95% | 5% |
| 99% | 1% |

---

## Consistency Models

### CAP Trade-offs

| Choice | During Partition | Example |
|--------|------------------|---------|
| CP | Reject requests | Banking, ZooKeeper |
| AP | Accept, reconcile later | Social media, Cassandra |

### Consistency Spectrum

```
Strong ← → Eventual
(slow)    (fast)
```

| Model | Use Case |
|-------|----------|
| Strong | Banking, inventory |
| Eventual | Social feeds, analytics |
| Causal | Collaborative editing |

---

## Messaging

### Delivery Guarantees

| Guarantee | Behavior | When |
|-----------|----------|------|
| At-most-once | May lose | Metrics, logs |
| At-least-once | May duplicate | Most systems |
| Exactly-once | No loss/dupe | Payments (expensive) |

### Kafka vs RabbitMQ

| Kafka | RabbitMQ |
|-------|----------|
| High throughput | Complex routing |
| Replay capability | Lower latency |
| Event streaming | Traditional queuing |

---

## API Design

### REST Best Practices

| Method | Action | Idempotent |
|--------|--------|------------|
| GET | Read | Yes |
| POST | Create | No |
| PUT | Replace | Yes |
| PATCH | Update | No |
| DELETE | Remove | Yes |

### Rate Limiting Algorithms

| Algorithm | Burst | Accuracy |
|-----------|-------|----------|
| Token bucket | Yes | Exact |
| Sliding window | Smooth | Approximate |
| Leaky bucket | No | Exact |

---

## Reliability Patterns

### Fault Tolerance

| Pattern | Purpose |
|---------|---------|
| Circuit breaker | Fail fast |
| Retry + backoff | Handle transient |
| Bulkhead | Isolate failures |
| Timeout | Prevent hanging |
| Fallback | Degrade gracefully |

### Health Checks

| Type | Purpose | Action on Failure |
|------|---------|-------------------|
| Liveness | Is it alive? | Restart |
| Readiness | Can serve traffic? | Remove from LB |

---

## Observability

### Three Pillars

| Pillar | What | Example Tool |
|--------|------|--------------|
| Metrics | Numbers | Prometheus |
| Logs | Events | ELK Stack |
| Traces | Flow | Jaeger |

### Key Metrics (RED)

- **R**ate: Requests per second
- **E**rrors: Error rate
- **D**uration: Latency (P50, P95, P99)

---

## Common Problems Quick Reference

| Problem | Key Component | Key Challenge |
|---------|---------------|---------------|
| URL Shortener | Base62 + ID gen | Collision, scale |
| Rate Limiter | Token bucket + Redis | Distribution |
| Chat | WebSocket + Queue | Delivery guarantee |
| News Feed | Fan-out + Ranking | Celebrity problem |
| Autocomplete | Trie + Cache | Latency, freshness |
| File Storage | Chunking + Sync | Conflicts |
| Video | CDN + Transcode | Encoding, cost |
| Ride Sharing | Geospatial (H3) | Matching speed |

---

## Red Flags to Avoid

| Red Flag | Why Bad | Do Instead |
|----------|---------|------------|
| Jump to solution | Shows no structure | Clarify requirements first |
| Single DB for everything | Won't scale | Consider polyglot persistence |
| No caching | Unnecessary load | Cache at multiple layers |
| Single point of failure | Low availability | Add redundancy |
| No trade-off discussion | Incomplete thinking | Every choice has trade-offs |
| No numbers | Vague arguments | Estimate and calculate |
| Over-engineering | Wastes time | Start simple, scale when needed |

---

## Magic Phrases

```
"Let me clarify the requirements first..."
"Given the scale requirements, I'd recommend..."
"The trade-off here is between X and Y..."
"To handle the failure scenario..."
"Let me do some quick math..."
"One potential bottleneck is..."
"We can mitigate this by..."
```

---

## Architecture Template

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENTS                               │
│               Web / Mobile / Third-party                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                      CDN / DNS                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   LOAD BALANCER                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   API GATEWAY                                │
│           Auth / Rate Limit / Routing                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   SERVICES                                   │
│        Service A │ Service B │ Service C                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌──────────┬──────────┼──────────┬──────────┬─────────────────┐
│  CACHE   │   DB     │  SEARCH  │  QUEUE   │  BLOB STORAGE   │
│  Redis   │ Postgres │   ES     │  Kafka   │    S3           │
└──────────┴──────────┴──────────┴──────────┴─────────────────┘
```

---

## Final Checklist

Before ending your interview, make sure you've covered:

- [ ] Clarified all requirements
- [ ] Calculated scale numbers
- [ ] Drew clear architecture diagram
- [ ] Explained database choice
- [ ] Discussed caching strategy
- [ ] Addressed scaling approach
- [ ] Covered failure scenarios
- [ ] Mentioned monitoring
- [ ] Discussed trade-offs
- [ ] Left time for questions

---

## Quick Links to Deep Dives

| Topic | Link |
|-------|------|
| Interview Framework | [01-interview-framework.md](01-interview-framework.md) |
| Estimation | [02-requirements-estimation.md](02-requirements-estimation.md) |
| Building Blocks | [03-core-building-blocks.md](03-core-building-blocks.md) |
| Scaling | [04-scalability-patterns.md](04-scalability-patterns.md) |
| Distributed Systems | [05-distributed-system-concepts.md](05-distributed-system-concepts.md) |
| Databases | [06-data-storage-strategies.md](06-data-storage-strategies.md) |
| Caching | [07-caching-strategies.md](07-caching-strategies.md) |
| Messaging | [08-messaging-async-patterns.md](08-messaging-async-patterns.md) |
| APIs | [09-api-design-gateway.md](09-api-design-gateway.md) |
| Reliability | [10-observability-reliability.md](10-observability-reliability.md) |
| Problems | [11-common-interview-problems.md](11-common-interview-problems.md) |

---

**Good luck with your interview!**

Remember: There's no perfect answer. Show your thought process, discuss trade-offs, and communicate clearly.

---

**Previous**: [← Common Interview Problems](11-common-interview-problems.md) | **Home**: [README →](README.md)
