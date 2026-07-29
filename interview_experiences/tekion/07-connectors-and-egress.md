# 07 — Connectors and the Egress Layer

[← Multi-Tenancy](06-multi-tenancy-and-isolation.md) · [Index](README.md) · [Next: Long-Running Flows →](08-long-running-flows-and-scheduling.md)

---

> **The engine is table stakes. The connector catalog is the moat — and the largest ongoing engineering cost.**
> 200 connectors against third-party APIs that change without notice is a permanent maintenance liability.

---

## The connector contract

A connector **declares** as much as possible as data, and writes code only for genuinely custom behaviour.

```mermaid
flowchart TB
    subgraph Declarative["Declarative (data — generatable from OpenAPI)"]
        D1[Operations + input/output schemas]
        D2[Auth mechanism]
        D3[Pagination style]
        D4[Rate-limit hints]
        D5[Error taxonomy mapping]
        D6["<b>Idempotency class per operation</b>"]
    end

    subgraph Imperative["Imperative (code — the expensive part)"]
        I1[Non-standard auth handshakes]
        I2[Protocol quirks]
        I3[Custom pagination cursors]
    end

    Declarative --> B["The more that is declarative,<br/>the more connectors we can GENERATE<br/>and the less bespoke code we maintain."]

    D6 --> ENG["Consumed by the retry engine<br/>→ turns 'we hope it's fine'<br/>into a property the engine reasons about"]

    style D6 fill:#1f6feb,color:#fff
    style ENG fill:#1f6feb,color:#fff
```

## Versioning — the dominant long-term maintainability risk

```mermaid
flowchart TB
    P["Once thousands of customer flows depend on<br/>connector behaviour, every quirk becomes<br/><b>load-bearing — including bugs.</b>"]

    P --> EX["Example: a connector silently coerces<br/>null → empty string.<br/>Flows now DEPEND on that.<br/>Fixing it breaks production integrations."]

    EX --> M["Mitigation must be STRUCTURAL and EARLY"]

    M --> M1["Connector operations are <b>versioned</b>"]
    M --> M2["Flows <b>pin a major version</b>"]
    M --> M3["Behaviour changes require a NEW version,<br/>never a mutation of the existing one"]

    M1 --> C["Cost: maintaining many versions<br/>of many connectors, indefinitely."]
    C --> J["Justification: the alternative is being<br/>PERMANENTLY UNABLE to fix bugs — where<br/>mature integration platforms end up if they<br/>don't do this from the start."]

    style EX fill:#8b2c2c,color:#fff
    style J fill:#1f6feb,color:#fff
```

### Testing the catalog

```mermaid
flowchart LR
    CT["<b>Contract tests</b><br/>against recorded fixtures"] --> CI[Every connector build]
    LC["<b>Live conformance suite</b><br/>against real third-party sandboxes<br/>on a schedule"] --> AL[Alert]

    AL --> R["Tells us Salesforce changed their API<br/><b>before our customers do.</b><br/><br/>Finding out from a customer ticket<br/>is the failure mode we are designing against."]

    style R fill:#1f6feb,color:#fff
```

---

## The egress proxy

Easy to omit; **expensive to retrofit.** Connectors do **not** open sockets directly.

```mermaid
flowchart TB
    subgraph Worker["Step Worker (sandboxed)"]
        CC["Connector code<br/>holds a credential HANDLE,<br/>never the secret"]
    end

    CC --> EG

    subgraph EG["Egress Proxy — the security choke point"]
        E1["<b>SSRF prevention</b><br/>destination allowlists<br/>block link-local / loopback / internal ranges<br/>resolve-then-PIN (DNS rebinding protection)"]
        E2["<b>Stable source IPs</b><br/>enterprises firewall by source IP;<br/>IPs changing with autoscaling breaks integrations"]
        E3["<b>Per-connection rate limiting<br/>+ circuit breaking</b><br/>one place that knows SFDC is returning 503s<br/>across many tenants"]
        E4["<b>Full audit log</b><br/>every outbound call<br/>'what did you do with my SAP password?'"]
        E5["<b>Credential injection</b><br/>handle → real credential,<br/>attached at the proxy"]
    end

    SEC[(Secret Store<br/>per-tenant KMS keys)] -.short-lived creds.-> E5

    EG --> EXT[(External Systems)]

    style EG fill:#9e6a03,color:#fff
    style SEC fill:#8957e5,color:#fff
```

### Why credentials never enter connector code's address space

```mermaid
flowchart LR
    subgraph Naive["✗ Credential passed into the sandbox"]
        N1[Sandbox escape] --> N2[Attacker reads<br/>process memory] --> N3["❌ CREDENTIALS COMPROMISED<br/>= vector into thousands of<br/>enterprises simultaneously"]
    end

    subgraph Ours["✓ Credential injected at the proxy"]
        O1[Sandbox escape] --> O2[Attacker reads<br/>process memory] --> O3["Finds only an opaque handle.<br/>Handle is scoped, short-lived,<br/>and only usable through the proxy —<br/>which audits every use."]
    end

    style N3 fill:#8b2c2c,color:#fff
    style O3 fill:#1a7f37,color:#fff
```

> **Structural mitigation:** sandbox escape ≠ credential compromise. Worth the extra network hop given that
> we are a concentrated store of thousands of enterprises' production credentials.

### The SSRF problem is inherent to the product

```mermaid
flowchart TB
    F["The <b>custom HTTP connector</b> lets customers<br/>configure ARBITRARY URLs.<br/>That is a request-forgery primitive<br/>handed to users by design."]

    F --> A1["Attack: point it at<br/>169.254.169.254 (cloud metadata)"]
    F --> A2["Attack: point it at internal<br/>service addresses"]
    F --> A3["Attack: DNS rebinding —<br/>resolve to a safe IP, then<br/>re-resolve to an internal one"]

    A1 --> M["<b>Egress-layer validation</b>"]
    A2 --> M
    A3 --> M

    M --> M1[Block link-local, loopback,<br/>RFC1918 and internal ranges]
    M --> M2["<b>Resolve-then-PIN</b> the IP<br/>— never resolve-then-trust"]
    M --> M3[Per-tenant destination allowlists<br/>for regulated customers]

    style F fill:#9e6a03,color:#fff
    style A3 fill:#8b2c2c,color:#fff
```

---

## Connector isolation and release independence

```mermaid
flowchart TB
    subgraph Coupled["✗ Connectors ship with the runtime"]
        C1[200 connectors × many teams<br/>shipping constantly] --> C2[Every release needs<br/>a runtime release]
        C2 --> C3[Runtime team is the bottleneck]
        C3 --> C4["They start rubber-stamping reviews —<br/><b>worse than no review</b>"]
    end

    subgraph Decoupled["✓ Independently versioned artifacts"]
        D1[Connector = versioned artifact<br/>with a stable contract]
        D1 --> D2["Runtime team owns the <b>CONTRACT</b>,<br/>not the connectors"]
        D2 --> D3["Catalog scales with HEADCOUNT,<br/>not with runtime release cadence"]
        D1 --> D4[Bad connector release cannot<br/>take down the worker fleet:<br/>same sandbox + per-invocation limits]
    end

    style C4 fill:#8b2c2c,color:#fff
    style D3 fill:#1a7f37,color:#fff
```

---

## Self-hosted runtime agent

Many integration targets are on-premises and unreachable from our cloud.

```mermaid
flowchart LR
    subgraph Cloud["Our cloud"]
        ORCH[Orchestrator]
        REG[(Flow Registry)]
    end

    subgraph CustomerNet["Customer network — no inbound firewall rules required"]
        AGENT["Self-hosted Runtime Agent<br/>same execution engine"]
        AGENT --> DB[(On-prem Oracle)]
        AGENT --> SAP[(On-prem SAP)]
        AGENT --> FS[(Internal SFTP)]
    end

    AGENT -->|<b>OUTBOUND ONLY</b><br/>long-lived connection| ORCH
    REG -.flow definitions.-> AGENT

    N["Outbound-only is what makes this<br/>deployable in real enterprises —<br/>no inbound firewall change to negotiate."]
    AGENT -.-> N

    style N fill:#1f6feb,color:#fff
```

> **Acknowledged gap:** version skew between customer-deployed agents and the control plane is a serious
> long-term operational burden. See [Risks](13-decisions-and-risks.md).
