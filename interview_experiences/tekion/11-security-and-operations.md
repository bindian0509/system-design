# 11 — Security and Operations

[← Cost and Maintainability](10-cost-and-maintainability.md) · [Index](README.md) · [Next: Evolution Roadmap →](12-evolution-roadmap.md)

---

## The defining security property

> **We are a concentrated store of thousands of enterprises' production credentials.**
>
> A breach of our secret store is worse than a breach of our own data — we would be the vector into
> thousands of enterprises *simultaneously*.

That framing drives every priority below.

```mermaid
flowchart TB
    A["Attacker's objective ranking<br/>against this platform"]

    A --> R1["<b>1. The secret store</b><br/>OAuth tokens, DB passwords, API keys<br/>for thousands of enterprises' prod systems"]
    A --> R2["<b>2. The transform/connector sandbox</b><br/>escape ⇒ cross-tenant data access"]
    A --> R3["<b>3. The custom HTTP connector</b><br/>a request-forgery primitive we<br/>hand to users BY DESIGN"]
    A --> R4["<b>4. Tenant-scoping bugs</b><br/>in the data access path"]
    A --> R5["<b>5. Our own business data</b><br/>— least valuable of the five"]

    style R1 fill:#8b2c2c,color:#fff
    style R2 fill:#8b2c2c,color:#fff
    style R3 fill:#9e6a03,color:#fff
    style R5 fill:#6e7681,color:#fff
```

---

## 1. Credential handling

```mermaid
flowchart LR
    subgraph Store["Secret Store"]
        K1[Per-tenant encryption keys<br/>HSM-backed KMS]
        K2["Optional <b>customer-managed keys</b> (CMK)<br/>customer can revoke unilaterally —<br/>a security control AND an<br/>enterprise sales requirement"]
    end

    subgraph Runtime
        CC[Connector code<br/>holds a HANDLE only]
        EG[Egress Proxy]
    end

    Store -.short-lived credential.-> EG
    CC -->|handle| EG
    EG -->|credential attached here| EXT[(Third-party system)]

    EG --> AUD["<b>Immutable access audit</b><br/>which execution · which flow version<br/>· which step · when<br/>separate retention"]

    style Store fill:#8957e5,color:#fff
    style AUD fill:#1f6feb,color:#fff
```

**Rules:**
- Per-tenant encryption keys in HSM-backed KMS; CMK offered.
- **Short-lived credentials wherever the third party supports it** — OAuth refresh flows over stored
  long-lived secrets, always.
- Credentials never enter connector code's address space.
- Full, immutable audit log of secret access.

## 2. Customer code execution

```mermaid
flowchart TB
    S["Sandbox escape = highest-severity<br/>vulnerability class"]

    S --> L1["<b>Language-level isolation</b><br/>isolates / WASM"]
    S --> L2["<b>Process-level isolation</b>"]
    S --> L3["<b>No ambient network</b><br/>all egress via the connector layer"]
    S --> L4["<b>Hard limits</b><br/>CPU · memory · wall-clock<br/>enforced by the isolate, not the process"]
    S --> L5["<b>Workers are NOT multi-tenant<br/>within a single sandbox instance</b>"]

    L5 --> T["Accept lower density to avoid two tenants'<br/>code sharing an isolate boundary that is<br/><b>one CVE away from cross-tenant reads.</b>"]

    style S fill:#8b2c2c,color:#fff
    style T fill:#1f6feb,color:#fff
```

## 3. SSRF via the custom HTTP connector

Covered in detail in [Connectors and Egress](07-connectors-and-egress.md#the-ssrf-problem-is-inherent-to-the-product).
Summary: destination validation at the egress layer, block internal ranges, **resolve-then-pin** (not
resolve-then-trust), per-tenant destination allowlists for regulated customers.

## 4. Tenant isolation in the data plane

```mermaid
flowchart TB
    W["✗ Enforce tenant scope at the API layer"] --> WR["Authorization bugs hide behind<br/>a MISSING check in one handler"]

    R["✓ Enforce at the DATA ACCESS layer"] --> RR["Every read carries tenant context.<br/>No raw client access — only a<br/>tenant-scoped accessor."]
    RR --> RG["<b>Goal: make omission<br/>structurally impossible</b>,<br/>not merely code-reviewed."]

    style WR fill:#8b2c2c,color:#fff
    style RG fill:#1a7f37,color:#fff
```

## 5. Data residency

```mermaid
flowchart TB
    GCP["<b>Global control plane</b><br/>tenant registry · placement · billing metadata<br/>⚠️ MUST NOT carry payload data"]

    GCP --> EU
    GCP --> US

    subgraph EU["EU region — fully regional data plane"]
        E1[Ingestion] --> E2[(Log)] --> E3[Orchestrator]
        E3 --> E4[(State)] --> E5[(Payloads)]
        E3 --> E6[Workers + Egress]
    end

    subgraph US["US region — fully regional data plane"]
        U1[Ingestion] --> U2[(Log)] --> U3[Orchestrator]
        U3 --> U4[(State)] --> U5[(Payloads)]
        U3 --> U6[Workers + Egress]
    end

    EU -.->|❌ NO cross-region<br/>execution of tenant data| US

    C["<b>Constraint:</b> this RULES OUT a design where<br/>any region can process any tenant's work.<br/>Tenants are region-PINNED.<br/>Consequence: no cross-region failover<br/>for pinned tenants."]

    EU -.-> C

    style GCP fill:#1f6feb,color:#fff
    style C fill:#9e6a03,color:#fff
```

---

## Observability

### Service level indicators

```text
SLI-1  Trigger ingestion success rate
       (accepted or correctly-rejected) / total
       SLO: 99.99% over 28 days

SLI-2  Scheduling latency
       fraction of accepted executions starting their first step within 15s
       SLO: 99% over 28 days

SLI-3  Platform-attributable execution failure rate
       failures caused by US / total executions
       SLO: < 0.01%
       (EXPLICITLY excludes third-party failures — see attribution rules in doc 01)

SLI-4  Trace visibility latency
       fraction of steps visible in the console within 10s
       SLO: 99%
```

### Alert on burn rate, not on raw metrics

```mermaid
flowchart TB
    E[Error budget<br/>28-day window]

    E --> F{Burn rate}
    F -->|"Fast burn<br/>(large fraction of the<br/>monthly budget in an hour)"| P["📟 PAGE"]
    F -->|Slow burn| T["🎫 Ticket"]

    X["✗ Alerting on 'CPU > 80%'"] --> XR["Produces alerts nobody trusts.<br/><b>An untrusted pager is worse<br/>than no pager.</b>"]

    style P fill:#8b2c2c,color:#fff
    style XR fill:#8b2c2c,color:#fff
```

### Two platform-specific signals

```mermaid
flowchart TB
    S1["<b>Accepted-but-unscheduled backlog</b><br/>the single best LEADING indicator"]
    S1 --> S1R["If growing: we are accepting work faster<br/>than we can execute it, heading toward a<br/><b>violation of the durability guarantee itself.</b><br/><br/>This is the 'the platform is failing at its<br/>core promise' metric."]

    S2["<b>Per-tenant health, exposed to the CUSTOMER</b>"]
    S2 --> S2R["Unusual — observability is normally internal.<br/>But most failures here are the third party's fault,<br/>so the customer needs their own view:<br/>their flows · their error rates · their parked runs.<br/><br/>Dramatically reduces support load, and the data<br/>already flows through the trace pipeline."]

    style S1 fill:#1f6feb,color:#fff
```

### Observability stack

```mermaid
flowchart LR
    subgraph Signals
        M["<b>Metrics</b><br/>traffic · errors · latency · saturation<br/>queue depth · consumer lag<br/>replication lag · backlog age"]
        L["<b>Logs</b><br/>structured · correlation IDs<br/>execution_id + tenant context<br/>PII redaction · sampling"]
        TR["<b>Traces</b><br/>cross-service · critical path<br/>downstream timing breakdown<br/>async propagation across the queue"]
    end

    Signals --> PIPE[Trace Pipeline]
    PIPE --> OLAP[(Columnar store)]
    OLAP --> INT[Internal dashboards + SLO burn]
    OLAP --> CUST[Customer console<br/>per-tenant health]

    style CUST fill:#1a7f37,color:#fff
```

---

## Operational practice

| Practice | Purpose |
|---|---|
| Runbook linked from **every** alert | Removes reasoning-under-pressure during incidents |
| Quarterly game days: AZ loss, state store failover | Exercises the ambiguous-outcome path before it's needed |
| Regular **restore** drills | *A backup you have not restored is a hypothesis* |
| Reconciler: durable log ↔ terminal execution states | Catches anything lost between tiers |
| Canary + cell-by-cell deploys (Stage 4) | Bounds blast radius of a bad release |
| Chaos injection at the egress layer | Validates circuit breakers and bulkheads |

---

## Deployment safety

```mermaid
flowchart LR
    D[Deploy] --> C[Canary: small % of<br/>traffic / one cell]
    C --> V{SLO burn<br/>within budget?}
    V -->|No| RB["Rollback = <b>pointer swap</b><br/>to the previous immutable<br/>flow_version / artifact"]
    V -->|Yes| E[Expand progressively]
    E --> F[Full fleet]

    FF[Feature flags] -.decouple deploy from release.-> D

    style RB fill:#1a7f37,color:#fff
```

Immutable, content-hashed versions ([doc 03](03-api-and-data-model.md)) make both deployment and rollback a
pointer swap — the cheapest possible rollback primitive.
