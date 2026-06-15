# Post-Interview Calibration

## The Good, The Bad, and The Ugly

### The Good

The candidate showed a strong platform mindset rather than treating the system as a simple queue-and-worker design. The strongest areas were security and blast-radius control: sandboxed ephemeral execution, per-task IAM, default-deny egress, signed artifacts, approval workflows, tenant quotas, downstream circuit breakers, and fail-closed fan-out controls.

The candidate improved through the session and incorporated feedback on CQRS, lazy task instantiation, tenant fairness, durable cancellation, immutable execution receipts, and forensic reruns.

### The Bad

The initial requirements were too qualitative and missed several Principal-level categories until prompted: workflow semantics, execution guarantees, scheduling precision, versioning, observability, idempotency boundaries, cost controls, and reproducibility.

The candidate leaned quickly on Kafka, Postgres, and Redis before fully defining the durable workflow state machine and transition model. Some early claims were imprecise, especially around S3 overwrite safety, last-write-wins state updates, Glacier retrieval time, and behavior during Postgres outage.

### The Ugly

The most serious early flaw was assuming deterministic S3 paths and atomic PUT were enough for retry correctness. That can still cause stale overwrites, duplicate logical side effects, and inconsistent downstream consumption.

Another critical issue was treating Postgres as the source of truth while still allowing too much activity during a Postgres outage without clearly defining a temporary durable acceptance log and reconciliation model.

## MAANG Matrix Scoring

| Category | Score | Rationale |
|---|---:|---|
| System Design and Hyperscale Architecture | 7.5/10 | Strong layered architecture, burst handling, fan-out controls, and CQRS direction. Needed more rigor in workflow engine semantics. |
| Requirements and Scope Mastery | 6.5/10 | Solid baseline requirements, but many critical requirements appeared only after interviewer prompting. |
| Security, Cost, and Maintainability Trade-offs | 8/10 | Strongest area. Good zero-trust execution, tenant isolation, quotas, lifecycle, and approval instincts. |
| Edge-Case and Crisis Resolution | 7/10 | Good cancellation, blast-radius, and forensic answers. Retry correctness and degraded-mode consistency needed sharpening. |

## Final Recommendation

Final score summary: 7.25/10

Hiring status: LEAN HIRE

For a MAANG L7+ leadership track, the candidate demonstrated credible architecture judgment, especially in security, multi-tenancy, and operational controls. The design still needs deeper rigor around durable orchestration semantics, state transitions, effectively-once boundaries, and degraded-mode correctness. Recommendation is lean hire with follow-up depth checks on workflow engines, distributed state machines, and large-scale incident design.

## Follow-Up Depth Checks

Use these if additional calibration is needed:

1. Ask the candidate to model the exact database tables and state transitions for `workflow_run`, `step_run`, and `task_attempt`.
2. Ask the candidate to compare Temporal, Step Functions, Airflow, and a custom orchestrator with concrete cost and operational trade-offs.
3. Ask the candidate to design the outbox/inbox and replay model for Postgres outage recovery.
4. Ask the candidate to define connector contracts for idempotent Snowflake writes, emails, callbacks, and S3 outputs.
5. Ask the candidate to define the policy model for PII workflows, network egress, secrets, and artifact retention.
