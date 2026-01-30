# Log Ingestion System Design - 10 PB/Day

A comprehensive system design document for a distributed log ingestion system capable of handling **10 petabytes per day** (~115 GB/s average, ~345 GB/s peak) for debugging/troubleshooting and compliance/audit trail use cases.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LOG SOURCES                                     │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│   │ Microservices│  │ Kubernetes   │  │ VMs/Infra    │                      │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                      │
└──────────┼─────────────────┼─────────────────┼──────────────────────────────┘
           │                 │                 │
           ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     COLLECTION LAYER (Fluent Bit/Vector)                     │
└─────────────────────────────────────────┬───────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          KAFKA (Multi-Region)                                │
└─────────────────────────────────────────┬───────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROCESSING LAYER (Flink Streaming)                        │
└─────────────────────────────────────────┬───────────────────────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
            ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
            │  HOT TIER    │      │  WARM TIER   │      │  COLD TIER   │
            │  ClickHouse  │      │  ClickHouse  │      │  S3/Parquet  │
            │  (7 days)    │      │  (30 days)   │      │  (1 year)    │
            └──────┬───────┘      └──────┬───────┘      └──────┬───────┘
                   │                     │                     │
                   └─────────────────────┼─────────────────────┘
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      QUERY LAYER (Trino/Presto Federation)                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Documentation Structure

```
log-ingestion/
├── README.md                              # This file
└── docs/
    ├── architecture.md                    # High-level architecture with Mermaid diagrams
    ├── capacity-planning.md               # Detailed capacity calculations
    ├── components/                        # Deep-dive component documentation
    │   ├── kafka.md                       # Kafka cluster design
    │   ├── clickhouse.md                  # ClickHouse storage design
    │   ├── flink.md                       # Flink processing pipeline
    │   ├── trino.md                       # Query layer federation
    │   ├── collection.md                  # Collection agents (Fluent Bit/Vector)
    │   └── cold-storage.md                # S3/Parquet cold tier
    └── runbooks/                          # Operational documentation
        ├── incident-response.md           # Incident handling procedures
        ├── scaling.md                     # Scaling operations
        └── maintenance.md                 # Maintenance procedures
```

## Key Documents

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | Complete system architecture with data flow diagrams |
| [Capacity Planning](docs/capacity-planning.md) | Storage, compute, and network calculations |
| [Kafka Design](docs/components/kafka.md) | Multi-region Kafka cluster design |
| [ClickHouse Design](docs/components/clickhouse.md) | Hot/warm tier storage architecture |
| [Flink Design](docs/components/flink.md) | Stream processing pipeline |
| [Trino Design](docs/components/trino.md) | Query federation layer |
| [Collection Layer](docs/components/collection.md) | Log collection agents |
| [Cold Storage](docs/components/cold-storage.md) | Long-term S3/Parquet storage |
| [Incident Response](docs/runbooks/incident-response.md) | Incident handling procedures |
| [Scaling Operations](docs/runbooks/scaling.md) | Horizontal/vertical scaling |
| [Maintenance](docs/runbooks/maintenance.md) | Upgrades and routine operations |

## Requirements Summary

| Dimension | Requirement |
|-----------|-------------|
| **Scale** | 10 PB/day ingestion, 2-3x peak ratio |
| **Use Cases** | Debugging, compliance/audit |
| **Sources** | Application logs (microservices), infrastructure logs |
| **Formats** | JSON (structured), plain text (unstructured) |
| **Latency** | 1-5 minutes end-to-end |
| **Retention** | Hot: 7 days, Warm: 30 days, Cold: 1 year |
| **Query Patterns** | Needle-in-haystack, aggregations, full-text search |

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Collection | Fluent Bit | Low resource footprint, K8s native |
| Streaming | Apache Kafka | Battle-tested at scale, tiered storage |
| Processing | Apache Flink | True streaming, exactly-once semantics |
| Hot Storage | ClickHouse | Column-oriented, excellent compression |
| Cold Storage | S3 + Parquet | Cost-effective, WORM compliance |
| Query Layer | Trino | Federated queries across all tiers |

## Capacity Estimates

### Storage (with ~10x compression)

| Tier | Raw Data | Compressed | Duration |
|------|----------|------------|----------|
| Hot | 70 PB | ~7 PB | 7 days |
| Warm | 300 PB | ~30 PB | 30 days |
| Cold | 3.65 EB | ~365 PB | 1 year |

### Compute

| Component | Quantity | Specification |
|-----------|----------|---------------|
| Kafka Brokers | ~275 | 32 cores, 128 GB RAM, 24 TB NVMe |
| ClickHouse Nodes | ~250 | 64 cores, 512 GB RAM, 48 TB NVMe |
| Flink TaskManagers | ~500 | 8 cores, 32 GB RAM |
| Trino Workers | ~50 | 16 cores, 128 GB RAM |

### Cost Estimate

| Component | Monthly Cost |
|-----------|-------------|
| Compute (Kafka, ClickHouse, Flink, Trino) | ~$1.2M |
| Cold Storage (S3) | ~$7.7M |
| Network & Operations | ~$0.2M |
| **Total** | **~$9.1M/month** |

*With optimization (Reserved Instances, Savings Plans): ~$5.5M/month*

## SLOs

| Metric | Target |
|--------|--------|
| Ingestion Latency | < 5 minutes end-to-end |
| Query Latency (Hot) | < 10 seconds for p95 |
| Query Latency (Cold) | < 5 minutes for p95 |
| Data Durability | 99.999999% |
| Availability | 99.9% |

## Key Trade-offs

| Trade-off | Decision | Rationale |
|-----------|----------|-----------|
| Local buffer sizing | Minutes only | Data loss on extended outages accepted |
| PII redaction accuracy | Accept false negatives | Not fully GDPR-compliant for right-to-erasure |
| Ordering guarantees | Best-effort by timestamp | Occasional out-of-order accepted |
| Disaster recovery | Secondary to availability | Focus on prevention |
| Query latency | 1-5 min acceptable | Not real-time |

## Implementation Risks

| Risk | Mitigation |
|------|------------|
| ClickHouse scaling at 70 PB | Federation design, extensive benchmarking, fallback to Elasticsearch |
| Kafka cross-region lag | Multi-region clusters, tiered storage overflow |
| Flink exactly-once at scale | Checkpointing tuning, idempotent sinks |
| Cold tier query performance | Partition pruning, Trino query optimization |

## Viewing Mermaid Diagrams

All documentation uses Mermaid diagrams. To view them:

1. **GitHub**: Renders automatically in markdown preview
2. **VS Code**: Install "Markdown Preview Mermaid Support" extension
3. **Online**: Use [Mermaid Live Editor](https://mermaid.live/)
4. **CLI**: Use `mmdc` (Mermaid CLI) to generate images
