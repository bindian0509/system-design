# Scaling Operations Runbook

## Overview

This runbook provides procedures for scaling the log ingestion system to handle increased load or to optimize costs during low-traffic periods.

---

## Scaling Triggers

```mermaid
flowchart TB
    subgraph Metrics["Scaling Metrics"]
        LAG[Kafka Consumer Lag<br/>> 5 minutes]
        CPU[CPU Utilization<br/>> 70%]
        MEMORY[Memory Usage<br/>> 80%]
        DISK[Disk Usage<br/>> 75%]
        QUERY[Query Latency<br/>p95 > 30s]
    end

    subgraph Actions["Scaling Actions"]
        KAFKA_UP[Add Kafka brokers]
        FLINK_UP[Scale Flink parallelism]
        CH_UP[Add ClickHouse shards]
        TRINO_UP[Add Trino workers]
    end

    LAG --> FLINK_UP
    LAG --> KAFKA_UP
    CPU --> FLINK_UP
    MEMORY --> CH_UP
    DISK --> CH_UP
    QUERY --> TRINO_UP
    QUERY --> CH_UP
```

---

## Kafka Scaling

### Adding Brokers

```mermaid
flowchart TB
    subgraph Before["Current State"]
        B1[Broker 0]
        B2[Broker 1]
        B3[Broker 2]
    end

    subgraph During["Scaling Process"]
        D1[Deploy new brokers]
        D2[Update cluster config]
        D3[Rebalance partitions]
        D4[Verify data distribution]
    end

    subgraph After["Target State"]
        A1[Broker 0]
        A2[Broker 1]
        A3[Broker 2]
        A4[Broker 3]
        A5[Broker 4]
    end

    Before --> During --> After
```

#### Procedure

1. **Verify current state**
   ```bash
   # Check current broker count
   kubectl get pods -n kafka -l app=kafka

   # Check partition distribution
   kafka-topics.sh --describe --topic logs.tenant.service \
     --bootstrap-server kafka:9092
   ```

2. **Scale StatefulSet**
   ```bash
   # Scale from 3 to 5 brokers
   kubectl scale statefulset kafka -n kafka --replicas=5

   # Wait for new brokers
   kubectl rollout status statefulset/kafka -n kafka
   ```

3. **Generate reassignment plan**
   ```bash
   # Create topics.json with topics to rebalance
   cat > topics.json << EOF
   {"topics": [
     {"topic": "logs.tenant-a.service-1"},
     {"topic": "logs.tenant-b.service-1"}
   ], "version": 1}
   EOF

   # Generate plan
   kafka-reassign-partitions.sh --generate \
     --topics-to-move-json-file topics.json \
     --broker-list "0,1,2,3,4" \
     --bootstrap-server kafka:9092 \
     > reassignment.json
   ```

4. **Execute reassignment with throttling**
   ```bash
   # Apply throttle to prevent overload
   kafka-reassign-partitions.sh --execute \
     --reassignment-json-file reassignment.json \
     --bootstrap-server kafka:9092 \
     --throttle 100000000  # 100 MB/s
   ```

5. **Monitor progress**
   ```bash
   # Check reassignment status
   kafka-reassign-partitions.sh --verify \
     --reassignment-json-file reassignment.json \
     --bootstrap-server kafka:9092
   ```

6. **Remove throttle**
   ```bash
   kafka-reassign-partitions.sh --verify \
     --reassignment-json-file reassignment.json \
     --bootstrap-server kafka:9092
   # Throttle automatically removed when complete
   ```

### Partition Expansion

```mermaid
sequenceDiagram
    participant Admin
    participant Kafka
    participant Flink

    Admin->>Kafka: Increase partition count
    Note over Kafka: New partitions created

    Admin->>Flink: Trigger consumer rebalance
    Flink->>Kafka: Leave and rejoin group
    Kafka->>Flink: Assign new partition set

    Note over Flink: Now consuming<br/>from all partitions
```

#### Procedure

```bash
# Increase partitions (100 -> 200)
kafka-topics.sh --alter \
  --topic logs.tenant-a.service-1 \
  --partitions 200 \
  --bootstrap-server kafka:9092

# Note: This will trigger Flink consumer rebalance automatically
```

---

## Flink Scaling

### Horizontal Scaling

```mermaid
flowchart TB
    subgraph Current["Current: 50 TaskManagers"]
        TM1[TM 1]
        TM2[TM 2]
        TMN[TM 50]
    end

    subgraph Scale["Scaling Action"]
        HPA[HPA or Manual]
    end

    subgraph Target["Target: 100 TaskManagers"]
        NTM1[TM 1]
        NTM2[TM 2]
        NTMN[TM 100]
    end

    Current --> Scale --> Target
```

#### Procedure

1. **Check current state**
   ```bash
   # Current TaskManager count
   kubectl get pods -n flink -l component=taskmanager | wc -l

   # Check consumer lag
   curl http://flink-jobmanager:8081/jobs/{job-id}/metrics \
     | jq '.[] | select(.id | contains("lag"))'
   ```

2. **Scale TaskManagers**
   ```bash
   # Manual scaling
   kubectl scale deployment flink-taskmanager -n flink --replicas=100

   # Or update HPA limits
   kubectl patch hpa flink-taskmanager -n flink \
     -p '{"spec":{"maxReplicas":100}}'
   ```

3. **Trigger job rescale**
   ```bash
   # Take savepoint
   flink savepoint {job-id} s3://bucket/savepoints/

   # Cancel job
   flink cancel {job-id}

   # Restart with new parallelism
   flink run -p 400 -s s3://bucket/savepoints/latest \
     /opt/flink/jobs/log-processor.jar
   ```

4. **Verify scaling**
   ```bash
   # Check new parallelism
   curl http://flink-jobmanager:8081/jobs/{job-id}/vertices \
     | jq '.[].parallelism'

   # Monitor lag reduction
   watch -n 5 "kafka-consumer-groups.sh --describe \
     --group flink-log-processor --bootstrap-server kafka:9092"
   ```

### Parallelism Adjustment

```mermaid
flowchart LR
    subgraph Operators["Operator Parallelism"]
        SOURCE[Source<br/>p=1000]
        MAP[Map<br/>p=500]
        SINK[Sink<br/>p=200]
    end

    subgraph Constraints["Constraints"]
        KAFKA[Kafka partitions]
        SLOTS[Available slots]
        CH[ClickHouse connections]
    end

    KAFKA --> SOURCE
    SLOTS --> MAP
    CH --> SINK
```

---

## ClickHouse Scaling

### Adding Shards

```mermaid
flowchart TB
    subgraph Current["Current: 4 Shards"]
        S1[Shard 1<br/>R1, R2, R3]
        S2[Shard 2<br/>R1, R2, R3]
        S3[Shard 3<br/>R1, R2, R3]
        S4[Shard 4<br/>R1, R2, R3]
    end

    subgraph Add["Add Shard 5"]
        NEW[Deploy 3 replicas]
        CONFIG[Update cluster config]
        TABLE[Create local tables]
    end

    subgraph Final["Final: 5 Shards"]
        F1[Shard 1]
        F2[Shard 2]
        F3[Shard 3]
        F4[Shard 4]
        F5[Shard 5]
    end

    Current --> Add --> Final
```

#### Procedure

1. **Deploy new shard nodes**
   ```bash
   # Update replica count
   kubectl scale statefulset clickhouse-shard-5 -n clickhouse --replicas=3

   # Wait for pods
   kubectl rollout status statefulset/clickhouse-shard-5 -n clickhouse
   ```

2. **Update cluster configuration**
   ```xml
   <!-- Add to config.xml on all nodes -->
   <remote_servers>
       <logs_cluster>
           <!-- Existing shards -->
           <shard>...</shard>

           <!-- New shard 5 -->
           <shard>
               <replica>
                   <host>clickhouse-shard-5-0</host>
                   <port>9000</port>
               </replica>
               <replica>
                   <host>clickhouse-shard-5-1</host>
                   <port>9000</port>
               </replica>
               <replica>
                   <host>clickhouse-shard-5-2</host>
                   <port>9000</port>
               </replica>
           </shard>
       </logs_cluster>
   </remote_servers>
   ```

3. **Create tables on new shard**
   ```sql
   -- On each new replica
   CREATE TABLE logs_local ON CLUSTER 'logs_cluster'
   (
       -- Same schema as existing
   ) ENGINE = ReplicatedMergeTree(...)
   ```

4. **Verify shard weight**
   ```sql
   -- Check data distribution
   SELECT
       hostName() as host,
       count() as rows
   FROM logs_distributed
   GROUP BY host;
   ```

### Adding Replicas

```mermaid
flowchart TB
    subgraph Before["Shard 1: 3 Replicas"]
        R1[Replica 1]
        R2[Replica 2]
        R3[Replica 3]
    end

    subgraph After["Shard 1: 4 Replicas"]
        NR1[Replica 1]
        NR2[Replica 2]
        NR3[Replica 3]
        NR4[Replica 4]
    end

    Before --> After
```

#### Procedure

```bash
# Scale up replicas for shard 1
kubectl scale statefulset clickhouse-shard-1 -n clickhouse --replicas=4

# The new replica will automatically sync from ZooKeeper
# Monitor replication progress
watch "clickhouse-client --query 'SELECT * FROM system.replicas'"
```

### Storage Expansion

```mermaid
flowchart TB
    subgraph Assessment["Assess Need"]
        DISK_USAGE[Disk > 75%]
        TTL_CHECK[TTL working?]
    end

    subgraph Options["Options"]
        EXPAND_PV[Expand PVC]
        ADD_DISK[Add disks]
        ADD_SHARD[Add shards]
        REDUCE_TTL[Reduce retention]
    end

    DISK_USAGE --> TTL_CHECK
    TTL_CHECK -->|Yes| Options
    TTL_CHECK -->|No| FIX_TTL[Fix TTL config]
```

---

## Trino Scaling

### Adding Workers

```mermaid
flowchart TB
    subgraph Current["Current: 20 Workers"]
        W1[Worker 1-10]
        W2[Worker 11-20]
    end

    subgraph Action["Scale Action"]
        DEPLOY[Deploy more workers]
        REGISTER[Workers auto-register]
    end

    subgraph Target["Target: 50 Workers"]
        NW1[Worker 1-25]
        NW2[Worker 26-50]
    end

    Current --> Action --> Target
```

#### Procedure

1. **Check current state**
   ```bash
   # Current worker count
   curl http://trino-coordinator:8080/v1/cluster | jq '.runningWorkers'

   # Active queries
   curl http://trino-coordinator:8080/v1/query | jq 'length'
   ```

2. **Scale workers**
   ```bash
   # Scale deployment
   kubectl scale deployment trino-worker -n trino --replicas=50

   # Wait for workers to register
   watch "curl -s http://trino-coordinator:8080/v1/cluster | jq '.runningWorkers'"
   ```

3. **Verify capacity**
   ```bash
   # Check cluster status
   curl http://trino-coordinator:8080/v1/cluster | jq
   ```

### Resource Group Adjustment

```mermaid
flowchart TB
    subgraph Before["Before"]
        BG[Global: 100%]
        BP[Premium: 50%]
        BS[Standard: 50%]
    end

    subgraph After["After - Increased Premium"]
        AG[Global: 100%]
        AP[Premium: 60%]
        AS[Standard: 40%]
    end

    Before --> After
```

---

## Auto-Scaling Configuration

### Kubernetes HPA

```yaml
# Flink TaskManager HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: flink-taskmanager
  namespace: flink
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: flink-taskmanager
  minReplicas: 50
  maxReplicas: 200
  metrics:
  - type: External
    external:
      metric:
        name: kafka_consumer_lag
        selector:
          matchLabels:
            consumer_group: flink-log-processor
      target:
        type: AverageValue
        averageValue: "1000000"  # 1M messages lag per pod
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 120
```

### KEDA Scaling

```yaml
# KEDA ScaledObject for Kafka lag
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: flink-kafka-scaler
  namespace: flink
spec:
  scaleTargetRef:
    name: flink-taskmanager
  pollingInterval: 30
  cooldownPeriod: 300
  minReplicaCount: 50
  maxReplicaCount: 200
  triggers:
  - type: kafka
    metadata:
      bootstrapServers: kafka:9092
      consumerGroup: flink-log-processor
      topic: logs.*
      lagThreshold: "100000"
      offsetResetPolicy: earliest
```

---

## Scaling Decision Matrix

```mermaid
flowchart TB
    subgraph Symptoms["Observed Symptoms"]
        S1[High consumer lag]
        S2[Slow queries]
        S3[High disk usage]
        S4[High CPU]
        S5[High memory]
    end

    subgraph Analysis["Root Cause"]
        A1[Insufficient Flink capacity]
        A2[ClickHouse bottleneck]
        A3[Need more storage]
        A4[Processing bottleneck]
        A5[Need more replicas]
    end

    subgraph Action["Scaling Action"]
        ACT1[Scale Flink TMs]
        ACT2[Add CH shards/replicas]
        ACT3[Expand storage / add shards]
        ACT4[Scale processing layer]
        ACT5[Add read replicas]
    end

    S1 --> A1 --> ACT1
    S2 --> A2 --> ACT2
    S3 --> A3 --> ACT3
    S4 --> A4 --> ACT4
    S5 --> A5 --> ACT5
```

---

## Capacity Planning

### Growth Estimation

```mermaid
xychart-beta
    title "Projected Capacity Needs (6 months)"
    x-axis ["Month 1", "Month 2", "Month 3", "Month 4", "Month 5", "Month 6"]
    y-axis "Daily Volume (PB)" 0 --> 15
    line "Current Capacity" [12, 12, 12, 12, 12, 12]
    line "Projected Usage" [10, 10.5, 11, 11.5, 12, 13]
```

### Scaling Thresholds

| Metric | Warning (75%) | Scale Trigger (85%) | Critical (95%) |
|--------|---------------|---------------------|----------------|
| **Kafka disk** | 300 GB | 340 GB | 380 GB |
| **ClickHouse disk** | 37.5 TB | 42.5 TB | 47.5 TB |
| **Consumer lag** | 3 min | 5 min | 10 min |
| **Query latency p95** | 15 s | 20 s | 30 s |

---

## Scale-Down Procedures

### Flink Scale-Down

```mermaid
flowchart TB
    subgraph Check["Pre-Check"]
        LAG[Lag < 1 minute]
        CPU[CPU < 40%]
        TIME[Low-traffic window]
    end

    subgraph Action["Scale-Down"]
        SAVE[Take savepoint]
        SCALE[Reduce replicas]
        RESTART[Restart job]
    end

    subgraph Verify["Verify"]
        MONITOR[Monitor lag]
        ROLLBACK[Ready to rollback]
    end

    Check --> Action --> Verify
```

### Kafka Scale-Down

```mermaid
flowchart TB
    subgraph Assessment["Assessment"]
        USAGE[Broker utilization < 40%]
        PARTITIONS[Partitions can be moved]
    end

    subgraph Procedure["Procedure"]
        MOVE[Move partitions away]
        VERIFY[Verify replication]
        REMOVE[Remove broker]
    end

    Assessment --> Procedure
```

**Warning**: Kafka scale-down is complex and risky. Only perform during maintenance windows.
