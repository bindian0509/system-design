# Cold Storage Component Design

## Overview

The cold storage tier provides long-term (1 year) retention of log data using S3/GCS with Parquet format. This tier is optimized for cost efficiency and compliance requirements while maintaining query capability through Trino/Athena.

---

## Architecture

### Storage Hierarchy

```mermaid
flowchart TB
    subgraph Hot["Hot Tier (ClickHouse)"]
        CH[(ClickHouse<br/>7 days)]
    end

    subgraph Compaction["Compaction Process"]
        EXPORT[Export Job<br/>Daily]
        TRANSFORM[Transform to Parquet]
        COMPRESS[Compress & Partition]
    end

    subgraph Cold["Cold Tier (S3)"]
        subgraph Buckets["S3 Buckets"]
            B1[(logs-cold-useast)]
            B2[(logs-cold-uswest)]
            B3[(logs-cold-eu)]
        end
        HIVE[(Hive Metastore)]
    end

    CH -->|TTL trigger| EXPORT
    EXPORT --> TRANSFORM
    TRANSFORM --> COMPRESS
    COMPRESS --> Buckets
    Buckets --> HIVE
```

### Multi-Region Layout

```mermaid
flowchart TB
    subgraph USEast["US-East Region"]
        S3_E[(S3 Bucket<br/>logs-cold-useast)]
        GLACIER_E[(Glacier<br/>Archive)]
    end

    subgraph USWest["US-West Region"]
        S3_W[(S3 Bucket<br/>logs-cold-uswest)]
        GLACIER_W[(Glacier<br/>Archive)]
    end

    subgraph EU["EU Region"]
        S3_EU[(S3 Bucket<br/>logs-cold-eu)]
        GLACIER_EU[(Glacier<br/>Archive)]
    end

    subgraph Replication["Cross-Region Replication"]
        REP[S3 Replication Rules]
    end

    S3_E <-->|replicate| REP
    S3_W <-->|replicate| REP
    S3_EU <-->|replicate| REP

    S3_E -->|lifecycle| GLACIER_E
    S3_W -->|lifecycle| GLACIER_W
    S3_EU -->|lifecycle| GLACIER_EU
```

---

## Data Format

### Parquet Schema

```mermaid
erDiagram
    PARQUET_FILE {
        DateTime64 timestamp
        String tenant_id
        String service
        String host
        String trace_id
        String span_id
        Int8 level
        String message
        String request_id
        String user_id
        Float64 duration_ms
        Int16 status_code
        String method
        String path
        Map_String_String labels
    }
```

### Partition Strategy

```mermaid
flowchart TB
    subgraph S3Path["S3 Path Structure"]
        ROOT[s3://logs-cold/]
        YEAR[year=2024/]
        MONTH[month=01/]
        DAY[day=15/]
        TENANT[tenant_id=acme/]
        SERVICE[service=payments/]
        FILE[data_000001.parquet]
    end

    ROOT --> YEAR --> MONTH --> DAY --> TENANT --> SERVICE --> FILE
```

### Partition Example

```
s3://logs-cold-useast/
└── logs/
    └── year=2024/
        └── month=01/
            └── day=15/
                ├── tenant_id=acme-corp/
                │   ├── service=payment-service/
                │   │   ├── part-00000.parquet
                │   │   ├── part-00001.parquet
                │   │   └── _SUCCESS
                │   └── service=user-service/
                │       └── part-00000.parquet
                └── tenant_id=globex/
                    └── service=inventory/
                        └── part-00000.parquet
```

---

## Compaction Process

### Compaction Pipeline

```mermaid
flowchart TB
    subgraph Source["Source: ClickHouse"]
        CH[(logs_local<br/>Day N-7 partition)]
    end

    subgraph Export["Export Job"]
        QUERY[Query partition]
        BUFFER[Buffer in memory]
        BATCH[Batch by tenant/service]
    end

    subgraph Transform["Transform"]
        CONVERT[Convert to Parquet]
        COMPRESS[Compress (ZSTD)]
        PARTITION[Write partitioned]
    end

    subgraph Target["Target: S3"]
        S3[(S3 Bucket)]
        META[Update Hive Metastore]
    end

    Source --> Export --> Transform --> Target

    META --> S3
```

### Compaction Schedule

```mermaid
gantt
    title Daily Compaction Schedule
    dateFormat  HH:mm
    axisFormat %H:%M

    section Export
    Query ClickHouse     :a1, 02:00, 30m
    Buffer & Batch       :a2, after a1, 30m

    section Transform
    Convert to Parquet   :b1, after a2, 1h
    Compress ZSTD        :b2, after b1, 30m

    section Load
    Upload to S3         :c1, after b2, 30m
    Update Metastore     :c2, after c1, 15m
    Verify               :c3, after c2, 15m
```

### Compaction Job Configuration

```yaml
# compaction-job.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: log-compaction
  namespace: data-pipeline
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: compaction
            image: log-compaction:latest
            env:
            - name: CLICKHOUSE_HOST
              value: clickhouse-hot
            - name: S3_BUCKET
              value: logs-cold-useast
            - name: PARTITION_DATE
              value: "$(date -d 'yesterday' +%Y-%m-%d)"
            resources:
              requests:
                memory: "8Gi"
                cpu: "2"
              limits:
                memory: "16Gi"
                cpu: "4"
          restartPolicy: OnFailure
```

---

## Storage Classes

### Lifecycle Management

```mermaid
flowchart LR
    subgraph Age["Data Age"]
        D0[Day 0-30<br/>Hot/Warm Tier]
        D30[Day 30-90<br/>S3 Standard]
        D90[Day 90-180<br/>S3 Standard-IA]
        D180[Day 180-365<br/>S3 Glacier IR]
        D365[Day 365+<br/>Delete]
    end

    D0 --> D30 --> D90 --> D180 --> D365
```

### S3 Lifecycle Policy

```json
{
  "Rules": [
    {
      "ID": "TransitionToIA",
      "Status": "Enabled",
      "Prefix": "logs/",
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 180,
          "StorageClass": "GLACIER_IR"
        }
      ],
      "Expiration": {
        "Days": 365
      }
    }
  ]
}
```

### Storage Class Comparison

```mermaid
xychart-beta
    title "Storage Cost by Class ($/TB/month)"
    x-axis ["S3 Standard", "S3 Standard-IA", "S3 Glacier IR", "S3 Glacier"]
    y-axis "Cost ($/TB)" 0 --> 25
    bar [23, 12.5, 10, 4]
```

| Storage Class | Cost ($/TB/month) | Retrieval Time | Use Case |
|---------------|-------------------|----------------|----------|
| **S3 Standard** | $23 | Instant | Days 30-90 |
| **S3 Standard-IA** | $12.50 | Instant | Days 90-180 |
| **S3 Glacier IR** | $10 | Minutes | Days 180-365 |
| **S3 Glacier** | $4 | Hours | Archival (if needed) |

---

## Compliance Features

### WORM (Write-Once-Read-Many)

```mermaid
flowchart TB
    subgraph Write["Write Phase"]
        UPLOAD[Upload Parquet file]
        LOCK[Apply Object Lock]
        VERIFY[Verify lock applied]
    end

    subgraph Protected["Protection Period"]
        RETAIN[Retention: 1 year]
        LEGAL[Legal hold: optional]
    end

    subgraph Access["Access Control"]
        READ[Read: Allowed]
        DELETE[Delete: Blocked]
        MODIFY[Modify: Blocked]
    end

    Write --> Protected
    Protected --> Access
```

### S3 Object Lock Configuration

```bash
# Enable Object Lock on bucket (at creation time)
aws s3api create-bucket \
  --bucket logs-cold-compliance \
  --object-lock-enabled-for-bucket

# Set default retention
aws s3api put-object-lock-configuration \
  --bucket logs-cold-compliance \
  --object-lock-configuration '{
    "ObjectLockEnabled": "Enabled",
    "Rule": {
      "DefaultRetention": {
        "Mode": "COMPLIANCE",
        "Years": 1
      }
    }
  }'
```

### Audit Trail

```mermaid
flowchart LR
    subgraph Actions["S3 Actions"]
        PUT[PutObject]
        GET[GetObject]
        DELETE[DeleteObject]
        LIST[ListObjects]
    end

    subgraph Logging["CloudTrail Logging"]
        LOG[(CloudTrail)]
        S3_LOG[(S3 Access Logs)]
    end

    subgraph Analysis["Audit Analysis"]
        ATHENA[Athena Queries]
        ALERT[Compliance Alerts]
    end

    Actions --> LOG
    Actions --> S3_LOG
    LOG --> Analysis
    S3_LOG --> Analysis
```

---

## Query Access

### Hive Metastore

```mermaid
flowchart TB
    subgraph Metastore["Hive Metastore"]
        DB[Database: logs_cold]
        TABLE[Table: logs_parquet]
        PARTITIONS[Partition metadata]
    end

    subgraph Storage["S3 Storage"]
        S3[(S3 Parquet files)]
    end

    subgraph Query["Query Engines"]
        TRINO[Trino]
        ATHENA[AWS Athena]
        SPARK[Spark SQL]
    end

    Metastore --> Query
    Query --> Storage
```

### Table Definition

```sql
-- Hive DDL for cold storage table
CREATE EXTERNAL TABLE logs_cold.logs_parquet (
    timestamp TIMESTAMP,
    tenant_id STRING,
    service STRING,
    host STRING,
    trace_id STRING,
    span_id STRING,
    level TINYINT,
    message STRING,
    request_id STRING,
    user_id STRING,
    duration_ms DOUBLE,
    status_code SMALLINT,
    method STRING,
    path STRING,
    labels MAP<STRING, STRING>
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT,
    tenant_partition STRING,
    service_partition STRING
)
STORED AS PARQUET
LOCATION 's3://logs-cold-useast/logs/'
TBLPROPERTIES (
    'parquet.compression' = 'ZSTD',
    'projection.enabled' = 'true',
    'projection.year.type' = 'integer',
    'projection.year.range' = '2024,2030',
    'projection.month.type' = 'integer',
    'projection.month.range' = '1,12',
    'projection.day.type' = 'integer',
    'projection.day.range' = '1,31'
);
```

### Query Examples

```sql
-- Query cold data via Trino
SELECT
    date_trunc('hour', timestamp) as hour,
    service,
    count(*) as count,
    approx_percentile(duration_ms, 0.95) as p95_latency
FROM hive_cold.logs_cold.logs_parquet
WHERE year = 2024
  AND month = 1
  AND day BETWEEN 1 AND 15
  AND tenant_partition = 'acme-corp'
  AND level >= 2  -- WARN and above
GROUP BY 1, 2
ORDER BY 1, 2;

-- Full-text search in cold data
SELECT timestamp, service, message
FROM hive_cold.logs_cold.logs_parquet
WHERE year = 2024
  AND month = 1
  AND regexp_like(message, '(?i)error|exception|failed')
LIMIT 100;
```

---

## Data Recovery

### Recovery Scenarios

```mermaid
flowchart TB
    subgraph Scenarios["Recovery Scenarios"]
        S1[Accidental deletion<br/>Object Lock prevents]
        S2[Corruption detected<br/>Restore from replica]
        S3[Restore to hot tier<br/>Re-import to ClickHouse]
    end

    subgraph Recovery["Recovery Options"]
        R1[Object versioning]
        R2[Cross-region replica]
        R3[Import job]
    end

    S1 --> R1
    S2 --> R2
    S3 --> R3
```

### Re-Import to ClickHouse

```sql
-- Re-import specific data from cold storage
INSERT INTO logs_local
SELECT *
FROM s3(
    'https://logs-cold-useast.s3.amazonaws.com/logs/year=2024/month=01/day=15/*.parquet',
    'PARQUET'
)
WHERE tenant_id = 'acme-corp';
```

---

## Monitoring

### Key Metrics

```mermaid
flowchart TB
    subgraph Storage["Storage Metrics"]
        SM1[Total size by bucket]
        SM2[Object count]
        SM3[Storage class distribution]
    end

    subgraph Operations["Operation Metrics"]
        OM1[Compaction job success rate]
        OM2[Export duration]
        OM3[Files written per day]
    end

    subgraph Cost["Cost Metrics"]
        CM1[Storage cost by tier]
        CM2[Request costs]
        CM3[Data transfer costs]
    end
```

### CloudWatch Alarms

```yaml
# S3 monitoring alarms
Alarms:
  - Name: ColdStorageObjectCount
    Metric: NumberOfObjects
    Threshold: 10000000  # Alert if > 10M objects
    Action: SNS notification

  - Name: CompactionJobFailed
    Metric: kubernetes.job.failed
    Namespace: data-pipeline
    Threshold: 1
    Action: PagerDuty

  - Name: StorageGrowthAnomaly
    Metric: BucketSizeBytes
    AnomalyDetection: true
    Action: SNS notification
```

---

## Cost Optimization

### Storage Cost Breakdown

```mermaid
pie title Monthly Cold Storage Costs (365 PB)
    "S3 Standard (90 days)" : 25
    "S3 Standard-IA (90 days)" : 20
    "S3 Glacier IR (185 days)" : 45
    "Data Transfer" : 5
    "Requests" : 5
```

### Optimization Strategies

```mermaid
flowchart TB
    subgraph Strategies["Cost Reduction Strategies"]
        S1[Aggressive lifecycle<br/>-20% storage cost]
        S2[Better compression<br/>-15% storage cost]
        S3[Intelligent tiering<br/>-10% storage cost]
        S4[Reduce retention<br/>-50% if applicable]
    end

    subgraph Implementation["Implementation"]
        I1[Update lifecycle policy]
        I2[Switch to ZSTD level 3]
        I3[Enable S3 Intelligent-Tiering]
        I4[Review compliance requirements]
    end

    S1 --> I1
    S2 --> I2
    S3 --> I3
    S4 --> I4
```

### Compression Comparison

| Codec | Compression Ratio | Write Speed | Read Speed |
|-------|------------------|-------------|------------|
| **Snappy** | 3:1 | Fast | Fast |
| **GZIP** | 6:1 | Slow | Medium |
| **ZSTD** | 5:1 | Medium | Fast |
| **ZSTD (level 3)** | 6:1 | Medium | Fast |

**Recommendation**: ZSTD level 3 for best balance of compression and performance.

---

## Configuration Reference

### S3 Bucket Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| **Versioning** | Enabled | Accidental deletion protection |
| **Object Lock** | Compliance mode, 1 year | WORM compliance |
| **Encryption** | SSE-S3 | At-rest encryption |
| **Access Logging** | Enabled | Audit trail |
| **Lifecycle** | 90d → IA, 180d → Glacier IR | Cost optimization |

### Parquet Writer Settings

| Setting | Value | Rationale |
|---------|-------|-----------|
| **Row group size** | 128 MB | Balance read/write performance |
| **Page size** | 1 MB | Efficient predicate pushdown |
| **Compression** | ZSTD (level 3) | Best compression ratio |
| **Dictionary encoding** | Enabled | Low-cardinality columns |
| **Statistics** | Enabled | Query optimization |

### Hive Metastore Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| **Partition projection** | Enabled | Faster partition pruning |
| **Table format** | Parquet | Columnar efficiency |
| **Partition scheme** | year/month/day/tenant/service | Query isolation |
