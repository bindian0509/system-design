# Cost Model

## 1. Scale Assumptions

```
Events:         10B/day = ~115K/sec avg, ~500K/sec peak
Event size:     ~500 bytes raw, ~200 bytes compressed (Snappy)
Raw data:       ~5 TB/day uncompressed, ~2 TB/day compressed
Total videos:   1B total, ~100M active in any 30-day window
Regions:        3 (US-East, EU-West, AP-South)
Pricing:        AWS, 2026 estimates, USD
```

---

## 2. Component-Level Cost Breakdown

### Kafka (Amazon MSK)

```
Cluster per region:
  Brokers: 12 x kafka.m5.4xlarge (16 vCPU, 64GB RAM)
  Sizing: 500K events/sec peak / ~50K events/sec/broker = 10 + 2 headroom
  Storage: 72h retention x 2TB/day compressed x RF 3 = ~432TB across cluster
  Tiered storage to S3 after 6h (reduces EBS costs)

Per-region:  12 x $1,800/mo (instance) + ~$15,000/mo (EBS gp3) = ~$36,600/mo
3 regions:   ~$110,000/mo
```

### Flink (on Amazon EKS)

```
Per region:
  Task Managers: 30 x c6i.4xlarge (16 vCPU, 32GB RAM)
  Sizing: 500K events/sec / ~20K events/sec/TM = 25 TMs + 5 headroom
  Job Managers: 3 x c6i.2xlarge (HA setup)
  RocksDB state: NVMe local storage (included with c6i)
  Checkpoint storage: S3 (~50GB/checkpoint x 24/day = ~1.2TB/day) → ~$28/mo

Per-region:  30 x $990/mo + 3 x $495/mo = ~$31,200/mo
3 regions:   ~$93,600/mo
```

### Redis (Amazon ElastiCache)

```
Working set calculation:
  100M active videos x ~10 keys/video x ~100 bytes/key = ~100GB per region
  With Redis overhead + headroom: ~200GB per region

Per region:
  6 x cache.r7g.2xlarge (52GB RAM) — 3 primary + 3 replica
  Total capacity: 312GB, ~200GB usable after replication overhead

Per-region:  6 x $620/mo = ~$3,720/mo
3 regions:   ~$11,200/mo
```

### Cassandra (Self-Managed on EC2)

```
Dataset:
  1B videos x 365 days x ~50 bytes/row = ~18TB total
  Replication factor 3 = ~54TB stored
  Write throughput: ~50K writes/sec (batch reconciliation bursts)

Per region:
  9 x i3.4xlarge (16 vCPU, 122GB RAM, 3.8TB NVMe)
  Total raw storage per region: 34TB, RF 3 across nodes

Per-region:  9 x $1,290/mo = ~$11,600/mo
3 regions:   ~$34,800/mo
```

### ClickHouse (Self-Managed on EC2)

```
Dataset:
  Fact table: ~10B rows/day x ~200 bytes/row compressed = ~2TB/day
  2-year retention: ~1.5PB uncompressed
  Columnar compression (~10:1): ~150TB compressed

Per region:
  12 x r6i.4xlarge (16 vCPU, 128GB RAM) — 6 shards x 2 replicas
  EBS: 15TB gp3 per node = ~180TB per region
  S3 cold tier for data > 90 days old

Per-region:  12 x $1,080/mo + 15TB x $80/TB/mo = ~$27,360/mo

Cost optimization: OLAP can be single primary region + 1 replica region
  2 regions:  ~$55,000/mo (instead of ~$82,000/mo for all 3)
```

### S3 (Data Lake)

```
Storage tiers:
  Raw events:
    Hot (0-30 days):      60TB  x $0.023/GB  = ~$1,400/mo
    Warm (30-90 days):    120TB x $0.0125/GB = ~$1,500/mo
    Cold (90-365 days):   550TB x $0.004/GB  = ~$2,200/mo

  Aggregated outputs + checkpoints: ~10TB hot = ~$230/mo
  Cross-region replication: ~2TB/day x $0.02/GB = ~$1,200/mo

Total S3: ~$6,500/mo
```

### Supporting Infrastructure

```
Edge ingestion (Lambda@Edge / CloudFront Functions):
  10B invocations/mo x $0.0000006/invocation    = ~$6,000/mo
  Data transfer: ~50TB egress x $0.09/GB         = ~$4,500/mo

EKS control plane: 3 clusters x $73/mo           = ~$220/mo
Load balancers (ALB): 3 regions x $200/mo         = ~$600/mo
Schema Registry (Confluent Cloud or self-hosted): = ~$500/mo
Monitoring (Prometheus + Grafana Cloud):           = ~$3,000/mo
Data quality (Great Expectations infra):           = ~$500/mo

Total supporting: ~$15,300/mo
```

---

## 3. Total Cost Summary

```
┌────────────────────────────────────────────────────────────────────┐
│  Monthly Infrastructure Cost — YouTube-Scale View Counting          │
├───────────────────────────┬───────────────┬────────────────────────┤
│  Component                │  Monthly Cost │  % of Total            │
├───────────────────────────┼───────────────┼────────────────────────┤
│  Kafka (MSK)              │   $110,000    │  33.7%                 │
│  Flink (EKS)              │    $93,600    │  28.7%                 │
│  ClickHouse (EC2)         │    $55,000    │  16.8%                 │
│  Cassandra (EC2)          │    $34,800    │  10.7%                 │
│  Supporting infra         │    $15,300    │   4.7%                 │
│  Redis (ElastiCache)      │    $11,200    │   3.4%                 │
│  S3 Data Lake             │     $6,500    │   2.0%                 │
├───────────────────────────┼───────────────┼────────────────────────┤
│  Subtotal (on-demand)     │  ~$326,400    │  100%                  │
│                           │               │                        │
│  Reserved/Spot savings    │  -$105,000    │  ~32% discount         │
│  (1yr RI for Kafka,       │               │                        │
│   Flink, ClickHouse;      │               │                        │
│   Spot for Spark batch)   │               │                        │
├───────────────────────────┼───────────────┼────────────────────────┤
│  TOTAL (optimized)        │  ~$221,000/mo │                        │
│                           │  ~$2.65M/year │                        │
├───────────────────────────┴───────────────┴────────────────────────┤
│  Cost per 1M view events:              $0.66                       │
│  Cost per active video per month:      $0.0022                     │
│  Cost per GB of raw data ingested:     $3.68                       │
└────────────────────────────────────────────────────────────────────┘
```

---

## 4. Cost Optimization Levers

| Lever | Savings | Trade-off |
|-------|---------|-----------|
| **Kafka tiered storage** (S3 after 6h) | ~20% of Kafka cost | Slight tail latency on replaying old data |
| **Spot instances for Spark batch** | ~70% of Spark cost | Job retries on spot eviction (acceptable for batch) |
| **ClickHouse in 2 regions** (not 3) | ~40% of ClickHouse cost | Higher OLAP query latency from third region |
| **S3 Intelligent Tiering** | ~15% of S3 cost | Minor retrieval latency for infrequently accessed data |
| **Flink incremental checkpoints** | ~10% of Flink cost | Slightly longer recovery (more checkpoints to replay) |
| **Reduce Kafka retention 72h→24h** | ~30% of Kafka EBS | Less replay buffer for debugging and reprocessing |
| **Graviton (ARM) instances** | ~15% across compute | Broadly supported now; minimal compatibility risk |
| **ClickHouse cold storage on S3** | ~25% of ClickHouse EBS | Queries on old data hit S3 (seconds vs. ms) |
| **Compress events more aggressively** (Zstd) | ~10% of S3 + Kafka | Higher CPU at edge (compression) and Flink (decompression) |

**Aggressive optimization scenario:**
Applying Kafka tiered storage + Spot Spark + 2-region ClickHouse + Graviton:
```
Optimized total: ~$165,000/mo (~$2.0M/year)
Savings: ~$56,000/mo vs. baseline optimized
Trade-offs: Acceptable for most production workloads
```

---

## 5. Cost Scaling Characteristics

```
                Cost ($)
                 ▲
                 │                         ╱
                 │                       ╱   Kafka + Flink
            300K │                     ╱     (LINEAR with events/sec)
                 │                   ╱       Every doubling of traffic ≈
                 │                 ╱         doubles Kafka + Flink cost
                 │               ╱
            200K │    ─────────╱───────────  ClickHouse + Cassandra
                 │   ╱                       (SUB-LINEAR)
                 │  ╱                        Compression + rollups mean
                 │ ╱                         2x data ≠ 2x storage
            100K │╱──────────────────────── Redis + S3
                 │                          (NEARLY FLAT)
                 │                          Bounded by active videos,
                 │                          not total events
              0  └──────────────────────────────────────▶ Events/day
                 1B    5B    10B   20B   50B
```

**Key insight for the interview:**

The **ingestion layer** (Kafka + Flink) scales **linearly** with event volume — this is unavoidable because every event must be processed.

The **storage and serving layers** scale **sub-linearly** because:
- Pre-aggregation: 5TB raw → ~200GB aggregated (25x reduction)
- Columnar compression: 10:1 ratio in ClickHouse
- Bounded working set: Redis holds ~100M active videos regardless of whether daily events are 5B or 50B
- Rollups: Materialized views compress hours of data into single rows

**Implication:** As the platform grows, optimize the ingestion layer first. That's where the marginal cost lives.

---

## 6. Cost vs. Accuracy Trade-offs

| Accuracy Level | Architecture | Monthly Cost | Use Case |
|----------------|-------------|-------------|----------|
| ~95% (approximate) | Flink only, no batch reconciliation | ~$130K | Internal dashboards, non-monetized content |
| ~99.5% (near-exact) | Flink + daily batch | ~$180K | Video page display, creator dashboards |
| ~99.9% (exact) | Flink + hourly batch + ML bot detection | ~$221K | Ad monetization, revenue calculations |
| 100% (auditable) | Above + SOX-compliant audit trail + immutable storage | ~$250K | Financial reporting, regulatory compliance |

The system is designed at the 99.9% tier. The 100% tier adds audit logging and compliance controls but uses the same core infrastructure.
