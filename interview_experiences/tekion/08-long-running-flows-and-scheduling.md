# 08 — Long-Running Flows and Scheduling

[← Connectors and Egress](07-connectors-and-egress.md) · [Index](README.md) · [Next: Resilience →](09-resilience-and-failure-modes.md)

---

## The requirement

> A flow has a step that waits **three days** for human approval.

**Critical property: a waiting execution must consume zero compute.**
If a paused flow holds a thread or a container, the cost model breaks — this is precisely where naive
workflow engines fail economically.

```mermaid
flowchart TB
    subgraph Naive["✗ A wait is a blocked call"]
        N1[Step: wait for approval] --> N2[Thread/container blocks<br/>for 3 days]
        N2 --> N3["Cost = 3 days of compute<br/>× every waiting execution.<br/>At scale this is unaffordable."]
    end

    subgraph Ours["✓ A wait is a state transition"]
        O1[Step: wait for approval] --> O2["Orchestrator writes state = WAITING<br/>+ wake condition"]
        O2 --> O3["Execution leaves hot memory <b>entirely</b>"]
        O3 --> O4["Cost = one durable row<br/>+ one timer entry"]
    end

    style N3 fill:#8b2c2c,color:#fff
    style O4 fill:#1a7f37,color:#fff
```

### Wake conditions

```mermaid
stateDiagram-v2
    RUNNING --> WAITING : wait step reached
    state WAITING {
        [*] --> Timer : wake at T
        [*] --> Signal : wake on callback URL hit
        [*] --> EventMatch : wake on matching event
    }
    Timer --> RUNNING : timer wheel fires
    Signal --> RUNNING : external POST received
    EventMatch --> RUNNING : predicate matched
    WAITING --> FAILED : wait deadline exceeded
```

---

## Hierarchical timer wheel

Timers are durable and bucketed by fire time, with **coarse buckets far out and fine buckets near-term** —
so we never scan three days of timers to find the next minute's work.

```mermaid
flowchart TB
    subgraph Wheel["Hierarchical timer wheel (durable)"]
        D["<b>Day buckets</b><br/>T+2d, T+3d, ...<br/>coarse"]
        H["<b>Hour buckets</b><br/>T+2h ... T+23h"]
        M["<b>Minute buckets</b><br/>T+1m ... T+59m"]
        S["<b>Second buckets</b><br/>next 60s — fine"]
    end

    D -->|cascade down<br/>as time approaches| H
    H -->|cascade| M
    M -->|cascade| S

    S --> SW[Sweeper]
    SW --> RQ[Re-enqueue due executions<br/>→ back to RUNNING]

    style S fill:#1f6feb,color:#fff
```

---

## Subtlety 1 — Thundering herds

> Everyone schedules cron at `0 * * * *`.

```mermaid
xychart-beta
    title "Cron fires per second around the top of the hour"
    x-axis ["-2s", "-1s", ":00", "+1s", "+2s", "+3s", "+30s", "+59s"]
    y-axis "Fires/sec (thousands)" 0 --> 200
    bar [1, 1, 180, 20, 5, 2, 1, 1]
```

**Mitigation — deterministic per-flow jitter derived from the flow ID:**

```mermaid
flowchart LR
    C["Cron: 0 * * * *"] --> J["offset = hash(flow_id) mod 60s<br/><b>deterministic</b> — same flow always<br/>fires at the same offset"]
    J --> S["Fires spread evenly<br/>across the minute"]
    S --> O["Customers needing exact timing<br/>opt out and pay for<br/>reserved capacity"]

    style S fill:#1a7f37,color:#fff
```

Determinism matters: a random offset each hour makes the schedule unpredictable to the customer and makes
debugging "why did this run at :37?" impossible.

---

## Subtlety 2 — Timer skew during outages

If the sweeper is down for ten minutes, **ten minutes of timers come due at once.**

```mermaid
sequenceDiagram
    autonumber
    participant W as Timer Wheel
    participant S as Sweeper
    participant O as Orchestrator

    Note over S: 💥 Sweeper down for 10 minutes
    Note over W: Timers accumulate in due buckets

    S->>S: recovers
    rect rgb(139, 44, 44)
    Note over S,O: ✗ Naive: dump everything at once<br/>→ instant 10x spike → secondary outage
    end

    rect rgb(26, 127, 55)
    Note over S,O: ✓ Rate-limited catch-up:<br/>drain the backlog at a bounded rate
    end

    S->>O: re-enqueue (bounded rate)
    Note over O: Each execution carries<br/>scheduled_at AND actual_fire_at
```

**Why carry both timestamps:**

```mermaid
flowchart TB
    T["Execution carries<br/>scheduled_at + actual_fire_at"]

    T --> V1["<b>Customer visibility</b><br/>'this run was 6 hours late'"]
    T --> V2["<b>Staleness policy</b><br/>flow can declare:<br/>if lateness > threshold, SKIP"]

    V2 --> R["<b>A daily report that runs 6 hours late<br/>is often WORSE than one that<br/>doesn't run at all.</b>"]

    style R fill:#1f6feb,color:#fff
```

---

## Parking: waiting applied to downstream outages

When a destination is confirmed down, executions move to `PARKED` — the same zero-compute mechanism.

```mermaid
sequenceDiagram
    autonumber
    participant E as Egress Proxy
    participant O as Orchestrator
    participant P as Probe
    participant X as Salesforce

    E->>E: Circuit breaker OPEN for<br/>(connection, salesforce.com)
    E-->>O: destination confirmed down

    O->>O: Move affected executions<br/>RUNNING → PARKED (zero compute)
    Note over O: 4,200 executions parked.<br/>No workers consumed.<br/>No retry storm generated.

    loop backoff with jitter
        P->>X: lightweight health probe
        X--xP: still down
    end

    P->>X: probe
    X-->>P: 200 OK
    P->>O: destination recovered
    O->>O: PARKED → RUNNING<br/>(rate-limited resume, jittered)
```

> **Customer-visible status:** *"Salesforce is unavailable; 4,200 of your executions are parked and will
> resume automatically."* That one feature deflects an enormous volume of support tickets — and it is cheap,
> because the data already flows through the trace pipeline.

---

## Scheduling components summary

| Component | Responsibility | Key risk | Mitigation |
|---|---|---|---|
| Timer wheel | Durable, bucketed wake times | Scanning cost at long horizons | Hierarchical buckets with cascade |
| Sweeper | Fire due timers | Backlog dump after downtime | Rate-limited catch-up |
| Cron planner | Translate schedules into timers | Thundering herd at round times | Deterministic per-flow jitter |
| Signal receiver | External wake (callback / event) | Unauthenticated wake calls | Signed, single-use callback tokens |
| Parking prober | Detect destination recovery | Probe storm on recovery | Jittered, rate-limited resume |
