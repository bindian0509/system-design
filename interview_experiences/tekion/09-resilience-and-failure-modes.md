# 09 — Resilience and Failure Modes

[← Long-Running Flows](08-long-running-flows-and-scheduling.md) · [Index](README.md) · [Next: Cost and Maintainability →](10-cost-and-maintainability.md)

---

## Failure catalogue

```mermaid
flowchart TB
    F((Failure<br/>modes))

    F --> A["<b>A. State store primary fails</b><br/>→ duplicate side effects on recovery"]
    F --> B["<b>B. Poison record</b><br/>→ log partition halted"]
    F --> C["<b>C. Availability zone loss</b><br/>→ capacity, not correctness"]
    F --> D["<b>D. Downstream third party down</b><br/>→ THE most likely real incident"]
    F --> E["<b>E. Retry storm on recovery</b><br/>→ second outage"]
    F --> G["<b>F. Sandbox escape</b><br/>→ existential (see Security)"]

    style D fill:#9e6a03,color:#fff
    style G fill:#8b2c2c,color:#fff
```

---

## A — Execution state store primary fails

```mermaid
sequenceDiagram
    autonumber
    participant I as Ingestion
    participant L as Durable Log
    participant O as Orchestrator
    participant S as State Store
    participant W as Worker
    participant X as External

    Note over S: 💥 Primary fails

    rect rgb(26, 127, 55)
    Note over I,L: Ingestion does NOT touch the state store.<br/>WE KEEP ACCEPTING WORK.<br/>The durability boundary HOLDS.
    end

    O->>S: write state transition
    S--xO: error
    O->>O: back off (do NOT spin)

    S->>S: automated failover to replica
    Note over S: ⚠️ Async replication may have lost<br/>the last few writes

    Note over O,X: DANGER: state says "step 3 dispatched" was<br/>rolled back, but the worker ALREADY executed it.<br/>Orchestrator would re-dispatch → duplicate side effect.
```

### Recovery: make the ambiguity explicit rather than implicit

```mermaid
flowchart TB
    FO[State store failover completes]
    FO --> W{Last transition inside the<br/>replication-lag window?}

    W -->|No| NORM[Resume normally]
    W -->|Yes| AMB["Mark RECOVERY_AMBIGUOUS"]

    AMB --> C{Idempotency class<br/>of the in-flight step}
    C -->|Class A idempotent| RE[Re-execute normally]
    C -->|Class B token + query| VER[Verify-before-retry]
    C -->|Class C non-idempotent| DL[DEAD_LETTER<br/>human decision]

    style AMB fill:#9e6a03,color:#fff
    style DL fill:#8b2c2c,color:#fff
```

> **"That's a lot of machinery for a rare event."**
>
> It isn't *new* machinery. It is the **same ambiguous-outcome path already required for network timeouts**,
> which happen constantly. Failover recovery just feeds into it. A path exercised daily is one we trust
> during an incident. Building a *separate* mechanism only for failover would not be worth it.

---

## B — Poison record halting a log partition

```mermaid
flowchart LR
    R["Malformed record"] --> O1[Orchestrator reads]
    O1 --> CR[💥 crash]
    CR --> RS[restart]
    RS --> O1

    CR -.->|offset never advances| BLK["<b>EVERY execution in that<br/>partition is blocked.</b><br/>One bad record halts<br/>a slice of the platform."]

    style BLK fill:#8b2c2c,color:#fff
```

### Mitigations

```mermaid
flowchart TB
    M1["<b>Per-record attempt counting</b><br/>tracked OUTSIDE the crashing process.<br/>After N crashes attributable to a record:<br/>quarantine, advance, alert.<br/><i>Availability of the many beats<br/>processing of the one.</i>"]
    M2["<b>Crash-safe deserialization</b><br/>Parsing untrusted input is the<br/>highest-risk operation — isolate it so a<br/>parse failure is a CAUGHT ERROR,<br/>not a process abort."]
    M3["<b>Blast radius via partitioning</b><br/>Log partitioned by execution_id ⇒<br/>a poison record blocks ONE partition.<br/>Partitioning is a RESILIENCE mechanism,<br/>not just a throughput one."]
    M4["<b>Schema validation at ingestion</b><br/>Reject malformed data at the boundary<br/>where rejection is cheap and the<br/>caller can react."]

    style M3 fill:#1f6feb,color:#fff
```

---

## C — Availability zone loss

```mermaid
flowchart TB
    subgraph Correctness["Correctness — solved"]
        C1["Log + state store replicate<br/>across AZs with quorum writes"]
        C1 --> C2["AZ loss = leader election,<br/>not data loss"]
    end

    subgraph Capacity["Capacity — the SUBTLE failure"]
        P1["Stateless tiers spread across ≥3 AZs"]
        P1 --> P2["Losing 1 AZ removes ~1/3 of<br/>worker capacity while retaining<br/><b>100% of traffic</b>"]
        P2 --> P3["If sized for exactly 3 AZs at peak,<br/>we now shed load"]
    end

    P3 --> R1["<b>Headroom:</b> run at ≤66% utilisation.<br/>Easier to justify on the 99.99% INGESTION tier<br/>than on the worker tier, where a shortfall<br/>only means slower scheduling."]
    P3 --> R2["<b>Prioritised shedding:</b><br/>preserve sync API flows + premium tiers,<br/>defer batch flows"]
    P3 --> R3["<b>Pre-warmed capacity</b> in surviving AZs —<br/>scaling from zero during an incident is<br/>exactly when cloud capacity is most contended"]

    style P2 fill:#9e6a03,color:#fff
```

---

## D — Downstream third party down (the most likely real incident)

> Salesforce is down for two hours. A thousand tenants depend on it.

```mermaid
flowchart TB
    subgraph Unprotected["✗ Without protection"]
        U1[1,000s of flows call SFDC]
        U1 --> U2[Every call hangs to its timeout]
        U2 --> U3[Workers fill with blocked calls]
        U3 --> U4[Retry logic AMPLIFIES load]
        U4 --> U5["Flows with NOTHING to do with SFDC<br/>can't get worker capacity"]
        U5 --> U6["<b>The downstream outage<br/>becomes OUR outage.</b>"]
    end

    style U6 fill:#8b2c2c,color:#fff
```

### Protections

```mermaid
flowchart TB
    P1["<b>Circuit breaker</b><br/>per (connection, destination), at egress.<br/>Fail fast instead of consuming a worker<br/>for 30s per call."]
    P2["<b>Bulkheads</b><br/>Cap the fraction of worker capacity any<br/>single destination can occupy.<br/>SFDC down consumes ≤ X% of the fleet."]
    P3["<b>Exponential backoff + JITTER</b><br/>Without jitter, every tenant's retries<br/>synchronise and hammer SFDC the instant<br/>it recovers — knocking it back down."]
    P4["<b>Automatic parking</b><br/>Confirmed-down destination ⇒ executions<br/>move to WAITING with probe-based wake.<br/><b>Zero compute while waiting.</b>"]
    P5["<b>Customer-visible status</b><br/>'Salesforce is unavailable; 4,200 of your<br/>executions are parked and will resume<br/>automatically.'"]

    P1 --> P2 --> P3 --> P4 --> P5

    P5 --> V["Deflects an enormous volume of<br/>support tickets. Cheap — the data<br/>already flows through the trace pipeline."]

    style P3 fill:#1f6feb,color:#fff
    style V fill:#1a7f37,color:#fff
```

**Jitter is not a nicety here** — it is the difference between a recovery and a second outage.

```mermaid
xychart-beta
    title "Requests to a recovering downstream: synchronised vs jittered retries"
    x-axis ["t+0s", "t+1s", "t+2s", "t+3s", "t+4s", "t+5s", "t+6s"]
    y-axis "Requests/sec (thousands)" 0 --> 100
    bar [95, 5, 2, 90, 3, 2, 85]
    line [12, 14, 13, 15, 14, 13, 14]
```

Bars: synchronised retries (repeatedly re-downs the target). Line: jittered retries (smooth recovery).

---

## What breaks first at 10× scale

```mermaid
flowchart TB
    S["10× = 20B executions/day<br/>~11M steps/sec peak"]

    S --> B1["<b>1. Trace / observability pipeline</b><br/>160 TB/day of trace metadata.<br/>Observability data volume EXCEEDS<br/>business data volume — and it's the thing<br/>people forget to scale because it's 'just logs'.<br/><i>Expected to break before the engine.</i>"]
    S --> B2["<b>2. State store write rate</b><br/>Partitioning by execution_id scales, but the<br/>execution_by_flow index has HOT TIME BUCKETS."]
    S --> B3["<b>3. Idempotency KV</b><br/>10× writes, all with TTLs.<br/>Manageable — it mostly just costs money."]

    B1 --> F1["Fix: tail-based sampling for successes,<br/>keep everything for failures"]
    B2 --> F2["Fix: finer bucketing; move console queries<br/>ENTIRELY onto the derived analytics store"]

    style B1 fill:#8b2c2c,color:#fff
```

### At 100× — cell-based architecture

```mermaid
flowchart TB
    GCP["Global Control Plane<br/>tenant placement · routing · registry"]

    GCP --> C1
    GCP --> C2
    GCP --> C3

    subgraph C1["Cell 1 — full vertical slice"]
        L1[(Log)] --> O1[Orchestrator] --> W1[Workers]
        O1 --> S1[(State)]
    end
    subgraph C2["Cell 2"]
        L2[(Log)] --> O2[Orchestrator] --> W2[Workers]
        O2 --> S2[(State)]
    end
    subgraph C3["Cell 3"]
        L3[(Log)] --> O3[Orchestrator] --> W3[Workers]
        O3 --> S3[(State)]
    end

    C1 -.-> B["<b>Benefits</b><br/>• Blast radius capped at one cell<br/>• Capacity planning is per-cell<br/>• Canary deploys cell-by-cell"]
    C3 -.-> Cst["<b>Costs</b><br/>• Global control plane for placement<br/>• Cross-cell routing<br/>• Operational overhead × cell count"]

    style GCP fill:#1f6feb,color:#fff
```

> **Do not build cells on day one.** The trigger is **not** a QPS number. It is:
> *a single incident routinely affecting a majority of tenants*, or
> *the state store partition count becoming operationally unmanageable.*

---

## Resilience mechanism inventory

| Mechanism | Where | Prevents |
|---|---|---|
| Timeouts (per-connector, configurable) | Egress | Unbounded worker occupancy |
| Bounded retries + exponential backoff + **jitter** | Worker / orchestrator | Retry storms, synchronised recovery hammering |
| Circuit breakers per (connection, destination) | Egress | Downstream outage cascading into ours |
| Bulkheads per destination | Worker pool | Fleet exhaustion by one third party |
| Load shedding with `429` + `Retry-After` | Ingestion | Unbounded queue growth, misleading PENDING |
| Admission control / burst credits | Ingestion | Backfill-driven starvation |
| Idempotency keys + dedup KV | Ingestion | Duplicate executions from webhook retries |
| Per-operation idempotency class | Retry engine | Duplicate business side effects |
| Dead-letter with ambiguity flag | Orchestrator | Silent data loss; silent duplication |
| Parking with probe-based wake | Orchestrator | Compute burn during downstream outages |
| Poison-record quarantine | Orchestrator | Partition-wide halt |
| Quorum replication across AZs | Log, state store | Data loss on AZ failure |
| Prioritised shedding + pre-warmed capacity | Worker fleet | Capacity shortfall during AZ loss |
| Reconciler (log ↔ state store) | Background job | Executions lost between tiers |
| Graceful degradation of the console | Read path | Data plane impact from console load |
