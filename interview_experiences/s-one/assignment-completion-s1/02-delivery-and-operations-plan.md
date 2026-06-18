# Delivery And Operations Plan

## Senior Manager Framing

As the Senior Engineering Manager, I would treat Singularity Health Center as a cross-functional platform and product initiative, not only a backend pipeline. The success criteria are customer trust, low false positives, operational reliability, and a delivery plan that reduces risk while moving quickly.

## Product Outcomes

- Customers can see which endpoints are unhealthy and why.
- Customers receive high-confidence alerts for critical operational health conditions.
- Support and customer success teams can explain alert evidence and health state transitions.
- Platform teams can operate the pipeline during spikes, regional failures, and customer incidents.
- Engineering can safely add new health rules without destabilizing ingestion.

## Team Topology

### Workstreams

| Workstream | Ownership | Primary Deliverables |
| --- | --- | --- |
| Ingestion and stream platform | Backend/platform engineers | Event contract, ingestion gateway, durable topics, schema registry, backpressure. |
| Health state and rules | Backend engineers | Normalization, state store, rule engine, replay support. |
| Alerts and notification | Backend engineers | Alert lifecycle, dedupe, grouping, notification integrations. |
| Console experience | Frontend and BFF engineers | Dashboard, drilldown, alert detail, actions. |
| Data and analytics | Data engineers | Raw retention, offline quality analysis, false-positive metrics. |
| SRE/infra | SRE and platform | Terraform, Helm, ArgoCD, dashboards, runbooks, SLOs. |
| Product/security/customer success | PM, security experts, CS | Rule definitions, severity, customer messaging, preview program. |

## Milestone Plan

### M0: Discovery And Design, 2-3 Weeks

Deliverables:

- Event taxonomy and schema compatibility rules.
- Health-state model and alert lifecycle.
- Capacity model and SLO proposal.
- Rule quality criteria.
- Architecture review with platform, security, and SRE.
- Preview tenant selection.

Exit criteria:

- Reviewed design.
- Known dependencies.
- Initial backlog sized.
- Risks and rollout gates agreed.

### M1: Ingestion And Shadow State, 4-6 Weeks

Deliverables:

- Ingestion gateway changes for health telemetry.
- Raw topic and normalized topic.
- Schema registry checks in CI.
- Health state service writing latest state.
- Synthetic telemetry generator.
- Internal dashboards for freshness, lag, and state coverage.

Exit criteria:

- Can process replayed and synthetic telemetry at target peak.
- State coverage above agreed threshold for dogfood tenants.
- No customer-visible alerts yet.

### M2: Rule Engine And Alert Candidates, 4-6 Weeks

Deliverables:

- Versioned rules for anti-tamper disabled, agent disabled, connectivity loss, and low disk.
- Alert candidate stream.
- Deduplication and suppression logic.
- Dead-letter and replay tooling.
- Rule dry-run metrics.

Exit criteria:

- False-positive review completed with security/product/CS.
- Candidate alerts explainable with evidence.
- Replay can reproduce outputs for a tenant and time range.

### M3: Console Preview And Alert Lifecycle, 4-6 Weeks

Deliverables:

- Health Center overview dashboard.
- Agent drilldown.
- Alert detail and evidence timeline.
- Acknowledge, mute, suppress, and resolve flows.
- RBAC and audit logging.
- Private preview launch.

Exit criteria:

- Preview customers can use the console without support intervention.
- Alert lifecycle actions are audited.
- API and UI latency meet preview SLOs.

### M4: Notifications, Scale Hardening, And GA, 4-8 Weeks

Deliverables:

- Notification integrations through existing notification channels.
- Tenant-level rule enablement and preferences.
- Canary rollout automation.
- Runbooks and incident response drills.
- GA readiness review.

Exit criteria:

- End-to-end SLOs met under load.
- Support docs and escalation paths complete.
- Rollback and kill switches tested.
- High-confidence rules enabled by default.

## Engineering Execution Practices

- Weekly cross-functional risk review.
- Architecture decision records for major tradeoffs.
- Rule review board for customer-visible rules.
- Contract tests for agent event schemas.
- Load tests before every broad rollout stage.
- Game days for regional outage, stream lag, state-store throttling, and notification backlog.
- Feature flags by region, tenant, rule, and notification channel.

## Quality Strategy

### Unit Tests

- Schema validation.
- Rule predicate behavior.
- State transition logic.
- Alert idempotency key generation.
- Suppression and maintenance-window logic.

### Integration Tests

- Agent event to normalized health fact.
- Normalized fact to state update.
- State update to alert candidate.
- Alert candidate to alert lifecycle.
- Console API authorization and pagination.

### Replay Tests

- Historical event replay for selected tenants.
- Rule version comparison.
- Out-of-order event replay.
- Duplicate event replay.
- Regional outage simulation.

### Load And Soak Tests

- Peak ingestion.
- Large tenant hot partition test.
- Consumer lag recovery.
- State-store write saturation.
- Alert storm and notification backlog.

## Observability Readiness

Required dashboards before customer preview:

- Ingestion health by region.
- Consumer lag by topic and partition.
- End-to-end detection latency.
- State-store latency and throttling.
- Alert candidate and dedupe rates by rule.
- Open alert count by tenant tier.
- Notification backlog.
- API latency and errors.

Required alerts before customer preview:

- Durable publish failure.
- Consumer lag above SLO.
- State update failures.
- Dead-letter spike.
- Alert creation failure.
- Duplicate alert spike.
- Notification backlog age.
- Console API error rate.

## Operational Runbooks

### Stream Lag Spike

1. Check whether lag is global, regional, topic-specific, or tenant-specific.
2. Scale stream processors if downstream stores are healthy.
3. If state store is throttling, reduce consumer rate and protect ingestion.
4. Disable low-priority rules if alert candidate processing is the bottleneck.
5. Communicate detection freshness impact using `as_of` timestamps.

### Alert Storm

1. Identify rule, tenant, region, and condition fingerprint.
2. Confirm whether this is real customer impact or pipeline artifact.
3. Apply rule-level or tenant-level suppression through audited control plane.
4. Preserve candidate events for postmortem.
5. Backfill resolved or corrected alerts if needed.

### Regional Ingestion Incident

1. Distinguish endpoint connectivity loss from ingestion service failure.
2. Mark region freshness degraded.
3. Suppress missing-heartbeat alerts caused by platform incident.
4. Fail over traffic if supported by agent routing.
5. Replay retained events after recovery.

### State Store Degradation

1. Keep ingestion accepting events if stream publish is healthy.
2. Slow or pause consumers that write to the degraded store.
3. Serve console data with freshness warnings.
4. Rebuild latest state from state-change stream or raw replay after recovery.

## Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| False positives reduce customer trust | Customers disable alerts | Shadow mode, preview program, explainable evidence, conservative defaults. |
| Hot tenants create stream partition imbalance | Delayed detection | Tenant sharding, dedicated lanes, autoscaling, lag-based routing. |
| Missing heartbeat interpreted as endpoint failure during platform outage | Massive alert storm | Ingest health correlation and platform-incident suppression. |
| Rule changes create inconsistent historical behavior | Customer confusion | Rule versioning and replay/dry-run. |
| API queries scan too much data | Console degradation | Precomputed read models, pagination, bounded filters. |
| Notification retries duplicate external tickets | Customer friction | Idempotency keys per integration target. |
| Agent versions emit inconsistent fields | Bad state | Schema compatibility and version-aware normalizers. |

## Staffing And Leadership Notes

For an L7+ senior manager interview, emphasize:

- Driving alignment across platform, product, frontend, data, SRE, security, and support.
- Sequencing delivery to learn in shadow mode before customer-visible alerts.
- Making explicit reliability and trust tradeoffs.
- Creating mechanisms: rule review, rollout gates, SLOs, runbooks, and post-launch feedback loops.
- Delegating ownership while keeping architectural coherence.

## Success Metrics

Product:

- Percentage of managed agents with current health state.
- Alert acknowledgement rate.
- Mean time from condition to customer visibility.
- Customer-reported false positive rate.
- Reduction in support cases related to agent health ambiguity.

Engineering:

- Ingestion availability.
- Detection latency.
- Replay success rate.
- Consumer lag recovery time.
- Duplicate alert rate.
- Change failure rate.

Customer experience:

- Console page load latency.
- Time to identify affected endpoint scope.
- Notification delivery success.
- Rule opt-out rate.

