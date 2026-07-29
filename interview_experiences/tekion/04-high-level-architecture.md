# 04 — High-Level Architecture

[← APIs and Data Model](03-api-and-data-model.md) · [Index](README.md) · [Next: Execution Semantics →](05-execution-semantics.md)

---

## Component architecture

```mermaid
flowchart LR
    subgraph Sources["Trigger Sources"]
        WH[Webhooks / HTTP]
        SCH[Scheduler / Cron]
        POLL[Pollers / Connector-based]
    end

    WH --> ING[Ingestion Service<br/>authN · dedupe · append]
    SCH --> ING
    POLL --> ING

    ING --> DEDUP[(Idempotency KV<br/>TTL 24h)]
    ING --> LOG[(Durable Event Log<br/>partitioned by execution_id)]

    LOG --> ORCH["Orchestrator<br/><b>state machine only</b><br/>NEVER does external I/O"]

    ORCH --> STATE[(Execution State Store<br/>partitioned by execution_id)]
    ORCH --> TASKQ[(Task Queues<br/>sharded by tenant class)]
    ORCH --> TIMER[(Durable Timer Wheel)]
    TIMER --> ORCH

    TASKQ --> WRK[Step Workers<br/>async I/O model]
    WRK --> SBX[Transform Sandbox<br/>expression lang / isolate]
    WRK --> CONN[Connector Runtime<br/>versioned artifacts]
    CONN --> EGRESS["Egress Proxy<br/>policy · credentials · audit<br/>circuit breakers · stable IPs"]
    EGRESS --> EXT[(External Systems<br/>SFDC · SAP · S3 · SFTP · REST)]

    WRK --> BLOB[(Payload Store<br/>content-addressed SHA-256)]
    WRK -->|step outcome| ORCH

    ORCH --> TRACE[Trace Pipeline]
    TRACE --> OLAP[(Console / Analytics Store<br/>columnar)]
    OLAP --> CONSOLE[Customer Console]

    subgraph ControlPlane["Control Plane"]
        DESIGN[Designer / Public API / CLI]
        REG[(Flow + Version Registry)]
        SEC[(Secret Store<br/>per-tenant KMS keys)]
    end

    DESIGN --> REG
    REG -.deployed config.-> ORCH
    SEC -.short-lived creds.-> EGRESS

    AGENT[Self-hosted Runtime Agent<br/>customer network] -.outbound only.-> ORCH
    AGENT --> ONPREM[(On-prem systems<br/>no public endpoint)]

    style LOG fill:#1f6feb,color:#fff
    style STATE fill:#1f6feb,color:#fff
    style BLOB fill:#1f6feb,color:#fff
    style REG fill:#1f6feb,color:#fff
    style SEC fill:#8957e5,color:#fff
    style OLAP fill:#6e7681,color:#fff
    style EGRESS fill:#9e6a03,color:#fff
```

**Legend** — Blue: source of truth · Purple: secrets · Orange: security choke point · Grey: derived/rebuildable

---

## Source of truth vs. derived

This boundary defines what a catastrophic restore actually needs to recover.

```mermaid
flowchart TB
    subgraph SOT["Source of truth — must be recovered"]
        S1[(Durable Event Log<br/>accepted events)]
        S2[(Execution State Store<br/>state machine position)]
        S3[(Payload Blob Store)]
        S4[(Flow Version Registry)]
        S5[(Secret Store)]
    end

    subgraph DER["Derived — rebuildable from the trace pipeline"]
        D1[(Console / Analytics Store)]
        D2[(Search indexes)]
        D3[Dashboards]
        D4[Metrics rollups]
    end

    SOT -->|trace pipeline| DER

    style S1 fill:#1f6feb,color:#fff
    style S2 fill:#1f6feb,color:#fff
    style S3 fill:#1f6feb,color:#fff
    style S4 fill:#1f6feb,color:#fff
    style S5 fill:#8957e5,color:#fff
```

---

## The three paths

### Write path — minimal dependencies by design

```text
Trigger → Ingestion → [authN · dedupe · append to log] → 202
```

Three operations. Nothing else. The log is the system of record for *"we accepted this."*

### Execution path — orchestrator decides, worker acts

```mermaid
sequenceDiagram
    autonumber
    participant L as Durable Log
    participant O as Orchestrator
    participant S as State Store
    participant Q as Task Queue
    participant W as Step Worker
    participant E as Egress Proxy
    participant X as External System
    participant B as Blob Store

    L->>O: consume accepted execution
    O->>S: create execution state (step 0)
    O->>Q: enqueue task(step 1, payload_ref)

    Q->>W: dequeue (weighted fair scheduling)
    W->>B: fetch payload by sha256 (AZ-local)
    W->>E: connector call (credential handle, not secret)
    E->>E: policy check · SSRF guard · circuit breaker
    E->>E: inject credential from Secret Store
    E->>X: HTTP / SOAP / SQL / SFTP
    X-->>E: response
    E-->>W: response + timing breakdown
    W->>B: put result payload (content-addressed)
    W-->>O: step outcome + payload_ref

    O->>S: advance state machine (step 1 → step 2)
    O->>Q: enqueue task(step 2, ...)

    Note over O,S: Orchestrator NEVER touched X.<br/>Slow third parties consume elastic WORKER capacity,<br/>not stateful ORCHESTRATOR capacity.
```

### Async / derived path

```text
Orchestrator → Trace Pipeline → Analytics Store → Console
                              → Metrics / SLO computation
                              → Per-tenant health view (a product feature)
```

---

## Why the orchestrator does no I/O

```mermaid
flowchart TB
    subgraph Merged["✗ Merged: orchestrator performs connector calls"]
        M1[Flow A calls a hung SFTP server<br/>10-minute timeout]
        M1 --> M2[Occupies an orchestrator thread]
        M2 --> M3[That thread is ALSO responsible<br/>for advancing other executions]
        M3 --> M4["One slow third party degrades<br/>the correctness/durability tier"]
    end

    subgraph Split["✓ Split: orchestrator decides, worker acts"]
        P1[Flow A calls a hung SFTP server]
        P1 --> P2[Occupies a WORKER slot]
        P2 --> P3["Workers are stateless, cheap, elastic<br/>Scale them out; shed them freely"]
        P3 --> P4["Orchestrator keeps advancing<br/>every other execution"]
    end

    style M4 fill:#8b2c2c,color:#fff
    style P4 fill:#1a7f37,color:#fff
```

**Division of responsibility:**

| Component | Job | Failure tolerance |
|---|---|---|
| Orchestrator | Durability and correctness of state transitions | Low — stateful, harder to scale |
| Worker | Dealing with the hostile outside world | High — stateless, cheap, elastic |

---

## Why both a durable log *and* a state store

A pure event-sourced design on the log alone is legitimate. It was rejected for **access pattern** reasons.

```mermaid
flowchart TB
    Q["'What is the current state of execution X?'<br/>Asked constantly: every worker callback,<br/>every console page load, every transition"]

    Q --> A["Log-only:<br/>replay the log partition"]
    Q --> B["State store:<br/>point lookup"]

    A --> A1["✗ Expensive per read<br/>✗ Gets worse as executions get longer<br/>✗ A 3-day 'wait for approval' flow<br/>would replay an enormous span"]
    B --> B1["✓ O(1) point read<br/>✗ Two things that can disagree"]

    B1 --> R["Accept the cost:<br/>a <b>reconciler</b> scans for executions<br/>in the log with no state record.<br/>Bounded, testable background job."]

    R --> F["Log = durable INTAKE + recovery<br/>State store = materialised CURRENT state<br/>Log covers the window between the last<br/>state checkpoint and a failure"]

    style A1 fill:#8b2c2c,color:#fff
    style F fill:#1f6feb,color:#fff
```

> Better to own one bounded reconciler job than to make every state read a log replay.

---

## Execution state machine

```mermaid
stateDiagram-v2
    [*] --> ACCEPTED : appended to durable log (202 returned)
    ACCEPTED --> PENDING : orchestrator picks up
    PENDING --> RUNNING : first step dispatched

    RUNNING --> RUNNING : step succeeds, advance
    RUNNING --> WAITING : wait step / timer / external signal
    WAITING --> RUNNING : timer fires or signal received
    WAITING --> PARKED : destination confirmed down

    PARKED --> RUNNING : probe detects recovery
    RUNNING --> RETRYING : retryable failure
    RETRYING --> RUNNING : backoff elapsed (jittered)
    RETRYING --> DEAD_LETTER : retry budget exhausted

    RUNNING --> RECOVERY_AMBIGUOUS : state store failover<br/>within replication-lag window
    RECOVERY_AMBIGUOUS --> RUNNING : step is idempotent → re-execute
    RECOVERY_AMBIGUOUS --> DEAD_LETTER : non-idempotent, cannot verify

    RUNNING --> SUCCEEDED : terminal step complete
    RUNNING --> FAILED : terminal, non-retryable
    RUNNING --> CANCELLED : operator or customer cancel

    DEAD_LETTER --> [*] : inspectable + replayable
    SUCCEEDED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]

    note right of WAITING
        ZERO COMPUTE while waiting.
        Execution leaves hot memory entirely.
    end note

    note right of DEAD_LETTER
        A terminal state — the durability
        promise is SATISFIED, not violated.
    end note
```

> **Key insight:** `DEAD_LETTER` is a *terminal state*, not a failure of the durability promise.
> The promise is "reaches a terminal state," not "always succeeds."
