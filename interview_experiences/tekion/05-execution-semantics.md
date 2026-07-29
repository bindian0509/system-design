# 05 — Execution Semantics

[← Architecture](04-high-level-architecture.md) · [Index](README.md) · [Next: Multi-Tenancy →](06-multi-tenancy-and-isolation.md)

---

## The guarantee, stated honestly

> **At-least-once execution of each step, with exactly-once *state transition* inside our system.**
>
> The step's side effect on a third-party system **may happen more than once.**

We cannot make an arbitrary HTTP `POST` to a customer's ERP idempotent by wishing.

### The failure that makes it unavoidable

```mermaid
sequenceDiagram
    autonumber
    participant W as Step Worker
    participant N as Network
    participant S as SAP

    W->>N: POST /orders
    N->>S: POST /orders
    S->>S: ✅ COMMITS THE ORDER
    S-->>N: 201 Created
    N--xW: 💥 response lost

    Note over W: Worker sees a TIMEOUT.<br/>It cannot distinguish:<br/>(a) never arrived<br/>(b) committed but response lost

    rect rgb(139, 44, 44)
        Note over W,S: Any retry MAY duplicate the order.<br/>This is the Two Generals Problem.<br/>No amount of platform engineering removes it.
    end
```

---

## What we *can* do: idempotency classification

Each connector operation **declares** its idempotency class. The engine's retry policy differs per class.

```mermaid
flowchart TB
    OP[Connector operation]

    OP --> C1["<b>Class A — Naturally idempotent</b><br/>GET · PUT-by-key · upsert-by-external-id"]
    OP --> C2["<b>Class B — Conditionally idempotent</b><br/>supports an idempotency token<br/>(Stripe keys, SFDC external IDs)"]
    OP --> C3["<b>Class C — Not idempotent</b><br/>bare POST, side-effecting RPC"]

    C1 --> R1["Auto-retry freely<br/>with jittered backoff"]
    C2 --> R2["Pass a DETERMINISTIC token<br/>derived from (execution_id, step_id, attempt_group)<br/>→ provider deduplicates"]
    C3 --> R3["<b>DO NOT auto-retry on<br/>ambiguous failure.</b><br/>Route to dead-letter with<br/>ambiguity explicitly flagged."]

    R2 --> V["<b>Verify-before-retry</b><br/>if the target supports query-by-token:<br/>'did this token already succeed?'"]
    R3 --> H["Human or customer-authored<br/>compensation decides"]

    style C3 fill:#8b2c2c,color:#fff
    style R3 fill:#8b2c2c,color:#fff
    style V fill:#1a7f37,color:#fff
```

### The deterministic idempotency token

```text
token = f(execution_id, step_id, attempt_group)

  • STABLE across retries of the same logical step
  • DIFFERENT across replays (a replay is a new logical attempt)
```

### Verify-before-retry collapses the ambiguity window

```mermaid
sequenceDiagram
    autonumber
    participant W as Worker
    participant P as Payment Provider

    W->>P: POST /charges (Idempotency-Key: tok_abc)
    P--xW: timeout — ambiguous

    Note over W: Retry policy for Class B:<br/>VERIFY FIRST, don't blind-retry

    W->>P: GET /charges?idempotency_key=tok_abc
    alt Charge exists
        P-->>W: 200 { charge_id, status: succeeded }
        W->>W: Treat as SUCCESS. No retry.
    else Not found
        P-->>W: 404
        W->>P: POST /charges (Idempotency-Key: tok_abc)
    end

    Note over W,P: Ambiguity window collapses from "unbounded"<br/>to "the provider's read-after-write consistency."<br/>Not exactly-once — but usually acceptable.
```

---

## Retry decision flow

```mermaid
flowchart TB
    F[Step fails] --> Q1{Deterministic failure?<br/>4xx validation, schema error}
    Q1 -->|Yes| DL1[DEAD_LETTER immediately<br/>retrying cannot help]

    Q1 -->|No| Q2{Unambiguous transient?<br/>connection refused, 503, DNS fail<br/>— request provably never landed}
    Q2 -->|Yes| RT[Retry with exponential<br/>backoff + JITTER]

    Q2 -->|No — AMBIGUOUS| Q3{Idempotency class?}

    Q3 -->|Class A| RT
    Q3 -->|Class B| VER{Target supports<br/>query-by-token?}
    Q3 -->|Class C| DL2["DEAD_LETTER<br/>flagged AMBIGUOUS_OUTCOME<br/>+ full evidence"]

    VER -->|Yes| VQ[Verify, then retry<br/>only if not found]
    VER -->|No| RTOK[Retry with the same<br/>idempotency token]

    RT --> Q4{Retry budget<br/>exhausted?}
    RTOK --> Q4
    VQ --> Q4
    Q4 -->|Yes| DL3[DEAD_LETTER]
    Q4 -->|No| RUN[Back to RUNNING]

    style DL2 fill:#8b2c2c,color:#fff
    style RT fill:#1a7f37,color:#fff
```

---

## Surfacing it in the product

> If we hide this, **every customer discovers it during their first production incident.**

The designer must:

- Visibly mark non-idempotent steps with a warning affordance.
- Prompt the author to configure ambiguous-failure behaviour explicitly.
- Show the dead-letter queue prominently, with the ambiguity reason attached.

```mermaid
flowchart LR
    subgraph Designer["Flow Designer"]
        S1[Fetch orders<br/>✅ idempotent]
        S2[Transform<br/>✅ pure]
        S3["Create SAP order<br/>⚠️ NOT IDEMPOTENT"]
        S1 --> S2 --> S3
    end

    S3 -.-> P["Prompt the author:<br/>On ambiguous failure —<br/>◯ Dead-letter for review (default)<br/>◯ Retry anyway (I accept duplicates)<br/>◯ Run compensation flow"]

    style S3 fill:#9e6a03,color:#fff
```

---

## What we refuse to do

| Temptation | Why we refuse |
|---|---|
| Claim "exactly-once" in marketing | The support cost of an over-promised guarantee exceeds the sales value. |
| Auto-retry Class C operations by default | Silently duplicates business transactions in customers' systems of record. |
| Hide the ambiguity from the console | The customer must be able to decide; they know whether a duplicate order is recoverable. |
| Build our own dedup for arbitrary targets | We cannot see the target's internal state. The guarantee must come from the provider. |

> When a customer insists they need exactly-once for a payment step: **the guarantee has to come from the
> payment provider, not from us.** Our job is to make using theirs easy — deterministic tokens plus
> verify-before-retry.
