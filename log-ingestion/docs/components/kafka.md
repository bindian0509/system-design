# Kafka Component Design

## Overview

Apache Kafka serves as the central nervous system for log ingestion, providing durable, scalable message transport between collection agents and processing pipelines.

---

## Architecture

### Multi-Region Topology

```mermaid
flowchart TB
    subgraph US_East["US-East (Primary)"]
        subgraph Brokers_E["Broker Pool (100 nodes)"]
            BE1[Broker 1-25<br/>Rack A]
            BE2[Broker 26-50<br/>Rack B]
            BE3[Broker 51-75<br/>Rack C]
            BE4[Broker 76-100<br/>Rack D]
        end
        ZK_E[(ZooKeeper<br/>Ensemble)]
        S3_E[(S3 Tiered<br/>Storage)]
    end

    subgraph US_West["US-West (Secondary)"]
        subgraph Brokers_W["Broker Pool (100 nodes)"]
            BW1[Broker 1-25<br/>Rack A]
            BW2[Broker 26-50<br/>Rack B]
            BW3[Broker 51-75<br/>Rack C]
            BW4[Broker 76-100<br/>Rack D]
        end
        ZK_W[(ZooKeeper<br/>Ensemble)]
        S3_W[(S3 Tiered<br/>Storage)]
    end

    subgraph EU["EU (Tertiary)"]
        subgraph Brokers_EU["Broker Pool (75 nodes)"]
            BEU1[Broker 1-25<br/>Rack A]
            BEU2[Broker 26-50<br/>Rack B]
            BEU3[Broker 51-75<br/>Rack C]
        end
        ZK_EU[(ZooKeeper<br/>Ensemble)]
        S3_EU[(S3 Tiered<br/>Storage)]
    end

    subgraph MirrorMaker["Cross-Region Replication"]
        MM1[MirrorMaker<br/>US-E → US-W]
        MM2[MirrorMaker<br/>US-W → EU]
        MM3[MirrorMaker<br/>EU → US-E]
    end

    Brokers_E <--> MM1 <--> Brokers_W
    Brokers_W <--> MM2 <--> Brokers_EU
    Brokers_EU <--> MM3 <--> Brokers_E

    Brokers_E --> S3_E
    Brokers_W --> S3_W
    Brokers_EU --> S3_EU
```

---

## Topic Design

### Topic Naming Convention

```
logs.{tenant_id}.{service_name}

Examples:
- logs.acme-corp.payment-service
- logs.globex.user-auth
- logs.initech.order-processor
```

### Partition Strategy

```mermaid
flowchart TB
    subgraph Producer["Log Producer"]
        LOG[Log Entry<br/>tenant: acme<br/>service: payments<br/>trace_id: abc123]
    end

    subgraph Partitioner["Custom Partitioner"]
        HASH[Hash Function:<br/>hash(trace_id) % partitions]
    end

    subgraph Topic["Topic: logs.acme.payments"]
        P0[Partition 0]
        P1[Partition 1]
        P2[Partition 2]
        PN[Partition N]
    end

    LOG --> Partitioner
    Partitioner -->|hash=0| P0
    Partitioner -->|hash=1| P1
    Partitioner -->|hash=2| P2
    Partitioner -->|hash=N| PN
```

### Partition Sizing

| Metric | Value | Rationale |
|--------|-------|-----------|
| **Partitions per topic** | 100-500 | Based on throughput needs |
| **Max partitions per broker** | 4,000 | Kafka recommendation |
| **Target partition throughput** | 50-100 MB/s | Optimal consumer performance |
| **Total partitions** | ~100,000 | 275 brokers × ~365 avg |

---

## Tiered Storage

### Storage Hierarchy

```mermaid
flowchart TB
    subgraph Hot["Hot Storage (Local SSD)"]
        LOCAL[Local Segments<br/>Latest 6-24 hours]
        ACTIVE[Active Segment<br/>Currently writing]
    end

    subgraph Remote["Remote Storage (S3)"]
        TIER1[Tier 1 Segments<br/>24h - 48h old]
        TIER2[Tier 2 Segments<br/>48h - 7 days old]
    end

    subgraph Lifecycle["Segment Lifecycle"]
        NEW[New Segment] --> ACTIVE
        ACTIVE -->|roll| LOCAL
        LOCAL -->|tiering| TIER1
        TIER1 -->|aging| TIER2
        TIER2 -->|retention| DELETE[Delete]
    end

    style Hot fill:#ff6b6b
    style Remote fill:#6bcb77
```

### Tiered Storage Configuration

```yaml
# Topic-level configuration
tiered.storage.enable: true
local.retention.ms: 86400000  # 24 hours local
retention.ms: 604800000       # 7 days total
remote.storage.manager.class: org.apache.kafka.tiered.storage.s3.S3RemoteStorageManager
```

---

## Replication

### Intra-Cluster Replication

```mermaid
sequenceDiagram
    participant P as Producer
    participant L as Leader Broker
    participant F1 as Follower 1
    participant F2 as Follower 2

    P->>L: Produce(acks=all)
    L->>L: Write to local log
    par Replication
        L->>F1: Replicate
        L->>F2: Replicate
    end
    F1->>L: ACK
    F2->>L: ACK
    L->>P: ACK (after ISR)
```

### Cross-Region Replication

```mermaid
flowchart LR
    subgraph Primary["Primary Region"]
        P_TOPIC[logs.acme.payments<br/>Source]
    end

    subgraph MirrorMaker["MirrorMaker 2"]
        MM[Consumer Group<br/>+ Producer]
        OFFSET[(Offset<br/>Sync)]
    end

    subgraph Secondary["Secondary Region"]
        S_TOPIC[logs.acme.payments<br/>Replica]
    end

    P_TOPIC -->|consume| MM
    MM -->|produce| S_TOPIC
    MM <--> OFFSET
```

---

## Consumer Groups

### Consumer Group Architecture

```mermaid
flowchart TB
    subgraph Topic["Topic: logs.acme.payments (100 partitions)"]
        P0[P0]
        P1[P1]
        P2[P2]
        P3[P3]
        P99[P99...]
    end

    subgraph CG_Flink["Consumer Group: flink-processors"]
        F1[Flink Task 1<br/>P0-24]
        F2[Flink Task 2<br/>P25-49]
        F3[Flink Task 3<br/>P50-74]
        F4[Flink Task 4<br/>P75-99]
    end

    subgraph CG_Audit["Consumer Group: audit-exporters"]
        A1[Audit Exporter 1<br/>P0-49]
        A2[Audit Exporter 2<br/>P50-99]
    end

    P0 & P1 & P2 --> F1
    P3 --> F2
    P99 --> F4

    P0 & P1 --> A1
    P99 --> A2
```

### Consumer Group Strategy

| Consumer Group | Purpose | Lag Tolerance |
|---------------|---------|---------------|
| `flink-processors` | Main processing pipeline | < 5 minutes |
| `audit-exporters` | Compliance archival | < 1 hour |
| `metrics-aggregators` | Real-time metrics | < 1 minute |
| `dlq-handlers` | Error recovery | Best effort |

---

## Producer Configuration

### Producer Settings

```mermaid
flowchart TB
    subgraph Config["Producer Configuration"]
        ACKS[acks=all<br/>Wait for all ISR]
        BATCH[batch.size=1MB<br/>Batch for throughput]
        LINGER[linger.ms=10<br/>Small delay for batching]
        COMPRESS[compression.type=lz4<br/>Fast compression]
        RETRY[retries=MAX_INT<br/>Never give up]
        IDEMPOTENT[enable.idempotence=true<br/>Exactly-once semantics]
    end

    subgraph Guarantees["Delivery Guarantees"]
        DURABLE[Durability:<br/>Survives broker failure]
        ORDER[Ordering:<br/>Preserved per partition]
        DEDUP[Deduplication:<br/>Idempotent writes]
    end

    Config --> Guarantees
```

---

## Monitoring

### Key Metrics

```mermaid
flowchart TB
    subgraph Broker["Broker Metrics"]
        BM1[BytesInPerSec]
        BM2[BytesOutPerSec]
        BM3[UnderReplicatedPartitions]
        BM4[ActiveControllerCount]
        BM5[OfflinePartitionsCount]
    end

    subgraph Consumer["Consumer Metrics"]
        CM1[consumer_lag]
        CM2[records_consumed_rate]
        CM3[fetch_latency_avg]
    end

    subgraph Producer["Producer Metrics"]
        PM1[record_send_rate]
        PM2[record_error_rate]
        PM3[request_latency_avg]
    end

    subgraph Alerts["Alert Thresholds"]
        A1[Lag > 5 min → Page]
        A2[UnderReplicated > 0 → Warn]
        A3[Offline > 0 → Page]
    end

    Broker --> Alerts
    Consumer --> Alerts
    Producer --> Alerts
```

### Dashboard Layout

```mermaid
block-beta
    columns 3

    block:row1
        columns 3
        a["Throughput (GB/s)"]
        b["Consumer Lag (min)"]
        c["Error Rate (%)"]
    end

    block:row2
        columns 3
        d["Partition Distribution"]
        e["ISR Health"]
        f["Storage Usage"]
    end

    block:row3
        columns 3
        g["Topic Breakdown"]
        h["Consumer Groups"]
        i["Cross-Region Lag"]
    end
```

---

## Failure Scenarios

### Broker Failure

```mermaid
stateDiagram-v2
    [*] --> Healthy: Normal operation

    Healthy --> BrokerDown: Broker failure detected
    BrokerDown --> LeaderElection: Controller triggers election
    LeaderElection --> Rebalancing: New leaders elected
    Rebalancing --> Healthy: Partition balance restored

    BrokerDown --> ISRShrunk: ISR shrinks
    ISRShrunk --> LeaderElection

    note right of BrokerDown
        Detection: ~10 seconds
        (session.timeout.ms)
    end note

    note right of LeaderElection
        Election: milliseconds
        per partition
    end note
```

### Network Partition

```mermaid
flowchart TB
    subgraph Before["Before Partition"]
        B1[Broker 1<br/>Leader]
        B2[Broker 2<br/>Follower]
        B3[Broker 3<br/>Follower]
        B1 <--> B2
        B2 <--> B3
        B1 <--> B3
    end

    subgraph During["During Partition"]
        B1_P[Broker 1<br/>Isolated]
        B2_P[Broker 2<br/>New Leader]
        B3_P[Broker 3<br/>Follower]
        B2_P <--> B3_P
    end

    subgraph After["After Healing"]
        B1_A[Broker 1<br/>Catches up]
        B2_A[Broker 2<br/>Leader]
        B3_A[Broker 3<br/>Follower]
        B1_A <--> B2_A
        B2_A <--> B3_A
        B1_A <--> B3_A
    end

    Before -->|partition| During
    During -->|heal| After
```

---

## Configuration Reference

### Broker Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `num.partitions` | 100 | Default for new topics |
| `default.replication.factor` | 3 | Durability |
| `min.insync.replicas` | 2 | Availability vs durability |
| `log.retention.hours` | 168 | 7 days |
| `log.segment.bytes` | 1073741824 | 1 GB segments |
| `num.io.threads` | 16 | I/O parallelism |
| `num.network.threads` | 8 | Network parallelism |
| `socket.send.buffer.bytes` | 1048576 | 1 MB send buffer |
| `socket.receive.buffer.bytes` | 1048576 | 1 MB receive buffer |

### Topic Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `retention.ms` | 604800000 | 7 days |
| `retention.bytes` | -1 | No size limit |
| `segment.ms` | 3600000 | 1 hour segments |
| `cleanup.policy` | delete | Time-based cleanup |
| `compression.type` | lz4 | Fast compression |

---

## Scaling Operations

### Adding Brokers

```mermaid
flowchart TB
    subgraph Step1["1. Deploy New Brokers"]
        DEPLOY[Start new broker instances]
        CONFIG[Apply configuration]
        JOIN[Join cluster]
    end

    subgraph Step2["2. Rebalance Partitions"]
        PLAN[Generate reassignment plan]
        THROTTLE[Set replication throttle]
        EXECUTE[Execute reassignment]
        MONITOR[Monitor progress]
    end

    subgraph Step3["3. Verify"]
        CHECK[Check partition balance]
        VALIDATE[Validate throughput]
        CLEANUP[Remove throttle]
    end

    Step1 --> Step2 --> Step3
```

### Partition Expansion

```mermaid
sequenceDiagram
    participant Admin as Admin
    participant Kafka as Kafka
    participant Consumers as Consumers

    Admin->>Kafka: Increase partitions (100→200)
    Kafka->>Kafka: Create new partitions

    Note over Consumers: Existing messages<br/>stay in old partitions

    Consumers->>Consumers: Trigger rebalance
    Consumers->>Kafka: Reassign partitions

    Note over Consumers: New messages<br/>use all partitions
```

---

## Security

### Authentication & Authorization

```mermaid
flowchart TB
    subgraph Auth["Authentication"]
        SASL[SASL/SCRAM]
        MTLS[mTLS Certificates]
    end

    subgraph Authz["Authorization"]
        ACL[Kafka ACLs]
        TOPIC_ACL[Topic-level<br/>read/write/describe]
        GROUP_ACL[Consumer Group<br/>read]
    end

    subgraph Encryption["Encryption"]
        TLS[TLS in-transit]
        ENCRYPT[At-rest encryption<br/>via S3 SSE]
    end

    Auth --> Authz --> Encryption
```

### ACL Structure

| Principal | Topic Pattern | Operation | Permission |
|-----------|--------------|-----------|------------|
| `user:fluent-bit` | `logs.*` | Write | Allow |
| `user:flink-processor` | `logs.*` | Read | Allow |
| `user:flink-processor` | `logs.dlq.*` | Write | Allow |
| `user:admin` | `*` | All | Allow |
