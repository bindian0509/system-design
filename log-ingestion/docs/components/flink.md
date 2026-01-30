# Flink Processing Component Design

## Overview

Apache Flink serves as the stream processing engine, responsible for consuming logs from Kafka, applying transformations (PII redaction, schema validation, enrichment), and writing to ClickHouse.

---

## Architecture

### Cluster Topology

```mermaid
flowchart TB
    subgraph HA["High Availability"]
        JM1[JobManager 1<br/>Active]
        JM2[JobManager 2<br/>Standby]
        ZK[(ZooKeeper<br/>Leader Election)]
    end

    subgraph Workers["Task Managers"]
        TM1[Task Manager 1<br/>4 slots]
        TM2[Task Manager 2<br/>4 slots]
        TM3[Task Manager 3<br/>4 slots]
        TMN[Task Manager N<br/>4 slots]
    end

    subgraph Storage["State Backend"]
        S3[(S3<br/>Checkpoints)]
        ROCKS[(RocksDB<br/>Local State)]
    end

    JM1 <--> ZK
    JM2 <--> ZK

    JM1 --> TM1
    JM1 --> TM2
    JM1 --> TM3
    JM1 --> TMN

    TM1 & TM2 & TM3 & TMN --> ROCKS
    ROCKS --> S3
```

### Processing Pipeline

```mermaid
flowchart LR
    subgraph Source["Kafka Source"]
        K1[logs.tenant-a.*]
        K2[logs.tenant-b.*]
        K3[logs.tenant-c.*]
    end

    subgraph Parse["Parsing"]
        JSON[JSON Parser]
        TEXT[Text Parser]
        ROUTER[Format Router]
    end

    subgraph Transform["Transformations"]
        PII[PII Redactor]
        SCHEMA[Schema Validator]
        ENRICH[Enricher]
        DEDUP[Deduplicator]
    end

    subgraph Sink["Sinks"]
        CH[(ClickHouse)]
        DLQ[(Dead Letter Queue)]
        METRICS[Metrics Exporter]
    end

    K1 & K2 & K3 --> ROUTER
    ROUTER --> JSON
    ROUTER --> TEXT
    JSON & TEXT --> PII
    PII --> SCHEMA
    SCHEMA -->|valid| ENRICH
    SCHEMA -->|invalid| DLQ
    ENRICH --> DEDUP
    DEDUP --> CH
    DEDUP --> METRICS
```

---

## Job Design

### Main Processing Job

```mermaid
flowchart TB
    subgraph Sources["Sources (parallelism=1000)"]
        KS1[KafkaSource<br/>Partition 0-99]
        KS2[KafkaSource<br/>Partition 100-199]
        KSN[KafkaSource<br/>Partition 900-999]
    end

    subgraph Operators["Operators"]
        MAP1[FlatMap: Parse & Route<br/>parallelism=1000]
        MAP2[Map: PII Redaction<br/>parallelism=500]
        FILTER[Filter: Schema Validate<br/>parallelism=500]
        KEY[KeyBy: tenant + service]
        WINDOW[Window: 1 min tumbling]
        REDUCE[Reduce: Dedup + Batch]
    end

    subgraph Sinks["Sinks (parallelism=200)"]
        CH_SINK[ClickHouseSink<br/>Async batched]
        DLQ_SINK[KafkaSink<br/>DLQ topic]
    end

    KS1 & KS2 & KSN --> MAP1
    MAP1 --> MAP2
    MAP2 --> FILTER
    FILTER -->|valid| KEY
    FILTER -->|invalid| DLQ_SINK
    KEY --> WINDOW
    WINDOW --> REDUCE
    REDUCE --> CH_SINK
```

### Operator Chaining

```mermaid
flowchart LR
    subgraph Chain1["Operator Chain 1"]
        SOURCE[Kafka Source]
        PARSE[JSON Parser]
        PII[PII Redactor]
    end

    subgraph Shuffle["Network Shuffle"]
        KEYBY[KeyBy tenant_id]
    end

    subgraph Chain2["Operator Chain 2"]
        WINDOW[Window]
        REDUCE[Reduce]
        SINK[ClickHouse Sink]
    end

    Chain1 -->|shuffle| Shuffle --> Chain2

    style Chain1 fill:#6bcb77
    style Chain2 fill:#6bcb77
    style Shuffle fill:#ff6b6b
```

---

## PII Redaction

### Redaction Pipeline

```mermaid
flowchart TB
    subgraph Input["Input Log"]
        LOG["{ 'message': 'User john@example.com paid $500',<br/> 'user_id': '123-45-6789' }"]
    end

    subgraph Detection["PII Detection"]
        EMAIL[Email Regex<br/>john@example.com]
        SSN[SSN Regex<br/>123-45-6789]
        CREDIT[Credit Card Regex]
        PHONE[Phone Regex]
        IP[IP Address Regex]
    end

    subgraph Redaction["Redaction"]
        MASK[Mask: ***]
        HASH[Hash: sha256]
        TOKENIZE[Tokenize: lookup]
    end

    subgraph Output["Output Log"]
        RESULT["{ 'message': 'User [EMAIL_REDACTED] paid $500',<br/> 'user_id': '[SSN_REDACTED]' }"]
    end

    Input --> Detection
    EMAIL & SSN & CREDIT & PHONE & IP --> Redaction
    Redaction --> Output
```

### PII Patterns

| PII Type | Regex Pattern | Redaction Strategy |
|----------|--------------|-------------------|
| **Email** | `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` | `[EMAIL_REDACTED]` |
| **SSN** | `\d{3}-\d{2}-\d{4}` | `[SSN_REDACTED]` |
| **Credit Card** | `\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}` | `****-****-****-XXXX` |
| **Phone** | `(\+\d{1,3})?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}` | `[PHONE_REDACTED]` |
| **IPv4** | `\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}` | `X.X.X.X` |
| **JWT** | `eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+` | `[JWT_REDACTED]` |

### Redaction Metrics

```mermaid
flowchart LR
    subgraph Metrics["PII Metrics"]
        TOTAL[Total logs processed]
        DETECTED[Logs with PII detected]
        BY_TYPE[Detections by type]
        FALSE_POS[False positive rate<br/>sampled]
    end

    subgraph Export["Prometheus Export"]
        pii_total[pii_logs_processed_total]
        pii_detected[pii_detected_total{type}]
        pii_rate[pii_detection_rate]
    end

    Metrics --> Export
```

---

## Schema Validation

### Validation Flow

```mermaid
flowchart TB
    subgraph Input["Incoming Log"]
        RAW[Raw log record]
    end

    subgraph Registry["Schema Registry"]
        SR[(Confluent Schema Registry)]
        SCHEMA[Log Schema v3]
    end

    subgraph Validation["Validation Steps"]
        V1[Check required fields]
        V2[Validate field types]
        V3[Validate enum values]
        V4[Check field constraints]
    end

    subgraph Output["Routing"]
        VALID[To ClickHouse]
        INVALID[To DLQ]
    end

    RAW --> Registry
    Registry --> Validation
    V1 --> V2 --> V3 --> V4
    V4 -->|pass| VALID
    V4 -->|fail| INVALID
```

### Schema Definition

```json
{
  "type": "record",
  "name": "LogRecord",
  "namespace": "com.company.logs",
  "fields": [
    {"name": "timestamp", "type": "long", "logicalType": "timestamp-millis"},
    {"name": "tenant_id", "type": "string"},
    {"name": "service", "type": "string"},
    {"name": "host", "type": "string"},
    {"name": "trace_id", "type": ["null", "string"], "default": null},
    {"name": "level", "type": {"type": "enum", "name": "Level",
      "symbols": ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]}},
    {"name": "message", "type": "string"},
    {"name": "labels", "type": {"type": "map", "values": "string"}, "default": {}}
  ]
}
```

---

## Checkpointing

### Checkpoint Flow

```mermaid
sequenceDiagram
    participant JM as JobManager
    participant TM1 as TaskManager 1
    participant TM2 as TaskManager 2
    participant S3 as S3 Storage

    Note over JM: Checkpoint barrier triggered

    JM->>TM1: Inject barrier (CP-n)
    JM->>TM2: Inject barrier (CP-n)

    TM1->>TM1: Snapshot state
    TM2->>TM2: Snapshot state

    TM1->>S3: Upload state
    TM2->>S3: Upload state

    TM1->>JM: Acknowledge CP-n
    TM2->>JM: Acknowledge CP-n

    JM->>JM: Mark CP-n complete

    Note over JM: Checkpoint successful
```

### Checkpoint Configuration

```mermaid
flowchart TB
    subgraph Config["Checkpoint Configuration"]
        INT[Interval: 60 seconds]
        TIMEOUT[Timeout: 10 minutes]
        MIN[Min pause: 30 seconds]
        MAX[Max concurrent: 1]
        MODE[Mode: EXACTLY_ONCE]
    end

    subgraph Backend["State Backend"]
        ROCKS[RocksDB<br/>Incremental checkpoints]
        S3[S3<br/>Checkpoint storage]
    end

    subgraph Recovery["Recovery"]
        RESTART[Restart strategy:<br/>Fixed delay (10s, 3 attempts)]
        SAVEPOINT[Savepoint restore<br/>for upgrades]
    end

    Config --> Backend --> Recovery
```

---

## Dead Letter Queue

### DLQ Flow

```mermaid
flowchart TB
    subgraph Processing["Processing Pipeline"]
        LOG[Incoming Log]
        PII[PII Redaction]
        SCHEMA[Schema Validation]
        ENRICH[Enrichment]
    end

    subgraph Errors["Error Scenarios"]
        E1[Parse error]
        E2[Schema violation]
        E3[Enrichment failure]
        E4[Sink failure<br/>after retries]
    end

    subgraph DLQ["Dead Letter Queue"]
        TOPIC[Kafka: logs.dlq]
        DLQ_SCHEMA[DLQ Record Schema]
    end

    subgraph Recovery["Recovery"]
        RETRY[Manual retry job]
        ANALYZE[Error analysis]
        FIX[Fix & reprocess]
    end

    LOG --> PII
    PII -->|error| E1 --> DLQ
    PII --> SCHEMA
    SCHEMA -->|error| E2 --> DLQ
    SCHEMA --> ENRICH
    ENRICH -->|error| E3 --> DLQ
    ENRICH -->|sink fail| E4 --> DLQ

    DLQ --> Recovery
```

### DLQ Record Schema

```json
{
  "original_record": "base64-encoded original",
  "error_type": "SCHEMA_VALIDATION",
  "error_message": "Field 'timestamp' is required",
  "error_timestamp": 1704067200000,
  "source_topic": "logs.acme.payments",
  "source_partition": 42,
  "source_offset": 123456,
  "processing_stage": "schema_validation",
  "retry_count": 0,
  "stack_trace": "..."
}
```

---

## Backpressure Handling

### Backpressure Detection

```mermaid
flowchart TB
    subgraph Detection["Backpressure Indicators"]
        QUEUE[Input queue full<br/>isBackpressured=true]
        LAG[Kafka consumer lag<br/>increasing]
        BUFFER[Output buffer full]
    end

    subgraph Response["Response Actions"]
        SCALE[Scale up TaskManagers]
        THROTTLE[Throttle source rate]
        BUFFER_INC[Increase buffer size]
    end

    subgraph Root["Root Cause Analysis"]
        SLOW_SINK[Slow sink<br/>ClickHouse backpressure]
        SLOW_OP[Slow operator<br/>CPU-bound]
        NETWORK[Network congestion]
    end

    Detection --> Root --> Response
```

### Backpressure Metrics

```mermaid
xychart-beta
    title "Backpressure Timeline"
    x-axis ["T0", "T1", "T2", "T3", "T4", "T5"]
    y-axis "Backpressure %" 0 --> 100
    line [0, 20, 60, 80, 95, 50]
    line [0, 0, 10, 30, 60, 20]
```

---

## Scaling

### Auto-Scaling Strategy

```mermaid
flowchart TB
    subgraph Metrics["Scaling Metrics"]
        LAG[Kafka consumer lag]
        CPU[CPU utilization]
        MEMORY[Memory usage]
        BACKPRESSURE[Backpressure ratio]
    end

    subgraph Rules["Scaling Rules"]
        RULE1[Lag > 5 min → Scale up]
        RULE2[Lag < 1 min & CPU < 30% → Scale down]
        RULE3[Backpressure > 50% → Scale up]
    end

    subgraph Actions["Scaling Actions"]
        ADD[Add TaskManagers]
        REMOVE[Remove TaskManagers]
        REBALANCE[Rebalance partitions]
    end

    Metrics --> Rules --> Actions
```

### Reactive Scaling

```mermaid
sequenceDiagram
    participant K8S as Kubernetes HPA
    participant FLINK as Flink Cluster
    participant KAFKA as Kafka

    loop Every 30s
        K8S->>FLINK: Query metrics endpoint
        FLINK->>K8S: Return lag, CPU, memory

        alt Lag > threshold
            K8S->>FLINK: Scale up replicas
            FLINK->>FLINK: Add TaskManagers
            FLINK->>KAFKA: Rebalance consumer group
        else Lag < threshold & underutilized
            K8S->>FLINK: Scale down replicas
            FLINK->>FLINK: Remove TaskManagers
            FLINK->>KAFKA: Rebalance consumer group
        end
    end
```

---

## Monitoring

### Key Metrics

```mermaid
flowchart TB
    subgraph Job["Job Metrics"]
        JM1[numRecordsInPerSecond]
        JM2[numRecordsOutPerSecond]
        JM3[numLateRecordsDropped]
        JM4[currentOutputWatermark]
    end

    subgraph Task["Task Metrics"]
        TM1[busyTimeMsPerSecond]
        TM2[backPressuredTimeMsPerSecond]
        TM3[idleTimeMsPerSecond]
        TM4[numBuffersInLocalPerSecond]
    end

    subgraph Kafka["Kafka Metrics"]
        KM1[records-lag-max]
        KM2[records-consumed-rate]
        KM3[commit-latency-avg]
    end

    subgraph Custom["Custom Metrics"]
        CM1[pii_redactions_total]
        CM2[schema_validation_errors]
        CM3[dlq_records_total]
    end
```

### Dashboard Layout

```mermaid
block-beta
    columns 3

    block:row1
        columns 3
        a["Throughput<br/>(records/s)"]
        b["Consumer Lag<br/>(minutes)"]
        c["Error Rate<br/>(%)"]
    end

    block:row2
        columns 3
        d["Checkpoint<br/>Duration"]
        e["Backpressure<br/>%"]
        f["Task Managers<br/>Active"]
    end

    block:row3
        columns 3
        g["PII Detections<br/>by Type"]
        h["DLQ Records<br/>Trend"]
        i["Latency<br/>p50/p95/p99"]
    end
```

---

## Failure Recovery

### Recovery Scenarios

```mermaid
stateDiagram-v2
    [*] --> Running: Job started

    Running --> TaskFailure: Task fails
    TaskFailure --> Restarting: Restart from checkpoint
    Restarting --> Running: Recovery successful

    TaskFailure --> JobFailure: Max restarts exceeded
    JobFailure --> Stopped: Alert operator

    Running --> JMFailure: JobManager fails
    JMFailure --> JMElection: ZooKeeper election
    JMElection --> JMRecovery: New JM takes over
    JMRecovery --> Running: Resume from checkpoint

    Running --> Savepoint: Planned upgrade
    Savepoint --> Stopped: Stop with savepoint
    Stopped --> Running: Start from savepoint
```

### Exactly-Once Guarantee

```mermaid
flowchart TB
    subgraph Guarantee["Exactly-Once Components"]
        CK[Checkpointing]
        TX[Two-phase commit sinks]
        IDEM[Idempotent writes]
    end

    subgraph Kafka["Kafka Source"]
        OFFSET[Offset committed<br/>with checkpoint]
    end

    subgraph CH["ClickHouse Sink"]
        DEDUP[ReplacingMergeTree<br/>deduplication key]
    end

    Guarantee --> Kafka
    Guarantee --> CH
```

---

## Configuration Reference

### Job Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `parallelism.default` | 1000 | Default operator parallelism |
| `taskmanager.numberOfTaskSlots` | 4 | Slots per TaskManager |
| `taskmanager.memory.process.size` | 8 GB | Total TM memory |
| `state.backend` | rocksdb | State backend type |
| `state.checkpoints.dir` | s3://bucket/checkpoints | Checkpoint location |
| `execution.checkpointing.interval` | 60 s | Checkpoint frequency |
| `execution.checkpointing.timeout` | 10 min | Checkpoint timeout |

### Kafka Consumer Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `group.id` | flink-log-processor | Consumer group |
| `auto.offset.reset` | earliest | Start from beginning |
| `enable.auto.commit` | false | Managed by Flink |
| `max.poll.records` | 500 | Records per poll |
| `fetch.max.bytes` | 52428800 | 50 MB max fetch |

### ClickHouse Sink Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `batch.size` | 100000 | Rows per batch |
| `flush.interval.ms` | 1000 | Max time before flush |
| `max.retries` | 5 | Retry attempts |
| `retry.backoff.ms` | 1000 | Initial retry delay |
