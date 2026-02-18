# Distributed Task Scheduler — Deep Dive

Scheduling is a **coordination problem, not a timing problem.** Single-server cron is trivial — write a crontab entry and walk away. But distributed scheduling with exactly-once execution, high availability, missed-fire recovery, and millions of tasks across a fleet of workers is deceptively hard. When your cron server dies at 11:59 PM and end-of-day reconciliation never runs, you discover that the simplest problems in computing become the hardest when you add "distributed" in front of them.

---

## The Problem — Why Cron Breaks at Scale

A single cron server works until it doesn't. It's a single point of failure with no high availability, no horizontal scaling, no visibility into what ran or failed, no retry mechanism, and no dead letter queue for poison tasks. When the cron server goes down, tasks silently don't run — and in fintech, that means reconciliation doesn't happen, statements don't generate, and interest doesn't calculate.

```mermaid
flowchart TB
    subgraph fragile ["❌ Single-Server Cron"]
        direction TB
        CRON["Cron Daemon<br/>(Single Server)"]
        CRON --> J1["Job 1: EOD Recon"]
        CRON --> J2["Job 2: Statements"]
        CRON --> J3["Job 3: Interest Calc"]
        CRON --> SPOF["💥 Server dies at 11:59 PM<br/>All jobs missed<br/>No retry, no alert, no recovery"]
    end

    subgraph resilient ["✅ Distributed Task Scheduler"]
        direction TB
        SCHED["Scheduler Cluster<br/>(HA, leader-elected)"]
        SCHED --> W1["Worker 1"]
        SCHED --> W2["Worker 2"]
        SCHED --> W3["Worker 3"]
        W1 --> R1["EOD Recon ✅"]
        W2 --> R2["Statements ✅"]
        W3 --> R3["Interest Calc ✅"]
        SCHED --> DLQ["DLQ + Retry<br/>Failed tasks recovered"]
    end

    style SPOF fill:#f44336,color:#fff
    style CRON fill:#ffebee
    style SCHED fill:#4CAF50,color:#fff
    style DLQ fill:#FF9800,color:#fff
```

### Capability Comparison

| Capability | Single-Server Cron | Distributed Task Scheduler |
|------------|-------------------|---------------------------|
| **High availability** | ❌ SPOF — server dies, jobs stop | ✅ Leader failover, standby promotion |
| **Horizontal scaling** | ❌ One machine, limited CPU/memory | ✅ Add workers to scale throughput |
| **Exactly-once execution** | ❌ No guarantee — may run twice after restart | ✅ Distributed locks + fencing tokens |
| **Retry / DLQ** | ❌ None — failed jobs vanish | ✅ Configurable retry + dead letter queue |
| **Monitoring & alerting** | ❌ Check logs manually | ✅ Metrics, dashboards, alerts |
| **Priority scheduling** | ❌ All jobs equal | ✅ Priority lanes, preemption |
| **Multi-tenant isolation** | ❌ Not applicable | ✅ Tenant-level fairness and quotas |
| **Missed-fire recovery** | ❌ Missed jobs are gone | ✅ Configurable catch-up policies |

---

## What is a Distributed Task Scheduler?

A distributed task scheduler coordinates the execution of tasks across a cluster of machines, ensuring tasks run on time, at most once (or exactly once), with fault tolerance and visibility. It has four core components: the **Scheduler** (brain), the **Worker Pool** (muscle), the **Task Store** (memory), and the **Dead Letter Queue** (safety net).

```mermaid
flowchart TB
    CLIENT["API / Client<br/>Submit & manage tasks"]
    CLIENT --> SCHED

    subgraph core ["Distributed Task Scheduler"]
        direction TB
        SCHED["Scheduler<br/>(Leader-elected)<br/>Polls, assigns, orchestrates"]
        STORE[("Task Store<br/>(PostgreSQL / Redis)<br/>Task definitions, state, history")]
        SCHED --> STORE
        STORE --> SCHED

        subgraph workers ["Worker Pool"]
            W1["Worker 1"]
            W2["Worker 2"]
            W3["Worker 3"]
        end

        SCHED --> workers
        workers --> DLQ["Dead Letter Queue<br/>Failed tasks after max retries"]
    end

    workers --> MONITOR["Monitoring & Alerting<br/>(Prometheus + Grafana)"]
    DLQ --> MONITOR

    style SCHED fill:#2196F3,color:#fff
    style STORE fill:#4CAF50,color:#fff
    style DLQ fill:#f44336,color:#fff
    style MONITOR fill:#FF9800,color:#fff
```

### Component Responsibilities

| Component | Responsibility | Technology Examples |
|-----------|---------------|-------------------|
| **Scheduler** | Polls task store for due tasks, assigns to workers, handles missed fires | Quartz Scheduler, Temporal Server, Airflow Scheduler |
| **Worker Pool** | Executes assigned tasks, reports status, sends heartbeats | Celery workers, Temporal workers, K8s Jobs |
| **Task Store** | Persists task definitions, schedules, state, execution history | PostgreSQL, MySQL, Redis, DynamoDB |
| **Dead Letter Queue** | Captures tasks that exceed max retries for manual investigation | Kafka DLQ topic, SQS DLQ, database table |
| **Monitoring** | Tracks queue depth, execution latency, failure rates, scheduler health | Prometheus, Grafana, PagerDuty |

---

## Task Lifecycle — State Machine

Every task moves through a well-defined set of states. Understanding this state machine is essential for reasoning about failure modes and recovery.

```mermaid
stateDiagram-v2
    [*] --> PENDING : Task submitted

    PENDING --> SCHEDULED : Scheduler picks up task<br/>at trigger time
    SCHEDULED --> ASSIGNED : Worker selected<br/>lock acquired
    ASSIGNED --> RUNNING : Worker begins execution

    RUNNING --> SUCCESS : Execution completed
    RUNNING --> FAILED : Execution threw error
    RUNNING --> TIMED_OUT : Heartbeat missed /<br/>deadline exceeded

    FAILED --> RETRY : Retries remaining > 0
    TIMED_OUT --> RETRY : Retries remaining > 0

    RETRY --> SCHEDULED : Backoff elapsed,<br/>re-enter scheduling

    FAILED --> DEAD_LETTERED : Max retries exhausted
    TIMED_OUT --> DEAD_LETTERED : Max retries exhausted

    SUCCESS --> [*]
    DEAD_LETTERED --> [*]

    PENDING : Waiting for trigger time
    SCHEDULED : Due for execution
    ASSIGNED : Locked to a worker
    RUNNING : Worker executing
    SUCCESS : Completed successfully
    FAILED : Execution error
    TIMED_OUT : No heartbeat / deadline
    RETRY : Awaiting retry with backoff
    DEAD_LETTERED : Permanently failed
```

### Happy Path — Scheduler to Worker to Success

```mermaid
sequenceDiagram
    participant Store as Task Store
    participant Sched as Scheduler
    participant Worker as Worker

    Sched->>Store: Poll: tasks WHERE status = PENDING<br/>AND trigger_time <= NOW
    Store-->>Sched: Task T-42 (EOD Reconciliation)

    Sched->>Store: UPDATE T-42 SET status = SCHEDULED
    Sched->>Worker: Assign T-42

    Worker->>Store: UPDATE T-42 SET status = RUNNING,<br/>worker_id = W-3, fence_token = 17
    Worker->>Worker: Execute EOD Reconciliation

    loop Every 10s
        Worker->>Store: Heartbeat: T-42, worker W-3
    end

    Worker->>Store: UPDATE T-42 SET status = SUCCESS,<br/>completed_at = NOW
    Store-->>Sched: T-42 complete
```

### State Descriptions

| State | Meaning | Valid Transitions | Trigger |
|-------|---------|-------------------|---------|
| **PENDING** | Task submitted, waiting for trigger time | SCHEDULED | Trigger time reached |
| **SCHEDULED** | Due for execution, awaiting worker assignment | ASSIGNED | Scheduler assigns worker |
| **ASSIGNED** | Locked to a specific worker | RUNNING | Worker begins execution |
| **RUNNING** | Worker is actively executing | SUCCESS, FAILED, TIMED_OUT | Execution result / heartbeat miss |
| **SUCCESS** | Completed successfully | Terminal | Worker reports completion |
| **FAILED** | Execution threw an error | RETRY, DEAD_LETTERED | Retry policy evaluation |
| **TIMED_OUT** | Worker missed heartbeat or exceeded deadline | RETRY, DEAD_LETTERED | Scheduler timeout detection |
| **RETRY** | Awaiting retry after backoff | SCHEDULED | Backoff timer elapsed |
| **DEAD_LETTERED** | Permanently failed, requires manual intervention | Terminal | Max retries exhausted |

---

## Scheduling Strategies

Different tasks need different scheduling strategies. A daily EOD reconciliation is time-based, while a post-deposit interest recalculation is event-driven.

```mermaid
flowchart TB
    Q1{What triggers<br/>the task?}
    Q1 -->|Fixed recurring time| CRON["Cron Expression<br/>e.g., 0 0 * * * (midnight daily)"]
    Q1 -->|Fixed interval from last run| INTERVAL["Interval-Based<br/>e.g., every 30 minutes"]
    Q1 -->|External event occurs| EVENT["Event-Driven<br/>e.g., deposit triggers interest calc"]
    Q1 -->|One-time future execution| ONESHOT["One-Shot Delayed<br/>e.g., send reminder in 24h"]
    Q1 -->|Business calendar dependent| CALENDAR["Calendar-Aware<br/>e.g., last business day of month"]

    style CRON fill:#4CAF50,color:#fff
    style INTERVAL fill:#2196F3,color:#fff
    style EVENT fill:#FF9800,color:#fff
    style ONESHOT fill:#9C27B0,color:#fff
    style CALENDAR fill:#9E9E9E,color:#fff
```

### Strategy Comparison

| Strategy | How It Works | Example | Pros | Cons |
|----------|-------------|---------|------|------|
| **Cron expression** | Fires at specific times defined by cron syntax | `0 0 * * *` — midnight daily EOD recon | Precise, well-understood, calendar-aligned | Missed fires need explicit policy |
| **Interval-based** | Fires N seconds/minutes after last completion | Every 5 min: poll payment gateway status | Prevents overlap, self-adjusting | Drift over time, no calendar alignment |
| **Event-driven** | Fires in response to an external event | Deposit webhook triggers interest recalc | Real-time, no polling waste | Requires event infrastructure |
| **One-shot delayed** | Fires once at a future timestamp | Send payment reminder in 48 hours | Simple, one-time use | No recurrence |
| **Calendar-aware** | Fires based on business calendar rules | Last business day of month: statement gen | Handles holidays, weekends | Requires business calendar data |

---

## Task Assignment Strategies

Once the scheduler determines a task is due, it must assign it to a worker. The two fundamental models are **push** (scheduler sends to worker) and **pull** (worker requests work).

```mermaid
flowchart TB
    subgraph push_model ["Push Model — Scheduler Assigns"]
        direction TB
        PS["Scheduler"]
        PS -->|Assign T-1| PW1["Worker 1"]
        PS -->|Assign T-2| PW2["Worker 2"]
        PS -->|Assign T-3| PW3["Worker 3"]
        PS -.->|Must track<br/>worker health| PH["Health Monitor"]
    end

    subgraph pull_model ["Pull Model — Workers Request"]
        direction TB
        PLS["Task Queue"]
        PLW1["Worker 1"] -->|Poll for work| PLS
        PLW2["Worker 2"] -->|Poll for work| PLS
        PLW3["Worker 3"] -->|Poll for work| PLS
    end

    style PS fill:#2196F3,color:#fff
    style PLS fill:#4CAF50,color:#fff
```

### Work Stealing

When workers have uneven load, idle workers can steal tasks from busy workers' local queues. This maximizes utilization without centralized rebalancing.

```mermaid
flowchart LR
    subgraph before ["Before Work Stealing"]
        direction TB
        WA1["Worker A<br/>Queue: T1, T2, T3, T4, T5<br/>🔥 Overloaded"]
        WB1["Worker B<br/>Queue: (empty)<br/>😴 Idle"]
    end

    before --> after

    subgraph after ["After Work Stealing"]
        direction TB
        WA2["Worker A<br/>Queue: T1, T2, T3<br/>✅ Balanced"]
        WB2["Worker B<br/>Queue: T4, T5<br/>✅ Working"]
    end

    style WA1 fill:#f44336,color:#fff
    style WB1 fill:#9E9E9E,color:#fff
    style WA2 fill:#4CAF50,color:#fff
    style WB2 fill:#4CAF50,color:#fff
```

### Assignment Strategy Comparison

| Strategy | How It Works | Pros | Cons | Best For |
|----------|-------------|------|------|----------|
| **Push (round-robin)** | Scheduler cycles through healthy workers | Simple, even distribution | Doesn't account for worker load | Uniform tasks, homogeneous workers |
| **Pull (competing consumers)** | Workers poll a shared queue | Natural load balancing, no scheduler bottleneck | Polling overhead, less control over assignment | Variable task durations, elastic scaling |
| **Consistent hashing** | Task key maps to a specific worker | Data locality, cache affinity | Rebalancing on worker change | Tasks needing local state/cache |
| **Work stealing** | Idle workers steal from busy workers' queues | Maximizes utilization | Complex implementation, contention on queues | Mixed task durations, heterogeneous workers |

---

## Leader Election for Scheduler HA

A single active scheduler avoids duplicate task assignment, but introduces a SPOF. Leader election provides HA: one scheduler is active (leader), others are standby. If the leader dies, a standby is promoted.

### Active-Passive Failover

```mermaid
flowchart TB
    subgraph zk ["ZooKeeper / etcd"]
        LOCK["Ephemeral Lock Node<br/>/scheduler/leader"]
    end

    S1["Scheduler 1<br/>🟢 ACTIVE (Leader)"]
    S2["Scheduler 2<br/>⏸️ STANDBY"]
    S3["Scheduler 3<br/>⏸️ STANDBY"]

    S1 -->|Holds lock| LOCK
    S2 -.->|Watches lock| LOCK
    S3 -.->|Watches lock| LOCK

    S1 -->|"💥 Leader dies"| DEAD["Ephemeral node deleted"]
    DEAD -->|"ZK notifies watchers"| S2
    S2 -->|"Acquires lock → becomes leader"| PROMOTED["Scheduler 2<br/>🟢 ACTIVE (New Leader)"]

    style S1 fill:#4CAF50,color:#fff
    style S2 fill:#9E9E9E,color:#fff
    style S3 fill:#9E9E9E,color:#fff
    style PROMOTED fill:#4CAF50,color:#fff
    style DEAD fill:#f44336,color:#fff
```

### Sharded Scheduler Model

For very high task volumes, a single scheduler becomes a bottleneck. Shard the task space across multiple active schedulers, each owning a partition.

```mermaid
flowchart TB
    subgraph sharded ["Sharded Schedulers — Each Owns a Partition"]
        direction TB
        S1["Scheduler 1<br/>Owns tasks A-F"]
        S2["Scheduler 2<br/>Owns tasks G-M"]
        S3["Scheduler 3<br/>Owns tasks N-Z"]
    end

    S1 --> STORE1[("Task Store<br/>Partition 1")]
    S2 --> STORE2[("Task Store<br/>Partition 2")]
    S3 --> STORE3[("Task Store<br/>Partition 3")]

    S1 --> WP["Shared Worker Pool"]
    S2 --> WP
    S3 --> WP

    style S1 fill:#2196F3,color:#fff
    style S2 fill:#FF9800,color:#fff
    style S3 fill:#9C27B0,color:#fff
```

### Leader Election Approaches

| Approach | Mechanism | Failover Time | Complexity |
|----------|-----------|---------------|------------|
| **ZooKeeper ephemeral nodes** | Leader creates ephemeral znode; watchers get notified on session loss | 1-10 seconds | Medium — requires ZK cluster |
| **etcd lease** | Leader acquires a lease with TTL; lease expiry triggers re-election | 1-15 seconds | Medium — requires etcd cluster |
| **Raft consensus** | Embedded Raft library for leader election among scheduler instances | Sub-second | High — embedded consensus |
| **DB advisory locks** | `SELECT pg_try_advisory_lock(1)` — leader holds a PostgreSQL lock | 10-30 seconds | Low — uses existing database |

---

## Exactly-Once Execution — The Hard Problem

The hardest problem in distributed scheduling is ensuring a task executes **exactly once**. Network partitions make this deceptively difficult: the scheduler assigns a task to Worker A, but the network partitions. Did Worker A execute it? The scheduler can't tell, so it re-assigns to Worker B. Now both execute the same task.

### The Problem and Solution with Fencing Tokens

```mermaid
sequenceDiagram
    participant Sched as Scheduler
    participant Store as Task Store
    participant WA as Worker A
    participant WB as Worker B

    Sched->>Store: Assign T-42 to Worker A<br/>fence_token = 17
    Store-->>WA: Execute T-42 (fence=17)

    Note over WA,Sched: 💥 Network partition<br/>Worker A still running

    Sched->>Sched: Heartbeat timeout for Worker A
    Sched->>Store: Re-assign T-42 to Worker B<br/>fence_token = 18
    Store-->>WB: Execute T-42 (fence=18)

    Note over WA: Partition heals<br/>Worker A tries to write result

    WA->>Store: Complete T-42 (fence=17)
    Store--xWA: REJECTED — fence_token 17 < current 18

    WB->>Store: Complete T-42 (fence=18)
    Store-->>WB: ACCEPTED — fence_token matches

    Note over Store: Exactly-once achieved via fencing
```

### Exactly-Once Mechanisms

| Mechanism | How It Works | Guarantees | Limitation |
|-----------|-------------|------------|------------|
| **Fencing tokens** | Monotonically increasing token assigned per assignment; store rejects stale tokens | Prevents zombie workers from writing results | Requires all downstream writes to check token |
| **Distributed lock (lease)** | Worker acquires a time-bounded lock; lock expires if worker dies | Prevents concurrent execution | Clock skew can cause dual execution during lease boundary |
| **Heartbeat + timeout** | Worker sends periodic heartbeats; scheduler re-assigns after timeout | Detects dead workers | Timeout too short = false re-assignment; too long = delayed recovery |
| **Idempotent execution** | Task handler is designed to be safely re-executed | Duplicates are harmless | Requires careful handler design — not always possible |

**Cross-reference:** [Idempotency](./idempotency.md) — idempotency is the safety net when exactly-once coordination fails.

---

## Failure Handling & Retry

Workers fail. Tasks fail. Networks fail. A robust scheduler must detect failures quickly, retry intelligently, and route poison pills to the dead letter queue.

```mermaid
flowchart TB
    FAIL["Task Execution Failed"] --> RETRYABLE{Retryable<br/>error?}

    RETRYABLE -->|No — permanent failure<br/>e.g., invalid input| DLQ["Dead Letter Queue<br/>Manual investigation"]
    RETRYABLE -->|Yes — transient failure<br/>e.g., timeout, 503| UNDER_MAX{Retries <br/>remaining?}

    UNDER_MAX -->|No — max retries exhausted| DLQ
    UNDER_MAX -->|Yes| BACKOFF["Wait: exponential backoff<br/>+ jitter"]

    BACKOFF --> RESCHEDULE["Re-schedule task<br/>status = RETRY → SCHEDULED"]

    RESCHEDULE --> POISON{Same task failed<br/>3+ consecutive runs?}
    POISON -->|Yes| FLAG["Flag as poison pill<br/>Alert on-call team"]
    POISON -->|No| EXECUTE["Execute on next<br/>available worker"]

    style DLQ fill:#f44336,color:#fff
    style BACKOFF fill:#FF9800,color:#fff
    style EXECUTE fill:#4CAF50,color:#fff
    style FLAG fill:#9C27B0,color:#fff
```

### Retry Configuration

| Parameter | Description | Fintech Example |
|-----------|-------------|-----------------|
| **maxRetries** | Maximum retry attempts before DLQ | EOD recon: 5, statement gen: 3 |
| **initialBackoff** | First retry delay | 1 second |
| **maxBackoff** | Cap on backoff growth | 5 minutes |
| **backoffMultiplier** | Exponential growth factor | 2.0 (1s → 2s → 4s → 8s → ...) |
| **jitterPercent** | Random spread to avoid thundering herd | 20% |
| **retryableErrors** | Error types eligible for retry | ConnectionTimeout, 503, 429 |
| **nonRetryableErrors** | Errors that go straight to DLQ | InvalidInput, AuthFailure, 400 |
| **deadlineTimeout** | Absolute deadline regardless of retries | EOD recon must complete by 2:00 AM |

---

## Backfill & Catch-Up — Missed Fire Policies

What if the scheduler was down from 11:00 PM to 1:00 AM and the midnight EOD reconciliation never fired? The missed-fire policy determines what happens when the scheduler recovers.

```mermaid
flowchart TB
    MISSED["Scheduler recovers.<br/>Midnight task was missed."] --> POLICY{Missed Fire<br/>Policy?}

    POLICY --> FIRE_NOW["🔥 Fire Immediately<br/>Run the missed task now"]
    POLICY --> FIRE_ONCE["1️⃣ Fire Once (Latest)<br/>Run only the most recent<br/>missed occurrence"]
    POLICY --> SKIP["⏭️ Skip<br/>Wait for next scheduled<br/>occurrence"]
    POLICY --> FIRE_ALL["📋 Fire All Missed<br/>Run every missed<br/>occurrence in order"]

    FIRE_NOW --> USE1["✅ EOD Reconciliation<br/>Must run, even late"]
    FIRE_ONCE --> USE2["✅ Statement Generation<br/>Only latest month matters"]
    SKIP --> USE3["✅ Metrics Aggregation<br/>Next run will cover the gap"]
    FIRE_ALL --> USE4["⚠️ Interest Calculation<br/>Every day must be computed<br/>(dangerous — verify idempotency)"]

    style FIRE_NOW fill:#4CAF50,color:#fff
    style FIRE_ONCE fill:#2196F3,color:#fff
    style SKIP fill:#9E9E9E,color:#fff
    style FIRE_ALL fill:#FF9800,color:#fff
```

### Policy Comparison

| Policy | Behavior | Risk | Best For |
|--------|----------|------|----------|
| **Fire immediately** | Run the missed task as soon as scheduler recovers | Task runs at unexpected time; downstream may not be ready | Critical tasks that must run (EOD recon) |
| **Fire once (latest)** | Run only the most recent missed occurrence, skip older ones | Skips intermediate occurrences | Tasks where only the latest run matters (cache refresh) |
| **Skip** | Don't run the missed task; wait for the next regular occurrence | Missed work is permanently lost | Non-critical tasks, metrics aggregation |
| **Fire all missed** | Run every missed occurrence sequentially | Resource spike, potential duplicate processing | Tasks where every occurrence matters (daily interest calc) — requires idempotent handlers |

---

## Priority & Fairness

Not all tasks are equal. EOD reconciliation (critical) must run before a marketing report (low). But priority alone can cause starvation — low-priority tasks never run if the queue always has critical tasks. Aging solves this: tasks that wait too long get their priority boosted.

```mermaid
flowchart TB
    subgraph priority_lanes ["Priority Lanes"]
        direction TB
        CRITICAL["🔴 CRITICAL<br/>EOD Recon, Interest Calc"]
        HIGH["🟠 HIGH<br/>Statement Gen, Compliance Reports"]
        NORMAL["🔵 NORMAL<br/>Notification Batches"]
        LOW["⚪ LOW<br/>Marketing Reports, Analytics"]
    end

    CRITICAL --> WP["Worker Pool<br/>(Processes highest<br/>priority first)"]
    HIGH --> WP
    NORMAL --> WP
    LOW --> WP

    LOW -.->|"Aging: priority boosted<br/>after 30 min wait"| NORMAL
    NORMAL -.->|"Aging: priority boosted<br/>after 60 min wait"| HIGH

    style CRITICAL fill:#f44336,color:#fff
    style HIGH fill:#FF9800,color:#fff
    style NORMAL fill:#2196F3,color:#fff
    style LOW fill:#9E9E9E,color:#fff
    style WP fill:#4CAF50,color:#fff
```

---

## The Fintech Use Cases

### Use Case 1: End-of-Day Reconciliation

Match internal ledger transactions against bank and payment provider statements. Every transaction recorded in your system must have a corresponding entry in the bank's records — and vice versa.

**Schedule:** Daily at midnight | **Scale:** Millions of transactions | **Failure impact:** Undetected fraud, regulatory violations

```mermaid
sequenceDiagram
    participant Sched as Scheduler
    participant Worker as Recon Worker
    participant Ledger as Ledger DB
    participant Bank as Bank API
    participant Report as Report Service
    participant Alert as Alert Service

    Sched->>Worker: Assign: EOD Reconciliation<br/>date=2024-01-15

    Worker->>Ledger: Fetch all transactions<br/>for 2024-01-15
    Ledger-->>Worker: 2.3M internal transactions

    Worker->>Bank: Fetch bank statement<br/>for 2024-01-15
    Bank-->>Worker: 2.3M bank records

    Worker->>Worker: Match transactions<br/>by reference ID + amount

    alt All matched
        Worker->>Report: Generate recon report<br/>status: CLEAN
        Worker->>Sched: Task SUCCESS
    else Discrepancies found
        Worker->>Alert: ALERT: 47 unmatched txns<br/>Total: $12,340 discrepancy
        Worker->>Report: Generate exception report
        Worker->>Sched: Task SUCCESS<br/>(recon ran, discrepancies logged)
    end
```

**Cross-reference:** [Wallet & Ledger System](./wallet-ledger-system.md) — the ledger reconciliation section describes the internal vs external reconciliation loops that this scheduled task automates.

### Use Case 2: Monthly Statement Generation

Generate PDF statements for millions of accounts on the 1st of every month. This is a classic **fan-out** pattern: a parent task spawns N child tasks (one per account), each generating and uploading a PDF.

```mermaid
flowchart TB
    PARENT["Parent Task<br/>Monthly Statement Gen<br/>Trigger: 1st of month"]

    PARENT --> FANOUT["Fan-Out<br/>Query all active accounts<br/>Create child task per account"]

    FANOUT --> C1["Child Task 1<br/>Account: A-001<br/>Key: A-001/2024-01"]
    FANOUT --> C2["Child Task 2<br/>Account: A-002<br/>Key: A-002/2024-01"]
    FANOUT --> C3["Child Task 3<br/>Account: A-003<br/>Key: A-003/2024-01"]
    FANOUT --> CN["Child Task N<br/>Account: A-N<br/>Key: A-N/2024-01"]

    C1 --> W1["Worker: Generate PDF"]
    C2 --> W2["Worker: Generate PDF"]
    C3 --> W3["Worker: Generate PDF"]
    CN --> WN["Worker: Generate PDF"]

    W1 --> S3["S3: Upload PDF"]
    W2 --> S3
    W3 --> S3
    WN --> S3

    S3 --> NOTIFY["Notification Service<br/>Email / Push: Statement ready"]

    style PARENT fill:#2196F3,color:#fff
    style FANOUT fill:#FF9800,color:#fff
    style S3 fill:#4CAF50,color:#fff
    style NOTIFY fill:#9C27B0,color:#fff
```

**Idempotency key:** `(account_id, year-month)` — regenerating the same statement for the same month produces the same PDF and overwrites the previous upload. No duplicate statements.

### Use Case 3: Daily Interest Calculation

Compute daily compound interest across all accounts. This task has a strict **ordering dependency**: it must run **after** EOD reconciliation completes, because interest should only be calculated on reconciled, verified balances.

**Idempotency key:** `(account_id, date)` — calculating interest twice for the same account on the same day must produce the same result. Double interest is catastrophic.

**Cross-reference:** [Idempotency](./idempotency.md) — the idempotency key pattern is essential here, as the "fire all missed" catch-up policy may re-execute past days.

### Fintech Use Case Summary

| Use Case | Schedule | Scale | Idempotency Key | Dependency | Failure Impact |
|----------|----------|-------|-----------------|------------|----------------|
| **EOD Reconciliation** | Daily midnight | Millions of txns | `(recon_type, date)` | None — runs first | Undetected fraud, regulatory breach |
| **Statement Generation** | 1st of month | Millions of accounts | `(account_id, month)` | None | Customer complaints, compliance gaps |
| **Interest Calculation** | Daily 2:00 AM | All interest-bearing accounts | `(account_id, date)` | After EOD Recon | Double interest = financial loss; missed interest = regulatory violation |

---

## Schema Design

```sql
-- Task definitions and current state
CREATE TABLE tasks (
    id                  UUID PRIMARY KEY,
    task_type           VARCHAR(100) NOT NULL,        -- 'EOD_RECON', 'STATEMENT_GEN', 'INTEREST_CALC'
    task_group          VARCHAR(100),                 -- grouping for fan-out parent/children
    parent_task_id      UUID REFERENCES tasks(id),    -- NULL for root tasks
    schedule_expr       VARCHAR(100),                 -- cron expression: '0 0 * * *'
    priority            INT NOT NULL DEFAULT 100,     -- lower = higher priority
    tenant_id           UUID,                         -- multi-tenant isolation
    payload             JSONB NOT NULL,               -- task-specific parameters
    status              VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    retry_count         INT NOT NULL DEFAULT 0,
    max_retries         INT NOT NULL DEFAULT 3,
    next_trigger_time   TIMESTAMP NOT NULL,
    deadline            TIMESTAMP,                    -- absolute deadline for completion
    idempotency_key     VARCHAR(255) UNIQUE,          -- prevents duplicate execution
    missed_fire_policy  VARCHAR(20) DEFAULT 'FIRE_IMMEDIATELY',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tasks_poll ON tasks (status, priority, next_trigger_time)
    WHERE status IN ('PENDING', 'RETRY');

-- Execution history (one row per attempt)
CREATE TABLE task_executions (
    id                  UUID PRIMARY KEY,
    task_id             UUID NOT NULL REFERENCES tasks(id),
    worker_id           VARCHAR(100) NOT NULL,
    fence_token         BIGINT NOT NULL,              -- monotonically increasing per task
    status              VARCHAR(20) NOT NULL,         -- 'RUNNING', 'SUCCESS', 'FAILED', 'TIMED_OUT'
    started_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMP,
    last_heartbeat      TIMESTAMP NOT NULL DEFAULT NOW(),
    error_message       TEXT,
    result              JSONB,
    attempt_number      INT NOT NULL DEFAULT 1
);

CREATE INDEX idx_executions_heartbeat ON task_executions (status, last_heartbeat)
    WHERE status = 'RUNNING';

-- Distributed locks with fencing tokens
CREATE TABLE task_locks (
    task_id             UUID PRIMARY KEY REFERENCES tasks(id),
    worker_id           VARCHAR(100) NOT NULL,
    fence_token         BIGINT NOT NULL,
    acquired_at         TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMP NOT NULL,           -- lease expiry
    CONSTRAINT unique_active_lock UNIQUE (task_id)
);
```

---

## Monitoring & Observability

A distributed scheduler without observability is a ticking time bomb. You must know how deep the queue is, how fast tasks execute, and how often they fail — before users notice.

```mermaid
flowchart LR
    SCHED["Scheduler"] -->|Metrics| PROM["Prometheus"]
    WORKERS["Workers"] -->|Metrics| PROM
    DLQ["DLQ"] -->|Metrics| PROM

    PROM --> GRAFANA["Grafana<br/>Dashboard"]
    GRAFANA --> ALERT["AlertManager<br/>PagerDuty / Slack"]

    SCHED -->|Structured logs| LOGS["ELK / Loki"]
    WORKERS -->|Structured logs| LOGS

    style SCHED fill:#2196F3,color:#fff
    style PROM fill:#FF9800,color:#fff
    style GRAFANA fill:#4CAF50,color:#fff
    style ALERT fill:#f44336,color:#fff
```

### Key Metrics

| Metric | Type | What It Tells You | Alert Threshold |
|--------|------|-------------------|-----------------|
| `task_queue_depth` | Gauge | Number of tasks waiting (PENDING + SCHEDULED) | > 1000 for > 5 min |
| `task_execution_duration_seconds` | Histogram | How long tasks take to execute | P99 > 2x normal |
| `task_failure_rate` | Gauge | Percentage of tasks failing | > 5% |
| `task_dlq_depth` | Gauge | Tasks in dead letter queue | > 0 |
| `scheduler_poll_lag_seconds` | Gauge | Delay between trigger time and poll time | > 30 seconds |
| `worker_utilization` | Gauge | Percentage of workers actively executing | > 90% sustained |
| `task_retry_count` | Counter | Total retries across all tasks | Spike detection |
| `scheduler_leader_changes` | Counter | Number of leader elections | > 2 in 10 minutes |

---

## Common Pitfalls

### ❌ No Distributed Lock

```
❌ Two scheduler instances both pick up the same task at the same time
   → Task executes twice, double-charging customers

✅ Distributed lock (or fencing token) ensures only one worker owns a task
   → Exactly-once assignment, stale workers rejected
```

### ❌ No Idempotency in Task Handlers

```
❌ Interest calculation handler: balance += daily_interest
   → Retry after transient failure = double interest applied

✅ Idempotent handler: UPSERT interest_entries WHERE (account_id, date)
   → Safe to retry — same result regardless of execution count
```

### ❌ Fixed Retry Without Backoff

```
❌ Retry immediately on failure, every 100ms, 1000 times
   → Hammers failing downstream service, delays recovery

✅ Exponential backoff with jitter: 1s → 2s → 4s → 8s (+ random jitter)
   → Gives downstream time to recover, prevents thundering herd
```

### ❌ No Missed-Fire Policy

```
❌ Scheduler restarts after 2-hour outage, no catch-up logic
   → Midnight EOD reconciliation silently skipped, nobody knows

✅ Missed-fire policy: FIRE_IMMEDIATELY for critical tasks
   → Scheduler detects missed triggers on recovery, executes them
```

### ❌ Monolithic Task — No Fan-Out

```
❌ Single task generates statements for 5 million accounts sequentially
   → Takes 8 hours, single worker bottleneck, no parallelism

✅ Fan-out: parent task spawns 5M child tasks, workers process in parallel
   → Completes in minutes, horizontally scalable
```

### ❌ Clock Skew Across Workers

```
❌ Worker A's clock is 30 seconds ahead, Worker B's is 10 seconds behind
   → Tasks fire at wrong times, lease expiry races, duplicate execution

✅ Use NTP sync, design with clock skew tolerance, server-side timestamps
   → Lease durations > expected skew, centralized time source for scheduling
```

---

## Real-World Implementations

| System | Type | Scheduling Model | Notable Features |
|--------|------|-----------------|------------------|
| **Quartz** | Java library | Cron + interval, DB-backed | Clustering support, rich trigger types, JDBC job store |
| **Apache Airflow** | Workflow orchestrator | DAG-based, cron triggers | Python DAGs, rich UI, dependency management |
| **Temporal** | Workflow engine | Durable execution, timers | Exactly-once, replay-based recovery, polyglot SDKs |
| **Celery Beat** | Python | Cron + interval, Redis/RabbitMQ | Simple, widely used, periodic task scheduling |
| **AWS EventBridge** | Managed service | Cron + rate expressions | Serverless, event-driven, SaaS integrations |
| **Google Cloud Scheduler** | Managed service | Cron expressions | HTTP/Pub/Sub targets, automatic retry |
| **Uber Cadence** | Workflow engine | Durable timers | Predecessor to Temporal, battle-tested at Uber scale |
| **LinkedIn Azkaban** | Batch workflow | DAG-based, cron triggers | Hadoop job scheduling, dependency management |
| **Kubernetes CronJob** | Container orchestrator | Cron expressions | Pod-based execution, K8s native, concurrency policies |
| **HashiCorp Nomad** | Cluster scheduler | Periodic stanza (cron) | Multi-region, batch + service scheduling, lightweight |

---

## Pros and Cons

### Pros

| Advantage | Detail |
|-----------|--------|
| **High availability** | Leader election and standby promotion ensure scheduling continues through server failures |
| **Exactly-once execution** | Fencing tokens + distributed locks prevent duplicate task execution |
| **Horizontal scaling** | Add workers to increase throughput; shard schedulers for higher task volumes |
| **Visibility & monitoring** | Centralized task state, execution history, dashboards, and alerting |
| **Retry & DLQ** | Automatic retry with backoff; permanent failures routed to DLQ for investigation |
| **Priority scheduling** | Critical tasks (EOD recon) preempt low-priority tasks (reports) |
| **Multi-tenant isolation** | Tenant-level queues, quotas, and fairness prevent noisy-neighbor problems |
| **Audit trail** | Complete execution history — who ran what, when, how long, what failed |

### Cons

| Disadvantage | Detail |
|--------------|--------|
| **Operational complexity** | ZooKeeper/etcd clusters, worker fleet management, monitoring infrastructure |
| **Coordination overhead** | Distributed locks, leader election, and heartbeats add latency and failure modes |
| **Clock synchronization** | Workers must have synchronized clocks; skew causes scheduling inaccuracies and lease races |
| **Debugging difficulty** | Task failures span multiple machines; requires centralized logging and tracing |
| **Cold start latency** | New workers need to register, connect, and begin polling before they can execute tasks |
| **Schema & migration management** | Task store schema evolves; migrations must be backward-compatible with running workers |

---

## When to Use

```mermaid
flowchart TB
    Q1{Do you have recurring<br/>batch jobs?}
    Q1 -->|No — one-off or<br/>event-driven only| EVENT["Event-driven architecture<br/>or simple job queue"]
    Q1 -->|Yes| Q2{Need HA and<br/>exactly-once?}

    Q2 -->|No — single server<br/>is acceptable| CRON["Use cron / systemd timer<br/>Simple and sufficient"]
    Q2 -->|Yes| Q3{Need horizontal<br/>scaling for workers?}

    Q3 -->|No — single worker<br/>handles the load| LIGHT["Lightweight scheduler<br/>DB-backed Quartz or<br/>pg_cron + advisory locks"]
    Q3 -->|Yes| DTS["✅ Distributed Task Scheduler<br/>Full system: scheduler cluster +<br/>worker pool + task store + DLQ"]

    style DTS fill:#4CAF50,color:#fff
    style CRON fill:#9E9E9E,color:#fff
    style LIGHT fill:#2196F3,color:#fff
    style EVENT fill:#FF9800,color:#fff
```

### Use When

- **Recurring fintech batch jobs** — EOD reconciliation, statement generation, interest calculation
- **High availability is mandatory** — missed execution has regulatory or financial consequences
- **Exactly-once matters** — duplicate execution causes financial loss (double interest, double charges)
- **Scale exceeds one machine** — millions of tasks, hundreds of workers
- **Task dependencies exist** — interest calc must run after reconciliation
- **Multi-tenant workloads** — different tenants have different schedules, priorities, and SLAs
- **Auditability required** — regulators need to see what ran, when, and what failed

### Do NOT Use When

- **Simple cron on a single server suffices** — if downtime is acceptable and tasks are idempotent, don't over-engineer
- **Pure event-driven workloads** — if tasks are triggered by events (not time), use a message queue instead
- **Low-stakes tasks** — if a missed cache refresh or analytics aggregation is tolerable, cron is fine
- **Serverless fits better** — for sporadic, lightweight tasks, AWS Lambda + EventBridge is simpler

---

## Key Takeaways for System Design Interviews

1. **Scheduling is coordination, not timing** — the hard problems are exactly-once execution, HA, missed-fire recovery, and scaling workers. Cron syntax is the easy part.

2. **Lead with the four components** — Scheduler (brain), Worker Pool (muscle), Task Store (memory), Dead Letter Queue (safety net). Draw this architecture first.

3. **Know the task state machine cold** — PENDING → SCHEDULED → ASSIGNED → RUNNING → SUCCESS/FAILED/TIMED_OUT → RETRY or DEAD_LETTERED. This shows you understand failure modes.

4. **Fencing tokens solve the zombie worker problem** — when a partitioned worker comes back and tries to write its result, the stale fence token causes rejection. This is how you get exactly-once.

5. **Leader election prevents duplicate scheduling** — a single active scheduler (or sharded schedulers) avoids assigning the same task to multiple workers. Mention ZooKeeper ephemeral nodes or etcd leases.

6. **Missed-fire policy is a must-mention for fintech** — what happens when the scheduler was down at midnight? Fire immediately, fire once, skip, or fire all missed. The answer depends on the use case.

7. **Fan-out for large batch jobs** — statement generation for millions of accounts should not be a single monolithic task. Parent task fans out to N child tasks processed in parallel by the worker pool.

8. **Idempotency is the safety net** — when exactly-once coordination fails (and it will), idempotent task handlers ensure duplicates are harmless. Every fintech task handler must be idempotent.

9. **Push vs Pull assignment is a real design decision** — push gives the scheduler control but requires health tracking. Pull (competing consumers) gives natural load balancing but less control. Know when to use each.

10. **Priority + aging prevents starvation** — priority queues ensure critical tasks run first, but aging (boosting priority of long-waiting tasks) prevents low-priority tasks from starving indefinitely.

11. **Monitor queue depth, execution latency, failure rate, and DLQ depth** — these four metrics tell you if the system is healthy. Alert on DLQ depth > 0 for critical task types.

12. **Task dependencies matter in fintech** — interest calculation depends on reconciliation. Express this as a DAG (directed acyclic graph) or explicit dependency in the task definition. Never calculate interest on unreconciled balances.

---

## Related Concepts

- **[Idempotency](./idempotency.md)** — Every task handler must be idempotent to survive retries and duplicate execution
- **[SAGA Pattern](./saga-pattern.md)** — Multi-step tasks (hold → execute → confirm) use SAGA orchestration with compensating actions
- **[Kafka Communication Patterns](./kafka-communication-patterns.md)** — Event-driven triggers and async result distribution via Kafka topics
- **[Wallet & Ledger System](./wallet-ledger-system.md)** — EOD reconciliation and interest calculation operate on the ledger system
- **[Event Sourcing](./event-sourcing.md)** — Task execution history as an append-only event log; replay for auditing
- **[Circuit Breaker](./circuit-breaker.md)** — Workers calling downstream services (bank APIs, payment gateways) need circuit breakers for resilience
- **Leader Election** — The mechanism ensuring a single active scheduler (ZooKeeper, etcd, Raft)
- **Distributed Locking** — Fencing tokens and leases that prevent concurrent execution of the same task
- **Outbox Pattern** — Reliable event publishing from task completion to downstream consumers
