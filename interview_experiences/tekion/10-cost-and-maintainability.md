# 10 — Cost and Maintainability

[← Resilience](09-resilience-and-failure-modes.md) · [Index](README.md) · [Next: Security and Operations →](11-security-and-operations.md)

---

## Cost drivers, ranked

```mermaid
flowchart TB
    T["Total cost of the platform"]

    T --> C1["<b>1. Trace + payload storage</b><br/>up to ~2 PB/month naive<br/>▶ likely the single largest line item"]
    T --> C2["<b>2. Worker compute</b><br/>dominated by WAITING on external I/O,<br/>not by CPU"]
    T --> C3["<b>3. State store provisioned capacity</b><br/>sized for peak, idle much of the day"]
    T --> C4["<b>4. Egress + cross-AZ traffic</b><br/>8 TB/day of payloads;<br/>cross-AZ transfer is a silent killer"]
    T --> C5["<b>5. Idempotency KV</b><br/>high write rate, memory-resident"]
    T --> C6["<b>6. Engineering labour on connectors</b><br/>not infra — but plausibly the largest<br/><b>true</b> cost, growing linearly<br/>with catalog size"]

    style C1 fill:#8b2c2c,color:#fff
    style C6 fill:#9e6a03,color:#fff
```

---

## Cutting 40% — ordered by value per unit of risk

```mermaid
flowchart LR
    A["<b>(a) Fix the observability pipeline</b><br/>~20–25% alone"]
    B["<b>(b) Make waiting free</b><br/>~10–15%"]
    C["<b>(c) Match capacity to the diurnal curve</b><br/>~5–10%"]
    D["<b>(d) Kill cross-AZ payload movement</b>"]

    A --> B --> C --> D --> TOT["≈ 40%"]

    style TOT fill:#1a7f37,color:#fff
```

### (a) Observability pipeline — the biggest single lever

```mermaid
flowchart TB
    O["Observability cost reduction"]

    O --> O1["<b>Metadata always, payloads by policy</b><br/>always on failure · rolling sample of successes<br/>· always for audited flows"]
    O --> O2["<b>Content-address blobs</b><br/>retries and fan-out re-reference,<br/>never re-copy"]
    O --> O3["<b>Tier to cold storage after 7 days</b>"]
    O --> O4["<b>Columnar + compression</b><br/>trace metadata is highly repetitive<br/>→ should compress ~an order of magnitude"]

    O1 --> W["Barely touches the product experience:<br/>debugging demand concentrates on FAILURES,<br/>which we retain completely."]

    style W fill:#1a7f37,color:#fff
```

### (b) Make waiting free — an architectural choice, not a tuning knob

```mermaid
flowchart TB
    subgraph Sync["✗ Thread-per-request worker"]
        S1[1 thread = 1 in-flight call]
        S1 --> S2["A 30s SAP call occupies a thread<br/>for 30 seconds of pure WAITING"]
        S2 --> S3["I/O wait is a COMPUTE cost"]
    end

    subgraph Async["✓ Async I/O worker"]
        A1["1 process = 1000s of in-flight calls"]
        A1 --> A2["I/O wait is a MEMORY cost"]
        A2 --> A3["Integration workloads are close to<br/>pure I/O-bound ⇒ large density gain"]
    end

    A3 --> N["<b>Must be decided early.</b><br/>Retrofitting async onto a thread-per-request<br/>engine is a rewrite."]

    style S3 fill:#8b2c2c,color:#fff
    style N fill:#1f6feb,color:#fff
```

### (c) Diurnal capacity matching — a cost lever that is also a product feature

```mermaid
flowchart LR
    P["6× peak-to-trough<br/>⇒ provisioning for peak<br/>wastes most of the day"]

    P --> L1["Reserved capacity for the trough,<br/>elastic for the peak"]
    P --> L2["<b>Deliberately schedule deferrable work<br/>into the trough</b><br/>batch flows · backfills · reindexing"]

    L2 --> F["Sell it: an 'economy tier' price<br/>for deferrable flows.<br/><br/>Only works if the scheduling primitives<br/>exist EARLY."]

    style F fill:#1a7f37,color:#fff
```

### (d) Cross-AZ payload movement

Payload blobs are fetched **AZ-locally**; the orchestrator→worker path carries **references, not payloads**.
This is why payloads never travel through the state store — a decision that is as much about cost as
about performance.

---

## What we would *not* cut

| Not cut | Why |
|---|---|
| Multi-AZ redundancy on the **ingestion** tier | It protects the durability guarantee, which *is* the product |
| Audit logging | It protects the security posture; also a compliance artifact |
| Failure-path payload retention | Debugging demand is concentrated exactly there |

---

## Ownership boundaries

> **Principle:** split along axes of *differing change rate*, *differing availability requirement*, or
> *differing scaling behaviour* — **not** along nouns in the domain model.

```mermaid
flowchart TB
    subgraph CR["Core Runtime team"]
        A1[Ingestion + Durable Log<br/>99.99% · tightest SLO]
        A2[Orchestrator + State Store<br/>correctness-critical]
    end

    subgraph RE["Runtime Execution team"]
        B1[Workers + Sandbox + Egress<br/>different scaling profile<br/>security-sensitive]
    end

    subgraph CN["Connectors org (multiple pods)"]
        C1[Connector catalog<br/>scales with PEOPLE, not traffic<br/>independent release cadence]
    end

    subgraph PP["Product Platform team"]
        D1[Control plane + Designer<br/>iterates fast · lower availability bar]
    end

    subgraph OB["Observability team"]
        E1[Trace pipeline + analytics store<br/>highest data volume<br/>specialised cost/scale problem]
    end

    CR -.stable contract.-> RE
    RE -.<b>connector contract</b><br/>owned by Core Runtime.-> CN
    CR -.deployed config.-> PP
    CR -.trace events.-> OB

    style A1 fill:#1f6feb,color:#fff
    style C1 fill:#9e6a03,color:#fff
```

**Why ingestion and orchestrator share a team:** they share a correctness model, even though they are
separate deployables. Splitting them across teams would put a team boundary in the middle of the
durability guarantee.

**Why connectors must be structurally independent:** the catalog grows with headcount. If a connector
release requires a runtime release, the runtime team becomes a bottleneck and eventually starts
rubber-stamping reviews — which is worse than no review.

---

## On-call design

```mermaid
flowchart LR
    subgraph DP["Data plane rotation — 24/7 pager"]
        P1["Accepted-but-unscheduled<br/>backlog GROWING"]
        P2[Ingestion error rate]
        P3[Fast error-budget burn]
    end

    subgraph CP["Control plane rotation — business hours for most"]
        Q1[Designer availability]
        Q2[Deploy propagation delay]
        Q3[Console latency]
    end

    DP -.-> R["Conflating these means the person who<br/>understands the designer UI gets paged<br/>at 3am for orchestrator backlog."]

    style P1 fill:#8b2c2c,color:#fff
```

---

## The biggest maintainability risk

```mermaid
flowchart TB
    R["<b>The connector contract</b><br/>— without hesitation"]

    R --> W["Once thousands of flows depend on connector<br/>behaviour, every quirk is load-bearing,<br/>including bugs."]

    W --> S["Structural mitigation, applied EARLY:<br/>• versioned operations<br/>• flows pin a major version<br/>• behaviour changes ⇒ new version"]
    W --> T["Test investment:<br/>• contract tests vs recorded fixtures<br/>• periodic LIVE conformance suite vs<br/>  real third-party sandboxes"]

    T --> V["The live suite tells us Salesforce changed<br/>their API <b>before our customers do.</b>"]

    style R fill:#8b2c2c,color:#fff
    style V fill:#1f6feb,color:#fff
```
