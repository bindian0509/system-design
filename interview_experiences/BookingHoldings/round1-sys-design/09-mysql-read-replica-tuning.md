# 09 — MySQL Read Replica Tuning

## The Key Insight: Replicas Don't Need Durability

The primary pays a massive performance tax for durability: fsync, doublewrite buffer, binary logging, redo log flushing. **The replica doesn't need any of this.** If a replica crashes, you promote another or rebuild it from the primary. This lets us strip out every durability mechanism and redirect those resources toward read performance.

---

## Optimal Replica Machine Configuration

### Why Different From Primary?

The primary is **write-optimized**: fast sequential writes, large redo logs, durable commits. The replica is **read-optimized**: maximum RAM for buffer pool cache and fast random reads.

```mermaid
graph LR
    subgraph "Primary (Write-Optimized)"
        P_CPU["32 cores"]
        P_RAM["128 GB RAM<br/>96 GB buffer pool"]
        P_DISK["64 TB NVMe<br/>high write endurance"]
    end

    subgraph "Replica (Read-Optimized)"
        R_CPU["16-24 cores<br/>fewer but sufficient"]
        R_RAM["256 GB RAM<br/>200 GB buffer pool"]
        R_DISK["64 TB NVMe<br/>read-optimized<br/>lower endurance OK"]
    end

    style P_CPU fill:#7b68ee,color:#fff
    style P_RAM fill:#7b68ee,color:#fff
    style P_DISK fill:#7b68ee,color:#fff
    style R_CPU fill:#4a90d9,color:#fff
    style R_RAM fill:#4a90d9,color:#fff
    style R_DISK fill:#4a90d9,color:#fff
```

| Resource | Primary | Replica | Why Different |
|---|---|---|---|
| **RAM** | 128 GB | **256 GB** | More buffer pool = more cache hits. RAM is the single biggest read performance lever. |
| **CPU** | 32 cores | 16-24 cores | Reads are I/O bound, not CPU bound. Fewer but sufficient cores. Saves cost. |
| **Disk** | 64 TB NVMe (high write endurance) | 64 TB NVMe (read-optimized, lower endurance OK) | Replica disk sees mostly sequential replication writes + random reads. Write endurance matters less. |
| **Network** | 25 Gbps | 25 Gbps | Same — scatter-gather responses need bandwidth. |

---

## Buffer Pool Sizing Math

This is the most critical decision for read performance.

```mermaid
graph TD
    subgraph "Per Shard, Per Hour"
        A["250,000 logs/sec ÷ 40 shards<br/>= 6,250 logs/sec per shard"]
        B["6,250 × 3,600 sec<br/>= 22.5M rows per hour"]
        C["22.5M × 1 KB<br/>= ~22.5 GB per hour (uncompressed)"]
    end

    subgraph "In Buffer Pool (ROW_FORMAT=COMPRESSED)"
        D["On disk: 8 KB compressed pages<br/>= ~11 GB per hour"]
        E["In buffer pool: compressed (8 KB)<br/>+ uncompressed (16 KB) pages<br/>= ~33 GB per hour"]
    end

    subgraph "Cache Coverage"
        F["200 GB buffer pool<br/>÷ 33 GB per hour<br/>= ~6 hours of hot data cached"]
    end

    A --> B --> C --> D --> E --> F

    style F fill:#50c878,color:#000
```

Most operational queries target the **last 1-2 hours** of logs (engineers debugging live issues). With 6 hours cached, the vast majority of queries are served entirely from memory — no disk I/O.

```mermaid
graph LR
    subgraph "Query Recency Distribution (typical)"
        H1["Last 1 hour<br/>~60% of queries"]
        H2["1-6 hours ago<br/>~25% of queries"]
        H3["6+ hours ago<br/>~15% of queries"]
    end

    subgraph "Buffer Pool Coverage"
        BP["200 GB buffer pool<br/>caches 6 hours"]
    end

    H1 -->|"100% cache hit"| BP
    H2 -->|"~90% cache hit"| BP
    H3 -->|"Cache miss → disk"| DISK["NVMe random read"]

    style H1 fill:#50c878,color:#000
    style H2 fill:#50c878,color:#000
    style H3 fill:#ff6b6b,color:#fff
```

---

## MySQL-Level Replica Optimizations

### 1. Disable All Durability Mechanisms

```ini
[mysqld]
# === DURABILITY STRIPPING (safe on replicas) ===

# Don't fsync redo log on commit — biggest single performance gain
# Primary uses 2, replica can use 0 (flush only every second)
innodb_flush_log_at_trx_commit = 0

# Don't fsync binary log (or disable it entirely)
sync_binlog = 0

# Disable binary logging entirely — replica doesn't need it
# (unless chaining replication to another replica)
skip-log-bin

# Disable doublewrite buffer — no need for torn page protection
# If replica crashes, rebuild from primary
innodb_doublewrite = OFF

# Disable change buffering — replica applies inserts sequentially
# via replication, so buffering random inserts is unnecessary
innodb_change_buffering = none
```

```mermaid
graph TB
    subgraph "Disk I/O Freed by Disabling Durability"
        D1["innodb_flush_log_at_trx_commit = 0<br/>Saves: redo log fsync per commit"]
        D2["sync_binlog = 0<br/>Saves: binlog fsync"]
        D3["skip-log-bin<br/>Saves: binary log writes entirely"]
        D4["innodb_doublewrite = OFF<br/>Saves: ~50% of data page writes"]
        D5["innodb_change_buffering = none<br/>Saves: change buffer maintenance I/O"]
    end

    D1 & D2 & D3 & D4 & D5 --> FREED["~60-70% of disk write I/O<br/>eliminated on replica"]
    FREED --> BENEFIT["Disk bandwidth freed<br/>entirely for serving reads"]

    style FREED fill:#50c878,color:#000
    style BENEFIT fill:#50c878,color:#000
```

### 2. Maximize Buffer Pool

```ini
# === BUFFER POOL (the #1 read performance lever) ===

# 200 GB buffer pool on a 256 GB machine
# Leave ~56 GB for OS page cache, connections, tmp tables
innodb_buffer_pool_size = 200G

# 32 instances to reduce mutex contention on concurrent reads
# Rule of thumb: 1 instance per 4-8 GB of buffer pool
innodb_buffer_pool_instances = 32

# Warm up buffer pool after restart — critical for replicas
# Without this, a restarted replica serves everything from disk
# until the buffer pool warms up naturally (could take hours)
innodb_buffer_pool_dump_at_shutdown = ON
innodb_buffer_pool_load_at_startup = ON

# Dump 100% of buffer pool pages (default is 25%)
innodb_buffer_pool_dump_pct = 100
```

```mermaid
graph LR
    subgraph "Without Buffer Pool Warming"
        COLD["Replica restarts"] --> MISS["Every query hits disk<br/>for hours"]
        MISS --> SLOW["P99 latency: 10-30 seconds<br/>until cache warms"]
    end

    subgraph "With Buffer Pool Warming"
        WARM["Replica restarts"] --> LOAD["Buffer pool loaded<br/>from dump file<br/>(~5-10 minutes)"]
        LOAD --> FAST["P99 latency: normal<br/>within minutes"]
    end

    style MISS fill:#ff6b6b,color:#fff
    style SLOW fill:#ff6b6b,color:#fff
    style LOAD fill:#50c878,color:#000
    style FAST fill:#50c878,color:#000
```

### 3. Read-Specific I/O Tuning

```ini
# === READ I/O OPTIMIZATION ===

# More read I/O threads for parallel disk reads
innodb_read_io_threads = 32

# Fewer write I/O threads (replica only does replication writes)
innodb_write_io_threads = 4

# Higher I/O capacity — tell InnoDB the NVMe can handle more
innodb_io_capacity = 20000
innodb_io_capacity_max = 40000

# Aggressive read-ahead for sequential scans (range queries on ts)
# Prefetch pages when 16 out of 64 pages in an extent are accessed
innodb_read_ahead_threshold = 16

# Parallel clustered index range scans (MySQL 8.0.14+)
# Speeds up large range scans across the (ts, id) primary key
innodb_parallel_read_threads = 8
```

```mermaid
graph TB
    subgraph "Read I/O Thread Allocation"
        subgraph "Primary"
            PW["Write threads: 16"]
            PR["Read threads: 16"]
        end
        subgraph "Replica"
            RW["Write threads: 4<br/>(only replication)"]
            RR["Read threads: 32<br/>(maximized for queries)"]
        end
    end

    style PW fill:#7b68ee,color:#fff
    style PR fill:#7b68ee,color:#fff
    style RW fill:#4a90d9,color:#fff
    style RR fill:#50c878,color:#000
```

### 4. Transaction Isolation Relaxation

```ini
# === ISOLATION LEVEL ===

# READ-UNCOMMITTED eliminates MVCC overhead:
# - No consistent read snapshots
# - No undo log lookups
# - No read view management
# Dirty reads are perfectly fine for log queries — a log entry
# being half-replicated won't cause business logic errors
transaction_isolation = READ-UNCOMMITTED
```

```mermaid
graph LR
    subgraph "REPEATABLE-READ (default)"
        RR1["Query starts"] --> RR2["Create consistent<br/>read snapshot"]
        RR2 --> RR3["For each row:<br/>check visibility via<br/>undo log chain"]
        RR3 --> RR4["Maintain read view<br/>until query ends"]
        RR4 --> RR5["~15-25% overhead"]
    end

    subgraph "READ-UNCOMMITTED"
        RU1["Query starts"] --> RU2["Read current page<br/>directly"]
        RU2 --> RU3["No snapshot<br/>No undo log<br/>No read view"]
        RU3 --> RU4["Zero MVCC overhead"]
    end

    style RR5 fill:#ff6b6b,color:#fff
    style RU4 fill:#50c878,color:#000
```

**This is a significant optimization most designs miss.** The default `REPEATABLE-READ` creates a consistent snapshot for every query, maintaining read views and potentially reading from undo logs. For log data, this is pure overhead. `READ-UNCOMMITTED` skips all of it.

### 5. Parallel Replication (Keep Replica In Sync)

```ini
# === REPLICATION PERFORMANCE ===

# Apply replication events in parallel (16 worker threads)
replica_parallel_workers = 16

# Use logical clock parallelism (MySQL 8.0+)
# Transactions committed in the same binlog group on primary
# can be applied in parallel on replica
replica_parallel_type = LOGICAL_CLOCK

# Preserve commit ordering for consistency
replica_preserve_commit_order = ON
```

```mermaid
graph LR
    subgraph "Serial Replication (default)"
        S1["Binlog event 1"] --> S2["Binlog event 2"]
        S2 --> S3["Binlog event 3"]
        S3 --> S4["1 event at a time<br/>Can fall behind during bursts"]
    end

    subgraph "Parallel Replication (16 workers)"
        P1["Worker 1: Event 1"]
        P2["Worker 2: Event 2"]
        P3["Worker 3: Event 3"]
        P4["Worker 16: Event N"]
        P1 & P2 & P3 & P4 --> DONE["All applied concurrently<br/>Keeps up during 2-3x bursts"]
    end

    style S4 fill:#ff6b6b,color:#fff
    style DONE fill:#50c878,color:#000
```

### 6. Enable Adaptive Hash Index (For Reads)

```ini
# === ADAPTIVE HASH INDEX ===

# ON for replicas (OFF on primaries)
# AHI builds in-memory hash indexes for frequently accessed pages
# Overhead on writes (maintaining the hash) — bad for primaries
# Pure benefit on reads (O(1) lookup vs B-tree traversal) — good for replicas
innodb_adaptive_hash_index = ON
innodb_adaptive_hash_index_parts = 16
```

```mermaid
graph TB
    subgraph "Without AHI"
        W1["Range query on ts"] --> W2["B-tree traversal<br/>Root → Branch → Leaf<br/>3-4 page accesses"]
    end

    subgraph "With AHI (hot pages)"
        A1["Range query on ts"] --> A2["Hash lookup for<br/>frequently accessed pages<br/>O(1) → 1 page access"]
    end

    subgraph "Why ON for Replica, OFF for Primary"
        R1["Primary: AHI maintenance<br/>cost on every INSERT<br/>outweighs read benefit"]
        R2["Replica: minimal writes<br/>(only replication)<br/>AHI is pure read upside"]
    end

    style W2 fill:#f5a623,color:#000
    style A2 fill:#50c878,color:#000
    style R1 fill:#ff6b6b,color:#fff
    style R2 fill:#50c878,color:#000
```

---

## Advanced: Partition-Affinity Replicas

Instead of every replica serving queries for all 180 days, assign each replica a time-range affinity:

```mermaid
graph TB
    QR[Query Router] --> CHECK{Query time range?}

    CHECK -->|"Last 7 days<br/>(~85% of queries)"| TIER_A
    CHECK -->|"8-180 days ago<br/>(~15% of queries)"| TIER_B

    subgraph TIER_A["Tier A: Hot Replicas (2 per shard)"]
        RA1["Replica A1<br/>256 GB RAM<br/>200 GB buffer pool<br/>7 days = ~90 GB hot data<br/>100% cache hit"]
        RA2["Replica A2<br/>(redundancy)"]
    end

    subgraph TIER_B["Tier B: Cold Replicas (1 per shard)"]
        RB1["Replica B1<br/>128 GB RAM<br/>96 GB buffer pool<br/>173 days of data<br/>Disk reads expected"]
    end

    style TIER_A fill:#50c878,color:#000
    style TIER_B fill:#4a90d9,color:#fff
    style RA1 fill:#50c878,color:#000
    style RB1 fill:#4a90d9,color:#fff
```

### Why This Works

| Aspect | All-Data Replica | Partition-Affinity Replica |
|---|---|---|
| Buffer pool utilization | Polluted with old + new data | Concentrated on relevant data |
| Cache hit rate (recent queries) | ~70-80% | **~95-100%** |
| Machine cost (Tier A) | Same for all | Can use smaller disks (only recent data needed fast) |
| Machine cost (Tier B) | Same for all | Can use less RAM (cold queries tolerate disk reads) |
| Routing complexity | Simple (any replica) | Query router must inspect time range |

### Implementation

The query router inspects `from`/`to` and routes accordingly:

```
if (from >= now - 7 days):
    route to Tier A replica (random pick for load balancing)
else:
    route to Tier B replica
```

All replicas still replicate ALL data from the primary (they have the full dataset). The tiering only affects which replica the query router prefers for a given time range. This means any replica can serve any query in a failover scenario.

---

## Complete Replica Configuration

```ini
[mysqld]
# ============================================
# READ REPLICA — OPTIMIZED FOR QUERY SERVING
# ============================================

# --- Durability: OFF (not needed on replicas) ---
innodb_flush_log_at_trx_commit      = 0
sync_binlog                         = 0
skip-log-bin
innodb_doublewrite                  = OFF
innodb_change_buffering             = none

# --- Buffer Pool: MAXIMIZED ---
innodb_buffer_pool_size             = 200G
innodb_buffer_pool_instances        = 32
innodb_buffer_pool_dump_at_shutdown = ON
innodb_buffer_pool_load_at_startup  = ON
innodb_buffer_pool_dump_pct         = 100

# --- Read I/O: AGGRESSIVE ---
innodb_read_io_threads              = 32
innodb_write_io_threads             = 4
innodb_io_capacity                  = 20000
innodb_io_capacity_max              = 40000
innodb_read_ahead_threshold         = 16
innodb_parallel_read_threads        = 8

# --- Isolation: RELAXED ---
transaction_isolation               = READ-UNCOMMITTED

# --- Replication: PARALLEL ---
replica_parallel_workers            = 16
replica_parallel_type               = LOGICAL_CLOCK
replica_preserve_commit_order       = ON

# --- Adaptive Hash Index: ON (benefits reads) ---
innodb_adaptive_hash_index          = ON
innodb_adaptive_hash_index_parts    = 16

# --- Compression (same as primary) ---
innodb_file_per_table               = ON
```

---

## Impact Summary

```mermaid
graph TD
    subgraph "Optimization Impact on Query Latency"
        O1["Disable durability<br/>(flush/sync/doublewrite)"] -->|"Frees 60-70%<br/>disk bandwidth"| FAST
        O2["200 GB buffer pool<br/>(vs 96 GB on primary)"] -->|"6 hours cached<br/>most queries from RAM"| FAST
        O3["Buffer pool warming<br/>on restart"] -->|"Minutes to warm<br/>vs hours cold"| FAST
        O4["READ-UNCOMMITTED<br/>isolation"] -->|"~15-25% faster<br/>no MVCC overhead"| FAST
        O5["Adaptive hash index ON"] -->|"O(1) page lookup<br/>for hot pages"| FAST
        O6["Parallel read threads"] -->|"4-8x faster<br/>large range scans"| FAST
        O7["Parallel replication"] -->|"Keeps replica in sync<br/>during bursts"| FAST

        FAST["Net result: 3-5x faster queries<br/>vs default MySQL configuration"]
    end

    style FAST fill:#50c878,color:#000
```

| Optimization | Mechanism | Expected Impact |
|---|---|---|
| Disable durability | Eliminates write I/O overhead | Frees ~60-70% of disk bandwidth for reads |
| 200 GB buffer pool | Cache 6 hours of hot data | Most queries served from memory — sub-second per shard |
| Buffer pool warm-up | Preloads cache from dump file | Avoids hours of cold cache after replica restart |
| `READ-UNCOMMITTED` | Skips MVCC read views and undo log | ~15-25% faster reads |
| Adaptive hash index ON | In-memory hash for hot pages | O(1) page lookup for repeated accesses |
| Parallel read threads | Parallel clustered index scans | Large range scans 4-8x faster |
| Parallel replication | 16 workers applying binlog events | Keeps replica in sync during burst traffic |

**Net effect:** A properly tuned read replica serves the same query **3-5x faster** than a default-configured MySQL instance, while costing roughly the same (trading CPU cores for RAM).
