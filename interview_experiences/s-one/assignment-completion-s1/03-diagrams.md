# Singularity Health Center Diagrams

These diagrams are written in Mermaid so they can be pasted into architecture docs, GitHub markdown, or diagram tools that support Mermaid.

## System Context

```mermaid
flowchart LR
    Agents["SentinelOne Agents<br/>millions of endpoints"]
    Gateway["Regional Ingestion Gateway<br/>auth, validation, rate limits"]
    Stream["Durable Streaming Backbone<br/>Kafka or cloud equivalent"]
    Health["Health Processing Platform<br/>normalize, state, rules"]
    Alerts["Alert Orchestration<br/>dedupe, group, lifecycle"]
    Console["SentinelOne Console<br/>React UI and APIs"]
    Notify["Notifications<br/>email, webhook, ticketing"]
    Lake["Data Lake<br/>raw events, replay, analytics"]

    Agents --> Gateway
    Gateway --> Stream
    Stream --> Health
    Stream --> Lake
    Health --> Alerts
    Alerts --> Console
    Alerts --> Notify
    Health --> Console
    Lake --> Health
```

## Detailed Streaming Architecture

```mermaid
flowchart TB
    subgraph Edge["Regional Edge"]
        A["Agent Telemetry"]
        IG["Ingestion Gateway<br/>Go"]
        RL["Tenant Rate Limits"]
        SV["Schema Validation"]
    end

    subgraph Stream["Streaming Backbone"]
        Raw["agent-telemetry-raw-v1"]
        Norm["agent-health-normalized-v1"]
        Changes["agent-health-state-changes-v1"]
        Candidates["agent-health-alert-candidates-v1"]
        DLQ["agent-health-dead-letter-v1"]
    end

    subgraph Processing["Health Processing"]
        N["Normalizer and Dedupe<br/>Java/Flink"]
        S["Health State Updater"]
        R["Rule Engine"]
        AO["Alert Orchestrator"]
    end

    subgraph Storage["Storage"]
        KV["Latest Health State<br/>DynamoDB/Cassandra/Bigtable"]
        AlertDB["Alert Store"]
        Obj["Object Storage<br/>Iceberg/Delta/BigQuery"]
        Cache["Redis/Edge Cache"]
    end

    subgraph Experience["Customer Experience"]
        API["Health APIs / BFF"]
        UI["React Health Center"]
        Int["Notifications and Integrations"]
    end

    A --> IG --> RL --> SV --> Raw
    Raw --> N
    N --> Norm
    N --> DLQ
    Norm --> S
    S --> KV
    S --> Changes
    Changes --> R
    R --> Candidates
    Candidates --> AO
    AO --> AlertDB
    AO --> Int
    Raw --> Obj
    Changes --> Obj
    KV --> Cache
    Cache --> API
    AlertDB --> API
    API --> UI
```

## Health State Machine

```mermaid
stateDiagram-v2
    [*] --> Unknown
    Unknown --> Healthy: valid heartbeat and policy compliant
    Healthy --> Degraded: warning signal or stale metric
    Healthy --> Unhealthy: critical signal
    Degraded --> Healthy: condition clears
    Degraded --> Unhealthy: threshold crossed
    Unhealthy --> Recovering: clear signal observed
    Recovering --> Healthy: grace period passes
    Recovering --> Unhealthy: condition recurs
    Healthy --> Unknown: agent decommissioned or no reliable signal
    Degraded --> Unknown: metadata conflict
    Unhealthy --> Unknown: metadata conflict
```

## Alert Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Candidate
    Candidate --> Suppressed: maintenance window or policy exception
    Candidate --> Open: passes dedupe and confidence checks
    Open --> Updated: additional evidence or affected scope changes
    Updated --> Open: update persisted
    Open --> Acknowledged: user action
    Acknowledged --> Open: condition worsens or new scope
    Open --> Muted: user or rule suppression
    Acknowledged --> Muted: user suppression
    Muted --> Open: mute expires and condition remains
    Open --> Resolving: clear condition observed
    Acknowledged --> Resolving: clear condition observed
    Resolving --> Resolved: grace period passes
    Resolving --> Open: condition recurs
    Resolved --> Open: recurrence after cooldown
```

## Core Data Model

```mermaid
erDiagram
    TENANT ||--o{ AGENT : owns
    TENANT ||--o{ HEALTH_ALERT : receives
    AGENT ||--|| AGENT_HEALTH_STATE : has
    AGENT ||--o{ HEALTH_STATE_CHANGE : emits
    HEALTH_ALERT ||--o{ ALERT_EVENT : contains
    HEALTH_RULE ||--o{ HEALTH_ALERT : triggers
    HEALTH_RULE ||--o{ RULE_VERSION : versions
    TENANT ||--o{ SUPPRESSION : configures

    TENANT {
        string tenant_id PK
        string name
        string tier
    }

    AGENT {
        string tenant_id FK
        string agent_id PK
        string site_id
        string agent_version
        string os_type
        string lifecycle_state
    }

    AGENT_HEALTH_STATE {
        string tenant_id PK
        string agent_id PK
        string connectivity_status
        string protection_status
        string anti_tamper_status
        string disk_status
        datetime last_seen_event_time
        datetime last_seen_ingest_time
        int state_version
    }

    HEALTH_STATE_CHANGE {
        string change_id PK
        string tenant_id
        string agent_id
        string previous_state_hash
        string new_state_hash
        datetime processed_at
    }

    HEALTH_ALERT {
        string tenant_id
        string alert_id PK
        string idempotency_key
        string rule_id
        string severity
        string state
        datetime first_seen_at
        datetime last_seen_at
    }

    ALERT_EVENT {
        string alert_event_id PK
        string alert_id FK
        string event_type
        string actor
        datetime created_at
    }

    HEALTH_RULE {
        string rule_id PK
        string rule_type
        string default_severity
    }

    RULE_VERSION {
        string rule_id FK
        int version
        string definition_hash
        datetime activated_at
    }

    SUPPRESSION {
        string suppression_id PK
        string tenant_id
        string scope_type
        string scope_id
        datetime expires_at
    }
```

## Connectivity Loss Decision Flow

```mermaid
flowchart TD
    Start["Heartbeat missing beyond threshold"] --> Fresh{"Is ingest pipeline fresh<br/>for tenant and region?"}
    Fresh -- "No" --> Platform["Mark platform freshness degraded<br/>suppress customer endpoint alert"]
    Fresh -- "Yes" --> Metadata{"Agent active and expected<br/>to report telemetry?"}
    Metadata -- "No" --> NoAlert["No alert<br/>decommissioned, uninstalled, or excluded"]
    Metadata -- "Yes" --> Scope{"Many agents affected<br/>same site or tenant?"}
    Scope -- "Yes" --> Grouped["Create grouped connectivity incident"]
    Scope -- "No" --> Single["Create per-agent connectivity alert"]
    Grouped --> Evidence["Attach evidence and freshness timestamps"]
    Single --> Evidence
```

## Deployment Topology

```mermaid
flowchart TB
    subgraph IaC["Terraform"]
        Cloud["Cloud Resources<br/>networking, IAM, streams, stores"]
    end

    subgraph CICD["CI/CD"]
        GH["GitHub Actions<br/>test, scan, build"]
        Argo["ArgoCD<br/>sync and promote"]
        Helm["Helm Charts"]
    end

    subgraph K8S_A["Kubernetes Region A"]
        IngestA["Ingestion Gateway"]
        ProcA["Stream Processors"]
        APIA["Health APIs"]
    end

    subgraph K8S_B["Kubernetes Region B"]
        IngestB["Ingestion Gateway"]
        ProcB["Stream Processors"]
        APIB["Health APIs"]
    end

    subgraph Shared["Shared / Replicated Services"]
        Stream["Kafka / Managed Stream"]
        State["State Store"]
        AlertStore["Alert Store"]
        Lake["Object Storage"]
        Obs["Observability"]
    end

    GH --> Helm --> Argo
    IaC --> Shared
    Argo --> K8S_A
    Argo --> K8S_B
    IngestA --> Stream
    IngestB --> Stream
    Stream --> ProcA
    Stream --> ProcB
    ProcA --> State
    ProcB --> State
    ProcA --> AlertStore
    ProcB --> AlertStore
    Stream --> Lake
    K8S_A --> Obs
    K8S_B --> Obs
```

## Rollout Sequence

```mermaid
gantt
    title Singularity Health Center Rollout
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d

    section Design
    Architecture and event contract       :a1, 2026-07-01, 21d

    section Platform
    Ingestion and raw stream              :b1, after a1, 28d
    Normalization and state service       :b2, after b1, 28d

    section Detection
    Rule engine in shadow mode            :c1, after b2, 28d
    Alert orchestration                   :c2, after c1, 21d

    section Product
    Console preview                       :d1, after c1, 35d
    Notifications and integrations        :d2, after c2, 28d

    section Launch
    Private preview                       :e1, after d1, 28d
    GA readiness and rollout              :e2, after e1, 21d
```

