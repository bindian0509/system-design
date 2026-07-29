# 03 — APIs and Data Model

[← Capacity](02-capacity-estimation.md) · [Index](README.md) · [Next: High-Level Architecture →](04-high-level-architecture.md)

---

## Surface 1 — Trigger ingestion (the durability boundary)

```http
POST /v1/triggers/{flow_id}
Idempotency-Key: <caller-supplied or derived>
Content-Type: application/json

{ "payload": { ... }, "headers": { ... } }

--- 202 Accepted ---
{
  "execution_id": "exe_01HQ...",
  "status": "ACCEPTED",
  "dedup": false
}
```

### Deliberate choices

| Choice | Reason |
|---|---|
| **`202`, not `200`** | We accepted responsibility; we have **not** done the work. `200` invites callers to assume completion. |
| **Idempotency-Key required for at-least-once sources** | Webhook senders retry. Without dedup we double-charge someone's customer. Scoped to `(tenant, flow, key)`, TTL 24h. |
| **Return the *original* `execution_id` on duplicate** | With `dedup: true`. We don't silently swallow — the caller needs to correlate. |
| **Write path is: validate → append to log → return** | Nothing else. No Postgres lookup of the flow definition. No DB quota check. Everything must be in-memory, cached, or async. |

```mermaid
sequenceDiagram
    autonumber
    participant C as Caller
    participant I as Ingestion
    participant K as Idempotency KV
    participant L as Durable Log

    C->>I: POST /v1/triggers/{flow_id}<br/>Idempotency-Key: k
    I->>I: AuthN/AuthZ (cached keys)
    I->>I: Schema validate (reject malformed here —<br/>cheapest place to reject)
    I->>I: Local approximate rate limit<br/>(cached tenant budget)

    I->>K: SETNX (tenant, flow, k) → execution_id
    alt Key already exists
        K-->>I: existing execution_id
        I-->>C: 202 { execution_id: existing, dedup: true }
    else New key
        K-->>I: OK
        I->>L: Append (execution_id, flow_version, payload_ref)
        L-->>I: durably committed
        Note over I,L: ◀── DURABILITY BOUNDARY CROSSED ──▶
        I-->>C: 202 { execution_id, dedup: false }
    end
```

### Why quota checks are asynchronous

```mermaid
flowchart TB
    Q{Enforce tenant limits<br/>on the ingest path?}

    Q --> S["Synchronous,<br/>strongly consistent"]
    Q --> A["Approximate local<br/>+ async reconcile"]

    S --> SR["✗ Makes the 99.99% component<br/>depend on a database<br/>✓ Exact enforcement"]
    A --> AR["✓ No DB on the hot path<br/>✗ Bounded overshoot ="]
    AR --> AR2["nodes × refresh interval<br/>× per-node allowance"]

    A --> D["DECISION: split the concerns"]
    D --> D1["<b>Rate limiting</b> = protect the platform<br/>fast + approximate<br/>enforced at the edge"]
    D --> D2["<b>Quota</b> = commercial enforcement<br/>exact but may lag<br/>counted at the durable log"]

    style S fill:#8b2c2c,color:#fff
    style D fill:#1f6feb,color:#fff
```

Counting at the **durable log** rather than at the API means the billing count is exact even though the
limit is fuzzy.

---

## Surface 2 — Execution control

```http
GET  /v1/executions/{execution_id}          → status + step timeline
POST /v1/executions/{execution_id}/replay   → NEW execution, links to parent
POST /v1/executions/{execution_id}/cancel
GET  /v1/flows/{flow_id}/executions?cursor=&status=&from=&to=
```

- **Cursor pagination** on `(tenant, flow, started_at, execution_id)`.
  Offset pagination over a table taking 23,000 inserts/sec is a guaranteed incident.
- **Replay creates a new execution** referencing the parent, never mutates the original.
  Mutating history destroys the audit trail — which is frequently the customer's compliance artifact.

```mermaid
flowchart LR
    E1["exe_A<br/>FAILED<br/>step 4: SAP timeout"] -->|replay| E2["exe_B<br/>parent = exe_A<br/>RUNNING"]
    E2 -->|replay| E3["exe_C<br/>parent = exe_B<br/>SUCCEEDED"]

    E1 -.->|immutable<br/>audit trail preserved| E1

    style E1 fill:#8b2c2c,color:#fff
    style E3 fill:#1a7f37,color:#fff
```

---

## Data model

| Entity | Partition key | Sort key | Notes |
|---|---|---|---|
| `flow` | `tenant_id` | `flow_id` | Metadata only; **definition body in object store** |
| `flow_version` | `flow_id` | `version` | **Immutable**; content hash of definition |
| `deployment` | `(tenant_id, env)` | `flow_id` | Pointer to active `flow_version` |
| `execution` | `execution_id` | — | State machine record; hot, high-churn |
| `execution_by_flow` | `(flow_id, time_bucket)` | `started_at, execution_id` | Query index for the console |
| `step_record` | `execution_id` | `step_seq` | Timing, status, error, **payload hash** |
| `payload_blob` | `sha256` | — | Object storage, content-addressed |
| `connection` | `tenant_id` | `connection_id` | Credential **reference**, never the secret |
| `dedup_key` | `(tenant, flow, idem_key)` | — | TTL 24h, KV store |

```mermaid
erDiagram
    TENANT ||--o{ FLOW : owns
    TENANT ||--o{ CONNECTION : owns
    FLOW ||--o{ FLOW_VERSION : "has (immutable)"
    FLOW_VERSION ||--o{ DEPLOYMENT : "pointed to by"
    DEPLOYMENT }o--|| ENVIRONMENT : "in"
    FLOW_VERSION ||--o{ EXECUTION : "produced"
    EXECUTION ||--o{ STEP_RECORD : "contains"
    STEP_RECORD }o--o| PAYLOAD_BLOB : "references by sha256"
    CONNECTION }o--|| SECRET_REF : "resolves to"
    EXECUTION ||--o| EXECUTION : "replay parent"
    FLOW ||--o{ EXECUTION_BY_FLOW : "indexed by"

    FLOW_VERSION {
        string version PK
        string content_hash
        blob definition_ref
        bool immutable
    }
    EXECUTION {
        string execution_id PK
        string state
        string flow_version
        timestamp started_at
        string parent_execution_id
    }
    STEP_RECORD {
        int step_seq PK
        string status
        int duration_ms
        string error_class
        string payload_sha256
    }
    PAYLOAD_BLOB {
        string sha256 PK
        int size_bytes
        int refcount
    }
    CONNECTION {
        string connection_id PK
        string secret_reference
        int max_concurrency
    }
```

---

## Three modelling decisions worth defending

### 1. `execution` is partitioned by `execution_id`, not `tenant_id`

```mermaid
flowchart TB
    subgraph Bad["✗ Partition by tenant_id"]
        T1[Tenant A<br/>small] --> P1[(Partition 1)]
        T2[Tenant B<br/>HUGE] --> P2[(Partition 2<br/>🔥 HOT)]
        T3[Tenant C<br/>small] --> P3[(Partition 3)]
        P2 --> X["Noisy neighbour built<br/>into the storage layer"]
    end

    subgraph Good["✓ Partition by execution_id"]
        E[All executions<br/>hashed by ID] --> U[(Uniform<br/>distribution<br/>across all partitions)]
        U --> Y["Cost: 'show me this tenant's<br/>executions' is no longer<br/>a single-partition read"]
        Y --> Z["→ separate execution_by_flow index,<br/>TIME-BUCKETED so the write hotspot<br/><b>moves</b> rather than concentrating"]
    end

    style P2 fill:#8b2c2c,color:#fff
    style U fill:#1a7f37,color:#fff
```

### 2. `connection` stores a reference, never a credential

Secrets live in a dedicated store with per-tenant encryption keys. The runtime resolves the reference to a
**short-lived credential at step execution time**.

> This matters because the credential blast radius *is* the product risk: we hold OAuth tokens and database
> passwords for thousands of enterprises' production systems. That is a more attractive target than our own data.

### 3. `flow_version` is immutable and content-hashed

```mermaid
flowchart LR
    D[Deploy request] --> H{Content hash<br/>== running version?}
    H -->|Yes| S["Skip propagation entirely<br/>(common in CI that redeploys<br/>on every commit)"]
    H -->|No| N[Create new immutable<br/>flow_version]
    N --> P["Deployment = <b>pointer swap</b>"]
    P --> R["Rollback = <b>pointer swap</b><br/>the cheapest possible<br/>rollback primitive"]

    style R fill:#1a7f37,color:#fff
```

Immutability also answers *"which version of the logic processed this record?"* — a question customers ask
during incidents, sometimes months later, sometimes with auditors present. Mutable versions make that
unanswerable.
