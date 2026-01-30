# Log Ingestion System

A system design for a petabyte-scale distributed log ingestion platform capable of handling FAANG-level workloads.

## Overview

This repository contains the system design documentation for a log ingestion system with the following capabilities:

- **Scale**: 10 petabytes per day (~116 GB/s, ~230 million events/second)
- **Latency**: Near real-time queryability (< 5 minutes)
- **Search**: Full-text search + structured queries + distributed tracing
- **Geography**: Multi-region with federated search
- **Retention**: 7-30 days with tiered storage

## Documentation

- [System Design Document](docs/system-design.md) - Complete architecture specification

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Log Sources │────>│  Ingestion  │────>│   Buffer    │
│             │     │   Layer     │     │   Layer     │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                                              ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Query    │<────│   Storage   │<────│ Processing  │
│    Layer    │     │    Layer    │     │   Layer     │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Key Components

| Layer | Purpose | Key Characteristics |
|-------|---------|-------------------|
| Ingestion | Collect logs from all sources | Lightweight agents, edge collectors, backpressure handling |
| Buffer | Decouple ingestion from processing | Distributed commit log, 24-72h retention, replay capability |
| Processing | Parse, enrich, transform logs | Stream processing, schema enforcement, trace linking |
| Storage | Store logs for querying | Hot tier (search-optimized), Warm tier (analytics-optimized) |
| Query | Unified search interface | Federated search, distributed tracing, full-text + structured |

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Push-based ingestion | Lower latency, guaranteed delivery |
| At-least-once delivery | Simpler than exactly-once, acceptable for logs |
| Tiered storage | 10x cost savings on warm tier |
| Regional isolation | Data sovereignty, reduced blast radius |
| Time-based sharding | Natural query patterns, easy retention management |

## Technology Options

The design is technology-agnostic. Recommended implementations:

### Open Source Stack
- **Agent**: Vector, Fluent Bit
- **Queue**: Apache Kafka, Redpanda
- **Processing**: Apache Flink
- **Hot Storage**: Elasticsearch, Grafana Loki
- **Warm Storage**: ClickHouse, Apache Druid

### Cloud-Native (AWS)
- **Agent**: CloudWatch Agent, Fluent Bit
- **Queue**: Amazon MSK
- **Processing**: Kinesis Data Analytics
- **Hot Storage**: Amazon OpenSearch
- **Warm Storage**: Athena + S3

## Success Metrics

| Metric | Target |
|--------|--------|
| Ingestion Latency | P99 < 1s |
| Query Latency (Simple) | P50 < 500ms |
| Ingestion Availability | 99.9% |
| Data Loss | < 0.001% |
| Cost per TB | < $0.10 |

## License

This is a system design document for educational and planning purposes.
