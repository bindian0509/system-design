# Collection Layer Design

## Overview

The collection layer is responsible for gathering logs from all sources (applications, infrastructure, Kubernetes) and reliably forwarding them to Kafka. This layer uses lightweight agents deployed as DaemonSets on Kubernetes and agents on VMs.

---

## Architecture

### Deployment Topology

```mermaid
flowchart TB
    subgraph K8S["Kubernetes Cluster"]
        subgraph Node1["Node 1"]
            P1[Pod: app-1]
            P2[Pod: app-2]
            FB1[Fluent Bit<br/>DaemonSet]
        end

        subgraph Node2["Node 2"]
            P3[Pod: app-3]
            P4[Pod: app-4]
            FB2[Fluent Bit<br/>DaemonSet]
        end

        subgraph Node3["Node 3"]
            P5[Pod: app-5]
            P6[Pod: app-6]
            FB3[Fluent Bit<br/>DaemonSet]
        end
    end

    subgraph VMs["VM Fleet"]
        VM1[VM 1<br/>Vector Agent]
        VM2[VM 2<br/>Vector Agent]
        VM3[VM 3<br/>Vector Agent]
    end

    subgraph Kafka["Kafka Cluster"]
        TOPIC[logs.{tenant}.{service}]
    end

    FB1 & FB2 & FB3 --> Kafka
    VM1 & VM2 & VM3 --> Kafka
```

### Collection Pipeline

```mermaid
flowchart LR
    subgraph Sources["Log Sources"]
        STDOUT[Container stdout]
        STDERR[Container stderr]
        FILE[Log files]
        JOURNAL[Systemd journal]
    end

    subgraph FluentBit["Fluent Bit Pipeline"]
        INPUT[Input Plugins]
        PARSER[Parsers]
        FILTER[Filters]
        BUFFER[Buffer]
        OUTPUT[Output Plugins]
    end

    subgraph Destination["Destination"]
        KAFKA[Kafka]
    end

    STDOUT & STDERR --> INPUT
    FILE & JOURNAL --> INPUT
    INPUT --> PARSER
    PARSER --> FILTER
    FILTER --> BUFFER
    BUFFER --> OUTPUT
    OUTPUT --> KAFKA
```

---

## Fluent Bit Configuration

### Plugin Pipeline

```mermaid
flowchart TB
    subgraph Input["Input Plugins"]
        TAIL[tail<br/>Container logs]
        SYSTEMD[systemd<br/>Node services]
        TCP[tcp<br/>Direct logging]
    end

    subgraph Parser["Parsers"]
        JSON_P[JSON parser]
        REGEX_P[Regex parser]
        DOCKER_P[Docker parser]
    end

    subgraph Filter["Filters"]
        K8S[kubernetes<br/>Pod metadata]
        MODIFY[modify<br/>Field manipulation]
        NEST[nest<br/>Structure fields]
        THROTTLE[throttle<br/>Rate limiting]
    end

    subgraph Buffer["Buffer"]
        MEM[Memory buffer]
        FILE_BUF[Filesystem buffer]
    end

    subgraph Output["Output"]
        KAFKA_OUT[kafka<br/>Primary destination]
        STDOUT_OUT[stdout<br/>Debug only]
    end

    Input --> Parser --> Filter --> Buffer --> Output
```

### Kubernetes Metadata Enrichment

```mermaid
flowchart TB
    subgraph RawLog["Raw Log"]
        RAW["{ 'message': 'Request processed', 'level': 'INFO' }"]
    end

    subgraph K8sFilter["Kubernetes Filter"]
        API[K8s API<br/>Pod metadata]
        CACHE[(Local cache)]
    end

    subgraph EnrichedLog["Enriched Log"]
        ENRICHED["{
          'message': 'Request processed',
          'level': 'INFO',
          'kubernetes': {
            'pod_name': 'app-xyz-123',
            'namespace': 'production',
            'container': 'app',
            'labels': {
              'app': 'payment-service',
              'team': 'payments'
            }
          }
        }"]
    end

    RawLog --> K8sFilter
    K8sFilter --> API
    API --> CACHE
    K8sFilter --> EnrichedLog
```

### Full Configuration

```yaml
[SERVICE]
    Flush         1
    Grace         30
    Log_Level     info
    Daemon        Off
    Parsers_File  parsers.conf
    HTTP_Server   On
    HTTP_Listen   0.0.0.0
    HTTP_Port     2020
    Health_Check  On
    storage.path  /var/log/flb-storage/
    storage.sync  normal
    storage.checksum off
    storage.max_chunks_up 128

[INPUT]
    Name              tail
    Tag               kube.*
    Path              /var/log/containers/*.log
    Parser            docker
    DB                /var/log/flb_kube.db
    Mem_Buf_Limit     50MB
    Skip_Long_Lines   On
    Refresh_Interval  10
    storage.type      filesystem

[INPUT]
    Name              systemd
    Tag               host.systemd
    Systemd_Filter    _SYSTEMD_UNIT=kubelet.service
    Systemd_Filter    _SYSTEMD_UNIT=docker.service
    Read_From_Tail    On
    Strip_Underscores On

[FILTER]
    Name                kubernetes
    Match               kube.*
    Kube_URL            https://kubernetes.default.svc:443
    Kube_CA_File        /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
    Kube_Token_File     /var/run/secrets/kubernetes.io/serviceaccount/token
    Kube_Tag_Prefix     kube.var.log.containers.
    Merge_Log           On
    Merge_Log_Key       log_processed
    K8S-Logging.Parser  On
    K8S-Logging.Exclude Off
    Labels              On
    Annotations         Off
    Buffer_Size         32k

[FILTER]
    Name          modify
    Match         *
    Add           cluster ${CLUSTER_NAME}
    Add           region ${AWS_REGION}
    Rename        log message
    Remove        stream

[FILTER]
    Name          throttle
    Match         *
    Rate          10000
    Window        5
    Interval      1s
    Print_Status  false

[OUTPUT]
    Name           kafka
    Match          *
    Brokers        kafka-0:9092,kafka-1:9092,kafka-2:9092
    Topics         logs.${tenant_id}.${service}
    Timestamp_Key  timestamp
    Timestamp_Format iso8601
    Retry_Limit    False
    rdkafka.compression.type lz4
    rdkafka.batch.size 1000000
    rdkafka.linger.ms 10
    rdkafka.acks all
    rdkafka.enable.idempotence true
```

---

## Vector Alternative

### Vector Pipeline

```mermaid
flowchart LR
    subgraph Sources["Sources"]
        FILE[file]
        DOCKER_SRC[docker_logs]
        JOURNAL_SRC[journald]
        K8S_SRC[kubernetes_logs]
    end

    subgraph Transforms["Transforms"]
        REMAP[remap<br/>VRL scripts]
        FILTER_V[filter]
        ROUTE[route]
        AGGREGATE[aggregate]
    end

    subgraph Sinks["Sinks"]
        KAFKA_SINK[kafka]
        CONSOLE[console<br/>debug]
    end

    Sources --> Transforms --> Sinks
```

### Vector vs Fluent Bit

```mermaid
quadrantChart
    title "Collection Agent Comparison"
    x-axis Low Resource Usage --> High Resource Usage
    y-axis Low Features --> High Features

    quadrant-1 "Full-featured"
    quadrant-2 "Lightweight"
    quadrant-3 "Avoid"
    quadrant-4 "Specialized"

    Fluent Bit: [0.2, 0.6]
    Vector: [0.5, 0.85]
    Logstash: [0.8, 0.9]
    Filebeat: [0.3, 0.5]
```

| Feature | Fluent Bit | Vector |
|---------|-----------|--------|
| **Memory Usage** | ~10 MB | ~50 MB |
| **CPU Usage** | Lower | Higher |
| **Configuration** | INI-based | TOML/YAML |
| **Transform Language** | Lua scripts | VRL (powerful) |
| **Kubernetes Native** | Excellent | Good |
| **Recommended For** | High-density K8s | Complex transforms |

---

## Buffering Strategy

### Buffer Architecture

```mermaid
flowchart TB
    subgraph Pipeline["Collection Pipeline"]
        INPUT[Input<br/>Log ingestion]
        MEMORY[Memory Buffer<br/>First tier]
        DISK[Disk Buffer<br/>Overflow]
        OUTPUT[Output<br/>Kafka]
    end

    subgraph Metrics["Buffer Metrics"]
        M1[chunks_up<br/>In-memory chunks]
        M2[chunks_down<br/>On-disk chunks]
        M3[overlimit<br/>Backpressure active]
    end

    INPUT --> MEMORY
    MEMORY -->|full| DISK
    MEMORY --> OUTPUT
    DISK --> OUTPUT

    MEMORY --> M1
    DISK --> M2
```

### Buffer Sizing

```mermaid
flowchart LR
    subgraph Capacity["Buffer Capacity"]
        MEM_SIZE[Memory: 50 MB<br/>per input]
        DISK_SIZE[Disk: 1 GB<br/>per node]
        TOTAL[Total: ~1-2 GB<br/>per node]
    end

    subgraph Duration["Buffer Duration"]
        NORMAL[Normal: seconds]
        DEGRADED[Degraded: 1-2 minutes]
        OUTAGE[Outage: 5-10 minutes<br/>before data loss]
    end

    Capacity --> Duration
```

### Backpressure Handling

```mermaid
stateDiagram-v2
    [*] --> Normal: Start

    Normal --> MemoryBuffering: Output slow
    MemoryBuffering --> DiskBuffering: Memory full
    DiskBuffering --> Throttling: Disk filling
    Throttling --> Dropping: Disk full

    MemoryBuffering --> Normal: Output recovers
    DiskBuffering --> MemoryBuffering: Disk drains
    Throttling --> DiskBuffering: Space available

    Dropping --> [*]: Data loss

    note right of MemoryBuffering
        Low latency
        Fast recovery
    end note

    note right of DiskBuffering
        Higher latency
        More capacity
    end note

    note right of Throttling
        Rate limiting input
        Warning alerts
    end note
```

---

## High Availability

### DaemonSet Deployment

```mermaid
flowchart TB
    subgraph K8S["Kubernetes Cluster"]
        subgraph DS["DaemonSet: fluent-bit"]
            DS_SPEC[Pod Template<br/>+ Tolerations<br/>+ Node Affinity]
        end

        subgraph Nodes["Nodes"]
            N1[Node 1<br/>FB Pod]
            N2[Node 2<br/>FB Pod]
            N3[Node 3<br/>FB Pod]
        end

        subgraph Storage["Persistent Storage"]
            PV1[Host Path<br/>/var/log]
            PV2[Host Path<br/>/var/lib/docker]
            PV3[EmptyDir<br/>Buffer storage]
        end
    end

    DS --> N1 & N2 & N3
    N1 --> PV1
    N2 --> PV2
    N3 --> PV3
```

### Pod Spec

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluent-bit
  namespace: logging
spec:
  selector:
    matchLabels:
      app: fluent-bit
  template:
    metadata:
      labels:
        app: fluent-bit
    spec:
      serviceAccountName: fluent-bit
      tolerations:
      - operator: Exists
        effect: NoSchedule
      - operator: Exists
        effect: NoExecute
      containers:
      - name: fluent-bit
        image: fluent/fluent-bit:2.2
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
        volumeMounts:
        - name: varlog
          mountPath: /var/log
          readOnly: true
        - name: containers
          mountPath: /var/lib/docker/containers
          readOnly: true
        - name: config
          mountPath: /fluent-bit/etc
        - name: buffer
          mountPath: /var/log/flb-storage
        ports:
        - containerPort: 2020
          name: metrics
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 2020
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 2020
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: varlog
        hostPath:
          path: /var/log
      - name: containers
        hostPath:
          path: /var/lib/docker/containers
      - name: config
        configMap:
          name: fluent-bit-config
      - name: buffer
        emptyDir:
          sizeLimit: 1Gi
```

---

## Log Parsing

### Parser Configuration

```mermaid
flowchart TB
    subgraph Formats["Log Formats"]
        JSON_LOG["JSON: {'level':'INFO',...}"]
        APACHE["Apache: 192.168.1.1 - - [...]"]
        CUSTOM["Custom: [TIMESTAMP] LEVEL msg"]
    end

    subgraph Parsers["Parsers"]
        JSON_PARSER[json<br/>Native JSON parsing]
        REGEX_PARSER[regex<br/>Pattern matching]
        LTSV_PARSER[ltsv<br/>Labeled TSV]
    end

    subgraph Decoded["Decoded Fields"]
        FIELDS[timestamp<br/>level<br/>message<br/>...metadata]
    end

    JSON_LOG --> JSON_PARSER
    APACHE --> REGEX_PARSER
    CUSTOM --> REGEX_PARSER
    JSON_PARSER & REGEX_PARSER & LTSV_PARSER --> FIELDS
```

### Parser Definitions

```ini
[PARSER]
    Name        docker
    Format      json
    Time_Key    time
    Time_Format %Y-%m-%dT%H:%M:%S.%L
    Time_Keep   On
    Decode_Field_As escaped log

[PARSER]
    Name        json
    Format      json
    Time_Key    timestamp
    Time_Format %Y-%m-%dT%H:%M:%S.%LZ

[PARSER]
    Name        apache
    Format      regex
    Regex       ^(?<host>[^ ]*) [^ ]* (?<user>[^ ]*) \[(?<time>[^\]]*)\] "(?<method>\S+)(?: +(?<path>[^\"]*?)(?: +\S*)?)?" (?<code>[^ ]*) (?<size>[^ ]*)(?: "(?<referer>[^\"]*)" "(?<agent>[^\"]*)")?$
    Time_Key    time
    Time_Format %d/%b/%Y:%H:%M:%S %z

[PARSER]
    Name        syslog
    Format      regex
    Regex       ^\<(?<pri>[0-9]+)\>(?<time>[^ ]* {1,2}[^ ]* [^ ]*) (?<host>[^ ]*) (?<ident>[a-zA-Z0-9_\/\.\-]*)(?:\[(?<pid>[0-9]+)\])?(?:[^\:]*\:)? *(?<message>.*)$
    Time_Key    time
    Time_Format %b %d %H:%M:%S
```

---

## Retry Logic

### Retry Strategy

```mermaid
flowchart TB
    subgraph Send["Send to Kafka"]
        ATTEMPT[Send attempt]
    end

    ATTEMPT --> Check{Success?}

    Check -->|Yes| Done[Move to next batch]

    Check -->|No| Classify[Classify error]

    Classify --> Retryable{Retryable?}

    Retryable -->|Yes| Backoff[Exponential backoff]
    Backoff --> Delay["Wait: 2^n seconds<br/>max 60 seconds"]
    Delay --> ATTEMPT

    Retryable -->|No| Buffer[Buffer to disk]
    Buffer --> Alert[Alert on persistent failure]
```

### Backoff Timeline

```mermaid
xychart-beta
    title "Exponential Backoff (seconds)"
    x-axis ["Retry 1", "Retry 2", "Retry 3", "Retry 4", "Retry 5", "Retry 6"]
    y-axis "Wait Time (s)" 0 --> 65
    bar [1, 2, 4, 8, 16, 32]
```

---

## Monitoring

### Key Metrics

```mermaid
flowchart TB
    subgraph Input["Input Metrics"]
        I1[fluentbit_input_records_total]
        I2[fluentbit_input_bytes_total]
        I3[fluentbit_input_files_rotated]
    end

    subgraph Buffer["Buffer Metrics"]
        B1[fluentbit_storage_chunks]
        B2[fluentbit_storage_overlimit]
        B3[fluentbit_storage_mem_chunks]
    end

    subgraph Output["Output Metrics"]
        O1[fluentbit_output_records_total]
        O2[fluentbit_output_retries_total]
        O3[fluentbit_output_errors_total]
    end

    subgraph Alerts["Alert Rules"]
        A1[Retries > 100/min → Warn]
        A2[Errors > 10/min → Page]
        A3[Overlimit = 1 → Page]
    end

    Input & Buffer & Output --> Alerts
```

### Dashboard Layout

```mermaid
block-beta
    columns 3

    block:row1
        columns 3
        a["Input Rate<br/>(records/s)"]
        b["Output Rate<br/>(records/s)"]
        c["Lag<br/>(buffered)"]
    end

    block:row2
        columns 3
        d["Buffer Usage<br/>(MB)"]
        e["Retry Rate"]
        f["Error Rate"]
    end

    block:row3
        columns 3
        g["Per-Node<br/>Breakdown"]
        h["Parser<br/>Failures"]
        i["Kafka<br/>Latency"]
    end
```

---

## Security

### RBAC Configuration

```mermaid
flowchart TB
    subgraph ServiceAccount["ServiceAccount: fluent-bit"]
        SA[ServiceAccount]
    end

    subgraph ClusterRole["ClusterRole: fluent-bit"]
        R1[get pods]
        R2[get namespaces]
        R3[list pods]
    end

    subgraph Binding["ClusterRoleBinding"]
        CRB[fluent-bit-binding]
    end

    SA --> CRB --> ClusterRole
```

### Kafka Authentication

```mermaid
flowchart LR
    subgraph FluentBit["Fluent Bit"]
        CLIENT[Kafka Client]
        SASL[SASL/SCRAM]
    end

    subgraph Kafka["Kafka"]
        BROKER[Broker]
        AUTH[Authentication]
    end

    CLIENT -->|credentials| SASL
    SASL -->|SASL_SSL| BROKER
    BROKER --> AUTH
```

```ini
[OUTPUT]
    Name           kafka
    Match          *
    Brokers        kafka-bootstrap:9093
    Topics         logs.${tenant}.${service}
    rdkafka.security.protocol SASL_SSL
    rdkafka.sasl.mechanism SCRAM-SHA-512
    rdkafka.sasl.username ${KAFKA_USERNAME}
    rdkafka.sasl.password ${KAFKA_PASSWORD}
    rdkafka.ssl.ca.location /etc/kafka/ca.crt
```

---

## Troubleshooting

### Common Issues

```mermaid
flowchart TB
    subgraph Issues["Common Issues"]
        I1[High memory usage]
        I2[Missing logs]
        I3[Parse failures]
        I4[Kafka connection errors]
    end

    subgraph Causes["Root Causes"]
        C1[Buffer too large]
        C2[File rotation issues]
        C3[Wrong parser config]
        C4[Network/auth issues]
    end

    subgraph Solutions["Solutions"]
        S1[Reduce Mem_Buf_Limit]
        S2[Check DB file, permissions]
        S3[Add parser annotations]
        S4[Check certificates, SASL]
    end

    I1 --> C1 --> S1
    I2 --> C2 --> S2
    I3 --> C3 --> S3
    I4 --> C4 --> S4
```

### Debug Commands

```bash
# Check Fluent Bit health
curl http://localhost:2020/api/v1/health

# View internal metrics
curl http://localhost:2020/api/v1/metrics

# Check storage status
curl http://localhost:2020/api/v1/storage

# View uptime
curl http://localhost:2020/api/v1/uptime

# Enable debug logging
[SERVICE]
    Log_Level    debug
```

---

## Configuration Reference

### Resource Limits

| Parameter | Minimum | Recommended | Maximum |
|-----------|---------|-------------|---------|
| **CPU** | 100m | 250m | 500m |
| **Memory** | 128Mi | 256Mi | 512Mi |
| **Disk Buffer** | 256Mi | 1Gi | 2Gi |

### Performance Tuning

| Parameter | Default | Tuned | Description |
|-----------|---------|-------|-------------|
| `Mem_Buf_Limit` | 5 MB | 50 MB | Memory buffer per input |
| `storage.max_chunks_up` | 128 | 256 | In-memory chunks |
| `Refresh_Interval` | 60 | 10 | File check interval (sec) |
| `Buffer_Chunk_Size` | 32 KB | 64 KB | Chunk size |
| `Buffer_Max_Size` | 32 KB | 256 KB | Max buffer per read |
| `rdkafka.batch.size` | 16 KB | 1 MB | Kafka batch size |
| `rdkafka.linger.ms` | 0 | 10 | Kafka batching delay |
