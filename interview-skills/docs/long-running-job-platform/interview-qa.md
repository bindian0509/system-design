# Interview Questions and Mature Answers

## Phase 1: Problem Introduction

Prompt:

Design an internal platform for long-running jobs such as quarterly business review reports from CRM data and daily customer health scores from multiple data sources. The platform should be generic, customizable, and support on-demand, scheduled, and recurring workflows. Teams should be able to define custom ordered steps, similar in spirit to Airflow.

Do not reveal metrics at first. Let the candidate clarify.

## Phase 2: Clarification Questions

### Question

What clarifying questions should the candidate ask?

### Mature Answer

A strong candidate should ask:

- Who are the users: internal teams, services, operators, or all three?
- Is the primary interface API, SDK, UI, or service-to-service integration?
- Are workflows linear, DAG-based, conditional, or fan-out/fan-in?
- What trigger modes are needed: on-demand, cron, recurring, event-driven, backfill?
- What are the scale assumptions: daily runs, peak trigger rate, duration, step count, output size, and concurrency?
- What does "start latency" mean: API accepted, queued, first step dispatched, or user code running?
- What outputs are supported: files, database writes, emails, callbacks?
- What data sensitivity exists: PII, customer data, regulated data, business-sensitive reports?
- What are the execution guarantees: at-least-once, effectively-once, or best-effort?
- What are the retention, audit, and reproducibility requirements?
- What are the team isolation, quota, and cost requirements?
- What observability is required for operators and workflow owners?

## Phase 3: Requirements

### Question

Define functional and non-functional requirements with numbers.

### Mature Answer

Functional requirements:

- CRUD and immutable versioning for workflow templates.
- Trigger on-demand, scheduled, recurring, and backfill workflows.
- Validate parameters and bind every run to a workflow version.
- Execute ordered or DAG-based steps with retries, timeout, cancellation, fan-out/fan-in, and partial failure handling.
- Support per-team quotas, priority classes, and downstream dependency limits.
- Provide API/SDK and lightweight UI/dashboard.
- Provide step-level logs, metrics, traces, audit, lineage, and output manifests.
- Support controlled reruns and forensic debugging.

Non-functional requirements:

- 440,000 job runs per day.
- Average trigger rate about 5 jobs per second.
- Peak trigger rate about 50 jobs per second for 5 minutes.
- 15,000 job starts during a 5-minute peak window.
- Typical workflow duration 5 to 20 minutes, with long reports up to 24 hours.
- Typical steps 5 to 12, with bounded fan-out up to 1,000 tasks.
- Output size 1 MB to 100 MB typical, 1 GB maximum by policy.
- Dashboard freshness p99 less than 3 seconds.
- Scheduler availability 99.95%.
- No lost scheduled jobs; missed schedules must be recoverable.

## Phase 4: High-Level Architecture

### Question

Propose a high-level architecture.

### Mature Answer

Use a control-plane/data-plane split.

The control plane contains API gateway, AuthN/AuthZ, workflow template service, job service, quota engine, scheduler, search/read APIs, dashboard, metadata store, and audit system.

The execution plane contains durable orchestration, partitioned queues, fair dispatcher, sandboxed workers, approved connectors, object storage, event/log streams, projections, and observability systems.

Postgres is used for authoritative workflow metadata, run state, state versions, quotas, and audit metadata. Kafka is used as a durable event backbone for job requests, state-change events, logs, and projection building. Object storage stores reports, manifests, logs, and intermediate artifacts. Redis is used only as a hot projection cache, not a source of truth.

## Question 1: Worker Crash After Partial S3 Write

### Question

A workflow fans out into 1,000 regional S3 processing tasks. Task 827 writes a partial output to S3, then the worker crashes before updating Postgres or Kafka state. Kafka redelivers the task. How does the system prevent duplicate or corrupted report output while still guaranteeing eventual completion?

### Mature Answer

S3 atomic PUT and deterministic paths are not enough. They prevent byte-level partial writes, but not stale overwrites, duplicate side effects, or consumers reading the wrong object.

Use an output commit protocol:

- Each attempt writes to an attempt-specific temporary object path.
- The worker records checksum, object size, input snapshot, workflow version, and attempt metadata.
- The orchestrator commits the result using compare-and-swap from `RUNNING` to `SUCCEEDED`.
- Only the winning attempt updates the task output pointer in the manifest.
- Final aggregation reads from the committed manifest, not by listing S3 paths.
- Retries use the same immutable workflow version, parameters, and data snapshot boundary.
- External side effects use idempotency keys or conditional writes.

This provides effectively-once business output even though task execution and message delivery may be at-least-once.

## Question 2: Durable Cancellation

### Question

A user cancels a running job from the dashboard. Redis receives the cancellation event, but Redis later evicts the key or the worker never sees the event because it is mid-step for 40 minutes. What is the durable cancellation model?

### Mature Answer

Use durable-state first, signal second.

- Persist `CANCEL_REQUESTED` in Postgres with a state version.
- Publish a best-effort cancellation event to Kafka/Redis/pub-sub.
- Workers poll or heartbeat against authoritative state.
- Long-running steps implement cooperative cancellation checkpoints.
- A control thread can send SIGTERM and then SIGKILL for local execution.
- Connectors cancel downstream work, such as Snowflake queries, where supported.
- The worker commits `CANCELED` or `FAILED` with a reason and attempt metadata.

Redis accelerates cancellation but is not authoritative. Expected cancellation can be less than 2 seconds on the happy path, 30 to 60 seconds through heartbeat catch-up, and longer when external systems only support best-effort cancellation.

## Question 3: Thundering Herd and Fairness

### Question

At 9:00 AM local time, 12 teams schedule large workflows. The system receives 50 jobs per second for 5 minutes, some with 1,000-task fan-out. How does the scheduler avoid a thundering herd while maintaining fairness and priority?

### Mature Answer

Use admission control plus fair dispatch:

- Pre-flight estimate fan-out and reject or pause workflows that exceed policy.
- Lazily instantiate large fan-outs in bounded chunks.
- Use tenant-level logical queues.
- Apply weighted fair queuing across teams.
- Separate priority classes such as critical, high, medium, and low.
- Enforce per-team, per-workflow, per-run, per-step, and global concurrency limits.
- Enforce downstream-specific limits for systems such as Snowflake, CRM, email, and S3.
- Use token-bucket dispatch so task creation and execution are both metered.
- Degrade lower priority work before critical workloads.

Fairness requires both queue scheduling and admission control. If too much work is allowed into runnable state, fair dispatch alone is too late.

## Question 4: Postgres, Kafka, Logs, and Dashboard Freshness

### Question

Every step emits frequent status updates and logs. What goes into Postgres, Kafka, object storage, and search? How do you keep dashboard freshness under 3 seconds without melting Postgres?

### Mature Answer

Use CQRS and separate authoritative state from read projections.

Postgres stores:

- Workflow templates and immutable versions.
- Run and step authoritative state.
- State versions, attempts, leases, heartbeats, quota config, and audit metadata.
- Output manifest pointers and checksums.

Kafka carries:

- Job requested events.
- State-change events.
- Log events.
- Metric and heartbeat events.
- Projection update streams.

Object storage stores:

- Reports.
- Intermediate artifacts.
- Large logs.
- Manifests.
- Archived Parquet data.

Search/ClickHouse stores:

- Recent queryable logs and operational events.
- Historical run search indexes.
- Aggregated operational analytics.

Redis stores:

- Hot status projections for dashboard reads.
- Short-lived UI state and websocket fan-out payloads.

Do not use last-write-wins for workflow state. Use monotonic state transitions with `run_id`, `step_id`, `attempt_id`, and `state_version`.

## Question 5: Secure Custom Steps

### Question

Twenty teams can define custom workflow steps. Some access CRM PII, some call Snowflake, some generate PDFs, and some write back to internal systems. How do you allow customization without creating an arbitrary-code execution security nightmare?

### Mature Answer

Treat the platform as controlled arbitrary code execution and reduce blast radius.

- Teams submit immutable container artifacts through approved CI/CD, not raw scripts.
- Artifacts must pass SAST, dependency scanning, image scanning, and signing.
- Kubernetes admission policies allow only signed images and approved base images.
- Runtime pods are ephemeral, non-privileged, resource-limited, and isolated by namespace/team.
- Use seccomp/AppArmor, read-only root filesystems, no host mounts, and no privileged containers.
- Use default-deny network policies and audited egress proxies.
- Assign per-task cloud identity with least privilege.
- Retrieve secrets through Vault or cloud secret manager using short-lived leases.
- Require code owner approval for DAG changes and security approval for IAM/network changes.
- Apply stronger isolation such as dedicated node pools or VM groups for high-risk workloads.
- Add data classification gates, DLP scanning, and stricter audit for PII workflows.

## Question 6: Build Versus Buy

### Question

Why build this instead of adopting Airflow, Temporal, or Step Functions?

### Mature Answer

Do not build every primitive. Buy or adopt commodity infrastructure and build the differentiated multi-tenant control plane.

Adopt:

- Kubernetes/EKS for isolated execution.
- Managed Kafka/SQS/PubSub where appropriate.
- Postgres or a managed relational database for metadata.
- Object storage for artifacts.
- Vault or cloud secret manager for secrets.
- OpenTelemetry for traces, metrics, and logs.
- Existing CI/CD, image signing, and scanning.

Strongly consider Temporal for durable workflow semantics: timers, retries, heartbeats, cancellation, and long-running orchestration. Then build the platform-specific layers around it: RBAC, quotas, approval, workflow UX, sandboxed execution, reporting semantics, data policy, cost controls, and internal integrations.

Limit Airflow if the workload is dynamic, user-facing, multi-tenant, and security-sensitive. Consider Step Functions for AWS-native workflows, but evaluate cost, limits, lock-in, and custom execution needs.

## Question 7: Storage Lifecycle and Cost

### Question

With 440,000 jobs per day, average output up to 100 MB, max 1 GB, plus logs and intermediate artifacts, how do you prevent storage and indexes from growing without bound while preserving audit and reproducibility?

### Mature Answer

Apply lifecycle by data type and classification.

- Intermediate artifacts: default TTL around 7 days, shorter for temporary noisy artifacts.
- Final reports: hot/warm for 30 to 90 days depending on product policy and classification.
- Cold reports: archive to lower-cost storage when access is rare.
- Logs: 30 days in ClickHouse/search; older logs compressed to Parquet on object storage.
- Audit records: immutable retention based on compliance policy, with checksums and object lock/WORM where required.
- Metadata: keep operational windows in Postgres; archive immutable snapshots to Iceberg/Parquet.

Preserve reproducibility through manifests rather than preserving everything forever:

- Workflow version.
- Code artifact digest.
- Input snapshot pointer.
- Parameters.
- Data source versions.
- Output checksums.
- Lineage.
- Approval records.

Add per-team quotas, lifecycle policies, output-size limits, compression, log sampling, cost attribution, and budget alerts.

## Question 8: Postgres Outage

### Question

Postgres is the source of truth. Suppose the primary Postgres instance has a 10-minute outage during the 9 AM burst. APIs still receive triggers, Kafka is up, workers are running, and users watch the dashboard. What degrades, what continues, and how do you reconcile?

### Mature Answer

If Postgres is unavailable, authoritative state transitions cannot be committed. The system must enter degraded mode.

- New triggers are accepted only if a durable `JobRequested` event is written to Kafka with an idempotency key.
- If Kafka write fails too, return retryable `503`.
- Scheduler and dispatcher pause creation of new executable work that requires Postgres state transitions.
- Already-running workers may finish local work and emit completion events to Kafka or an outbox.
- Final authoritative commits wait for Postgres recovery.
- Dashboard continues from Redis/search projections, but labels the control plane as degraded.
- Operations requiring authoritative reads or writes may fail or become read-only.
- Reconciliation replays ordered events into Postgres with `run_id`, `step_id`, `attempt_id`, and monotonic state versions.

Do not allow uncontrolled new side effects while the authoritative state machine cannot record them.

## Question 9: Accidental Million-Task Fan-Out

### Question

A team accidentally triggers a 1,000-task fan-out for every customer instead of every region. It starts producing millions of tasks and saturates Kafka, workers, Snowflake, and S3 writes. What automated controls stop the blast radius?

### Mature Answer

Use defense in depth and fail closed:

- Pre-flight fan-out estimation blocks or pauses workflows that exceed policy.
- Hard caps exist per workflow, run, step, team, and global pool.
- Lazy task instantiation creates tasks in small chunks.
- Tenant quotas prevent one team from starving others.
- Token-bucket dispatch limits task creation and execution.
- Downstream connectors use bulkheads and circuit breakers.
- Snowflake, CRM, S3, email, and callbacks each have separate pools.
- Anomaly detection pauses workflows that exceed historical baselines.
- Kill switches can disable a workflow version, team, connector, or priority class.
- Budget alarms and forecasted spend caps can pause runaway execution.

The system should stop expansion before human intervention and leave an audit trail explaining why the run was paused.

## Question 10: Wrong Report Sent to Customers

### Question

An executive says, "This report is wrong, and it was sent to 400 customers." How does the platform support forensic debugging and safe correction?

### Mature Answer

Use immutable execution receipts, manifests, lineage, and controlled reruns.

Forensics:

- Identify the report run IDs and customer recipients.
- Read the run manifest for workflow ID, workflow version, parameters, schedule key, trigger identity, and approval record.
- Verify the container image digest, code version, config version, and dependency versions.
- Identify the input snapshot or query snapshot used for each data source.
- Inspect step-level input and output manifests.
- Use traces and WAP-style audit records to locate where the bad value was introduced.
- Confirm whether the error came from input data, transformation logic, aggregation logic, template rendering, or delivery.

Correction:

- Patch the workflow code or configuration.
- Build, scan, approve, and sign a new immutable artifact.
- Run targeted verification using the same historical input snapshot.
- Regenerate only affected outputs if safe.
- Use output manifests and recipient records to send corrected reports to the affected 400 customers.
- Preserve the original report, corrected report, root cause, operator actions, and customer notification as audit records.

Do not overwrite history silently. Publish a corrected artifact and record the relationship between original and corrected outputs.
