# Capacity Planning

## Overview

This document details the capacity planning calculations for the 10 PB/day log ingestion system.

---

## Table of Contents

1. [Throughput Calculations](#throughput-calculations)
2. [Storage Requirements](#storage-requirements)
3. [Compute Requirements](#compute-requirements)
4. [Network Requirements](#network-requirements)
5. [Cost Estimates](#cost-estimates)

---

## Throughput Calculations

### Daily Volume Breakdown

```mermaid
pie title Daily Log Volume Distribution (10 PB)
    "Application Logs" : 50
    "Infrastructure Logs" : 25
    "Kubernetes Events" : 15
    "Security/Audit" : 10
```

### Throughput Metrics

| Metric | Value | Calculation |
|--------|-------|-------------|
| Daily Volume | 10 PB | Requirement |
| Hourly Average | 416.67 TB | 10 PB / 24 |
| Per-Second Average | 115.74 GB/s | 10 PB / 86,400 |
| Peak Ratio | 3x | Industry standard |
| Peak Throughput | 347.22 GB/s | 115.74 × 3 |

### Time-of-Day Traffic Pattern

```mermaid
xychart-beta
    title "Hourly Traffic Pattern (Relative to Average)"
    x-axis ["00", "02", "04", "06", "08", "10", "12", "14", "16", "18", "20", "22"]
    y-axis "Traffic Multiplier" 0 --> 3
    bar [0.5, 0.4, 0.4, 0.6, 1.5, 2.5, 2.8, 3.0, 2.5, 2.0, 1.5, 0.8]
```

---

## Storage Requirements

### Compression Analysis

```mermaid
flowchart LR
    subgraph Raw["Raw Data"]
        RAW[10 PB/day<br/>Uncompressed]
    end

    subgraph Compression["Compression"]
        ALGO[ClickHouse LZ4<br/>+ Column encoding]
    end

    subgraph Compressed["Compressed"]
        COMP[~1 PB/day<br/>10x compression]
    end

    RAW -->|10:1 ratio| Compression --> COMP

    style RAW fill:#ff6b6b
    style COMP fill:#6bcb77
```

### Storage by Tier

```mermaid
sankey-beta

    Raw,Hot Tier,7
    Hot Tier,Compressed Hot,0.7
    Raw,Warm Tier,30
    Warm Tier,Compressed Warm,3
    Raw,Cold Tier,365
    Cold Tier,Compressed Cold,36.5
```

### Detailed Storage Calculations

| Tier | Retention | Raw Volume | Compression | Compressed Volume |
|------|-----------|------------|-------------|-------------------|
| **Hot** | 7 days | 70 PB | 10x | 7 PB |
| **Warm** | 30 days | 300 PB | 10x | 30 PB |
| **Cold** | 365 days | 3.65 EB | 10x | 365 PB |

### Storage Growth Projection

```mermaid
xychart-beta
    title "Storage Growth Over Time (Compressed PB)"
    x-axis ["Month 1", "Month 3", "Month 6", "Month 9", "Month 12"]
    y-axis "Total Storage (PB)" 0 --> 400
    line [37, 67, 127, 247, 365]
```

### ClickHouse Storage Layout

```mermaid
flowchart TB
    subgraph Cluster["ClickHouse Cluster (Hot Tier)"]
        subgraph Shard1["Shard 1 (Day 1-2)"]
            S1R1[(500 TB)]
            S1R2[(500 TB)]
            S1R3[(500 TB)]
        end
        subgraph Shard2["Shard 2 (Day 3-4)"]
            S2R1[(500 TB)]
            S2R2[(500 TB)]
            S2R3[(500 TB)]
        end
        subgraph Shard3["Shard 3 (Day 5-6)"]
            S3R1[(500 TB)]
            S3R2[(500 TB)]
            S3R3[(500 TB)]
        end
        subgraph Shard4["Shard 4 (Day 7)"]
            S4R1[(500 TB)]
            S4R2[(500 TB)]
            S4R3[(500 TB)]
        end
    end

    TOTAL["Total: ~7 PB compressed<br/>4 shards × 3 replicas × 500 TB = 6 PB usable"]
```

---

## Compute Requirements

### Kafka Cluster Sizing

```mermaid
flowchart TB
    subgraph Requirements["Requirements"]
        THROUGHPUT[115 GB/s average<br/>345 GB/s peak]
        RETENTION[24-48h in-cluster]
        RF[Replication Factor: 3]
    end

    subgraph Sizing["Sizing Calculation"]
        BROKER_CAP[Per-broker capacity:<br/>1-2 GB/s write]
        BROKERS[Brokers needed:<br/>345 / 1.5 ≈ 230 brokers]
        OVERHEAD[+ 20% overhead<br/>≈ 275 brokers total]
    end

    subgraph Distribution["Distribution"]
        R1[Region 1: 100 brokers]
        R2[Region 2: 100 brokers]
        R3[Region 3: 75 brokers]
    end

    Requirements --> Sizing --> Distribution
```

### Kafka Broker Specifications

| Component | Specification | Quantity per Broker |
|-----------|--------------|---------------------|
| **CPU** | 32 cores | 1 |
| **Memory** | 128 GB | 1 |
| **Storage** | NVMe SSD | 4 TB × 6 drives |
| **Network** | 25 Gbps | Dual-attached |

### Flink Cluster Sizing

```mermaid
flowchart TB
    subgraph Tasks["Processing Tasks"]
        READ[Read from Kafka<br/>115 GB/s]
        PII[PII Redaction<br/>CPU-intensive]
        VALID[Schema Validation<br/>CPU-bound]
        WRITE[Write to ClickHouse<br/>I/O-intensive]
    end

    subgraph Sizing["Sizing"]
        PARALLEL[Parallelism:<br/>Thousands of tasks]
        TM[Task Managers:<br/>~500 instances]
        SLOTS[Slots per TM: 4]
    end

    subgraph Specs["Per Task Manager"]
        CPU[8 cores]
        MEM[32 GB RAM]
        DISK[100 GB scratch]
    end

    Tasks --> Sizing --> Specs
```

### ClickHouse Cluster Sizing

```mermaid
flowchart TB
    subgraph HotTier["Hot Tier Requirements"]
        STORAGE_H[7 PB storage]
        WRITE_H[115 GB/s write]
        READ_H[1000+ QPS]
    end

    subgraph Nodes["Node Calculation"]
        PER_NODE[Per-node capacity:<br/>- 50 TB storage<br/>- 2 GB/s write<br/>- 50 QPS]
        TOTAL_NODES[Nodes needed:<br/>max(7000/50, 115/2, 1000/50)<br/>= max(140, 58, 20)<br/>= 140 nodes minimum]
    end

    subgraph Config["Configuration"]
        SHARDS[Shards: 50]
        REPLICAS[Replicas: 3]
        TOTAL[Total: 150 nodes<br/>(50 × 3)]
    end

    HotTier --> Nodes --> Config
```

### ClickHouse Node Specifications

| Component | Hot Tier | Warm Tier |
|-----------|----------|-----------|
| **CPU** | 64 cores | 32 cores |
| **Memory** | 512 GB | 256 GB |
| **Storage** | 12 × 4 TB NVMe | 12 × 8 TB SSD |
| **Network** | 50 Gbps | 25 Gbps |

---

## Network Requirements

### Bandwidth by Component

```mermaid
flowchart LR
    subgraph Ingress["Ingress Traffic"]
        COLLECT[Collection Layer<br/>115 GB/s]
    end

    subgraph Internal["Internal Traffic"]
        K_REP[Kafka Replication<br/>230 GB/s (RF=3)]
        CH_REP[ClickHouse Replication<br/>230 GB/s (RF=3)]
        FLINK_K[Flink ↔ Kafka<br/>230 GB/s]
        FLINK_CH[Flink ↔ ClickHouse<br/>115 GB/s]
    end

    subgraph Egress["Egress Traffic"]
        QUERY[Query Results<br/>~10 GB/s]
        COLD[Cold Tier Export<br/>~15 GB/s]
    end

    COLLECT --> K_REP
    K_REP --> FLINK_K
    FLINK_K --> FLINK_CH
    FLINK_CH --> CH_REP
    CH_REP --> QUERY
    CH_REP --> COLD
```

### Total Network Capacity

| Traffic Type | Bandwidth | Notes |
|-------------|-----------|-------|
| **Ingestion** | 115 GB/s | From collectors to Kafka |
| **Kafka Internal** | 345 GB/s | Replication (3x) |
| **Processing** | 230 GB/s | Flink read + write |
| **ClickHouse** | 345 GB/s | Replication (3x) |
| **Cross-Region** | ~50 GB/s | Kafka MirrorMaker |
| **Query Egress** | ~10 GB/s | Query results |

---

## Cost Estimates

### Monthly Cost Breakdown

```mermaid
pie title Monthly Cost Distribution
    "Compute (Kafka)" : 25
    "Compute (ClickHouse)" : 30
    "Compute (Flink)" : 15
    "Storage (Hot/Warm)" : 10
    "Storage (Cold S3)" : 12
    "Network" : 5
    "Operations" : 3
```

### Detailed Cost Estimate (AWS)

| Component | Quantity | Unit Cost | Monthly Cost |
|-----------|----------|-----------|--------------|
| **Kafka Brokers** | 275 × i3en.6xlarge | $1.90/hr | $380,000 |
| **ClickHouse Hot** | 150 × i3en.12xlarge | $4.00/hr | $430,000 |
| **ClickHouse Warm** | 100 × d3en.12xlarge | $3.50/hr | $250,000 |
| **Flink Cluster** | 500 × m5.2xlarge | $0.38/hr | $140,000 |
| **Trino Cluster** | 50 × r5.4xlarge | $1.00/hr | $36,000 |
| **S3 Cold Storage** | 365 PB | $21/TB/month | $7,665,000 |
| **Network Transfer** | ~500 TB/month | $0.02/GB | $10,000 |
| **Total** | | | **~$8.9M/month** |

### Cost Optimization Strategies

```mermaid
flowchart TB
    subgraph Strategies["Cost Optimization"]
        RI[Reserved Instances<br/>-40% compute]
        SP[Savings Plans<br/>-30% flexibility]
        SPOT[Spot for Flink<br/>-60% processing]
        S3IT[S3 Intelligent Tiering<br/>-30% cold storage]
        COMP[Better Compression<br/>-20% storage]
    end

    subgraph Impact["Impact"]
        BEFORE[Baseline: $8.9M/month]
        AFTER[Optimized: ~$5.5M/month]
        SAVINGS[Savings: ~38%]
    end

    Strategies --> Impact
```

---

## Scaling Guidelines

### Horizontal Scaling Thresholds

```mermaid
flowchart TB
    subgraph Metrics["Scaling Metrics"]
        CPU[CPU > 70%]
        MEM[Memory > 80%]
        DISK[Disk > 75%]
        LAG[Kafka Lag > 5min]
        QUERY[Query p95 > 30s]
    end

    subgraph Actions["Scaling Actions"]
        ADD_KAFKA[Add Kafka brokers]
        ADD_CH[Add ClickHouse shards]
        ADD_FLINK[Scale Flink parallelism]
        ADD_TRINO[Add Trino workers]
    end

    CPU -->|Flink| ADD_FLINK
    MEM -->|ClickHouse| ADD_CH
    DISK -->|ClickHouse| ADD_CH
    LAG -->|Kafka/Flink| ADD_KAFKA
    LAG -->|Kafka/Flink| ADD_FLINK
    QUERY -->|Trino| ADD_TRINO
```

### Scaling Formula

| Component | Scale When | Add |
|-----------|-----------|-----|
| **Kafka** | Broker CPU > 70% | +10 brokers |
| **Flink** | Consumer lag > 5min | +50 task managers |
| **ClickHouse** | Query p95 > 10s | +1 shard (3 nodes) |
| **Trino** | Queue depth > 100 | +10 workers |

---

## Resource Summary

### Total Infrastructure

```mermaid
mindmap
    root((Infrastructure<br/>Summary))
        Kafka
            275 brokers
            6.6 PB storage
            3 regions
        Flink
            500 task managers
            2000 task slots
            Auto-scaling
        ClickHouse
            250 nodes total
            150 hot
            100 warm
        Trino
            50 workers
            Query federation
        Cold Storage
            365 PB S3
            Parquet format
            WORM enabled
```

### Capacity Buffer

| Component | Current Need | Provisioned | Buffer |
|-----------|-------------|-------------|--------|
| **Ingestion** | 115 GB/s | 200 GB/s | 74% |
| **Hot Storage** | 7 PB | 9 PB | 29% |
| **Query** | 1000 QPS | 2500 QPS | 150% |

---

## Growth Planning

### 24-Month Projection

```mermaid
xychart-beta
    title "Capacity Growth Projection"
    x-axis ["Now", "+6mo", "+12mo", "+18mo", "+24mo"]
    y-axis "Daily Ingestion (PB)" 0 --> 30
    line [10, 13, 17, 22, 28]
    line [20, 26, 34, 44, 56]
```

*Lines represent baseline (1.3x/year) and high (1.5x/year) growth scenarios*

### Capacity Expansion Plan

| Timeframe | Trigger | Action |
|-----------|---------|--------|
| **Now** | Baseline | Deploy initial capacity |
| **+6 months** | 30% growth | Add 2 ClickHouse shards |
| **+12 months** | 70% growth | Add 50 Kafka brokers |
| **+18 months** | 120% growth | Second cluster deployment |
| **+24 months** | 180% growth | Third region expansion |
