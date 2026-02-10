# Log Ingestion System — System Design

## Problem Statement

Design a log ingestion system that handles **250,000 log entries per second** from multiple microservices, with each log entry approximately **1 KB** in size. The system must persist all data to **MySQL** and support time-range queries.

## API Contract

### POST `/logs` — Ingest Log Entry

```json
// Request
{
  "service": "payment-service",
  "level": "ERROR",
  "timestamp": "2024-06-15T10:30:00.123Z",
  "message": "Connection timeout to downstream service..."
}

// Response: 202 Accepted
{
  "status": "accepted",
  "id": "uuid-v7"
}
```

### GET `/logs?from={unix_ts}&to={unix_ts}` — Query Logs

```
Constraint: (to - from) <= 3600 seconds
```

```json
// Response: 200 OK
{
  "logs": [
    {
      "id": "...",
      "service": "payment-service",
      "level": "ERROR",
      "timestamp": "2024-06-15T10:30:00.123Z",
      "message": "..."
    }
  ],
  "count": 12345
}
```

## Design Constraints

| Constraint | Detail |
|---|---|
| Persistent store | MySQL only |
| Write rate | 250k RPS baseline (can burst higher) |
| Entry size | ~1 KB per log |
| Retention | 6 months |
| Write acknowledgment | 202 Accepted (async persistence) |
| Query window | Max 3600 seconds (1 hour) |
| Query latency | Multi-second P99 acceptable |
| Data loss tolerance | Small window acceptable (2-3s on crash) |
| Query filters | Timestamp range only (no service/level filters) |

## High-Level Architecture

```mermaid
graph TB
    subgraph Microservices
        MS1[Service A]
        MS2[Service B]
        MS3[Service C]
        MSN[Service N...]
    end

    subgraph Ingestion Layer
        LB[Load Balancer<br/>L7 / Round Robin]
        API1[API Server 1]
        API2[API Server 2]
        APIN[API Server N]
    end

    subgraph Buffer Layer
        K1[Kafka Broker 1]
        K2[Kafka Broker 2]
        K3[Kafka Broker 3]
    end

    subgraph Writer Layer
        W1[Writer Worker 1]
        W2[Writer Worker 2]
        WN[Writer Worker N]
    end

    subgraph MySQL Cluster
        subgraph Shard 1
            P1[(Primary)]
            R1[(Replica)]
        end
        subgraph Shard 2
            P2[(Primary)]
            R2[(Replica)]
        end
        subgraph Shard N
            PN[(Primary)]
            RN[(Replica)]
        end
    end

    subgraph Query Layer
        QR[Query Router]
    end

    MS1 & MS2 & MS3 & MSN -->|POST /logs| LB
    LB --> API1 & API2 & APIN
    API1 & API2 & APIN -->|Produce| K1 & K2 & K3
    K1 & K2 & K3 -->|Consume| W1 & W2 & WN
    W1 -->|Bulk INSERT| P1
    W2 -->|Bulk INSERT| P2
    WN -->|Bulk INSERT| PN
    P1 -->|Async Replication| R1
    P2 -->|Async Replication| R2
    PN -->|Async Replication| RN
    QR -->|Scatter-Gather| R1 & R2 & RN

    style LB fill:#f5a623,color:#000
    style K1 fill:#4a90d9,color:#fff
    style K2 fill:#4a90d9,color:#fff
    style K3 fill:#4a90d9,color:#fff
    style P1 fill:#7b68ee,color:#fff
    style P2 fill:#7b68ee,color:#fff
    style PN fill:#7b68ee,color:#fff
    style QR fill:#50c878,color:#000
```

## Data Flow Summary

```mermaid
sequenceDiagram
    participant MS as Microservice
    participant API as API Server
    participant KF as Kafka
    participant WW as Writer Worker
    participant MY as MySQL Shard

    MS->>API: POST /logs (log entry)
    API->>API: Validate payload
    API->>KF: Produce message
    API-->>MS: 202 Accepted

    Note over KF,WW: Async - decoupled from request

    KF->>WW: Consume batch
    WW->>WW: Accumulate 5000 rows<br/>or 2-second window
    WW->>MY: Bulk INSERT (5000 rows)
    MY-->>WW: ACK
```

## Document Index

| Document | Description |
|---|---|
| [01 — Requirements & Capacity Estimates](./01-requirements-and-estimates.md) | Functional/non-functional requirements, back-of-envelope math |
| [02 — Write Path Deep Dive](./02-write-path.md) | API layer, Kafka design, writer workers, batching strategy |
| [03 — MySQL Storage Design](./03-mysql-storage-design.md) | Sharding, partitioning, schema, indexing, retention |
| [04 — Read Path & Query Routing](./04-read-path.md) | Scatter-gather, partition pruning, response assembly |
| [05 — Resource Estimation (6 Months)](./05-resource-estimation.md) | Hardware sizing, instance counts, cost analysis |
| [06 — Failure Modes & Trade-offs](./06-failure-modes.md) | Failure scenarios, data loss analysis, trade-off summary |
