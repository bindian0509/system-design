# Capacity Planning

## Overview

This document provides infrastructure sizing calculations to support the flight search system at scale.

**Target Scale:**
- 100M+ searches per day
- ~1,200 RPS average, 5,000 RPS peak
- < 2 second search latency (P95)
- 99.9% availability

---

## Traffic Analysis

### Daily Traffic Pattern

```
RPS
5000 |                    ████
4000 |                 ███    ███
3000 |              ███          ███
2000 |           ███                ███
1200 |_________███______________________███_________
1000 |      ███                            ███
 500 | ████                                    ████
     +----+----+----+----+----+----+----+----+----+
     0    3    6    9   12   15   18   21   24  Hour (UTC)
```

### Traffic Breakdown

| Time Period | RPS | % of Peak |
|-------------|-----|-----------|
| Off-peak (00:00-06:00 UTC) | 500 | 10% |
| Normal (06:00-12:00 UTC) | 1,200 | 24% |
| Peak (12:00-20:00 UTC) | 3,000-5,000 | 60-100% |
| Evening (20:00-00:00 UTC) | 1,500 | 30% |

### Request Type Distribution

| Request Type | % of Traffic | Avg Size | Compute |
|--------------|--------------|----------|---------|
| Flight Search | 70% | 50KB response | High |
| Price Check | 15% | 5KB response | Low |
| Autocomplete | 10% | 2KB response | Low |
| Booking | 3% | 10KB response | High |
| Alerts | 2% | 1KB response | Low |

---

## Compute Requirements

### Search Service

**Per-Request Profile:**
- CPU: 50ms average computation
- Memory: 100MB peak working set
- Network: 50KB response + 20KB to suppliers

**Instance Sizing:**

```
Requests per instance = (1000ms / 50ms) × utilization_target
                      = 20 × 0.7  (70% target utilization)
                      = 14 RPS per instance
```

| Load | RPS | Instances (4 vCPU, 8GB) |
|------|-----|-------------------------|
| Normal | 1,200 | 86 |
| Peak | 5,000 | 358 |
| With 20% headroom | 5,000 | 430 |

**Recommended Configuration:**
- Instance type: `c6i.xlarge` (4 vCPU, 8GB RAM)
- Minimum instances: 50 (maintain capacity during low traffic)
- Maximum instances: 500 (handle peak + bursts)
- Auto-scale trigger: 70% CPU utilization

### Supplier Gateway

**Per-Request Profile:**
- CPU: 10ms (mostly I/O wait)
- Memory: 50MB working set
- Network: High (fan-out to multiple suppliers)
- Connections: 500+ persistent connections to suppliers

**Instance Sizing:**

```
# Each instance handles concurrent supplier connections
# Limited by connection pool and memory
Max concurrent per instance = 1000
At 200ms avg supplier latency = 5000 RPS capacity

Instances needed = Peak RPS / 5000 × safety_factor
                 = 5000 / 5000 × 2
                 = 10 instances minimum
```

**Recommended Configuration:**
- Instance type: `c6i.2xlarge` (8 vCPU, 16GB RAM)
- Minimum instances: 10
- Maximum instances: 50
- Each instance maintains connection pools to all 500+ suppliers

### Booking Service

**Per-Request Profile:**
- CPU: 100ms (payment processing, supplier confirmation)
- Memory: 200MB
- I/O: Database writes, supplier API calls

**Sizing:**

```
Bookings per day = 100M searches × 2% conversion = 2M bookings
Peak booking RPS = 2M / 86400 × 5 (peak factor) = 116 RPS

At 100ms/request with 70% utilization:
Instances = 116 / (10 × 0.7) = 17 instances
```

**Recommended Configuration:**
- Instance type: `m6i.xlarge` (4 vCPU, 16GB RAM)
- Minimum instances: 10
- Maximum instances: 50

### Pricing Engine

**Per-Request Profile:**
- CPU: 5ms (mostly math operations)
- Memory: 50MB
- Often called in batch (100+ flights per search)

**Sizing:**

```
Calls per second = 5000 searches × 100 flights = 500,000/s
At 5ms/call with batching (10ms for 100 flights):
Instances = 50 (for redundancy and latency)
```

**Recommended Configuration:**
- Instance type: `c6i.xlarge` (4 vCPU, 8GB RAM)
- Minimum instances: 20
- Maximum instances: 100

### Prediction Service

**Per-Request Profile:**
- CPU: 30ms (ML inference)
- Memory: 2GB (model loading)
- GPU: Optional (NVIDIA T4 for LSTM acceleration)

**Sizing:**

```
Prediction requests = 10% of searches request predictions
= 500 RPS at peak

At 30ms/inference with 70% utilization:
Instances = 500 / (33 × 0.7) = 22 instances
```

**Recommended Configuration:**
- Instance type: `g4dn.xlarge` (4 vCPU, 16GB RAM, 1 NVIDIA T4)
- Or CPU-only: `c6i.2xlarge` (8 vCPU, 16GB RAM)
- Minimum instances: 10
- Maximum instances: 50

---

## Database Sizing

### PostgreSQL

**Data Volume Estimates:**

| Table | Row Size | Rows/Day | Retention | Total Size |
|-------|----------|----------|-----------|------------|
| users | 500B | 50K | Forever | 50GB |
| bookings | 2KB | 2M | 7 years | 5TB |
| booking_passengers | 500B | 5M | 7 years | 2.5TB |
| booking_segments | 300B | 4M | 7 years | 1TB |
| price_alerts | 500B | 500K | 1 year | 100GB |
| search_history | 200B | 100M | 90 days | 200GB |

**Total: ~9TB primary data**

**Configuration:**

| Component | Specification |
|-----------|---------------|
| Instance | `db.r6g.4xlarge` (16 vCPU, 128GB RAM) |
| Storage | 10TB gp3 SSD |
| IOPS | 16,000 provisioned |
| Throughput | 1000 MB/s |
| Replicas | 3 read replicas |
| Backup | Daily snapshots, 30-day retention |

**Connection Pooling (PgBouncer):**
- Pool size: 500 connections per application instance
- Max connections to DB: 2000
- PgBouncer instances: 3 (for HA)

### Redis Cluster

**Data Volume:**

| Data Type | Count | Avg Size | Total |
|-----------|-------|----------|-------|
| Search cache entries | 10M | 50KB | 500GB |
| Route prices | 1M | 10KB | 10GB |
| Sessions | 5M | 1KB | 5GB |
| Rate limits | 10M | 100B | 1GB |
| Miscellaneous | - | - | 50GB |

**Total: ~600GB with 30% headroom = 800GB**

**Configuration:**

| Component | Specification |
|-----------|---------------|
| Nodes | 6 (3 primary, 3 replica) |
| Instance | `r6g.2xlarge` (8 vCPU, 52GB RAM) |
| Total Memory | 312GB usable |
| Cluster Mode | Enabled (16384 slots) |
| Persistence | RDB snapshots every 15 min |

**Memory Distribution:**
- 70% for search cache
- 15% for route prices
- 10% for sessions/rate limits
- 5% overhead

### ClickHouse

**Data Volume (90-day retention):**

| Table | Rows/Day | Row Size | 90-Day Size |
|-------|----------|----------|-------------|
| price_history | 500M | 200B | 9TB |
| search_events | 100M | 500B | 4.5TB |
| booking_events | 2M | 500B | 90GB |
| supplier_performance | 50M | 100B | 450GB |

**Total: ~15TB with compression (10x) = 1.5TB**

**Configuration:**

| Component | Specification |
|-----------|---------------|
| Nodes | 3-node cluster |
| Instance | `r6g.4xlarge` (16 vCPU, 128GB RAM) |
| Storage | 2TB NVMe per node |
| Replication | 2 copies |

### Kafka

**Topic Sizing:**

| Topic | Partitions | Retention | Daily Volume | Storage |
|-------|------------|-----------|--------------|---------|
| search-events | 64 | 7 days | 50GB | 350GB |
| price-updates | 128 | 24 hours | 20GB | 20GB |
| booking-events | 32 | 30 days | 2GB | 60GB |
| alert-triggers | 16 | 7 days | 1GB | 7GB |

**Total: ~450GB**

**Configuration:**

| Component | Specification |
|-----------|---------------|
| Brokers | 5 |
| Instance | `m6i.2xlarge` (8 vCPU, 32GB RAM) |
| Storage | 500GB SSD per broker |
| Replication Factor | 3 |
| Min ISR | 2 |

### ElasticSearch

**Index Sizing:**

| Index | Documents | Size |
|-------|-----------|------|
| airports | 10K | 10MB |
| airlines | 500 | 1MB |
| routes | 50K | 50MB |

**Total: <100MB (very small)**

**Configuration:**

| Component | Specification |
|-----------|---------------|
| Nodes | 3 (1 primary, 2 replicas) |
| Instance | `t3.medium` (2 vCPU, 4GB RAM) |
| Storage | 50GB gp3 |

---

## Network Architecture

### Load Balancing

**API Gateway / ALB:**
- Target: 10,000 RPS capacity
- Cross-zone load balancing enabled
- Connection draining: 30 seconds
- Health check interval: 5 seconds

**Internal Load Balancing:**
- Service mesh (Istio) for service-to-service
- gRPC load balancing for internal APIs

### Bandwidth Requirements

| Flow | Bandwidth |
|------|-----------|
| Client → API Gateway | 500 Mbps average, 2 Gbps peak |
| Search Service → Suppliers | 2 Gbps aggregate |
| Internal service traffic | 1 Gbps |
| Database replication | 500 Mbps |

**Total egress: ~5 Gbps peak**

### CDN

- CloudFront distribution for static assets
- Edge locations: Global
- Cache hit rate target: 95% for static content

---

## Availability Zones

### Multi-AZ Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                        Region: US-East-1                         │
│                                                                  │
│  ┌────────────────────┐  ┌────────────────────┐                 │
│  │       AZ-1a        │  │       AZ-1b        │                 │
│  │                    │  │                    │                 │
│  │  Search: 40%       │  │  Search: 40%       │                 │
│  │  Booking: 50%      │  │  Booking: 50%      │                 │
│  │  Redis: Primary    │  │  Redis: Replica    │                 │
│  │  Postgres: Primary │  │  Postgres: Replica │                 │
│  │  Kafka: 2 brokers  │  │  Kafka: 2 brokers  │                 │
│  └────────────────────┘  └────────────────────┘                 │
│                                                                  │
│  ┌────────────────────┐                                         │
│  │       AZ-1c        │  (Standby for disaster recovery)       │
│  │                    │                                         │
│  │  Search: 20%       │                                         │
│  │  Booking: 0% (standby)                                       │
│  │  Redis: Replica    │                                         │
│  │  Postgres: Replica │                                         │
│  │  Kafka: 1 broker   │                                         │
│  └────────────────────┘                                         │
└─────────────────────────────────────────────────────────────────┘
```

### Disaster Recovery

| Component | RTO | RPO | Strategy |
|-----------|-----|-----|----------|
| Compute | 5 min | N/A | Auto-scaling in standby AZ |
| PostgreSQL | 15 min | 0 | Synchronous replica in AZ-1b |
| Redis | 5 min | 1 min | Automatic failover |
| Kafka | 5 min | 0 | Multi-AZ replication |

---

## Cost Estimate

### Monthly Cost Breakdown (US-East-1)

| Component | Configuration | Monthly Cost |
|-----------|---------------|--------------|
| **Compute** | | |
| Search Service | 100 × c6i.xlarge avg | $12,000 |
| Supplier Gateway | 20 × c6i.2xlarge | $4,800 |
| Booking Service | 20 × m6i.xlarge | $3,200 |
| Pricing Engine | 30 × c6i.xlarge | $3,600 |
| Prediction Service | 20 × g4dn.xlarge | $10,400 |
| **Databases** | | |
| PostgreSQL (RDS) | db.r6g.4xlarge + 3 replicas | $8,000 |
| Redis (ElastiCache) | 6 × r6g.2xlarge | $4,800 |
| ClickHouse (EC2) | 3 × r6g.4xlarge | $3,600 |
| ElasticSearch | 3 × t3.medium | $100 |
| **Messaging** | | |
| Kafka (MSK) | 5 × m6i.2xlarge | $2,500 |
| **Network** | | |
| ALB | 5,000 RPS capacity | $500 |
| Data Transfer | 100TB egress | $8,500 |
| CloudFront | 500TB transfer | $10,000 |
| **Storage** | | |
| S3 (backups, logs) | 50TB | $1,150 |
| EBS volumes | 30TB | $3,000 |
| **Monitoring** | | |
| CloudWatch | Metrics, logs | $2,000 |
| Datadog/equivalent | APM, infra | $5,000 |
| | | |
| **Total** | | **~$83,000/month** |

### Cost Optimization Opportunities

| Optimization | Potential Savings |
|--------------|-------------------|
| Reserved Instances (1-year) | 30-40% on compute |
| Spot Instances for batch jobs | 60-70% on ML training |
| S3 Intelligent Tiering | 20-30% on storage |
| Right-sizing after production data | 10-20% overall |

**Estimated optimized cost: ~$55,000-60,000/month**

---

## Scaling Thresholds

### Auto-Scaling Rules

| Service | Scale Up Trigger | Scale Down Trigger | Cooldown |
|---------|------------------|-------------------|----------|
| Search | CPU > 70% OR RPS > 50/instance | CPU < 30% for 10min | 60s up, 300s down |
| Booking | CPU > 60% | CPU < 25% for 15min | 120s up, 600s down |
| Supplier Gateway | Connections > 800/instance | Connections < 200 | 60s up, 300s down |

### Circuit Breaker Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Error rate | > 5% | > 10% |
| P99 latency | > 3s | > 5s |
| Database connection pool | > 70% | > 90% |
| Redis memory | > 70% | > 85% |

---

## Monitoring & Alerting

### Key SLIs

| SLI | Target | Measurement |
|-----|--------|-------------|
| Availability | 99.9% | Successful requests / Total requests |
| Search Latency (P95) | < 2s | Time to first result |
| Search Latency (P99) | < 3.5s | Time to complete results |
| Error Rate | < 0.1% | 5xx responses / Total requests |

### Alerting Thresholds

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| High Error Rate | > 1% for 5min | P1 | Page on-call |
| High Latency | P95 > 3s for 5min | P2 | Page on-call |
| Database Connection Pool | > 90% for 2min | P1 | Page DBA |
| Kafka Consumer Lag | > 100K messages | P2 | Alert team |
| Redis Memory | > 85% | P2 | Alert team |
| Certificate Expiry | < 14 days | P3 | Alert team |

---

## Capacity Review Schedule

| Review Type | Frequency | Participants |
|-------------|-----------|--------------|
| Weekly metrics review | Weekly | SRE team |
| Capacity planning | Monthly | SRE + Engineering leads |
| Cost optimization | Quarterly | SRE + Finance |
| Architecture review | Bi-annually | Engineering leadership |
| Disaster recovery test | Quarterly | SRE + All teams |
