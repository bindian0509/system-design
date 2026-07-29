# 06 — Multi-Tenancy and Isolation

[← Execution Semantics](05-execution-semantics.md) · [Index](README.md) · [Next: Connectors and Egress →](07-connectors-and-egress.md)

---

## The scenario to design for

> One tenant starts a backfill and pushes **30% of total platform writes.**

Under a naive single-queue design: everyone's latency degrades, the scheduling SLO breaks platform-wide,
and we have a Sev1 caused by one customer doing something entirely legitimate.

**Backfills are normal. The design must assume them.**

```mermaid
flowchart TB
    subgraph Naive["✗ Single global FIFO queue"]
        T1[Tenant A: 10 tasks] --> GQ[(Global Queue)]
        T2[Tenant B: 5,000,000 tasks<br/>backfill] --> GQ
        T3[Tenant C: 20 tasks] --> GQ
        GQ --> W1[Workers drain FIFO]
        W1 --> BAD["Tenant A waits behind<br/>5M of Tenant B's tasks.<br/>Platform-wide SLO breach."]
    end

    style BAD fill:#8b2c2c,color:#fff
```

---

## Five layers of defence

```mermaid
flowchart TB
    L1["<b>Layer 1 — Queue sharding</b><br/>Tenants map to a BOUNDED SUBSET of shards.<br/>More shards than any tenant can saturate.<br/>Cell-based thinking, applied to the queue layer."]
    L2["<b>Layer 2 — Weighted fair scheduling</b><br/>Deficit round-robin across tenants with pending work,<br/>weighted by plan tier. NOT FIFO.<br/>◀ the single most important mechanism"]
    L3["<b>Layer 3 — Concurrency caps</b><br/>Per tenant (max in-flight steps)<br/>AND per connection (protect the third party)"]
    L4["<b>Layer 4 — Admission control</b><br/>When genuinely saturated, shed at ingestion<br/>with 429 + Retry-After."]
    L5["<b>Layer 5 — Burst credits</b><br/>Token bucket: large burst allowance,<br/>slow refill. Legitimate backfills complete fast;<br/>sustained abuse hits the sustained rate."]

    L1 --> L2 --> L3 --> L4 --> L5

    style L2 fill:#1f6feb,color:#fff
```

### Layer 1 — Queue sharding

```mermaid
flowchart LR
    TA[Tenant A] --> S1
    TA --> S2
    TB["Tenant B<br/>🔥 backfill"] --> S3
    TB --> S4
    TC[Tenant C] --> S5
    TC --> S6
    TD[Tenant D] --> S1
    TD --> S7

    subgraph Shards["Task queue shards"]
        S1[(shard 1)]
        S2[(shard 2)]
        S3[(shard 3 🔥)]
        S4[(shard 4 🔥)]
        S5[(shard 5)]
        S6[(shard 6)]
        S7[(shard 7)]
        S8[(shard 8)]
    end

    Shards --> R["A hot tenant degrades<br/>a SUBSET of shards,<br/>not the platform."]

    style S3 fill:#9e6a03,color:#fff
    style S4 fill:#9e6a03,color:#fff
```

### Layer 2 — Weighted deficit round-robin (the key mechanism)

```mermaid
flowchart TB
    W["Worker scheduling round"]
    W --> P[Poll tenants with pending work<br/>on my assigned shards]
    P --> D["Allocate each tenant a deficit quantum<br/>proportional to plan-tier weight"]
    D --> E[Execute up to the quantum,<br/>carry the remainder forward]
    E --> N[Next round]
    N --> P

    E --> OUT["<b>Effect:</b> a tenant with 1M queued tasks<br/>gets its FAIR SHARE per round —<br/>not all of it.<br/><br/>'one tenant starves everyone'<br/>becomes<br/>'one tenant's own work takes longer'"]

    style OUT fill:#1a7f37,color:#fff
```

**Why local, not globally coordinated:**

```mermaid
flowchart TB
    Q{How does a worker know<br/>global tenant state?}

    Q --> G["Globally coordinated scheduler"]
    Q --> L["Local decisions over<br/>assigned shards only"]

    G --> GR["✗ Needs CONSENSUS on the hot path<br/>✗ Trades a real availability risk<br/>for a marginal fairness gain"]

    L --> LR["✓ No coordination on the hot path<br/>✓ Uniform shard assignment ⇒<br/>local fairness ≈ global fairness"]

    LR --> BD["Breakdown case: a tenant skewed<br/>onto few shards"]
    BD --> FIX["Monitor per-shard tenant concentration.<br/>Rebalance as a SLOW background process —<br/><b>minutes, not milliseconds.</b>"]

    FIX --> PR["<b>Principle:</b> a slightly unfair scheduler<br/>that never goes down beats a perfectly<br/>fair one that needs consensus."]

    style G fill:#8b2c2c,color:#fff
    style PR fill:#1f6feb,color:#fff
```

### Layer 3 — Per-connection concurrency caps protect the *customer*

```mermaid
flowchart LR
    F[Tenant's flow<br/>5,000 parallel branches] --> C{Per-connection<br/>concurrency cap}
    C -->|capped at 20| SF[(Salesforce org)]
    C -.->|without the cap| BAN["❌ SFDC rate-limits or<br/>BANS the customer's org"]

    style BAN fill:#8b2c2c,color:#fff
```

> Respecting the downstream's limits is a **feature, not a restriction** — it protects the customer from
> themselves. The binding constraint is frequently the third party, not us.

### Layer 4 — Shed honestly rather than queue dishonestly

```mermaid
flowchart TB
    SAT[Platform genuinely saturated]

    SAT --> A["✗ Accept into an unbounded queue"]
    SAT --> B["✓ Shed at ingestion<br/>429 + Retry-After"]

    A --> AR["Queue grows → latency climbs →<br/>customer sees ACCEPTED executions<br/>sitting PENDING for an hour.<br/><br/>A fast honest failure has been converted<br/>into a slow confusing one."]
    B --> BR["Caller retries with backoff.<br/>The durability promise is preserved:<br/>we never accepted it."]

    style AR fill:#8b2c2c,color:#fff
    style BR fill:#1a7f37,color:#fff
```

### Layer 5 — Burst credits make the common case pleasant

```mermaid
xychart-beta
    title "Token bucket: large burst, slow refill"
    x-axis [t0, t1, t2, t3, t4, t5, t6, t7]
    y-axis "Available tokens" 0 --> 100
    line [100, 100, 20, 5, 15, 30, 45, 60]
```

A legitimate backfill drains the burst and completes fast. Sustained abuse hits the slow refill rate.
A hard cap alone would make backfills impossible; a pure rate limit alone would make them painfully slow.

---

## Tenant isolation summary

| Dimension | Mechanism | Failure mode prevented |
|---|---|---|
| Storage | Partition by `execution_id`, not `tenant_id` | Hot partition from one large tenant |
| Queueing | Bounded shard subset per tenant | Global queue head-of-line blocking |
| Scheduling | Weighted deficit round-robin, local | Starvation by a backfilling tenant |
| Concurrency | Per-tenant + per-connection caps | Worker fleet exhaustion; third-party bans |
| Admission | 429 with `Retry-After` at ingestion | Unbounded queue growth, misleading PENDING states |
| Bursts | Token bucket, large burst / slow refill | Backfills becoming impossible or abuse being unbounded |
| Compute | No shared sandbox instance across tenants | Cross-tenant data exposure via isolate escape |
| Data access | Tenant scoping enforced at the **data layer**, not the API layer | Missing authorization check in one handler |
