# 12 — Evolution Roadmap

[← Security and Operations](11-security-and-operations.md) · [Index](README.md) · [Next: Decisions and Risks →](13-decisions-and-risks.md)

---

## Stages and their triggers

```mermaid
flowchart TB
    S1["<b>Stage 1 — Launch</b><br/>Single region, multi-AZ<br/>Managed durable log<br/>Managed relational store for flow metadata AND execution state<br/>Object storage for payloads<br/>Orchestrator + workers separate but modest<br/>~20 connectors · DSL authoring + basic canvas"]

    T1{{"<b>Trigger →</b><br/>Execution state store write capacity > ~60% sustained<br/>OR trace query latency degrading console usability"}}

    S2["<b>Stage 2 — Growth</b><br/>Split execution state into a partitioned store<br/>Trace pipeline → dedicated columnar/OLAP, decoupled<br/>Queue sharding + weighted fair scheduling<br/>Connector catalog opens internally with the versioned contract"]

    T2{{"<b>Trigger →</b><br/>Enterprise deals BLOCKED on data residency<br/>or on-premises connectivity"}}

    S3["<b>Stage 3 — Regional and hybrid</b><br/>Multi-region: regional data planes, global control plane<br/>Self-hosted runtime agent (outbound-only)<br/>Region-pinned tenants<br/>No cross-region execution of tenant data"]

    T3{{"<b>Trigger →</b><br/>Single incidents ROUTINELY affect a majority of tenants<br/>OR state store operational complexity exceeds one team"}}

    S4["<b>Stage 4 — Cells</b><br/>Cell-based isolation within regions<br/>Tenant placement service<br/>Cell-by-cell deployment<br/>Per-cell capacity management"]

    S1 --> T1 --> S2 --> T2 --> S3 --> T3 --> S4

    style S1 fill:#1a7f37,color:#fff
    style T1 fill:#9e6a03,color:#fff
    style T2 fill:#9e6a03,color:#fff
    style T3 fill:#9e6a03,color:#fff
```

> Note that **none of the triggers is a QPS number.** Each is an operational or commercial signal.

---

## Stage 1 — Launch

```mermaid
flowchart LR
    C[Clients] --> ING[Ingestion]
    ING --> LOG[(Managed durable log)]
    LOG --> ORCH[Orchestrator]
    ORCH --> RDB[("Managed relational store<br/>flow metadata <b>+</b> execution state")]
    ORCH --> Q[(Task queue)]
    Q --> W[Workers]
    W --> EG[Egress Proxy] --> EXT[(~20 connectors)]
    W --> OBJ[(Object storage<br/>payloads)]
    ORCH --> TR[Trace] --> RDB

    style RDB fill:#1f6feb,color:#fff
```

**Ship the durability guarantee and the observability, because those are what people buy.**

## Stage 2 — Growth

```mermaid
flowchart LR
    C[Clients] --> ING[Ingestion]
    ING --> LOG[(Durable log)]
    LOG --> ORCH[Orchestrator]
    ORCH --> PST[("<b>Partitioned</b> execution<br/>state store")]
    ORCH --> QS[("<b>Sharded</b> task queues<br/>+ weighted fair scheduling")]
    QS --> W[Workers]
    W --> EG[Egress] --> EXT[(External)]
    W --> OBJ[(Content-addressed<br/>payload store)]
    ORCH --> TR[Trace pipeline]
    TR --> OLAP[("<b>Dedicated columnar</b><br/>analytics store")]
    OLAP --> CON[Console]

    REG[(Flow registry)] -.-> ORCH

    style PST fill:#1a7f37,color:#fff
    style QS fill:#1a7f37,color:#fff
    style OLAP fill:#1a7f37,color:#fff
```

Green = what changed. Fair scheduling should land **slightly before** the first noisy-neighbour incident,
not after it.

## Stage 3 — Regional and hybrid

```mermaid
flowchart TB
    GCP[Global Control Plane<br/>registry · placement · no payload data]

    GCP --> RA
    GCP --> RB

    subgraph RA["Region: EU"]
        A1[Ingestion] --> A2[(Log)] --> A3[Orchestrator] --> A4[Workers]
        A3 --> A5[(State + Payloads)]
    end

    subgraph RB["Region: US"]
        B1[Ingestion] --> B2[(Log)] --> B3[Orchestrator] --> B4[Workers]
        B3 --> B5[(State + Payloads)]
    end

    subgraph CN["Customer network"]
        AG[Self-hosted agent]
        AG --> ON[(On-prem SAP / Oracle / SFTP)]
    end

    AG -.outbound only.-> B3

    RA -.->|❌ no cross-region<br/>tenant data| RB
```

## Stage 4 — Cells

```mermaid
flowchart TB
    P[Tenant Placement Service]
    P --> C1[Cell 1]
    P --> C2[Cell 2]
    P --> C3[Cell N]

    C1 --> D1["Full vertical slice:<br/>log · orchestrator · state · workers"]
    C2 --> D2["Full vertical slice"]
    C3 --> D3["Full vertical slice"]

    DEP[Deploy] -->|canary| C1
    DEP -.->|then| C2
    DEP -.->|then| C3

    style P fill:#1f6feb,color:#fff
```

---

## The most common platform failure mode

```mermaid
flowchart TB
    F["<b>Building the Stage 4 architecture<br/>at Stage 1 scale</b>"]
    F --> C1["Pay FULL operational complexity"]
    F --> C2["While still carrying<br/>product-market-fit risk"]
    C1 --> R["Complexity slows down<br/><b>exactly the iteration you need most.</b>"]
    C2 --> R

    style F fill:#8b2c2c,color:#fff
    style R fill:#8b2c2c,color:#fff
```

---

## Day-one irreversibles

These must be right from the start, because retrofitting is prohibitive.

```mermaid
flowchart TB
    I(("Day-one<br/>irreversibles"))

    I --> I1["<b>Flow definition format</b><br/>it is a PUBLIC CONTRACT.<br/>Customers commit it to Git."]
    I --> I2["<b>Connector versioning contract</b><br/>bugs become load-bearing;<br/>without pinning you can never fix them."]
    I --> I3["<b>Durability boundary semantics</b><br/>customers BUILD on the guarantee.<br/>Weakening it later breaks their systems."]
    I --> I4["<b>Async I/O worker model</b><br/>retrofitting async onto<br/>thread-per-request is a REWRITE."]

    style I fill:#8b2c2c,color:#fff
```

### Safely deferrable

| Deferrable | Why it's safe to defer |
|---|---|
| Multi-region | Regional data planes can be added; tenants start region-pinned to one region trivially |
| Cell-based isolation | An additive layer above an already-partitioned design |
| Visual designer polish | The DSL is the source of truth; the canvas is a renderer |
| Connector SDK for customers | Internal-only catalog first validates the contract |
| Columnar trace store | Trace data is derived and rebuildable |
| Self-hosted agent | Same engine, different deployment topology |

---

## Migration and deployment techniques by stage

```mermaid
flowchart LR
    S1["Stage 1<br/>Rolling deploy<br/>Feature flags<br/>Pointer-swap rollback"]
    S2["Stage 2<br/>+ Dual writes during the<br/>state store split<br/>+ Backfill + reconcile<br/>+ Expand-and-contract schema"]
    S3["Stage 3<br/>+ Region-by-region migration<br/>+ Tenant-by-tenant pinning<br/>+ Shadow traffic"]
    S4["Stage 4<br/>+ Cell-by-cell canary<br/>+ Tenant relocation<br/>between cells"]

    S1 --> S2 --> S3 --> S4
```

The Stage 2 state store split is the riskiest migration: it moves the **source of truth for in-flight work**.
Approach: dual-write to old and new, read from old, reconcile continuously, flip reads behind a flag per
partition, then contract — with the durable log as the safety net throughout, since it can replay anything
lost in the window.
