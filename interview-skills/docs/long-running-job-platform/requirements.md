# Requirements Blueprint

## Functional Requirements

1. Workflow template management
   - Create, read, update, delete, and version workflow templates.
   - Support immutable workflow versions for every execution.
   - Support validation before a template can be activated.

2. Triggering and scheduling
   - Trigger workflows on demand through API/SDK/UI.
   - Support scheduled and recurring workflows.
   - Support missed schedule recovery, deduplication, time zones, and daylight savings behavior.
   - Support backfills where explicitly authorized.

3. Workflow execution
   - Execute ordered steps or DAG-based steps.
   - Support fan-out/fan-in, conditional execution, retries, timeouts, cancellation, and partial failure handling.
   - Support lazy task instantiation for large fan-out workflows.
   - Support idempotent step execution and external side effects.

4. Multi-tenant control plane
   - Enforce team, workflow, run, step, and downstream dependency quotas.
   - Support priority classes such as critical, high, medium, and low.
   - Prevent one team or workflow from exhausting shared platform resources.

5. User and operator interfaces
   - Provide service-to-service APIs and SDKs as the primary integration surface.
   - Provide a lightweight React PWA dashboard for internal users and operators.
   - Allow users to view job state, step state, logs, retry history, artifacts, and audit records.
   - Allow authorized cancellation and limited modification through versioned workflow definitions.

6. Output handling
   - Support report outputs as files such as CSV, Excel, PDF, or JSON.
   - Support database writes and callbacks to downstream internal systems.
   - Store output metadata, checksums, manifests, lineage, and access policies.

7. Observability and operations
   - Provide step-level logs, metrics, traces, heartbeats, audit events, and lineage.
   - Support alerting for failures, stuck jobs, quota breaches, unusual fan-out, downstream saturation, and scheduler lag.
   - Support forensic debugging and controlled reruns.

## Non-Functional Requirements

## Scale

- Daily job runs: about 440,000.
- Average trigger rate: about 5 jobs per second.
- Burst trigger rate: about 50 jobs per second for 5 minutes.
- Burst starts in 5 minutes: 15,000 job starts.
- Typical job duration: 5 to 20 minutes.
- Long-running reports: 12 to 24 hours.
- Typical workflow steps: 5 to 12.
- Maximum workflow fan-out: up to 1,000 tasks per job template, subject to policy.
- Typical output size: 1 MB to 100 MB.
- Maximum output size: about 1 GB, with explicit quota controls.

Peak concurrency must be estimated from burst rate and job duration. At 50 starts per second for 5 minutes, the platform may admit 15,000 jobs. If many run for 20 minutes, active job concurrency can reach tens of thousands. With fan-out, runnable step concurrency can be much higher and must be controlled by admission and dispatch policies.

## SLOs

Define "start" precisely. Recommended SLO split:

- Trigger API accepted: p99 less than 300 ms.
- Job record visible in dashboard: p99 less than 1 second.
- First step dispatched for normal priority: p99 less than 2 to 10 seconds.
- First user code running: depends on worker warm pool and isolation tier.
- Dashboard freshness: p99 less than 3 seconds for projection state.
- Scheduler availability: 99.95%.
- No lost schedules: missed recurring jobs must be recoverable and auditable.

## Security

- Enforce identity-aware access to workflow templates, runs, outputs, and logs.
- Enforce least-privilege access to data sources through scoped service identities.
- Do not allow the orchestration platform to become a universal superuser.
- Encrypt data in transit and at rest.
- Use short-lived secrets from a managed secret store.
- Apply data classification, DLP checks, and stricter policy for PII.
- Audit who triggered what, which data was accessed, and which workflow version ran.

## Reliability and Correctness

- Prefer effectively-once business semantics over claiming exactly-once distributed execution.
- Use idempotency keys at job trigger, step, and side-effect boundaries.
- Use monotonic state transitions with sequence numbers or version checks.
- Store immutable execution receipts for forensic debugging.
- Recover from worker crashes, dispatcher crashes, queue redelivery, and dependency failures.

## Cost and Lifecycle

- Apply per-team quotas, budget alerts, priority-based capacity allocation, and hard caps.
- Enforce object lifecycle policies for intermediate artifacts, final reports, logs, and metadata.
- Preserve auditability and reproducibility without keeping every intermediate artifact forever.
- Store manifests, checksums, workflow versions, input snapshot pointers, code digests, and lineage.
