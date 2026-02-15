# 08 — Client-Side Resilience Patterns

## Context

The baseline design responds with **202 Accepted** and relies on the pipeline (Kafka → Writers → MySQL) for durability. But what happens when the POST endpoint itself is unavailable? If we consider our clients (backend microservices) to be **smart enough** to hold and retry, several resilience patterns become viable.

This document evaluates four patterns for client-side resilience, their trade-offs at 250k RPS, and the recommended combination.

```mermaid
graph TB
    subgraph "Client-Side Resilience Patterns"
        P1["Pattern 1<br/>In-Memory Ring Buffer<br/>+ Exponential Backoff"]
        P2["Pattern 2<br/>Local Disk WAL<br/>+ Background Shipper"]
        P3["Pattern 3<br/>Circuit Breaker<br/>+ Batch Accumulator"]
        P4["Pattern 4<br/>Dual-Path<br/>with Failover Sink"]
    end

    subgraph "What They Solve"
        S1["Brief blips<br/>(1-30 seconds)"]
        S2["Prolonged outages<br/>(minutes to hours)"]
        S3["Thundering herd<br/>on recovery"]
        S4["Regional / total<br/>endpoint failure"]
    end

    P1 --> S1
    P2 --> S2
    P3 --> S3
    P4 --> S4

    style P1 fill:#50c878,color:#000
    style P2 fill:#4a90d9,color:#fff
    style P3 fill:#f5a623,color:#000
    style P4 fill:#7b68ee,color:#fff
```

---

## Pattern 1: In-Memory Ring Buffer + Exponential Backoff

The simplest "smart client." Logs go into a fixed-size circular buffer. A background thread drains the buffer to the POST endpoint. On failure, it backs off and retries.

### Architecture

```mermaid
graph LR
    subgraph "Application Process"
        LOG["log.Info(msg)"] --> RB["Ring Buffer<br/>(fixed size: 50K entries)"]
        RB --> BG["Background Thread<br/>drains buffer"]
    end

    BG -->|"Batch POST<br/>(500-1000 entries)"| EP[POST /logs]
    EP -->|"200/202"| BG
    EP -->|"503 / timeout"| RETRY["Exponential Backoff<br/>100ms → 200ms → 400ms<br/>→ 800ms → max 30s"]
    RETRY --> EP

    style RB fill:#50c878,color:#000
    style RETRY fill:#f5a623,color:#000
```

### How It Works at 250k RPS

```mermaid
graph TD
    subgraph "Per Service Instance (~5,000 logs/sec)"
        A["Log call<br/>~1μs (push to ring)"] --> B["Ring Buffer<br/>50,000 entries = ~50 MB"]
        B --> C["Background thread<br/>reads 1,000 entries"]
        C --> D["Batch POST<br/>(1,000 entries per request)"]
    end

    subgraph "Capacity Math"
        E["Buffer: 50,000 entries"]
        F["Fill rate: 5,000/sec"]
        G["Survival window:<br/>50,000 / 5,000 = 10 seconds"]
    end

    style B fill:#50c878,color:#000
    style G fill:#f5a623,color:#000
```

- Each service instance produces ~500-5,000 logs/sec
- Buffer size: 50,000 entries (~50 MB per instance)
- At 5,000 logs/sec, buffer holds ~10 seconds of data before overwriting oldest entries
- Background thread batches 500-1,000 entries per POST (reduces HTTP calls 500-1000x)

### Pros

| Pro | Detail |
|---|---|
| Minimal implementation | 100-200 lines of code in any language. No external dependencies. |
| No disk I/O | Purely in-memory. Zero impact on application's disk performance. |
| Handles brief outages | Seconds to low minutes without any data loss. |
| Natural batching | Background thread accumulates entries, amortizing HTTP overhead. |
| Bounded memory | Fixed ring size. Memory footprint is predictable regardless of failure duration. |

### Cons

| Con | Detail at 250k RPS |
|---|---|
| Data loss on prolonged outages | 50 MB buffer at 5,000 logs/sec overflows in ~10 seconds. A 5-minute outage loses ~95% of logs during that window. |
| Data loss on application crash | Entire buffer is in-process memory. Gone on crash/restart. |
| Memory pressure | 50 MB per instance. Across 100 instances on a host, that is 5 GB dedicated to log buffering. |
| Silent data loss | Ring buffer overwrites oldest entries without notification unless you add drop counters. |
| Backoff tuning is fragile | Too aggressive: saturates recovering server. Too conservative: buffer fills while server is already healthy. |
| No crash recovery | After restart, no way to recover what was in the buffer. Starts fresh with empty ring. |

### Verdict

**Best for brief network blips (1-30 seconds).** Not suitable for multi-minute outages or when data loss on crash is unacceptable.

---

## Pattern 2: Local Disk WAL (Write-Ahead Log) + Background Shipper

Logs are appended to a local write-ahead log file first (durable), then a background thread reads from the WAL and ships to the POST endpoint. The WAL is the durability guarantee.

### Architecture

```mermaid
graph LR
    subgraph "Application Process"
        LOG["log.Info(msg)"] --> WAL["Append to WAL<br/>/var/log/app-wal/"]
        WAL --> CP["Checkpoint File<br/>(byte offset of last<br/>shipped entry)"]
    end

    subgraph "Background Shipper"
        CP --> SHIP["Read from checkpoint<br/>Batch 5,000-10,000 entries"]
        SHIP -->|"Batch POST"| EP[POST /logs]
        EP -->|"Success"| ADV["Advance checkpoint"]
        EP -->|"Failure"| PAUSE["Pause + retry<br/>WAL keeps growing"]
        ADV --> SHIP
    end

    subgraph "WAL Segments"
        S1["segment-001.wal<br/>100 MB"]
        S2["segment-002.wal<br/>100 MB"]
        S3["segment-003.wal<br/>in progress"]
    end

    WAL --> S1 & S2 & S3

    style WAL fill:#4a90d9,color:#fff
    style CP fill:#f5a623,color:#000
```

### How It Works at 250k RPS

```mermaid
graph TD
    subgraph "Per Service Instance"
        A["Log call → append to WAL<br/>~50-100μs (sequential write)"]
        B["Disk write rate:<br/>5,000 logs/sec × 1 KB = 5 MB/sec"]
        C["WAL segments:<br/>100 MB each, rotate on full"]
        D["Max WAL size: 5 GB<br/>= ~16 minutes of buffer"]
    end

    subgraph "Shipper Behavior"
        E["Normal: ships as fast as produced<br/>WAL stays small (~1 segment)"]
        F["Outage: WAL grows at 5 MB/sec<br/>5 GB cap reached in ~16 min"]
        G["Recovery: ships at 2x rate<br/>drains backlog + live traffic"]
    end

    A --> B --> C --> D
    E --> F --> G

    style D fill:#f5a623,color:#000
    style G fill:#50c878,color:#000
```

- Each instance appends to a local file: 5,000 logs/sec x 1 KB = 5 MB/sec disk write
- WAL is segmented (100 MB per segment file, rotate when full)
- Shipper tracks position via checkpoint file (byte offset of last successfully shipped entry)
- On failure, shipper stops advancing — WAL keeps growing
- On recovery, shipper catches up from checkpoint
- Configurable max WAL size (e.g., 5 GB = ~16 minutes of buffering at 5,000 logs/sec)

### Pros

| Pro | Detail |
|---|---|
| Survives application crashes | WAL is on disk. Shipper resumes from checkpoint after restart. Zero data loss on crash. |
| Survives prolonged outages | 5 GB WAL holds ~16 minutes of data. Configurable larger for longer outages. |
| Zero data loss within WAL capacity | Every log that hits the WAL is eventually shipped (unless WAL overflows). |
| Fast log calls | Append to local file is ~50-100μs. Sequential writes are SSD-friendly. |
| Aggressive batching from WAL | Shipper reads 10,000 entries at once from disk. Efficient bulk POST. |
| Crash recovery is built in | Checkpoint file tells shipper exactly where to resume. No duplicate guessing. |

### Cons

| Con | Detail at 250k RPS |
|---|---|
| Disk I/O on every log call | 5 MB/sec sequential write per instance. On hosts with 20 instances, that is 100 MB/sec of disk I/O dedicated to WAL writes. |
| fsync trade-off | fsync per write: durable but costs ~1-5ms per log call. fsync per batch (every 1,000 writes): faster but risks losing up to 1,000 entries on power loss. Must choose. |
| Disk space management | WAL must be bounded. When it hits max size, oldest segments are deleted — same data loss as ring buffer, just with a much larger window. |
| Implementation complexity | File rotation, checkpoint tracking, crash recovery, segment cleanup, file locking. ~500-1,000 lines of robust code. |
| Essentially reinventing the sidecar | At this point, you're building Filebeat inside your application. A dedicated agent does this better with years of battle-testing. |
| Disk failure = log failure | If the local disk has issues (full, slow, failing), both the application and its log buffering are affected simultaneously. |

### Verdict

**Best for multi-minute outages where zero data loss matters.** Trade-off is disk I/O and implementation complexity. At this complexity level, consider whether an external agent (Filebeat/Vector) does this better.

---

## Pattern 3: Circuit Breaker + Batch Accumulator

Uses the circuit breaker pattern to detect POST endpoint health. When the circuit is open (endpoint down), logs accumulate in a buffer. When it closes (recovery), the buffer drains in a controlled manner.

### Architecture

```mermaid
stateDiagram-v2
    [*] --> CLOSED

    CLOSED --> OPEN : Failure threshold exceeded<br/>(3 consecutive failures OR<br/>50% failure rate in 10s window)
    OPEN --> HALF_OPEN : Cooldown timer expires<br/>(30 seconds)
    HALF_OPEN --> CLOSED : Probe request succeeds<br/>→ Drain accumulated buffer
    HALF_OPEN --> OPEN : Probe request fails<br/>→ Reset cooldown timer

    state CLOSED {
        [*] --> SendBatches
        SendBatches --> SendBatches : Batch logs normally<br/>(500 entries per POST)
    }

    state OPEN {
        [*] --> Accumulate
        Accumulate --> Accumulate : Buffer all logs<br/>No POST attempts<br/>(protect downed server)
    }

    state HALF_OPEN {
        [*] --> Probe
        Probe --> Probe : Send 1 test batch<br/>Evaluate health
    }
```

### How It Works at 250k RPS

```mermaid
graph TD
    subgraph "Normal Operation (CLOSED)"
        N1["Logs arrive: 5,000/sec"]
        N2["Batch accumulator: 500 logs"]
        N3["POST every 100ms"]
        N4["10 POST calls/sec per instance"]
        N1 --> N2 --> N3 --> N4
    end

    subgraph "During Outage (OPEN)"
        O1["3 failures detected"]
        O2["Circuit OPENS"]
        O3["All POSTs stop immediately"]
        O4["Logs accumulate in memory"]
        O5["No hammering the dead server"]
        O1 --> O2 --> O3 --> O4 --> O5
    end

    subgraph "Recovery (HALF-OPEN → CLOSED)"
        R1["30s cooldown expires"]
        R2["Send 1 probe batch"]
        R3["Probe succeeds → CLOSE circuit"]
        R4["Drain buffer at 2x rate"]
        R5["Catch up without overwhelming server"]
        R1 --> R2 --> R3 --> R4 --> R5
    end

    style O3 fill:#ff6b6b,color:#fff
    style R3 fill:#50c878,color:#000
```

### Pros

| Pro | Detail |
|---|---|
| Protects recovering server | Unlike retry-based patterns, circuit breaker stops ALL traffic to a downed endpoint. No thundering herd. |
| Fast failure detection | Application knows within seconds that the endpoint is down. Can emit metrics, log locally, or take alternative action. |
| Controlled drain on recovery | Doesn't flood the server with buffered logs on recovery. Drains at configurable rate (e.g., 2x normal) to let the server warm up. |
| Well-understood pattern | Standard pattern with library support in every language (Hystrix, resilience4j, gobreaker, polly). |
| Composable | Pairs naturally with Pattern 1 or 2. Circuit breaker controls *when* to send. Buffer controls *what* to store. |
| Prevents cascade failures | Without circuit breaker, 500 instances retrying against a struggling server can prevent it from recovering. Circuit breaker gives the server breathing room. |

### Cons

| Con | Detail at 250k RPS |
|---|---|
| Incomplete solution alone | Circuit breaker only decides when to stop/start sending. Still needs a buffer strategy (memory or disk) for the accumulation period. On its own, logs are simply dropped while the circuit is open. |
| Tuning is sensitive | Failure threshold too low: opens on a single timeout (false positive). Too high: hammers a struggling server before opening. Half-open interval too short: probes overwhelm recovering server. Too long: delays recovery detection. |
| Thundering herd on close | If 500 instances all detect recovery simultaneously, they all drain buffers at once. Need jitter and rate limiting on drain. |
| Doesn't help with crashes | Accumulated buffer is in-memory (unless paired with WAL). |
| Per-dependency state | Multiple log endpoints or failover targets each need their own circuit. Adds state management complexity. |
| False positives | A single slow network hop can trip the circuit for a healthy server. Need to distinguish between "server down" and "network slow." |

### Verdict

**Best for protecting downstream services during outages.** Not a standalone solution — must be combined with Pattern 1 or 2 for buffering.

---

## Pattern 4: Dual-Path with Failover Sink

Client writes to the primary endpoint (POST). On failure, it automatically fails over to a secondary sink. A reconciliation process later drains the secondary sink back into the primary pipeline.

### Architecture

```mermaid
graph TD
    LOG["log.Info(msg)"] --> ROUTER["Sink Router"]

    ROUTER -->|"Primary (healthy)"| PRIMARY["POST /logs<br/>(normal path)"]
    ROUTER -->|"Failover (primary down)"| SECONDARY["Secondary Sink"]

    subgraph "Failover Sink Options"
        OPT_A["Option A: Local File<br/>/var/log/failover/"]
        OPT_B["Option B: Secondary Endpoint<br/>(different region/LB)"]
        OPT_C["Option C: Local UDP Collector<br/>(localhost:9999)"]
    end

    SECONDARY --> OPT_A & OPT_B & OPT_C

    subgraph "Reconciliation (when primary recovers)"
        RECON["Drain failover sink<br/>→ POST to primary<br/>at controlled rate"]
        CLEANUP["Delete drained data<br/>from failover sink"]
        RECON --> CLEANUP
    end

    OPT_A & OPT_B & OPT_C -.->|"Primary recovers"| RECON

    style PRIMARY fill:#50c878,color:#000
    style SECONDARY fill:#f5a623,color:#000
    style RECON fill:#4a90d9,color:#fff
```

### How It Works at 250k RPS

```mermaid
sequenceDiagram
    participant App as Service Instance
    participant R as Sink Router
    participant P as Primary POST /logs
    participant F as Failover Sink (Local File)
    participant RC as Reconciliation

    Note over App,P: Normal Operation
    App->>R: log.Info(msg)
    R->>P: POST /logs (batch)
    P-->>R: 202 OK

    Note over App,F: Primary Goes Down
    App->>R: log.Info(msg)
    R->>P: POST /logs (batch)
    P-->>R: 503 / timeout
    R->>R: 3 failures → switch to failover
    R->>F: Append to local file

    Note over App,F: During Outage (~5 min at 5k/sec)
    App->>R: log.Info(msg)
    R->>F: Append to file<br/>(5,000/sec × 300s = 1.5M entries = 1.5 GB)

    Note over RC,P: Primary Recovers
    R->>P: Probe succeeds → switch back to primary
    RC->>F: Read failover file
    RC->>P: POST (batch, rate-limited)<br/>1.5M entries at 2x rate
    RC->>F: Delete drained files
```

### Failover Sink Options Compared

| Sink | Durability | Latency | Complexity | Best For |
|---|---|---|---|---|
| Local file | Survives crashes | ~50-100μs | Medium (file mgmt) | Most scenarios |
| Secondary endpoint | Survives host failure | ~2-5ms | High (two infra paths) | Regional failover |
| Local UDP collector | No durability | ~10-20μs | Low | Ultra-low latency needs |

### Pros

| Pro | Detail |
|---|---|
| Near-zero data loss | If failover sink is disk-based, survives both outages and application crashes. |
| Application never blocks | Always has somewhere to write — primary or failover. Log call never fails from the application's perspective. |
| Geographic resilience | If failover is a secondary endpoint in another region, survives regional outages entirely. |
| Clean separation | Primary path stays simple and fast. Failover logic is isolated. Easy to reason about each independently. |
| Graceful degradation | System degrades from "logs in pipeline" to "logs on local disk" rather than "logs dropped." Operator knows exactly where to look. |
| Predictable failover behavior | Unlike retry/backoff, the switchover is explicit. Easy to monitor: "failover sink active" is a clear alert. |

### Cons

| Con | Detail at 250k RPS |
|---|---|
| Reconciliation complexity | Draining failover back into primary must handle: ordering (failover logs are out-of-order relative to primary), deduplication (some logs may have reached both paths), rate limiting (don't overwhelm primary with replay + live traffic). |
| Two code paths | Primary POST logic and failover write logic both need testing, monitoring, and alerting. Bugs hide in the failover path because it's rarely exercised. |
| Dual-write risk | During transition between primary and failover (and back), there is a window where logs might go to both sinks or neither. Need atomic switchover logic. |
| Failover sink capacity | 1-hour outage at 5,000 logs/sec = 5,000 x 3,600 x 1 KB = 18 GB per instance. Must ensure local disk can handle this across all instances on the host. |
| Query blind spot | Logs in the failover sink are not yet in MySQL and not yet queryable via GET. During an outage, query results are incomplete. Need alerting on failover sink depth. |
| Testing burden | Failover path is the path you need most and test least. Must actively exercise it (chaos engineering / game days) to ensure it works when needed. |

### Verdict

**Most resilient pattern.** Best for systems where data loss is unacceptable and you can invest in reconciliation logic. Also the most complex — ~1,500 lines of robust implementation.

---

## Head-to-Head Comparison at 250k RPS

### Data Loss Scenarios

```mermaid
graph TB
    subgraph "10-Second Outage"
        A1["Ring Buffer: No loss ✓"]
        A2["Disk WAL: No loss ✓"]
        A3["Circuit Breaker: No loss ✓<br/>(if buffered)"]
        A4["Dual-Path: No loss ✓"]
    end

    subgraph "5-Minute Outage"
        B1["Ring Buffer: ~95% loss ✗"]
        B2["Disk WAL: No loss ✓"]
        B3["Circuit Breaker: OOM risk ✗"]
        B4["Dual-Path: No loss ✓"]
    end

    subgraph "Application Crash"
        C1["Ring Buffer: All buffer lost ✗"]
        C2["Disk WAL: No loss ✓"]
        C3["Circuit Breaker: All buffer lost ✗"]
        C4["Dual-Path: No loss ✓<br/>(disk sink)"]
    end

    style A1 fill:#50c878,color:#000
    style A2 fill:#50c878,color:#000
    style A3 fill:#50c878,color:#000
    style A4 fill:#50c878,color:#000
    style B1 fill:#ff6b6b,color:#fff
    style B2 fill:#50c878,color:#000
    style B3 fill:#ff6b6b,color:#fff
    style B4 fill:#50c878,color:#000
    style C1 fill:#ff6b6b,color:#fff
    style C2 fill:#50c878,color:#000
    style C3 fill:#ff6b6b,color:#fff
    style C4 fill:#50c878,color:#000
```

### Quantitative Comparison

| Factor | Ring Buffer | Disk WAL | Circuit Breaker | Dual-Path |
|---|---|---|---|---|
| Data loss on 10s outage | None | None | None (if buffered) | None |
| Data loss on 5-min outage | ~95% of window | None (within WAL cap) | Depends on buffer | None |
| Data loss on app crash | **All buffered data** | None | **All buffered data** | None (disk sink) |
| Implementation complexity | Low (~200 LOC) | Medium (~800 LOC) | Low (~100 LOC + library) | High (~1500 LOC) |
| Disk I/O impact | None | 5 MB/sec per instance | None | 5 MB/sec during failover |
| Memory overhead | 50 MB fixed | Minimal | Variable (grows during outage) | Minimal |
| Protects recovering server | No (retry storms) | No | **Yes** | Partial (reconciliation rate) |
| Survives prolonged outage | No | Yes (within disk cap) | No (memory OOM) | **Yes** |

---

## Recommended Combination

These patterns are **not mutually exclusive**. The strongest client layers them together:

```mermaid
graph TD
    LOG["log.Info(msg)"] --> CB["Layer 1: Circuit Breaker<br/>Controls WHEN to send<br/>(detects endpoint health)"]

    CB -->|"CLOSED<br/>(healthy)"| BATCH["Layer 2: Batch Accumulator<br/>Controls HOW to send<br/>(500-1000 entries per POST)"]

    CB -->|"OPEN<br/>(unhealthy)"| WAL["Layer 3: Disk WAL<br/>Controls WHERE to buffer<br/>(survives crashes + outages)"]

    BATCH -->|"Batch POST"| EP["POST /logs"]
    WAL -->|"On recovery<br/>(circuit CLOSED)"| DRAIN["Drain WAL at 2x rate<br/>Merge with live traffic"]
    DRAIN --> EP

    style CB fill:#f5a623,color:#000
    style BATCH fill:#4a90d9,color:#fff
    style WAL fill:#7b68ee,color:#fff
    style EP fill:#50c878,color:#000
```

| Layer | Role | Handles |
|---|---|---|
| **Circuit Breaker** | Controls *when* to send | Prevents thundering herd, detects recovery |
| **Batch Accumulator** | Controls *how* to send | Reduces HTTP overhead, efficient bulk POST |
| **Disk WAL** | Controls *where* to buffer | Survives crashes, prolonged outages, bounded disk |

### The Convergence Observation

> Building a robust "smart client" with all three layers (circuit breaker + batching + disk WAL) produces **~1,500 lines of code that does exactly what a sidecar agent already does.** Filebeat, Vector, and Fluentd implement all of these patterns with years of production hardening.
>
> The question becomes: do you embed this complexity in every microservice (N implementations, N languages, N maintenance burdens), or externalize it into one well-tested agent?

```mermaid
graph LR
    subgraph "Smart Client (embedded)"
        SC["Circuit Breaker<br/>+ Batch Accumulator<br/>+ Disk WAL<br/>+ Retry Logic<br/>+ Checkpoint Recovery<br/>~1500 LOC per language"]
    end

    subgraph "Sidecar Agent (externalized)"
        SA["Filebeat / Vector<br/>All of the above<br/>+ battle-tested<br/>+ 0 LOC in your services"]
    end

    SC -.->|"Same functionality<br/>different ownership model"| SA

    style SC fill:#f5a623,color:#000
    style SA fill:#50c878,color:#000
```

**If you have the organizational ability to deploy a sidecar agent, that is strictly better than building smart clients.** Smart clients make sense when you cannot control the deployment environment (e.g., third-party services sending you logs, edge devices, mobile clients).
