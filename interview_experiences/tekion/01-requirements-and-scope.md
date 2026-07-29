# 01 — Requirements and Scope

[← Index](README.md) · [Next: Capacity Estimation →](02-capacity-estimation.md)

---

## Problem framing

We are building a **platform**, not an integration. Customers author *flows* that move and transform data
between systems they do not control — Salesforce, SAP, Postgres, S3, Kafka, arbitrary REST/SOAP endpoints,
SFTP. The platform runs those flows, guarantees they complete, and shows the customer what happened when
something breaks.

### Clarifications that changed the design

| Question | Answer | Consequence |
|---|---|---|
| Who is the primary user? | Both developers and business users; **developer is the buyer** | The flow definition is a **versioned declarative document**; the visual canvas *renders* it. One format, one source of truth. |
| What triggers a flow? | Majority **event-driven and scheduled batch**; sync APIs are a minority | The platform is fundamentally an **async durable workflow engine**. The sync path is a thin special case layered on top. |
| Shared or dedicated runtime? | **Shared by default**, dedicated as a topology | Integration traffic is spiky and mostly idle; dedicated always-on compute per tenant destroys gross margin. |
| On-prem systems? | Yes — many targets are unreachable from our cloud | A **self-hosted runtime agent** (outbound-only) is a real requirement, not a nice-to-have. |

### Why the canvas must not have its own format

```mermaid
flowchart LR
    subgraph Wrong["✗ Two sources of truth"]
        C1[Canvas] --> F1[(Canvas format)]
        D1[CLI / Git] --> F2[(DSL format)]
        F1 <-.->|lossy round-trip<br/>permanent tax| F2
    end

    subgraph Right["✓ One source of truth"]
        C2[Canvas] --> F3[(Flow Definition<br/>versioned document)]
        D2[CLI / Git] --> F3
        F3 --> R[Runtime]
    end
```

---

## Scope

```mermaid
flowchart TB
    subgraph P0["P0 — Core product"]
        A1[Author a flow:<br/>trigger + steps]
        A2[Version + deploy<br/>to environment]
        A3[Durable execution:<br/>every accepted event<br/>reaches terminal state]
        A4[Connector framework<br/>+ ~20 connectors<br/>+ custom HTTP]
        A5[Per-execution<br/>step-level observability]
        A6[Retry, dead-letter,<br/>manual replay]
        A7[Multi-tenant isolation<br/>data / compute / rate]
        A8[Secret + credential<br/>management]
    end

    subgraph P1["P1 — Important, can be simplified"]
        B1[Visual designer<br/>v1 = DSL + basic canvas]
        B2[Connector SDK<br/>for customers]
        B3[Self-hosted<br/>runtime agent]
        B4[Publish flow as<br/>managed HTTP API]
        B5[Cron triggers<br/>+ backfill]
    end

    subgraph P2["P2 — Out of scope"]
        C1[Connector marketplace<br/>/ monetization]
        C2[B2B / EDI suite<br/>AS2, X12, EDIFACT]
        C3[Data catalog<br/>/ lineage]
        C4[Billing implementation]
        C5[ML-assisted mapping]
    end

    P0 --> P1 --> P2

    style A3 fill:#1f6feb,color:#fff
```

> **The single most important P0 is A3.** Customers tolerate slow integrations.
> They do not tolerate silently lost orders.

---

## The riskiest requirement: customer transformation logic

Customers need expression logic — field mapping, conditionals, string manipulation, aggregation.
This means **running untrusted customer code**, which is the highest-severity risk in the whole platform.

```mermaid
flowchart TB
    Q{Transformation<br/>capability}

    Q --> O1["Option 1<br/>Restricted expression language<br/>(JSONata / JMESPath style)"]
    Q --> O2["Option 2<br/>Sandboxed general language<br/>(JS isolate / WASM)"]
    Q --> O3["Option 3<br/>Customer-supplied containers"]

    O1 --> R1["✓ Safe, cheap, dense<br/>✗ Customers hit the ceiling"]
    O2 --> R2["✓ Powerful<br/>✗ Untrusted code in shared runtime<br/>✗ We own the blast radius"]
    O3 --> R3["✓ Maximum power<br/>✗ Worst density<br/>✗ Cold start"]

    R1 --> D["DECISION<br/>Ship Option 1 as default path.<br/>Option 2 as explicit escape hatch.<br/>Option 3 NOT in shared runtime."]
    R2 --> D
    R3 --> D

    style D fill:#1f6feb,color:#fff
    style O3 fill:#8b2c2c,color:#fff
```

**Guardrails for the escape hatch:** hard CPU and wall-clock limits per invocation, memory cap enforced by the
isolate (not the process), and **no ambient network access** — all egress goes through the connector layer so
it is policy-controlled and auditable.

---

## Non-functional requirements

```text
Control plane (authoring, deploy, console)
  Availability:            99.9%
  Deploy propagation:      p99 < 60s from "deploy" to runtime serving new version

Data plane — trigger ingestion  (THE DURABILITY BOUNDARY)
  Availability:            99.99%
  Ingest latency:          p50 < 30ms, p99 < 150ms   (accept + durably persist)
  Durability:              < 1 accepted event lost per 10^11 events

Data plane — execution
  Scheduling latency:      p50 < 1s, p99 < 15s   (accepted -> first step starts)
  End-to-end:              UNBOUNDED BY DESIGN — flows call slow third parties.
                           SLO covers OUR overhead only.
  Throughput:              2B executions/day steady; absorb 10x tenant bursts

Synchronous API-triggered flows (minority path)
  Platform overhead:       p99 < 100ms excluding downstream calls
  Availability:            99.95%

Observability
  Trace visibility:        p99 < 10s after step completion
  Retention:               30d hot, 1y cold (configurable)

Disaster recovery
  RTO < 30 min, RPO < 1 min for accepted-but-unexecuted work
```

### The durability boundary, drawn explicitly

```mermaid
flowchart LR
    subgraph Before["Before the line — we may reject freely"]
        C[Caller] -->|trigger| I[Ingestion]
        I -->|429 / 4xx| C
    end

    L{{"202 Accepted<br/>THE DURABILITY BOUNDARY"}}

    subgraph After["After the line — we own it, forever"]
        T1[Terminal: SUCCESS]
        T2[Terminal: FAILED<br/>+ dead-letter record<br/>+ replayable]
    end

    I --> L
    L --> After

    style L fill:#1f6feb,color:#fff
```

### What we deliberately did *not* promise

We did **not** promise end-to-end latency. A flow calling a customer's SAP instance can take four minutes
because SAP took four minutes. Putting that in an SLO means being on-call for someone else's ERP.

This forces a hard requirement: **every failure must be classified as ours vs. theirs**, defensibly.

```mermaid
flowchart TB
    F[Connector call fails] --> Q1{Did we issue the request<br/>and respect the<br/>configured timeout?}
    Q1 -->|No| OURS[Platform-attributable]
    Q1 -->|Yes| Q2{Was our egress healthy<br/>at that moment?<br/>NAT saturation, DNS, TLS}
    Q2 -->|No| OURS
    Q2 -->|Yes| THEIRS[Third-party-attributable]

    OURS --> B[Counts against<br/>our error budget]
    THEIRS --> E["Excluded from SLO<br/>but MUST emit evidence:<br/>DNS / TLS / connect / first-byte<br/>breakdown + timestamps"]

    style OURS fill:#8b2c2c,color:#fff
```

> **Bias:** over-attribute to ourselves. The moment customers believe we are gaming the classification,
> the metric is worthless — and it is also the basis of support arguments and service credits.
