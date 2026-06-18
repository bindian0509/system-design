# Overall Project Management Gantt And Resource Plan

## Purpose

This plan consolidates the Health Center architecture, delivery, operations, and people-management work into a project-management view. It is designed for an interview discussion where the panel wants to see how an L7+ engineering manager sequences work across quarters while handling dependencies and live-site distractions.

## Resource Assumptions

Team size: 10 engineers.

| Resource Group | Count | Primary Focus |
| --- | ---: | --- |
| Backend stream/state | 3 | Consumers, normalization, state, rules, replay. |
| Backend API/alerts | 2 | Alert lifecycle, coalescing, APIs, notifications, suppressions. |
| Frontend | 2 | Health Center dashboard, agent list, alert detail, freshness UX. |
| QA/SDET | 2 | Contract tests, integration automation, replay validation, load tests. |
| Tech lead/flex | 1 | Architecture coherence, cross-team integration, incident support. |

Temporary allocation during legacy offline-status spike:

| Lane | Engineers | Duration | Goal |
| --- | ---: | --- | --- |
| Legacy stabilization tiger team | 3 | 2-4 weeks | Reduce false offline escalations and add regression coverage. |
| Health Center critical path | 5 | Ongoing | Keep MVP moving. |
| UI/QA/support tooling | 2 | Ongoing | Dashboard work, test automation, support visibility. |

## Overall Timeline

The timeline assumes a July 2026 start. Adjust dates in an interview if the interviewer gives a different launch target.

```mermaid
gantt
    title Singularity Health Center Overall Timeline And Resource Plan
    dateFormat  YYYY-MM-DD
    axisFormat  %b %Y

    section Q1: Foundation
    Architecture alignment and ADRs                 :milestone, m1, 2026-07-01, 0d
    Event contract with Ingestion Gateway           :active, q1_contract, 2026-07-01, 28d
    Stream consumer and normalization               :q1_stream, 2026-07-15, 49d
    Latest health state store                       :q1_state, 2026-07-22, 42d
    Synthetic telemetry and replay harness          :q1_replay, 2026-07-22, 49d
    Observability foundation                        :q1_obs, 2026-07-29, 42d
    Legacy offline tiger team                       :crit, q1_legacy, 2026-07-15, 28d

    section Q2: MVP
    Initial rule engine                             :q2_rules, 2026-09-16, 42d
    Alert coalescing spike and ADR                  :crit, q2_coalesce_adr, 2026-09-16, 7d
    Stream-time alert coalescing MVP                :crit, q2_coalesce, 2026-09-23, 35d
    Dashboard read models                           :q2_read, 2026-09-23, 42d
    Health Center APIs                              :q2_api, 2026-10-01, 42d
    React console MVP                               :q2_ui, 2026-10-08, 49d
    Shadow mode for selected tenants                :q2_shadow, 2026-10-22, 35d
    Private preview                                 :milestone, m2, 2026-11-26, 0d

    section Dependency Delay Mitigation
    Gateway thin-slice negotiation                  :crit, dep1, 2026-08-01, 21d
    Temporary adapter or simulator path             :dep2, 2026-08-15, 42d
    Contract tests against gateway                  :dep3, 2026-09-01, 56d

    section Q3: GA Hardening
    Alert lifecycle: ack mute resolve reopen        :q3_alerts, 2026-12-01, 49d
    RBAC and audit logging                          :q3_rbac, 2026-12-08, 42d
    Notifications integration                       :q3_notify, 2026-12-15, 42d
    Replay and backfill tooling                     :q3_backfill, 2026-12-15, 49d
    Scale and soak testing                          :crit, q3_scale, 2027-01-05, 42d
    Legacy offline dual-read migration              :crit, q3_legacy_mig, 2027-01-05, 56d
    Sev-1 game day                                  :milestone, m3, 2027-02-16, 0d
    GA readiness review                             :milestone, m4, 2027-03-01, 0d

    section Q4: Expansion
    Rule expansion                                  :q4_rules, 2027-03-15, 56d
    Advanced suppressions and maintenance windows   :q4_suppress, 2027-03-15, 49d
    Reusable alert lifecycle platformization        :q4_platform_alerts, 2027-04-01, 56d
    Reusable rule framework                         :q4_platform_rules, 2027-04-01, 56d
    Legacy heartbeat retirement                     :milestone, m5, 2027-05-15, 0d
```

## Resource Loading By Phase

```mermaid
gantt
    title Resource Loading By Workstream
    dateFormat  YYYY-MM-DD
    axisFormat  %b

    section Backend Stream/State: 3 engineers
    Event consumer and normalizer       :bs1, 2026-07-15, 49d
    State service and read events       :bs2, 2026-07-22, 49d
    Rules and stream coalescing         :bs3, 2026-09-16, 56d
    Replay and scale hardening          :bs4, 2026-12-15, 63d

    section Backend API/Alerts: 2 engineers
    Alert store and lifecycle skeleton  :ba1, 2026-09-23, 42d
    Health Center APIs                  :ba2, 2026-10-01, 42d
    Notifications and suppressions      :ba3, 2026-12-15, 56d
    Platformization                     :ba4, 2027-04-01, 56d

    section Frontend: 2 engineers
    UI prototypes with mocked data      :fe1, 2026-08-15, 35d
    Dashboard and agent list MVP        :fe2, 2026-10-08, 49d
    Alert detail and freshness UX       :fe3, 2026-10-22, 42d
    GA polish and RBAC states           :fe4, 2027-01-05, 42d

    section QA/SDET: 2 engineers
    Contract and schema tests           :qa1, 2026-07-22, 42d
    Replay and integration automation   :qa2, 2026-08-15, 56d
    Load and soak tests                 :qa3, 2027-01-05, 42d
    Regression and rollout validation   :qa4, 2027-02-01, 42d

    section Tech Lead/Flex: 1 engineer
    Architecture and ADRs               :tl1, 2026-07-01, 42d
    Dependency mitigation               :tl2, 2026-08-01, 56d
    Operational readiness               :tl3, 2026-12-15, 63d
    Cross-team platformization          :tl4, 2027-04-01, 56d
```

## Critical Path

```mermaid
flowchart LR
    A["Event contract"] --> B["Telemetry consumer"]
    B --> C["Latest health state"]
    C --> D["Rule evaluation"]
    D --> E["Alert coalescing"]
    E --> F["Read models"]
    F --> G["APIs under 200ms"]
    G --> H["React console MVP"]
    H --> I["Private preview"]
    I --> J["Scale and soak"]
    J --> K["GA readiness"]
```

Critical-path risks:

- Ingestion Gateway routing delay.
- Alert coalescing decision churn.
- Legacy offline-status escalation consuming too much capacity.
- API read model not meeting 200ms P95.
- Rule false positives eroding preview trust.
- Inadequate freshness observability before customer exposure.

## Milestone Gates

| Milestone | Gate | Required Evidence |
| --- | --- | --- |
| Foundation complete | Pipeline can process synthetic/replayed events | State updates, lag dashboards, DLQ, canary freshness. |
| MVP private preview | Customer-visible dashboard is safe | P95 API < 200ms, freshness UX, basic RBAC, shadow rule review. |
| Alerting preview | Alerts are trustworthy | Coalescing ratio, duplicate rate, false-positive review, suppression. |
| GA readiness | Broad rollout is safe | Scale test, game day, replay/backfill, support docs, rollback plan. |
| Legacy retirement | Old offline status can be removed | Dual-read comparison, tenant canary success, escalation rate reduced. |

## Operating Cadence

| Cadence | Meeting | Purpose |
| --- | --- | --- |
| Daily | Team standup | Coordinate execution and blockers. |
| Twice weekly during incidents | Legacy escalation review | Track false offline impact and patches. |
| Weekly | Dependency sync with Gateway team | Track contract, thin-slice, routing dates. |
| Weekly | Product/engineering checkpoint | Review scope, risks, customer preview feedback. |
| Weekly | Demo | Preserve visible progress and morale. |
| Biweekly | Architecture review | Resolve design decisions through ADRs. |
| Monthly | Executive review | Timeline, risks, staffing, launch confidence. |
| Per milestone | Operational readiness review | SLOs, runbooks, dashboards, rollback. |

## Resource Guardrails

- Keep at least 5 engineers on the Health Center MVP critical path during operational distractions.
- Time-box legacy stabilization tiger team work and review allocation weekly.
- Reduce MVP scope before cutting observability, freshness, idempotency, or security.
- Use a simulator/replay path to keep the team productive during Gateway delays.
- Require ADRs for decisions that affect latency, cost, or operational complexity.
- Keep QA involved from Q1, not only before GA.

## Interview Summary

The project plan has three lanes running in parallel: Health Center delivery, dependency mitigation, and live-platform stabilization. The Gantt chart shows that the team can keep making progress even if the Ingestion Gateway slips, but GA should remain gated on real telemetry freshness, scale tests, alert quality, and operational readiness.

