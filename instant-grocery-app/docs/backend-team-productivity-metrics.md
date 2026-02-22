# Backend Engineering Productivity Metrics — Instant Grocery Delivery

**Context:** Blinkit-scale platform · 40 dark stores · 100k orders/day · 7 microservices
**Reference:** DORA State of DevOps · SPACE Framework (Forsgren et al.)

---

## The Four Layers of Productivity

```mermaid
graph TD
    L1["Layer 1: Delivery Speed<br/>DORA Metrics"]
    L2["Layer 2: Flow Metrics<br/>Where time actually goes"]
    L3["Layer 3: System & Code Quality<br/>What you're shipping"]
    L4["Layer 4: Team Health<br/>Sustainability signals"]

    L1 --> L2 --> L3 --> L4

    style L1 fill:#0f3460,color:#fff
    style L2 fill:#533483,color:#fff
    style L3 fill:#16213e,color:#fff
    style L4 fill:#1a1a2e,color:#fff
```

---

## Layer 1: DORA Metrics

The four metrics that predict both engineering performance and business outcomes.

```mermaid
quadrantChart
    title DORA Performance Levels
    x-axis Low Frequency --> High Frequency
    y-axis Slow Recovery --> Fast Recovery
    quadrant-1 Elite
    quadrant-2 High
    quadrant-3 Low
    quadrant-4 Medium
    Elite Team: [0.95, 0.95]
    High Performer: [0.75, 0.7]
    Medium Performer: [0.45, 0.4]
    Low Performer: [0.2, 0.2]
```

| Metric | What It Measures | Elite Benchmark | Red Flag |
|---|---|---|---|
| **Deployment Frequency** | How often each service ships to production | Multiple times/day per service | < once/month |
| **Lead Time for Changes** | Commit → production time | < 1 hour | > 1 month |
| **Change Failure Rate** | % of deploys causing incidents/rollbacks | < 5% | > 15% |
| **MTTR** | Time to restore service after failure | < 1 hour | > 1 week |

### Grocery Platform Context

At this scale, each of the 7 services should deploy independently:

| Service | Deploy Risk | Expected Frequency | Key Gate |
|---|---|---|---|
| Order Service | High — payment + inventory path | Daily with feature flags | All order placement tests green |
| Inventory Service | High — Redis + Kafka coupling | Daily | Lua script contract tests |
| Catalog Service | Low — read-heavy, cacheable | Multiple times/day | Search latency regression test |
| Dispatch Service | Medium — geospatial + Kafka | Daily | Rider assignment integration test |
| ETA Service | Low | Multiple times/day | ETA accuracy smoke test |
| Notification Service | Low — async, fire-and-forget | Multiple times/day | Delivery rate check |
| User Service | Low | Multiple times/day | Auth flow smoke test |

> Track DORA metrics **per service**, not fleet-wide. A slow Dispatch release cadence hidden behind a fast Catalog deploy is a risk signal.

---

## Layer 2: Flow Metrics — Where Work Gets Stuck

### PR Lifecycle Breakdown

```mermaid
flowchart LR
    C["Code Written<br/>(Coding Time)"]
    PR["PR Opened<br/>(Review Pickup Time)"]
    R["First Review<br/>(Review-to-Merge Time)"]
    M["Merged"]
    D["Deployed<br/>(Deploy Time)"]

    C -->|"Target: < 1 day"| PR
    PR -->|"Target: < 4 hours"| R
    R -->|"Target: < 8 hours"| M
    M -->|"Target: < 1 hour"| D

    style C fill:#0f3460,color:#fff
    style PR fill:#533483,color:#fff
    style R fill:#533483,color:#fff
    style M fill:#16213e,color:#fff
    style D fill:#1a1a2e,color:#fff
```

### Flow Metrics Reference

| Metric | Target | Red Flag | Notes |
|---|---|---|---|
| **Cycle Time** (PR open → deployed) | < 1 day | > 3 days | Measure per service |
| **PR Size** | < 400 lines | > 800 lines | Large PRs hide bugs in Kafka schema changes |
| **Review Pickup Time** | < 4 hours | > 24 hours | Blocks on-call rotation knowledge transfer |
| **Work In Progress per engineer** | ≤ 2 items | > 3 items | Microservice context switching is expensive |
| **Sprint Goal Attainment** | > 80% | < 60% two sprints in a row | Investigate unplanned work ratio |

### WIP vs Throughput

```mermaid
xychart-beta
    title "WIP vs Throughput — Little's Law"
    x-axis ["1 item", "2 items", "3 items", "4 items", "5 items", "6 items"]
    y-axis "Relative Throughput" 0 --> 100
    line [95, 90, 75, 55, 35, 20]
```

> Engineers switching between Order Service and Dispatch Service lose significant context. Prefer WIP=1 on high-risk services.

---

## Layer 3: System & Code Quality

### Pre-merge and Post-deploy Signals

```mermaid
graph LR
    subgraph "Pre-merge gates"
        A["Test Coverage<br/>Target: > 80% on critical paths"]
        B["PR Size<br/>Target: < 400 lines"]
        C["CI Duration<br/>Target: < 10 min"]
        D["Flaky Test Rate<br/>Target: < 2%"]
        E["Kafka schema compatibility<br/>Backward-compatible only"]
    end

    subgraph "Post-deploy signals"
        F["P99 API Latency per endpoint"]
        G["5xx Error Rate per service"]
        H["Kafka Consumer Lag"]
        I["Redis Memory Usage %"]
    end

    A & B & C & D & E --> MERGE["Merge to Main"]
    MERGE --> F & G & H & I
```

### Service-Specific SLA Targets

These come directly from the system design non-functional requirements. Any regression triggers a rollback.

| Service | Endpoint / Signal | SLA | Alert Threshold |
|---|---|---|---|
| Order Service | `POST /orders` p99 latency | < 500ms | > 800ms |
| Inventory Service | Reservation failure rate | < 1% | > 1% |
| Catalog Service | `GET /catalog/search` p99 latency | < 200ms | > 300ms |
| Catalog Service | `GET /catalog/autocomplete` p99 latency | < 10ms | > 25ms |
| Dispatch Service | Rider assignment p99 latency | < 2s | > 3s |
| Dispatch Service | Rider assignment success rate | > 95% | < 95% |
| ETA Service | Pre-checkout ETA p99 latency | < 100ms | > 150ms |
| All services | 5xx error rate | < 0.1% | > 0.5% |

### Kafka Consumer Health

Kafka lag is the most important operational signal after HTTP latency. Lag spikes directly degrade delivery SLA.

| Consumer Group | Topic | Lag Alert | Impact if breached |
|---|---|---|---|
| `dispatch-workers` | `order.placed` | > 500 msgs | Riders assigned late → SLA breach |
| `inventory-workers` | `order.delivered` | > 1,000 msgs | Stock counts drift from reality |
| `notification-workers` | `rider.assigned` | > 200 msgs | Customer not notified of rider |
| `analytics-pipeline` | `order.delivered` | > 10,000 msgs | Reporting lag — no operational impact |

```mermaid
flowchart TD
    LAG{"Kafka lag > threshold?"}
    LAG -->|dispatch-workers| D1["Page on-call immediately<br/>SLA impact in < 30s"]
    LAG -->|inventory-workers| D2["Alert ops team<br/>Stock accuracy degrades"]
    LAG -->|notification-workers| D3["Alert within 5 min<br/>Customer experience impact"]
    LAG -->|analytics-pipeline| D4["Slack alert only<br/>No operational impact"]

    style D1 fill:#e94560,color:#fff
    style D2 fill:#533483,color:#fff
    style D3 fill:#533483,color:#fff
    style D4 fill:#16213e,color:#fff
```

### Redis Health

| Signal | Alert Threshold | Action |
|---|---|---|
| `redis_memory_usage_pct` (Inventory) | > 80% | Scale Redis, audit key TTLs |
| `redis_memory_usage_pct` (ETA/GEO) | > 70% | Rider location data growing — check GPS update rate |
| Key eviction rate | > 0 evictions/min on Inventory Redis | **Page immediately** — oversell risk |
| Inventory Redis replication lag | > 1s | Check Sentinel, promote replica if needed |

> Set `maxmemory-policy noeviction` on the Inventory Redis instance. Silent key eviction = silent oversell.

---

## Layer 4: Team Health & Sustainability

```mermaid
flowchart TD
    TH["Team Health Signals"]

    TH --> UW["Unplanned Work %<br/>Reactive vs planned ratio<br/>Red flag: > 30%"]
    TH --> OC["Oncall Incident Frequency<br/>Pages per engineer per week<br/>Red flag: > 3/week"]
    TH --> ML["Meeting Load<br/>Hours per week<br/>Red flag: > 30% of work hours"]
    TH --> BF["Bus Factor<br/>Engineers who own each service<br/>Red flag: single-owner services"]
    TH --> RD["Reviewer Distribution<br/>Are 2 engineers reviewing everything?<br/>Signal: bottleneck + silo"]
    TH --> OB["Time to First Meaningful PR<br/>Days for new hire<br/>Measures: docs + DX health"]

    style TH fill:#0f3460,color:#fff
    style UW fill:#533483,color:#fff
    style OC fill:#e94560,color:#fff
    style ML fill:#533483,color:#fff
    style BF fill:#e94560,color:#fff
    style RD fill:#533483,color:#fff
    style OB fill:#16213e,color:#fff
```

### Oncall Load by Team

At this scale, three teams share oncall responsibility:

| Team | Owns | Expected Incidents/Week | Red Flag |
|---|---|---|---|
| **Order Platform** | Order Service, Payment reconciliation | 2–4 | > 8/week |
| **Fulfillment** | Inventory Service, Dispatch Service, ETA | 3–6 | > 10/week |
| **Catalog & Search** | Catalog Service, Elasticsearch | 0–2 | > 5/week |

### Oncall Burnout Signal

```mermaid
xychart-beta
    title "Oncall Pages per Week vs Burnout Risk"
    x-axis ["0-1", "2-3", "4-5", "6-7", "8+"]
    y-axis "Burnout Risk Score" 0 --> 100
    bar [10, 25, 50, 75, 95]
```

> Fulfillment team carries highest oncall burden. Protect them. If `orders_in_picking_gt_8min` > 5 becomes a weekly page, run a reliability sprint.

### Grocery Platform — Common Unplanned Work Sources

| Source | Typical % of sprint | Fix |
|---|---|---|
| Dark store network outages causing stuck orders | 5–10% | Offline-first tablet + ops auto-escalation |
| Rider GPS stale causing manual dispatch | 3–8% | Improve rider app reliability, STALE_GPS auto-recovery |
| Redis memory alerts during festive peaks | 2–5% | Pre-scale Redis before peak events |
| Elasticsearch index corruption (one store) | 1–3% | Blue/green alias pattern on index rebuild |
| Payment reconciliation job failures | 2–4% | Idempotent job + alerting at stuck PAYMENT_PENDING > 15 min |

---

## What NOT to Measure

```mermaid
flowchart LR
    BAD["Harmful Metrics"]

    BAD --> LC["Lines of Code Written<br/>Incentivises bloat"]
    BAD --> NC["Number of Commits<br/>Incentivises meaningless micro-commits"]
    BAD --> TC["Tickets Closed<br/>Incentivises cherry-picking easy work"]
    BAD --> IV["Individual Velocity Comparison<br/>Destroys psychological safety"]
    BAD --> HW["Hours Worked<br/>Measures presence, not output"]

    style BAD fill:#e94560,color:#fff
    style LC fill:#1a1a2e,color:#fff
    style NC fill:#1a1a2e,color:#fff
    style TC fill:#1a1a2e,color:#fff
    style IV fill:#1a1a2e,color:#fff
    style HW fill:#1a1a2e,color:#fff
```

---

## The SPACE Framework Applied

```mermaid
mindmap
  root((SPACE))
    Satisfaction and Wellbeing
      Oncall load per engineer
      Sprint goal attainment
      Attrition intent surveys
    Performance
      Order placement p99 latency
      Delivery SLA success rate
      5xx error rate per service
    Activity
      Deploys per service per week
      PRs merged per engineer
      Kafka consumer lag trend
    Communication and Collaboration
      PR reviewer distribution
      ADR authorship spread
      Cross-team incident response time
    Efficiency and Flow
      PR cycle time
      WIP per engineer
      CI build duration
```

> No single metric captures productivity. For this platform, the most honest picture comes from: **DORA + SLA compliance + Kafka lag + oncall load**.

---

## Metrics Rollout Sequence

```mermaid
timeline
    title Instrumentation Rollout — Grocery Platform
    Week 1-2 : Deployment Frequency per service
             : MTTR
             : Are you shipping and recovering fast?
    Week 3-4 : Order placement p99 latency
             : Kafka consumer lag per group
             : Are the critical paths healthy?
    Week 5-6 : Change Failure Rate
             : 5xx error rate per service
             : Are deploys causing regressions?
    Week 7-8 : Unplanned Work percentage
             : Oncall incident frequency per team
             : Are you in control of your roadmap?
    Week 9-10 : Redis memory + key eviction alerts
              : Rider assignment success rate
              : Are long-tail operational risks managed?
```

---

## Metric → Action Decision Tree

```mermaid
flowchart TD
    START["Metric Trending Negative"]
    START --> Q1{Which layer?}

    Q1 -->|Delivery Speed| A1{Deploy frequency low?}
    A1 -->|Yes| A2["Check: CI pipeline, approval gates,<br/>feature flag rollout process"]
    A1 -->|No| A3{Lead time high?}
    A3 -->|Yes| A4["Check: PR size, review pickup time,<br/>WIP limit breaches"]

    Q1 -->|System Quality| B1{Which SLA breached?}
    B1 -->|Order placement p99| B2["Check: Inventory gRPC latency,<br/>Payment Service p99, Redis Lua time"]
    B1 -->|Kafka consumer lag| B3["Check: consumer scaling,<br/>DLQ backlog, partition assignment"]
    B1 -->|Search latency| B4["Check: Elasticsearch GC pauses,<br/>index shard health, cache hit rate"]

    Q1 -->|Team Health| C1{Unplanned work > 30%?}
    C1 -->|Yes| C2["Triage top interrupt sources,<br/>add 20% buffer in sprint planning"]
    C1 -->|No| C3{Oncall > threshold?}
    C3 -->|Yes| C4["Reliability sprint: fix top 3<br/>recurring incident triggers"]
```

---

## Quick Reference Card

```mermaid
graph TD
    subgraph "Green Zone"
        G1["Deploy freq: Daily per service"]
        G2["Order p99: < 500ms"]
        G3["Search p99: < 200ms"]
        G4["Kafka dispatch lag: < 100 msgs"]
        G5["CFR: < 5%"]
        G6["MTTR: < 1 hour"]
        G7["Oncall: < 3 pages/week/engineer"]
    end

    subgraph "Yellow Zone — Investigate"
        Y1["Deploy freq: Weekly"]
        Y2["Order p99: 500ms–800ms"]
        Y3["Search p99: 200ms–300ms"]
        Y4["Kafka dispatch lag: 100–500 msgs"]
        Y5["CFR: 5–10%"]
        Y6["MTTR: 1–24 hours"]
        Y7["Oncall: 3–6 pages/week/engineer"]
    end

    subgraph "Red Zone — Intervene Now"
        R1["Deploy freq: Monthly or less"]
        R2["Order p99: > 800ms"]
        R3["Search p99: > 300ms"]
        R4["Kafka dispatch lag: > 500 msgs"]
        R5["CFR: > 15%"]
        R6["MTTR: > 24 hours"]
        R7["Oncall: > 6 pages/week/engineer"]
    end
```

---

*Reference: DORA State of DevOps Report · SPACE Framework (Forsgren et al., 2021) · Flow Engineering · System design SLAs from `docs/plans/2026-02-22-instant-grocery-system-design.md`*
