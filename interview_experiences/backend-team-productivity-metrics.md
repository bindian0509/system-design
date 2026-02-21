# Backend Engineering Team — Developer Productivity Metrics

---

## The Four Layers of Productivity

```mermaid
graph TD
    L1["Layer 1: Delivery Speed<br/>DORA Metrics"]
    L2["Layer 2: Flow Metrics<br/>Where time actually goes"]
    L3["Layer 3: Code & System Quality<br/>What you're shipping"]
    L4["Layer 4: Team Health<br/>Sustainability signals"]

    L1 --> L2 --> L3 --> L4

    style L1 fill:#0f3460,color:#fff
    style L2 fill:#533483,color:#fff
    style L3 fill:#16213e,color:#fff
    style L4 fill:#1a1a2e,color:#fff
```

---

## Layer 1: DORA Metrics — Industry Standard Benchmarks

The four metrics from Google's DevOps Research that predict both team performance and business outcomes.

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
| **Deployment Frequency** | How often you ship to production | Multiple times/day | < once/month |
| **Lead Time for Changes** | Commit → production time | < 1 hour | > 1 month |
| **Change Failure Rate** | % of deploys causing incidents/rollbacks | < 5% | > 15% |
| **Mean Time to Recovery (MTTR)** | Time to restore service after failure | < 1 hour | > 1 week |

> Start here before any custom metrics. These four are externally benchmarkable and have 7+ years of research behind them.

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

| Metric | What It Signals | Target |
|---|---|---|
| **Cycle Time** | PR open → deployed | < 1 day |
| **PR Size** | Lines changed per PR | < 400 lines |
| **PR Review Pickup Time** | Time to first review after opening | < 4 hours |
| **Work In Progress (WIP)** | Active items per engineer | ≤ 2 per engineer |
| **Throughput** | Stories closed per sprint per engineer | Trend, not absolute |
| **Sprint Goal Attainment** | % of committed scope delivered | > 80% consistently |

### WIP vs. Throughput Trade-off

```mermaid
xychart-beta
    title "WIP vs Throughput — Little's Law"
    x-axis ["1 item", "2 items", "3 items", "4 items", "5 items", "6 items"]
    y-axis "Relative Throughput" 0 --> 100
    line [95, 90, 75, 55, 35, 20]
```

> High WIP = context switching = slower delivery. Throughput peaks when engineers carry 1–2 items at a time.

---

## Layer 3: Code & System Quality

```mermaid
graph LR
    subgraph "Pre-merge signals"
        A["Test Coverage %<br/>Target: > 80% on critical paths"]
        B["PR Size<br/>Target: < 400 lines"]
        C["CI Duration<br/>Target: < 10 min"]
        D["Flaky Test Rate<br/>Target: < 2%"]
        E["Technical Debt Ratio<br/>Via SonarQube / static analysis"]
    end

    subgraph "Post-deploy signals"
        F["P95 / P99 API Latency"]
        G["5xx Error Rate"]
        H["Code Churn<br/>% rewritten within 2 weeks"]
        I["Change Failure Rate"]
    end

    A & B & C & D & E --> MERGE["Merge to Main"]
    MERGE --> F & G & H & I
```

| Metric | Why It Matters |
|---|---|
| **Test Coverage %** | Confidence floor for changes in critical paths |
| **Flaky Test Rate** | Unreliable tests erode CI trust — engineers start ignoring failures |
| **CI Build Duration** | Slow CI breaks flow state; > 10 min causes context switching |
| **P95/P99 API Latency** | Direct quality signal tied to backend work |
| **5xx Error Rate** | Measures production stability post-deploy |
| **Technical Debt Ratio** | Remediation cost vs. development cost — flags long-term drag |
| **Code Churn** | High churn = rework = unclear requirements or poor design |

---

## Layer 4: Team Health & Sustainability

These are **leading indicators** — they predict delivery degradation before it shows up in DORA metrics.

```mermaid
flowchart TD
    TH["Team Health Signals"]

    TH --> UW["Unplanned Work %<br/>Reactive vs planned work ratio<br/>Red flag: > 30%"]
    TH --> OC["Oncall Incident Frequency<br/>Pages per engineer per week<br/>Red flag: > 3/week"]
    TH --> ML["Meeting Load<br/>Hours in meetings per week<br/>Red flag: > 30% of work hours"]
    TH --> BF["Bus Factor<br/>Engineers who can work each service<br/>Red flag: single-owner services"]
    TH --> PR["PR Reviewer Distribution<br/>Are same 2 people reviewing everything?<br/>Signal: bottleneck + knowledge silo"]
    TH --> OB["Time to Onboard<br/>Days until first meaningful PR<br/>Measures: docs + codebase health"]

    style TH fill:#0f3460,color:#fff
    style UW fill:#533483,color:#fff
    style OC fill:#e94560,color:#fff
    style ML fill:#533483,color:#fff
    style BF fill:#e94560,color:#fff
    style PR fill:#533483,color:#fff
    style OB fill:#16213e,color:#fff
```

### Oncall Load as a Burnout Predictor

```mermaid
xychart-beta
    title "Oncall Incidents per Week vs. Burnout Risk"
    x-axis ["0-1", "2-3", "4-5", "6-7", "8+"]
    y-axis "Burnout Risk Score" 0 --> 100
    bar [10, 25, 50, 75, 95]
```

---

## What NOT to Measure

These are commonly tracked but actively harmful to team culture and output quality:

```mermaid
flowchart LR
    BAD["Harmful Metrics"]

    BAD --> LC["Lines of Code Written<br/>→ Incentivises bloat & copy-paste"]
    BAD --> NC["Number of Commits<br/>→ Incentivises meaningless micro-commits"]
    BAD --> TC["Tickets Closed<br/>→ Incentivises cherry-picking easy work"]
    BAD --> IV["Individual Velocity Comparison<br/>→ Destroys psychological safety"]
    BAD --> HW["Hours Worked<br/>→ Measures presence, not output"]

    style BAD fill:#e94560,color:#fff
    style LC fill:#1a1a2e,color:#fff
    style NC fill:#1a1a2e,color:#fff
    style TC fill:#1a1a2e,color:#fff
    style IV fill:#1a1a2e,color:#fff
    style HW fill:#1a1a2e,color:#fff
```

---

## The SPACE Framework

Developed by GitHub & Microsoft researchers as a multi-dimensional alternative to single-metric productivity.

```mermaid
mindmap
  root((SPACE))
    Satisfaction & Wellbeing
      Engineer happiness surveys
      Burnout signals
      Attrition intent
    Performance
      System reliability
      Error rates
      Customer outcomes
    Activity
      PRs merged
      Deploys shipped
      Volume signals
    Communication & Collaboration
      PR review patterns
      Knowledge sharing
      Cross-team contributions
    Efficiency & Flow
      Cycle time
      WIP limits
      Interruption frequency
```

> **Key insight:** No single metric captures productivity. You need signals from at least 3–4 SPACE dimensions to get an honest picture.

---

## Priority Order — Where to Start

If instrumenting from scratch, roll out in this sequence:

```mermaid
timeline
    title Metrics Rollout Sequence
    Week 1-2 : Deployment Frequency
             : MTTR
             : Are you shipping and recovering fast?
    Week 3-4 : Lead Time
             : PR Cycle Time
             : Where is work getting stuck?
    Week 5-6 : Change Failure Rate
             : 5xx Error Rate
             : Are you shipping quality?
    Week 7-8 : Unplanned Work Percentage
             : Are you in control of your roadmap?
    Week 9-10 : Oncall Load
              : Flaky Test Rate
              : Is the team sustainable long-term?
```

---

## Metric → Action Decision Tree

```mermaid
flowchart TD
    START[Metric Trending Negative]

    START --> Q1{Which layer?}

    Q1 -->|Delivery Speed| A1{Deployment frequency low?}
    A1 -->|Yes| A2[Check: CI/CD pipeline, approval gates, release process]
    A1 -->|No| A3{Lead time high?}
    A3 -->|Yes| A4[Check: PR size, review pickup time, WIP]

    Q1 -->|Flow| B1{Cycle time high?}
    B1 -->|Yes| B2[Break down: coding vs review vs deploy time]
    B2 --> B3[Fix the slowest stage first]

    Q1 -->|Quality| C1{Error rate rising?}
    C1 -->|Yes| C2[Check: test coverage, flaky tests, PR size]
    C1 -->|No| C3{Churn rising?}
    C3 -->|Yes| C4[Check: requirements clarity, design review process]

    Q1 -->|Team Health| D1{Unplanned work > 30%?}
    D1 -->|Yes| D2[Triage interrupt sources, add buffer in sprint planning]
    D1 -->|No| D3{Oncall > 3 pages/week?}
    D3 -->|Yes| D4[Reliability sprint: fix top incident causes]
```

---

## Quick Reference Card

```mermaid
graph TD
    subgraph "Green Zone"
        G1["Deploy freq: Daily+"]
        G2["Lead time: < 1 day"]
        G3["CFR: < 5%"]
        G4["MTTR: < 1 hour"]
        G5["PR size: < 400 lines"]
        G6["Unplanned work: < 20%"]
    end

    subgraph "Yellow Zone — Investigate"
        Y1["Deploy freq: Weekly"]
        Y2["Lead time: 1-7 days"]
        Y3["CFR: 5-10%"]
        Y4["MTTR: 1-24 hours"]
        Y5["PR size: 400-800 lines"]
        Y6["Unplanned work: 20-30%"]
    end

    subgraph "Red Zone — Intervene Now"
        R1["Deploy freq: Monthly or less"]
        R2["Lead time: > 1 week"]
        R3["CFR: > 15%"]
        R4["MTTR: > 24 hours"]
        R5["PR size: 800+ lines"]
        R6["Unplanned work: > 30%"]
    end
```

---

*Reference: DORA State of DevOps Report · SPACE Framework (Forsgren et al.) · Flow Engineering (Value Stream Mapping)*
