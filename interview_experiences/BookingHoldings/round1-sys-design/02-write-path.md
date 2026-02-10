# 02 — Write Path Deep Dive

## Overview

The write path is designed around three principles:
1. **Decouple ingestion from persistence** — API responds immediately, MySQL writes happen async
2. **Absorb bursts** — Kafka acts as a shock absorber between variable-rate producers and fixed-rate MySQL consumers
3. **Maximize MySQL efficiency** — Batch inserts to amortize transaction overhead

```mermaid
graph LR
    subgraph "1. Accept (μs)"
        MS[Microservice] -->|POST /logs| API[API Server]
        API -->|202| MS
    end

    subgraph "2. Buffer (ms)"
        API -->|Produce| KF[Kafka]
    end

    subgraph "3. Persist (sec)"
        KF -->|Consume batch| WW[Writer Worker]
        WW -->|Bulk INSERT| MY[(MySQL)]
    end

    style API fill:#f5a623,color:#000
    style KF fill:#4a90d9,color:#fff
    style MY fill:#7b68ee,color:#fff
```

## Layer 1: API Servers

### Responsibilities

1. Accept HTTP POST request
2. Validate payload structure (reject malformed entries)
3. Assign a UUID v7 (time-ordered) as the log ID
4. Serialize and produce to Kafka
5. Return 202 Accepted

### Why UUID v7?

UUID v7 embeds a timestamp prefix, making it **monotonically increasing** and friendly to B-tree inserts. This avoids the random-write penalty of UUID v4 which causes page splits in InnoDB.

```
UUID v7 structure:
┌──────────────────┬────────┬──────────────┐
│ 48-bit timestamp │ 4-bit  │ 76-bit       │
│ (ms precision)   │ version│ random       │
└──────────────────┴────────┴──────────────┘
```

### Sizing

```
Single API server throughput: ~30-50k RPS (Go/Rust, fire-and-forward)
Required servers: 250,000 / 35,000 ≈ 8 servers (baseline)
With headroom for bursts: 10-12 servers
```

### Request Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant V as Validator
    participant S as Serializer
    participant K as Kafka Producer

    C->>V: POST /logs {service, level, ts, message}
    V->>V: Schema validation<br/>Size check (reject > 10KB)
    V->>S: Assign UUID v7 ID
    S->>K: Produce to partition<br/>key = ts_hour % num_partitions
    K-->>S: ACK (acks=1)
    S-->>C: 202 Accepted {id: "..."}

    Note over K: Async from here.<br/>Client does not wait<br/>for MySQL write.
```

### Trade-off: `acks=1` vs `acks=all`

| Setting | Durability | Latency | Throughput |
|---|---|---|---|
| `acks=0` | Fire-and-forget, can lose data | ~0.5ms | Highest |
| `acks=1` | Leader acknowledged | ~2-5ms | High |
| `acks=all` | All ISR replicas acknowledged | ~10-20ms | Lower |

**Choice: `acks=1`** — The leader acknowledges the write. If the leader crashes before replicating, we lose that batch. Since we tolerate small data loss, this is the right trade-off. `acks=all` would add 5-15ms to every POST response for durability we don't need.

---

## Layer 2: Kafka Buffer

### Topic Design

```
Topic: logs
Partitions: 48-64
Replication Factor: 3
Retention: 72 hours
```

### Partition Strategy

**Key: `timestamp_hour MOD num_partitions`**

```mermaid
graph TB
    subgraph "Incoming Logs (current hour: 14:00)"
        L1["Log ts=14:00:01"]
        L2["Log ts=14:00:02"]
        L3["Log ts=14:00:03"]
    end

    subgraph "Partition Assignment"
        H["hash(14) MOD 48"]
    end

    subgraph "Kafka Partitions (48 total)"
        P14["Partition 14<br/>(current hour)"]
        P15["Partition 15"]
        P0["Partition 0"]
    end

    L1 & L2 & L3 --> H
    H --> P14

    style P14 fill:#ff6b6b,color:#fff
    style P15 fill:#ddd,color:#333
    style P0 fill:#ddd,color:#333
```

**Problem:** All traffic for the current hour hits the same partition — hot partition.

**Solution:** Use `timestamp_hour * 1000 + random(0, spread_factor) MOD num_partitions` where `spread_factor` is 8-16. This distributes current-hour traffic across multiple partitions while keeping temporal locality.

```mermaid
graph TB
    subgraph "Improved: Spread Factor = 8"
        L1["Log ts=14:00:01"]
        L2["Log ts=14:00:02"]
        L3["Log ts=14:00:03"]
        L4["Log ts=14:00:04"]
    end

    subgraph "Partition Assignment"
        H1["(14*1000 + rand(0,8)) % 48"]
    end

    subgraph "Kafka Partitions"
        PA["Partition 8"]
        PB["Partition 14"]
        PC["Partition 20"]
        PD["Partition 32"]
    end

    L1 --> H1 --> PA
    L2 --> H1 --> PB
    L3 --> H1 --> PC
    L4 --> H1 --> PD

    style PA fill:#4a90d9,color:#fff
    style PB fill:#4a90d9,color:#fff
    style PC fill:#4a90d9,color:#fff
    style PD fill:#4a90d9,color:#fff
```

### Why 72-Hour Retention?

Kafka retention serves as a **replay buffer**, not long-term storage. 72 hours gives us:

- **MySQL maintenance window**: If a shard needs failover (promote replica, repair), we have 3 days to catch up
- **Reprocessing**: If writer workers had a bug, fix and replay from Kafka offsets
- **Burst absorption**: If MySQL can't keep up temporarily, Kafka absorbs the backlog

### Kafka Broker Sizing

```
Data rate:       250 MB/sec inbound
Replication:     x3 = 750 MB/sec total disk write
72h retention:   250 MB/sec x 72h x 3600 = 64.8 TB per replica
                 x 3 replicas = ~194.4 TB total Kafka storage
Broker count:    5-7 brokers (each with ~30 TB SSD)
```

---

## Layer 3: Writer Workers

### Core Loop

```mermaid
flowchart TD
    A[Consume from Kafka partition] --> B{Buffer full?<br/>5000 rows OR<br/>2 sec elapsed}
    B -->|No| A
    B -->|Yes| C[Build multi-row INSERT]
    C --> D[Execute against MySQL shard]
    D --> E{Success?}
    E -->|Yes| F[Commit Kafka offset]
    F --> A
    E -->|No| G{Retryable error?}
    G -->|Yes| H[Exponential backoff<br/>100ms → 200ms → 400ms...]
    H --> D
    G -->|No| I[Log to DLQ topic<br/>Alert on-call]
    I --> F

    style B fill:#f5a623,color:#000
    style D fill:#7b68ee,color:#fff
    style I fill:#ff6b6b,color:#fff
```

### Batching Strategy

Each writer worker accumulates rows in memory and flushes when **either** threshold is met:

```
Flush Trigger:
  row_count >= 5000   (row threshold)
  OR
  elapsed   >= 2s     (time threshold, prevents stale data in low-traffic periods)
```

**The generated SQL:**

```sql
INSERT INTO logs (id, ts, service, level, message)
VALUES
  (uuid1, '2024-06-15 10:30:00.123', 'payment-svc', 3, 'Connection timeout...'),
  (uuid2, '2024-06-15 10:30:00.124', 'auth-svc', 1, 'User login success...'),
  ... (5000 rows)
;
```

### Why Multi-Row INSERT?

```mermaid
graph LR
    subgraph "Individual INSERTs"
        I1[INSERT 1<br/>parse → lock → write → commit] --> I2[INSERT 2<br/>parse → lock → write → commit] --> I3[INSERT N<br/>parse → lock → write → commit]
    end

    subgraph "Batched INSERT"
        B1["INSERT 5000 rows<br/>parse once → lock once → write batch → commit once"]
    end

    style I1 fill:#ff6b6b,color:#fff
    style I2 fill:#ff6b6b,color:#fff
    style I3 fill:#ff6b6b,color:#fff
    style B1 fill:#50c878,color:#000
```

| Approach | Transactions/sec needed | InnoDB fsync calls | Network round trips |
|---|---|---|---|
| 1 row per INSERT | 250,000/sec | 250,000/sec | 250,000/sec |
| 5,000 rows per INSERT | 50/sec | 50/sec | 50/sec |

**5000x reduction** in transaction overhead, fsync calls, and network round trips. This is what makes MySQL viable at this scale.

### Worker-to-Shard Affinity

Each writer worker is assigned to **exactly one MySQL shard**. This avoids:
- Cross-shard connection pool bloat
- Distributed transaction complexity
- Unpredictable load distribution

```mermaid
graph TB
    subgraph "Kafka Partitions"
        KP1[Partition 0-7]
        KP2[Partition 8-15]
        KP3[Partition 16-23]
        KPN[Partition 24-47]
    end

    subgraph "Writer Workers"
        W1[Worker Group 1]
        W2[Worker Group 2]
        W3[Worker Group 3]
        WN[Worker Group N]
    end

    subgraph "MySQL Shards"
        S1[(Shard 1)]
        S2[(Shard 2)]
        S3[(Shard 3)]
        SN[(Shard N)]
    end

    KP1 --> W1 --> S1
    KP2 --> W2 --> S2
    KP3 --> W3 --> S3
    KPN --> WN --> SN

    style W1 fill:#f5a623,color:#000
    style W2 fill:#f5a623,color:#000
    style W3 fill:#f5a623,color:#000
    style WN fill:#f5a623,color:#000
```

### Dead Letter Queue (DLQ)

Rows that fail after max retries (e.g., schema mismatch, data too large) are sent to a separate Kafka topic `logs-dlq` for manual inspection. This prevents a single bad row from blocking the entire partition.

### Writer Worker Sizing

```
Global batch rate:   250,000 / 5,000 = 50 batches/sec
Per shard (N=40):    50 / 40 = 1.25 batches/sec per shard
Workers per shard:   2 (for redundancy during rebalances)
Total workers:       40 x 2 = 80 worker instances
                     (but lightweight — 2-4 cores, 8 GB RAM each)
```

### Trade-off: Batch Size vs. Data Loss Window

```mermaid
graph LR
    subgraph "Small Batch (1000 rows)"
        S[Lower latency to MySQL<br/>~4ms data loss window<br/>Higher transaction overhead<br/>250 batches/sec needed]
    end

    subgraph "Medium Batch (5000 rows)"
        M[Balanced latency<br/>~20ms data loss window<br/>Moderate overhead<br/>50 batches/sec needed]
    end

    subgraph "Large Batch (10000 rows)"
        L[Higher latency to MySQL<br/>~40ms data loss window<br/>Lowest overhead<br/>25 batches/sec needed]
    end

    style S fill:#ff6b6b,color:#fff
    style M fill:#50c878,color:#000
    style L fill:#4a90d9,color:#fff
```

**Choice: 5,000 rows.** The data loss window on worker crash is ~20ms worth of data (5000 rows in the in-memory buffer), which is within our tolerance. Going larger gives diminishing returns on transaction overhead reduction.
