# 04 — Read Path & Query Routing

## Overview

The read path handles `GET /logs?from=X&to=Y` with a maximum 3600-second window. Since data is distributed across all shards (round-robin writes), every query must **scatter-gather** across all N shards, merge results by timestamp, and return a paginated response.

```mermaid
graph TB
    Client[Client] -->|"GET /logs?from=X&to=Y<br/>&limit=10000&cursor=..."| QR[Query Router]

    QR -->|Parallel queries| R1[(Shard 1<br/>Replica)]
    QR -->|Parallel queries| R2[(Shard 2<br/>Replica)]
    QR -->|Parallel queries| R3[(Shard 3<br/>Replica)]
    QR -->|Parallel queries| RN[(Shard N<br/>Replica)]

    R1 -->|Partial results| M[Merge Layer<br/>K-way merge by ts]
    R2 -->|Partial results| M
    R3 -->|Partial results| M
    RN -->|Partial results| M

    M -->|Paginated response| Client

    style QR fill:#50c878,color:#000
    style M fill:#f5a623,color:#000
    style R1 fill:#4a90d9,color:#fff
    style R2 fill:#4a90d9,color:#fff
    style R3 fill:#4a90d9,color:#fff
    style RN fill:#4a90d9,color:#fff
```

---

## Query Router

### Responsibilities

1. Parse and validate `from` / `to` parameters (reject if delta > 3600s)
2. Determine which daily partition(s) the range spans
3. Fan out parallel queries to all shard replicas
4. K-way merge results by timestamp
5. Apply pagination (cursor-based)
6. Return response

### Request Lifecycle

```mermaid
sequenceDiagram
    participant C as Client
    participant QR as Query Router
    participant R1 as Shard 1 Replica
    participant R2 as Shard 2 Replica
    participant RN as Shard N Replica

    C->>QR: GET /logs?from=1718441400&to=1718445000&limit=10000

    QR->>QR: Validate: to - from = 3600 ✓
    QR->>QR: Resolve partitions: p20240615, p20240616<br/>(spans midnight)

    par Scatter to all shards
        QR->>R1: SELECT * FROM logs PARTITION (p20240615, p20240616)<br/>WHERE ts BETWEEN '...' AND '...'<br/>ORDER BY ts, id LIMIT 10000
        QR->>R2: Same query
        QR->>RN: Same query
    end

    R1-->>QR: Rows (sorted by ts)
    R2-->>QR: Rows (sorted by ts)
    RN-->>QR: Rows (sorted by ts)

    QR->>QR: K-way merge sort<br/>Take first 10,000 rows globally

    QR-->>C: 200 OK {logs: [...], cursor: "..."}
```

---

## The SQL Query

### Generated Per Shard

```sql
SELECT id, ts, service, level, message
FROM logs PARTITION (p20240615, p20240616)
WHERE ts >= '2024-06-15 23:30:00.000'
  AND ts <  '2024-06-16 00:30:00.000'
ORDER BY ts, id
LIMIT 10000;
```

### Why Explicit `PARTITION` Clause?

MySQL's optimizer does automatic partition pruning based on `WHERE` conditions. However, explicitly naming partitions:
- **Guarantees pruning** even if the optimizer makes a suboptimal plan
- **Documents intent** — makes it clear to code reviewers which partitions are targeted
- **Avoids edge cases** with `MAXVALUE` catch-all partition

### Query Execution Plan (EXPLAIN)

```
+----+-------------+-------+------------+-------+---------------+---------+---------+------+------+----------+-----------------------------+
| id | select_type | table | partitions | type  | possible_keys | key     | key_len | ref  | rows | filtered | Extra                       |
+----+-------------+-------+------------+-------+---------------+---------+---------+------+------+----------+-----------------------------+
|  1 | SIMPLE      | logs  | p20240615, | range | PRIMARY       | PRIMARY | 11      | NULL | 5000 |   100.00 | Using where                 |
|    |             |       | p20240616  |       |               |         |         |      |      |          |                             |
+----+-------------+-------+------------+-------+---------------+---------+---------+------+------+----------+-----------------------------+
```

**Key points:**
- `partitions` shows only 2 partitions accessed (out of 180)
- `type: range` confirms B-tree range scan on primary key
- `key: PRIMARY` — using the clustered index directly, no secondary index lookup
- No filesort needed — data is already ordered by `(ts, id)` in the clustered index

---

## Pagination Strategy

### Why Cursor-Based (Not Offset)?

```mermaid
graph LR
    subgraph "OFFSET-based (Bad)"
        O1["Page 1: OFFSET 0 LIMIT 10000"] --> O2["Page 2: OFFSET 10000 LIMIT 10000"]
        O2 --> O3["Page 3: OFFSET 20000 LIMIT 10000"]
        O3 --> O4["MySQL scans and discards<br/>20,000 rows before returning<br/>the next 10,000"]
    end

    subgraph "Cursor-based (Good)"
        C1["Page 1: LIMIT 10000"] --> C2["Page 2: WHERE (ts, id) > (last_ts, last_id)<br/>LIMIT 10000"]
        C2 --> C3["Page 3: WHERE (ts, id) > (last_ts, last_id)<br/>LIMIT 10000"]
        C3 --> C4["MySQL seeks directly<br/>to cursor position.<br/>No wasted work."]
    end

    style O4 fill:#ff6b6b,color:#fff
    style C4 fill:#50c878,color:#000
```

### Cursor Encoding

```
Cursor = base64(last_ts_unix_ms + ":" + last_id_hex)

Example:
  last_ts  = 2024-06-15T23:45:12.456Z → 1718494712456
  last_id  = 0190a3b4-5c6d-7e8f-9a0b-1c2d3e4f5a6b → hex bytes
  cursor   = base64("1718494712456:0190a3b45c6d7e8f9a0b1c2d3e4f5a6b")
           = "MTcxODQ5NDcxMjQ1NjowMTkwYTNiNDVjNmQ3ZThmOWEwYjFjMmQzZTRmNWE2Yg=="
```

### Per-Shard Query with Cursor

```sql
-- First page
SELECT id, ts, service, level, message
FROM logs PARTITION (p20240615)
WHERE ts >= '2024-06-15 23:30:00.000'
  AND ts <  '2024-06-16 00:30:00.000'
ORDER BY ts, id
LIMIT 250;  -- limit/N shards = per-shard limit

-- Subsequent page (with cursor)
SELECT id, ts, service, level, message
FROM logs PARTITION (p20240615)
WHERE ts >= '2024-06-15 23:30:00.000'
  AND ts <  '2024-06-16 00:30:00.000'
  AND (ts > '2024-06-15 23:45:12.456'
       OR (ts = '2024-06-15 23:45:12.456' AND id > 0x0190A3B45C6D7E8F9A0B1C2D3E4F5A6B))
ORDER BY ts, id
LIMIT 250;
```

---

## K-Way Merge

The query router receives sorted streams from N shards and must produce a single globally-sorted result.

```mermaid
graph TB
    subgraph "Shard Streams (pre-sorted by ts, id)"
        S1["Shard 1: [10:30:00.001, 10:30:00.005, 10:30:00.012, ...]"]
        S2["Shard 2: [10:30:00.002, 10:30:00.007, 10:30:00.009, ...]"]
        S3["Shard 3: [10:30:00.003, 10:30:00.006, 10:30:00.011, ...]"]
    end

    subgraph "Min-Heap (size N)"
        H["Heap top: smallest ts across all shards<br/><br/>Pop min → add to result<br/>Pull next from that shard<br/>Push to heap<br/>Repeat until limit reached"]
    end

    subgraph "Output"
        OUT["[10:30:00.001, 10:30:00.002, 10:30:00.003,<br/> 10:30:00.005, 10:30:00.006, 10:30:00.007, ...]"]
    end

    S1 & S2 & S3 --> H --> OUT

    style H fill:#f5a623,color:#000
    style OUT fill:#50c878,color:#000
```

### Complexity

```
N = number of shards (40-50)
K = result page size (10,000)

Merge: O(K * log N) — for each of K results, heap operation is O(log N)
       = O(10,000 * log 50) ≈ O(10,000 * 6) = O(60,000 comparisons)
       = negligible (sub-millisecond)
```

The merge itself is cheap. The latency is dominated by the slowest shard's query execution.

---

## Handling Shard Failures During Query

```mermaid
flowchart TD
    QR[Query Router] -->|Fan out| ALL[Send to all N shards]
    ALL --> WAIT[Wait with timeout<br/>e.g., 5 seconds]
    WAIT --> CHECK{All shards<br/>responded?}

    CHECK -->|Yes| MERGE[K-way merge<br/>Return 200]
    CHECK -->|Partial| DECIDE{How many<br/>failed?}

    DECIDE -->|"< 10% of shards"| PARTIAL["Return 200<br/>+ header X-Partial-Results: true<br/>+ metadata showing which shards failed"]
    DECIDE -->|">= 10% of shards"| RETRY["Retry failed shards once<br/>with shorter timeout"]
    RETRY --> FINAL{Still failing?}
    FINAL -->|Yes| ERR["Return 503<br/>Service Unavailable"]
    FINAL -->|No| MERGE

    style MERGE fill:#50c878,color:#000
    style PARTIAL fill:#f5a623,color:#000
    style ERR fill:#ff6b6b,color:#fff
```

**Trade-off:** Returning partial results (with a header indicating incompleteness) vs. failing the entire query. For a debugging/ops tool, partial results are more useful than a 503.

---

## Query Latency Breakdown

```mermaid
pie title "P99 Query Latency (~2-4 seconds)"
    "Network: Router → Shard replicas" : 5
    "MySQL partition pruning + range scan" : 60
    "Data transfer: Shard → Router" : 25
    "K-way merge in Router" : 2
    "Serialization (JSON)" : 8
```

The dominant cost is the MySQL range scan across the partition. For a 3600-second window at 250k RPS per shard slice, each shard scans:

```
250,000 / 40 shards = 6,250 logs/sec per shard
x 3600 seconds = 22.5M rows per shard per query
At 1 KB each = ~22.5 GB scanned per shard (worst case, no LIMIT)
```

This is why pagination with reasonable `LIMIT` sizes (10,000-100,000) is critical.

---

## Read Path Optimization: Read Replicas

```mermaid
graph TB
    subgraph "Write Path"
        W[Writer Workers] -->|INSERT| P[(Primary)]
    end

    subgraph "Read Path"
        QR[Query Router] -->|SELECT| R1[(Replica 1)]
        QR -->|SELECT| R2[(Replica 2<br/>optional)]
    end

    P -->|"Async binlog<br/>replication"| R1
    P -->|"Async binlog<br/>replication"| R2

    style P fill:#7b68ee,color:#fff
    style R1 fill:#4a90d9,color:#fff
    style R2 fill:#4a90d9,color:#fff
```

Reads go to replicas exclusively. This ensures:
- Query load never impacts write performance on primaries
- Read scaling is independent — add more replicas if query load grows
- Replication lag (~1 second) is acceptable for log querying use case
