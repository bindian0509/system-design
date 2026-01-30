# ClickHouse Component Design

## Overview

ClickHouse serves as the primary storage engine for hot and warm tier data, providing columnar storage with excellent compression and fast analytical queries for the log ingestion system.

---

## Architecture

### Cluster Topology

```mermaid
flowchart TB
    subgraph LB["Load Balancer"]
        HAP[HAProxy / CHProxy]
    end

    subgraph Cluster["ClickHouse Cluster"]
        subgraph Shard1["Shard 1 (Days 1-2)"]
            S1R1[(Replica 1<br/>500 TB)]
            S1R2[(Replica 2<br/>500 TB)]
            S1R3[(Replica 3<br/>500 TB)]
        end

        subgraph Shard2["Shard 2 (Days 3-4)"]
            S2R1[(Replica 1<br/>500 TB)]
            S2R2[(Replica 2<br/>500 TB)]
            S2R3[(Replica 3<br/>500 TB)]
        end

        subgraph ShardN["Shard N (Days N...)"]
            SNR1[(Replica 1<br/>500 TB)]
            SNR2[(Replica 2<br/>500 TB)]
            SNR3[(Replica 3<br/>500 TB)]
        end
    end

    subgraph ZK["ZooKeeper Ensemble"]
        ZK1[ZK Node 1]
        ZK2[ZK Node 2]
        ZK3[ZK Node 3]
    end

    LB --> Shard1
    LB --> Shard2
    LB --> ShardN

    Shard1 <--> ZK
    Shard2 <--> ZK
    ShardN <--> ZK
```

### Shard Distribution Strategy

```mermaid
flowchart LR
    subgraph Incoming["Incoming Data"]
        FLINK[Flink Writer]
    end

    subgraph Router["Shard Router"]
        HASH[Sharding Key:<br/>sipHash64(tenant_id, service)]
    end

    subgraph Shards["Distributed Table"]
        S1[Shard 1<br/>tenant_id hash 0-20]
        S2[Shard 2<br/>tenant_id hash 21-40]
        S3[Shard 3<br/>tenant_id hash 41-60]
        SN[Shard N<br/>tenant_id hash 61-100]
    end

    FLINK --> Router
    Router --> S1
    Router --> S2
    Router --> S3
    Router --> SN
```

---

## Schema Design

### Table Hierarchy

```mermaid
erDiagram
    LOGS_DISTRIBUTED ||--o{ LOGS_LOCAL : "routes to"
    LOGS_LOCAL ||--o{ PARTITION_202401 : "partitioned by"
    LOGS_LOCAL ||--o{ PARTITION_202402 : "partitioned by"
    LOGS_LOCAL ||--o{ ERROR_COUNTS_MV : "materializes"
    LOGS_LOCAL ||--o{ LATENCY_MV : "materializes"

    LOGS_DISTRIBUTED {
        DateTime64 timestamp
        String tenant_id
        String service
        String host
        String trace_id
        Enum8 level
        String message
    }

    LOGS_LOCAL {
        DateTime64 timestamp
        String tenant_id
        String service
        String host
        String trace_id
        Enum8 level
        String message
        INDEX idx_trace_id
        INDEX idx_message
    }

    ERROR_COUNTS_MV {
        String tenant_id
        String service
        DateTime minute
        UInt64 count
    }

    LATENCY_MV {
        String tenant_id
        String service
        DateTime hour
        Float64 p50
        Float64 p95
        Float64 p99
    }
```

### Primary Table Schema

```sql
-- Local table on each shard
CREATE TABLE logs_local ON CLUSTER '{cluster}'
(
    -- Core fields
    timestamp DateTime64(3, 'UTC'),
    tenant_id LowCardinality(String),
    service LowCardinality(String),
    host LowCardinality(String),
    trace_id String,
    span_id String,
    level Enum8('DEBUG' = 0, 'INFO' = 1, 'WARN' = 2, 'ERROR' = 3, 'FATAL' = 4),

    -- Log content
    message String,

    -- Structured fields (nullable for schema flexibility)
    request_id Nullable(String),
    user_id Nullable(String),
    duration_ms Nullable(Float64),
    status_code Nullable(UInt16),
    method Nullable(LowCardinality(String)),
    path Nullable(String),
    error_type Nullable(LowCardinality(String)),
    error_message Nullable(String),

    -- Dynamic fields as Map
    labels Map(String, String),

    -- Ingestion metadata
    _ingested_at DateTime64(3) DEFAULT now64(3),

    -- Indexes for common query patterns
    INDEX idx_trace_id trace_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_span_id span_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_request_id request_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_user_id user_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_message message TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_error_message error_message TYPE tokenbf_v1(16384, 3, 0) GRANULARITY 1
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/logs_local', '{replica}')
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (tenant_id, service, timestamp, trace_id)
TTL timestamp + INTERVAL 7 DAY
SETTINGS index_granularity = 8192;

-- Distributed table for queries
CREATE TABLE logs ON CLUSTER '{cluster}'
AS logs_local
ENGINE = Distributed('{cluster}', currentDatabase(), logs_local, sipHash64(tenant_id, service));
```

### Materialized Views

```mermaid
flowchart TB
    subgraph Source["Source Table"]
        LOGS[(logs_local)]
    end

    subgraph Views["Materialized Views"]
        MV1[error_counts_mv<br/>Per-minute error counts]
        MV2[latency_percentiles_mv<br/>Hourly latency stats]
        MV3[throughput_mv<br/>Per-minute message count]
        MV4[top_errors_mv<br/>Error frequency ranking]
    end

    subgraph Storage["MV Storage Tables"]
        S1[(error_counts)]
        S2[(latency_percentiles)]
        S3[(throughput)]
        S4[(top_errors)]
    end

    LOGS -->|INSERT trigger| MV1 --> S1
    LOGS -->|INSERT trigger| MV2 --> S2
    LOGS -->|INSERT trigger| MV3 --> S3
    LOGS -->|INSERT trigger| MV4 --> S4
```

```sql
-- Error counts per minute
CREATE MATERIALIZED VIEW error_counts_mv ON CLUSTER '{cluster}'
TO error_counts
AS SELECT
    tenant_id,
    service,
    toStartOfMinute(timestamp) AS minute,
    count() AS error_count,
    uniqExact(trace_id) AS unique_traces
FROM logs_local
WHERE level >= 'ERROR'
GROUP BY tenant_id, service, minute;

CREATE TABLE error_counts ON CLUSTER '{cluster}'
(
    tenant_id LowCardinality(String),
    service LowCardinality(String),
    minute DateTime,
    error_count AggregateFunction(count),
    unique_traces AggregateFunction(uniqExact, String)
)
ENGINE = ReplicatedAggregatingMergeTree('/clickhouse/tables/{shard}/error_counts', '{replica}')
PARTITION BY toYYYYMM(minute)
ORDER BY (tenant_id, service, minute);

-- Latency percentiles per hour
CREATE MATERIALIZED VIEW latency_percentiles_mv ON CLUSTER '{cluster}'
TO latency_percentiles
AS SELECT
    tenant_id,
    service,
    toStartOfHour(timestamp) AS hour,
    quantileState(0.5)(duration_ms) AS p50,
    quantileState(0.95)(duration_ms) AS p95,
    quantileState(0.99)(duration_ms) AS p99,
    avg(duration_ms) AS avg_duration,
    max(duration_ms) AS max_duration
FROM logs_local
WHERE duration_ms IS NOT NULL
GROUP BY tenant_id, service, hour;
```

---

## Data Lifecycle

### Partition Management

```mermaid
stateDiagram-v2
    [*] --> Active: New partition created
    Active --> Active: Receiving writes
    Active --> Merging: Parts accumulate
    Merging --> Merged: Background merge
    Merged --> Frozen: No more writes (next day)
    Frozen --> TTLProcessing: TTL check
    TTLProcessing --> Dropped: TTL expired (7 days)
    Dropped --> [*]

    note right of Active
        Current day partition
        Multiple parts being written
    end note

    note right of Merging
        Background merges
        combine small parts
    end note

    note right of Frozen
        Read-only partition
        Optimal for queries
    end note
```

### Part Merging

```mermaid
flowchart TB
    subgraph Before["Before Merge"]
        P1[Part 1<br/>100 MB]
        P2[Part 2<br/>100 MB]
        P3[Part 3<br/>100 MB]
        P4[Part 4<br/>100 MB]
    end

    subgraph Merge["Merge Process"]
        SELECTOR[Part Selector]
        MERGER[Merge Engine]
    end

    subgraph After["After Merge"]
        PM[Merged Part<br/>~350 MB<br/>compressed]
    end

    P1 & P2 & P3 & P4 --> SELECTOR
    SELECTOR --> MERGER
    MERGER --> PM

    style PM fill:#6bcb77
```

---

## Query Patterns

### Query Routing

```mermaid
flowchart TB
    Query[Incoming Query]

    Query --> Parse[Parse Query]
    Parse --> Analyze[Analyze WHERE clause]

    Analyze --> TimeRange{Time range<br/>specified?}

    TimeRange -->|Yes| Prune[Partition pruning]
    TimeRange -->|No| AllPartitions[Query all partitions]

    Prune --> TenantFilter{tenant_id<br/>specified?}
    TenantFilter -->|Yes| SingleShard[Route to shard]
    TenantFilter -->|No| AllShards[Scatter to all shards]

    SingleShard --> Execute[Execute query]
    AllShards --> Execute
    AllPartitions --> AllShards

    Execute --> Merge[Merge results]
    Merge --> Return[Return to client]
```

### Common Query Patterns

```mermaid
flowchart LR
    subgraph Patterns["Query Patterns"]
        P1[Needle-in-haystack<br/>trace_id = 'xxx']
        P2[Time-range scan<br/>last 1 hour errors]
        P3[Aggregation<br/>error rate by service]
        P4[Full-text search<br/>message LIKE '%error%']
    end

    subgraph Indexes["Index Usage"]
        I1[bloom_filter<br/>on trace_id]
        I2[Partition pruning<br/>+ Primary key]
        I3[Materialized View<br/>pre-aggregated]
        I4[tokenbf_v1<br/>on message]
    end

    P1 --> I1
    P2 --> I2
    P3 --> I3
    P4 --> I4
```

### Query Examples

```sql
-- Needle in haystack (uses bloom filter)
SELECT *
FROM logs
WHERE trace_id = 'abc-123-def-456'
  AND timestamp >= now() - INTERVAL 1 DAY
ORDER BY timestamp;

-- Time-range with aggregation (uses partition pruning + MV)
SELECT
    service,
    countMerge(error_count) AS errors,
    uniqMerge(unique_traces) AS affected_traces
FROM error_counts
WHERE tenant_id = 'acme-corp'
  AND minute >= now() - INTERVAL 1 HOUR
GROUP BY service
ORDER BY errors DESC;

-- Full-text search (uses tokenbf index)
SELECT timestamp, service, message
FROM logs
WHERE tenant_id = 'acme-corp'
  AND timestamp >= now() - INTERVAL 1 HOUR
  AND hasToken(message, 'NullPointerException')
LIMIT 100;

-- Complex aggregation
SELECT
    toStartOfMinute(timestamp) AS minute,
    service,
    countIf(level = 'ERROR') AS errors,
    countIf(level = 'WARN') AS warnings,
    quantile(0.95)(duration_ms) AS p95_latency
FROM logs
WHERE tenant_id = 'acme-corp'
  AND timestamp >= now() - INTERVAL 6 HOUR
GROUP BY minute, service
ORDER BY minute, service;
```

---

## Replication

### Replication Flow

```mermaid
sequenceDiagram
    participant Writer as Flink Writer
    participant R1 as Replica 1 (Leader)
    participant ZK as ZooKeeper
    participant R2 as Replica 2
    participant R3 as Replica 3

    Writer->>R1: INSERT INTO logs_local
    R1->>R1: Write to local part
    R1->>ZK: Log entry to replication queue

    par Async Replication
        ZK->>R2: Notify new entry
        R2->>R1: Fetch part
        R2->>R2: Write locally
        R2->>ZK: Confirm replication
    and
        ZK->>R3: Notify new entry
        R3->>R1: Fetch part
        R3->>R3: Write locally
        R3->>ZK: Confirm replication
    end

    R1->>Writer: ACK (configurable)
```

### Replica Failover

```mermaid
stateDiagram-v2
    [*] --> AllHealthy: 3 replicas active

    AllHealthy --> ReplicaDown: Replica 1 fails
    ReplicaDown --> Degraded: Queries route to R2/R3
    Degraded --> Recovering: Replica 1 restarts
    Recovering --> CatchingUp: Fetching missing parts
    CatchingUp --> AllHealthy: Caught up

    ReplicaDown --> WritesBlocked: All replicas down
    WritesBlocked --> [*]: Data loss risk

    note right of Degraded
        Read queries distributed
        to healthy replicas
    end note

    note right of CatchingUp
        Background replication
        from ZooKeeper queue
    end note
```

---

## Performance Optimization

### Index Types

```mermaid
flowchart TB
    subgraph Indexes["Index Types"]
        subgraph Primary["Primary Index"]
            PK[ORDER BY columns<br/>Sparse index every 8192 rows]
        end

        subgraph Data["Data Skipping Indexes"]
            BLOOM[bloom_filter<br/>ID lookups]
            TOKEN[tokenbf_v1<br/>Full-text search]
            MINMAX[minmax<br/>Range queries]
            SET[set<br/>Low cardinality values]
        end
    end

    subgraph Usage["Query Usage"]
        U1[WHERE tenant_id = ?<br/>→ Primary Index]
        U2[WHERE trace_id = ?<br/>→ bloom_filter]
        U3[WHERE message LIKE '%err%'<br/>→ tokenbf_v1]
        U4[WHERE duration_ms > 1000<br/>→ minmax]
    end

    Indexes --> Usage
```

### Compression Settings

| Column Type | Codec | Compression Ratio |
|-------------|-------|-------------------|
| **timestamp** | Delta + LZ4 | 50:1 |
| **tenant_id** | LowCardinality + LZ4 | 100:1 |
| **service** | LowCardinality + LZ4 | 100:1 |
| **level** | Enum8 + LZ4 | 200:1 |
| **message** | ZSTD(3) | 5:1 |
| **trace_id** | LZ4 | 3:1 |
| **labels (Map)** | ZSTD(3) | 8:1 |

### Write Optimization

```mermaid
flowchart TB
    subgraph Writers["Flink Writers"]
        W1[Writer 1]
        W2[Writer 2]
        W3[Writer 3]
    end

    subgraph Buffer["Buffer Layer"]
        BUF[Async Insert Buffer<br/>Batch Size: 100K rows<br/>Flush Interval: 1 sec]
    end

    subgraph Cluster["ClickHouse"]
        INSERT[Insert Handler]
        PARTS[Part Writer]
    end

    W1 & W2 & W3 --> BUF
    BUF -->|Batched INSERT| INSERT
    INSERT --> PARTS

    style BUF fill:#ffd93d
```

---

## Monitoring

### Key Metrics

```mermaid
flowchart TB
    subgraph Write["Write Metrics"]
        WM1[InsertedRows]
        WM2[InsertedBytes]
        WM3[InsertQueryTimeMicroseconds]
        WM4[MergedRows]
    end

    subgraph Query["Query Metrics"]
        QM1[SelectQueryTimeMicroseconds]
        QM2[SelectedRows]
        QM3[SelectedBytes]
        QM4[QueryCacheHits]
    end

    subgraph Storage["Storage Metrics"]
        SM1[DiskSpaceUsed]
        SM2[PartsActive]
        SM3[PartsTemporary]
        SM4[ReplicatedPartFetches]
    end

    subgraph Health["Health Metrics"]
        HM1[ZooKeeperExceptions]
        HM2[ReplicasMaxQueueSize]
        HM3[DelayedInserts]
        HM4[DistributedFilesToInsert]
    end
```

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| **ReplicationLag** | > 100 parts | > 1000 parts |
| **MergedPartSize** | > 100 GB | > 500 GB |
| **DelayedInserts** | > 100 | > 1000 |
| **QueryLatency p95** | > 10s | > 30s |
| **DiskUsage** | > 70% | > 85% |
| **ZooKeeperExceptions** | > 0 | > 10/min |

---

## Scaling Operations

### Adding a Shard

```mermaid
flowchart TB
    subgraph Step1["1. Prepare New Nodes"]
        DEPLOY[Deploy 3 replica nodes]
        CONFIG[Apply cluster config]
        JOIN[Register with ZooKeeper]
    end

    subgraph Step2["2. Update Distributed Table"]
        ALTER[ALTER TABLE ... ADD SHARD]
        WEIGHT[Set initial weight: 0]
        VERIFY[Verify connectivity]
    end

    subgraph Step3["3. Enable Traffic"]
        GRADUAL[Gradually increase weight]
        MONITOR[Monitor insert distribution]
        FULL[Set weight to 100%]
    end

    subgraph Step4["4. Rebalance (Optional)"]
        MOVE[Move parts for even distribution]
        CLEANUP[Clean up source shards]
    end

    Step1 --> Step2 --> Step3 --> Step4
```

### Rolling Upgrade

```mermaid
sequenceDiagram
    participant LB as Load Balancer
    participant R1 as Replica 1
    participant R2 as Replica 2
    participant R3 as Replica 3

    Note over LB,R3: Start rolling upgrade

    LB->>R1: Remove from rotation
    R1->>R1: Stop ClickHouse
    R1->>R1: Upgrade version
    R1->>R1: Start ClickHouse
    R1->>R1: Catch up replication
    LB->>R1: Add back to rotation

    LB->>R2: Remove from rotation
    R2->>R2: Upgrade process...
    LB->>R2: Add back to rotation

    LB->>R3: Remove from rotation
    R3->>R3: Upgrade process...
    LB->>R3: Add back to rotation

    Note over LB,R3: Upgrade complete
```

---

## Configuration Reference

### Server Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| `max_concurrent_queries` | 200 | Per-server query limit |
| `max_threads` | 64 | Query parallelism |
| `max_memory_usage` | 400 GB | Per-query memory limit |
| `max_bytes_before_external_sort` | 50 GB | Before spilling to disk |
| `max_insert_block_size` | 1,048,576 | Rows per insert block |
| `async_insert` | 1 | Enable async inserts |
| `async_insert_busy_timeout_ms` | 1000 | Batch wait time |
| `async_insert_max_data_size` | 10485760 | 10 MB batch size |

### MergeTree Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| `index_granularity` | 8192 | Rows per index entry |
| `min_bytes_for_wide_part` | 10485760 | 10 MB min for wide parts |
| `merge_with_ttl_timeout` | 14400 | TTL merge interval (4h) |
| `max_parts_in_total` | 100000 | Max parts before blocking |
| `parts_to_delay_insert` | 300 | Throttle inserts threshold |
| `parts_to_throw_insert` | 600 | Block inserts threshold |
