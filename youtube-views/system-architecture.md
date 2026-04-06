# System Architecture

## High-Level Architecture

```mermaid
flowchart TB
    subgraph Clients ["Client Layer"]
        iOS[iOS App]
        Android[Android App]
        Web[Web Browser]
        TV[Smart TV / Console]
        EmbedPlayer[Embedded Player]
    end

    subgraph EdgeLayer ["Edge Ingestion Layer - 30+ Global PoPs"]
        CDN[CloudFront CDN PoP]
        SchemaVal[Schema Validation]
        GeoIP[MaxMind GeoIP Resolution]
        TSNorm[Timestamp Normalization to UTC]
        EdgeRL[Rate Limiter per user_id + video_id]
    end

    subgraph Backbone ["Event Backbone - Apache Kafka"]
        RawTopic[view-events-raw\n256 partitions, RF=3\nkey: video_id]
        DedupTopic[view-events-deduplicated\n128 partitions]
        ChangelogTopic[view-counts-changelog\n64 partitions, compacted]
    end

    subgraph SpeedLayer ["Speed Layer - Apache Flink"]
        Deser[Deserialize Event]
        Dedup[Sliding Window Dedup\nBloom + RocksDB]
        Counter[View Counter\n5s Tumbling Window]
        Enrich[Dimension Enricher\nBroadcast State]
        MultiSink[Multi-Sink Output]
    end

    subgraph BatchLayer ["Batch Layer - Spark + S3"]
        S3Raw[(S3 Raw Events\nParquet, Snappy\nPartitioned by date/hour/region)]
        SparkDedup[Spark Exact Dedup\nSELECT DISTINCT user_id, video_id, date]
        S3Deduped[(S3 Deduplicated Events)]
        SparkAgg[Spark Aggregation\nPer video × hour × region × device]
    end

    subgraph ServingLayer ["Serving Layer"]
        API[View Count API]
        RedisCluster[(Redis Cluster\n3 primary + 3 replica\nReal-time Counts)]
        CassCluster[(Cassandra Cluster\n9 nodes per region\nHistorical Counts)]
    end

    subgraph OLAPLayer ["OLAP Layer"]
        CH[(ClickHouse\n6 shards × 2 replicas\nStar Schema)]
        Trino[Trino\nAd-hoc over S3]
        dbt[dbt Cubes\nAirflow Orchestrated]
    end

    Clients --> CDN
    CDN --> SchemaVal --> GeoIP --> TSNorm --> EdgeRL
    EdgeRL --> RawTopic

    RawTopic --> Deser --> Dedup --> Counter --> Enrich --> MultiSink
    MultiSink -->|counts| RedisCluster
    MultiSink -->|deduplicated events| DedupTopic
    MultiSink -->|count changelog| ChangelogTopic

    RawTopic -->|Kafka Connect S3 Sink| S3Raw
    S3Raw --> SparkDedup --> S3Deduped --> SparkAgg
    SparkAgg --> CH
    SparkAgg -->|reconciled counts| RedisCluster
    SparkAgg -->|historical| CassCluster

    API --> RedisCluster
    API --> CassCluster
    CH --> dbt
    Trino --> S3Raw
```

---

## Happy Case: User Watches a Video

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant SDK as Client SDK
    participant E as Edge PoP (CDG-1, Paris)
    participant K as Kafka (EU-West)
    participant F as Flink (EU-West)
    participant R as Redis (EU-West)
    participant S3 as S3 (EU-West)

    U->>SDK: Watches video for 35 seconds
    SDK->>SDK: Generate client_dedup_token (UUID)
    SDK->>E: POST /v1/events/view
    Note right of SDK: {video_id, user_id, session_id,<br/>watch_duration_ms: 35000,<br/>client_dedup_token, client_timestamp}

    E->>E: Validate schema (required fields present)
    E->>E: Resolve IP → country: FR, region: IDF, city: Paris
    E->>E: Attach server_timestamp (authoritative)
    E->>E: Rate limit check (user_id + video_id < 50/min)
    E->>K: Produce to view-events-raw (key: video_id)
    E-->>SDK: 202 Accepted (async — don't block playback)

    par Speed Layer
        K->>F: Consume event (partition 42, offset 1_234_567)
        F->>F: Bloom filter check (user_id + video_id)
        Note right of F: Bloom says "probably not seen" → skip RocksDB
        F->>F: Add to 5s tumbling window for video_id
        F->>F: Window fires: 247 new views for this video in last 5s
        F->>R: INCRBY vc:{video_id} 247
        F->>R: INCRBY vc:{video_id}:geo:FR 12
        F->>K: Produce deduplicated event to view-events-deduplicated
    and S3 Sink
        K->>S3: Kafka Connect writes Parquet batch
        Note right of S3: s3://lake/raw/year=2026/month=04/day=06/hour=14/region=eu-west/
    end

    Note over U,R: User refreshes page after 8 seconds
    U->>E: GET /v1/videos/{id}/views
    E->>R: GET vc:{video_id}
    R-->>E: 1_234_814
    E-->>U: {"views": 1234814, "freshness": "real-time"}
```

---

## Component Deep Dives

### 1. Edge Ingestion Layer

Deployed at 30+ CDN PoPs globally. Stateless, horizontally scaled.

**Responsibilities:**
- Schema validation — reject malformed events early (saves ~5-10% of downstream cost)
- Attach server-side timestamp — client clocks are unreliable; server timestamp is authoritative
- IP-to-geo resolution — MaxMind GeoIP at the edge (cheaper than doing it downstream for every event)
- Rate limiting — per `user_id` + `video_id` pair (first line of bot defense)
- Produce to nearest regional Kafka cluster

**Why at the edge?** At 10B events/day, every byte and millisecond saved at ingestion compounds. Rejecting 5-10% invalid events at the edge saves ~500GB/day of downstream processing. Geo resolution at the edge means the downstream pipeline doesn't need to carry raw IP addresses (PII benefit).

**Edge PoP configuration:**
```
rate_limiting:
  per_user_video: 50/minute    # No human watches 50 videos per minute
  per_ip: 1000/minute          # Shared IP (NAT) allowance
  burst: 10

validation:
  required_fields: [video_id, user_id, session_id, watch_duration_ms]
  max_event_size: 2KB
  max_watch_duration_ms: 86400000  # 24 hours (live streams)
```

---

### 2. Kafka Topology

```mermaid
flowchart LR
    subgraph Topics
        Raw[view-events-raw\n256 partitions\nRF=3, retention=72h\nCompaction: disabled]
        Dedup[view-events-deduplicated\n128 partitions\nRF=3, retention=24h]
        Changelog[view-counts-changelog\n64 partitions\nRF=3, compaction=enabled]
    end

    subgraph Producers
        Edge[Edge PoPs]
        Flink[Flink Pipeline]
        Spark[Spark Batch]
    end

    subgraph Consumers
        FlinkC[Flink Consumer Group]
        S3Sink[S3 Sink Connector]
        TrendC[Trending Service]
    end

    Edge -->|key: video_id| Raw
    Flink -->|deduplicated| Dedup
    Flink -->|count deltas| Changelog
    Spark -->|corrections| Changelog

    Raw --> FlinkC
    Raw --> S3Sink
    Dedup --> TrendC
```

**Partitioning by `video_id`** is critical: all events for a single video land on the same Flink task manager, enabling accurate per-video windowed dedup without distributed state coordination.

**Topic design rationale:**

| Topic | Partitions | Why |
|-------|-----------|-----|
| `view-events-raw` | 256 | High throughput (500K/sec peak). 256 = good parallelism for Flink. ~2K events/sec/partition. |
| `view-events-deduplicated` | 128 | Lower volume after dedup (~85-95% of raw). Consumed by trending + other downstream. |
| `view-counts-changelog` | 64 | Compacted topic. Low volume (count deltas per video, not individual events). |

**Hot partition mitigation (viral videos):**

A single viral video can generate 100K+ events/sec, overwhelming one partition. Solution: dynamic salted partitioning.

```
Normal mode:
  partition_key = video_id
  → All events on 1 partition (fine at normal volume)

Hot video detected (>10K events/min via Flink side-output):
  partition_key = video_id + ":" + (murmur3(user_id) % salt_factor)
  salt_factor = 4 (medium viral) or 16 (extreme viral)
  → Events spread across salt_factor partitions
  → Counts merged at serving layer: sum(vc:{video_id}:shard:*)

Detection: Flink maintains a Count-Min Sketch for top-K video velocity.
Edge layer picks up salt config via broadcast channel within ~30 seconds.
```

---

### 3. Flink Speed Layer

The core of the real-time path. Processes 115K events/sec avg with exactly-once semantics.

```mermaid
flowchart TB
    Input[Kafka: view-events-raw]
    
    Deser["[1] DeserializeEvent\nAvro → POJO\nSchema Registry lookup"]
    
    Dedup["[2] SlidingWindowDedup\nKeyed by (user_id, video_id)\n12-hour event-time window\nBloom filter + RocksDB state"]
    
    Counter["[3] ViewCounter\nKeyed by video_id\n5-second tumbling window\nIncremental aggregation"]
    
    Enrich["[4] DimensionEnricher\nAttach geo_region, device_category\nBroadcast state (refreshed 5min)"]
    
    Sink["[5] MultiSink"]
    
    RedisSink[Redis: INCRBY per video_id\n+ per video_id:region]
    DedupSink[Kafka: view-events-deduplicated]
    ChangelogSink[Kafka: view-counts-changelog]
    
    Input --> Deser --> Dedup --> Counter --> Enrich --> Sink
    Sink --> RedisSink
    Sink --> DedupSink
    Sink --> ChangelogSink
```

**Dedup strategy — Bloom filter + RocksDB hybrid:**

Why hybrid? Pure RocksDB state is accurate but expensive in I/O at 115K events/sec. Pure Bloom filter is fast but has false positives (missed dedup). The hybrid approach gets the best of both:

```
For each event (user_id, video_id):
  1. Hash into Bloom filter (in-memory, ~10 bits per element)
  2. If Bloom says "definitely not seen" → pass through (true negative)
  3. If Bloom says "maybe seen" → check RocksDB state (resolve ambiguity)
  4. If RocksDB confirms duplicate → discard
  5. If RocksDB says new → add to both Bloom and RocksDB, pass through

Performance impact:
  - ~85% of events: step 2 exits (Bloom true negative) → fast path
  - ~14% of events: step 2 triggers, step 4 confirms duplicate → medium path
  - ~1% of events: step 2 triggers (false positive), step 5 resolves → slow path
  - Net result: ~60% reduction in RocksDB I/O vs. pure state approach

Bloom filter sizing:
  - Expected elements per 12h window: ~2B (unique user+video pairs)
  - False positive rate target: 1%
  - Memory: ~2.4GB (10 bits × 2B elements / 1% FPR)
  - Distributed across Flink task managers by key
```

**Checkpointing:**
- Interval: every 60 seconds
- Backend: S3 (incremental checkpoints)
- On failure: restart from last checkpoint, replay Kafka from saved offsets
- Worst case: 60 seconds of re-processing
- Exactly-once guarantee: Kafka transactions + idempotent Redis writes (INCRBY is re-applied, corrected by batch)

---

### 4. Batch Layer (Spark + S3)

**S3 layout (Hive-style partitioning):**

```
s3://yt-views-lake/
  raw/
    year=2026/month=04/day=06/hour=14/
      region=us-east/
        part-00000.snappy.parquet
        part-00001.snappy.parquet
      region=eu-west/
        part-00000.snappy.parquet
  deduplicated/
    year=2026/month=04/day=06/
      part-00000.snappy.parquet
  aggregated/
    daily/year=2026/month=04/day=06/
    hourly/year=2026/month=04/day=06/hour=14/
```

**Hourly reconciliation job (the batch path):**

```mermaid
flowchart LR
    S3Raw[(S3 Raw Events\nhour=H)]
    Read[Read Parquet\n~200GB/hour]
    Dedup[Exact Dedup\nDISTINCT user_id,\nvideo_id, date]
    Agg[Aggregate\nPer video × hour ×\nregion × device]
    
    CH[(ClickHouse\nfact_view_counts)]
    Redis[(Redis\nOverwrite with\nexact count)]
    Cass[(Cassandra\nHistorical)]
    S3Out[(S3 Deduplicated)]

    S3Raw --> Read --> Dedup --> Agg
    Agg --> CH
    Agg --> Redis
    Agg --> Cass
    Dedup --> S3Out
```

1. Read raw events from `s3://yt-views-lake/raw/.../hour=H`
2. Exact dedup: `SELECT DISTINCT user_id, video_id, date FROM events` (deterministic, no probabilistic structures)
3. Compute authoritative counts per `(video_id, date, hour, region, device)`
4. Write to ClickHouse `fact_view_counts` table
5. Publish correction deltas to `view-counts-changelog` Kafka topic
6. Redis counts updated: `SET video:{id}:views <exact_count>` (overwrites approximate)
7. Write to Cassandra for historical retention

**Why both real-time AND batch?** Real-time Flink gives ~99.5% accuracy (Bloom filter misses + race conditions). Batch gives 100% accuracy. The hourly reconciliation corrects the ~0.5% drift. Users see "close enough" in real-time; creators see exact numbers in dashboards.

---

### 5. Serving Layer

```mermaid
flowchart TB
    Client[Client Request\nGET /v1/videos/id/views]
    
    CDNCache{CDN Cache\nTTL: 5s}
    APICache{API Local Cache\nTTL: 2s}
    Redis{Redis Cluster}
    Cass{Cassandra}
    
    Response[Response\nviews: 1234567\nfreshness: real-time]
    
    Client --> CDNCache
    CDNCache -->|HIT 95%| Response
    CDNCache -->|MISS| APICache
    APICache -->|HIT 3%| Response
    APICache -->|MISS| Redis
    Redis -->|HIT 99%+| Response
    Redis -->|MISS rare| Cass
    Cass --> Response
    Cass -->|backfill| Redis
```

**Redis key schema:**
```
vc:{video_id}              → total view count (integer)
vc:{video_id}:rt           → real-time delta since last reconciliation
vc:{video_id}:geo:{region} → per-region count (for quick geo breakdowns)
vc:{video_id}:daily:{date} → daily breakdown (for sparklines)
```

**Why Cassandra for historical, not just Redis?**

1B videos x ~10 keys each = 10B keys. At ~100 bytes/key = ~1TB of Redis. Too expensive for cold data. Instead:
- Redis holds hot videos (last 30 days of active videos, ~100M videos) → ~100GB
- Cassandra holds everything (1B videos × years of history) → ~18TB, cheap on NVMe

**Read path latency budget:**
```
CDN hit:          ~5ms  (95% of requests for popular videos)
API cache hit:    ~10ms (3% — recently fetched by another user on same pod)
Redis hit:        ~15ms (1.9% — cache miss but video is active)
Cassandra hit:    ~25ms (0.1% — old video, not in Redis)
```
