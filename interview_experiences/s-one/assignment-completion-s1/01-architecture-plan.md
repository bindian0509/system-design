# Singularity Health Center Architecture Plan

## Executive Framing

Singularity Health Center is a multi-tenant operational health platform for SentinelOne agents. It ingests high-volume endpoint telemetry, derives health state per agent, detects operational anomalies, and delivers actionable alerts to the SentinelOne console, APIs, and notification channels.

The design optimizes for:

- High ingest throughput: billions of telemetry events per day.
- Low-latency detection: seconds to minutes for event-driven anomalies, bounded windows for heartbeat-based anomalies.
- Trustworthy alerts: deduplication, suppression, explainability, and policy-aware context.
- Tenant isolation: noisy customers cannot degrade other tenants.
- Operability: graceful degradation, replayability, auditable state transitions, and safe rollout.

## Goals

- Detect agent disabled, anti-tamper disabled, connectivity loss, stale heartbeat, low disk, telemetry gaps, and version/config drift.
- Maintain latest health state per agent and aggregate health posture per site, group, account, and tenant.
- Provide actionable alerts with severity, evidence, recommended remediation, and affected scope.
- Support console views, APIs, webhooks, ticketing integrations, and customer notification preferences.
- Allow historical investigation and backfill when rules change.

## Non-Goals

- Replacing the security detection pipeline for malicious activity.
- Delivering arbitrary customer-defined analytics in v1.
- Performing endpoint remediation directly in the first milestone unless an existing command channel already supports it.
- Guaranteeing exact-once alerting across all downstream integrations. The platform should be effectively-once using idempotency keys and dedupe.

## Capacity Model

Use explicit assumptions in the interview and show how the design scales if the interviewer changes them.

| Dimension | Example Assumption | Design Implication |
| --- | ---: | --- |
| Managed agents | 10 million | State store must handle tens of millions of hot keys. |
| Telemetry events | 5 billion/day | Average ~58k events/sec before peak multiplier. |
| Peak multiplier | 10x | Plan for ~580k events/sec regional burst capacity. |
| Event size | 0.5-2 KB compressed | 25-100 TB/day compressed raw ingest envelope. |
| Detection latency | P95 < 2 min | Stream processing plus windowed heartbeat detection. |
| Alert fanout | 1-5% agents/day affected during incidents | Dedup and grouping are mandatory. |

The exact numbers are less important than the posture: partition by tenant and agent, autoscale processors, protect shared dependencies, and retain raw events for replay.

## High-Level Architecture

1. Agents emit signed telemetry and heartbeat events to regional ingestion gateways.
2. Ingestion services authenticate, validate, rate-limit, enrich, and publish events to a durable streaming backbone.
3. Stream processors normalize telemetry, deduplicate repeated events, and update per-agent health state.
4. A rule and anomaly engine evaluates state transitions and time-window conditions.
5. Alert orchestration creates grouped, deduplicated alerts with evidence and remediation metadata.
6. Read APIs serve console dashboards, drilldowns, exports, and integrations.
7. Raw events and state-change facts are stored in a data lake for replay, audit, and analytics.

## Component Responsibilities

### Agent Telemetry Contract

Events should be schema-versioned and backward compatible.

Required fields:

- `tenant_id`
- `site_id`
- `agent_id`
- `agent_uuid`
- `event_id`
- `event_type`
- `event_time`
- `ingest_time`
- `agent_version`
- `os_type`
- `policy_id`
- `sequence_number`, when available
- `payload`
- `signature` or transport-level identity assertion

Health event examples:

- `agent.heartbeat`
- `agent.status.changed`
- `agent.protection.disabled`
- `agent.antitamper.changed`
- `agent.disk.low`
- `agent.connectivity.changed`
- `agent.policy.applied`
- `agent.upgrade.changed`

### Regional Ingestion Gateway

Recommended implementation: Go for high-throughput IO and predictable resource usage.

Responsibilities:

- Terminate mTLS or validate agent identity through existing SentinelOne agent auth.
- Enforce per-tenant and per-agent rate limits.
- Validate envelope and schema version.
- Attach `ingest_region`, `ingest_time`, and request metadata.
- Reject malformed events with sampled diagnostics.
- Publish accepted events to the streaming backbone.
- Return fast acknowledgements after durable publish.

Key decision: acknowledge after durable stream write, not after downstream processing. This isolates agents from health processing spikes.

### Streaming Backbone

Use Kafka-compatible infrastructure, cloud-managed Kafka, or a SentinelOne-standard equivalent. In AWS/GCP, Kinesis/Pub/Sub can also work, but Kafka keeps a portable mental model across regions and cloud providers.

Topic strategy:

- `agent-telemetry-raw-v1`
- `agent-health-normalized-v1`
- `agent-health-state-changes-v1`
- `agent-health-alert-candidates-v1`
- `agent-health-alerts-v1`
- `agent-health-dead-letter-v1`

Partition key:

- Primary: `tenant_id + agent_id`
- Optional high-volume tenant sharding: `tenant_id + hash(agent_id)`.

This keeps most per-agent events ordered while distributing large tenants.

### Schema Registry

Responsibilities:

- Enforce compatibility.
- Support versioned protobuf or Avro schemas.
- Allow old agents to emit old event versions during staged upgrades.
- Block incompatible producers in CI/CD before deployment.

### Normalization And Deduplication

Recommended implementation: Java with Flink/Kafka Streams, or Go if the organization has strong stream-processing primitives there.

Responsibilities:

- Parse raw events into canonical health facts.
- Validate tenant ownership and agent existence using cached metadata.
- Deduplicate by `tenant_id + event_id`; fall back to `agent_id + sequence_number + event_type`.
- Handle late and out-of-order events using event-time windows.
- Emit normalized health facts and bad records to a dead-letter topic.

### Health State Service

Maintains the latest health state for each agent.

State dimensions:

- Connectivity: online, offline, degraded, unknown.
- Protection status: enabled, disabled, partially disabled.
- Anti-tamper: enabled, disabled, unknown.
- Disk: normal, warning, critical, unknown.
- Agent lifecycle: active, decommissioned, uninstalled, duplicate identity suspected.
- Policy compliance: expected policy, applied policy, drift state.
- Last seen: event time and ingest time.

Storage:

- Hot state: DynamoDB/Cassandra/Bigtable equivalent, keyed by `tenant_id, agent_id`.
- Cache: Redis or in-process cache for high-read dashboard paths.
- Historical state changes: append-only topic plus object storage table such as Iceberg/Delta/BigQuery partitioned by date and tenant.

Why not store everything in Elasticsearch/OpenSearch first?

- Search is useful for investigation, but the source of truth for latest state should be a predictable key-value store. Search systems are weaker for high-churn authoritative state and can become expensive under write amplification.

### Rule And Anomaly Engine

Start with deterministic rules; leave room for statistical anomaly detection later.

Rule types:

- State transition: anti-tamper changed from enabled to disabled.
- Threshold: disk free percent below policy threshold.
- Absence: no heartbeat for N minutes.
- Aggregation: more than X% agents in a group lose connectivity in 10 minutes.
- Policy-aware: protection disabled but only alert if outside a maintenance window or expected policy state.

Rule requirements:

- Versioned rule definitions.
- Tenant and policy overrides.
- Explainable evidence.
- Simulation mode before production enforcement.
- Replay support for backtesting.

Implementation option:

- Java service for core rule evaluation.
- Python offline jobs for rule quality analysis, threshold tuning, and anomaly research.

### Alert Orchestration Service

Responsibilities:

- Convert rule matches into alert candidates.
- Deduplicate by stable idempotency key.
- Group related agents into incidents.
- Suppress noisy or expected conditions.
- Track lifecycle: open, updated, acknowledged, muted, resolved, reopened.
- Emit notifications and update console read models.

Alert idempotency key examples:

- `tenant_id + rule_id + agent_id + condition_fingerprint` for per-agent alerts.
- `tenant_id + rule_id + group_id + window_start` for grouped incidents.

Alert lifecycle:

- Open when condition is confirmed.
- Update when evidence or affected scope changes.
- Resolve after the condition clears and remains healthy for a configurable grace period.
- Reopen if the same condition recurs after cooldown.

### Console And API Layer

Recommended implementation:

- Backend-for-frontend in Java or Go.
- React console views using existing SentinelOne design system.

Core views:

- Health Center overview by tenant/site/group.
- Affected agents list with filters.
- Alert detail with evidence timeline.
- Rule configuration and notification preferences.
- Suppression, maintenance windows, and acknowledgement workflows.

API examples:

```http
GET /v1/health/summary?tenantId={tenant_id}
GET /v1/health/agents?tenantId={tenant_id}&status=unhealthy&reason=anti_tamper_disabled
GET /v1/health/agents/{agent_id}
GET /v1/health/alerts?tenantId={tenant_id}&state=open
POST /v1/health/alerts/{alert_id}/ack
POST /v1/health/suppressions
POST /v1/health/rules/{rule_id}/dry-run
```

Response principles:

- Use cursor pagination.
- Include server-generated `as_of` timestamps.
- Avoid expensive unbounded filters.
- Enforce tenant isolation at every layer, not only in UI.

## Data Model

### `agent_health_state`

| Field | Notes |
| --- | --- |
| `tenant_id` | Partition key component. |
| `agent_id` | Sort/key component. |
| `site_id` | Denormalized for query and grouping. |
| `group_ids` | Used for rollups and authorization. |
| `last_seen_event_time` | Agent-reported event time. |
| `last_seen_ingest_time` | Server-observed ingest time. |
| `connectivity_status` | online/offline/degraded/unknown. |
| `protection_status` | enabled/disabled/partial/unknown. |
| `anti_tamper_status` | enabled/disabled/unknown. |
| `disk_status` | normal/warning/critical/unknown. |
| `policy_id` | Current expected policy. |
| `policy_revision` | Helps distinguish drift from stale metadata. |
| `health_score` | Optional derived score for ranking. |
| `state_version` | Monotonic version for optimistic writes. |
| `updated_at` | Server update time. |

### `health_alert`

| Field | Notes |
| --- | --- |
| `tenant_id` | Required for isolation. |
| `alert_id` | Stable unique ID. |
| `idempotency_key` | Unique constraint. |
| `rule_id` | Versioned rule identity. |
| `severity` | critical/high/medium/low/info. |
| `state` | open/acknowledged/muted/resolved. |
| `affected_scope` | agent/site/group/tenant. |
| `affected_agent_count` | Supports grouped incidents. |
| `first_seen_at` | Event or detection time. |
| `last_seen_at` | Updated on repeated evidence. |
| `resolved_at` | Nullable. |
| `evidence` | Compact JSON facts, not full raw payload dump. |
| `recommended_action` | Product-owned remediation guidance. |

### `health_state_change`

Append-only facts for audit and replay:

- `tenant_id`
- `agent_id`
- `change_id`
- `previous_state_hash`
- `new_state_hash`
- `source_event_ids`
- `rule_context`
- `event_time`
- `processed_at`

## Detection Semantics

### Agent Disabled

Signal sources:

- Direct `agent.status.changed` event.
- Absence of protection telemetry while heartbeats continue.
- Policy state showing protection expected but runtime status disabled.

Avoid false positives:

- Check decommission/uninstall state.
- Respect maintenance windows.
- Distinguish customer-initiated disablement from unexpected disablement.

### Anti-Tamper Disabled

Signal sources:

- `agent.antitamper.changed`.
- Periodic heartbeat field reporting anti-tamper status.
- Policy compliance reports.

Alerting:

- Critical if policy requires anti-tamper and the endpoint is active.
- Suppress if policy explicitly disables anti-tamper for that group.

### Connectivity Loss

Signal sources:

- Missing heartbeat beyond threshold.
- Explicit disconnect event.
- Regional ingest gap metrics.

Design detail:

- Missing data is not the same as unhealthy endpoint. The system must distinguish endpoint offline, network partition, regional ingestion incident, and pipeline delay.

### Low Disk Space

Signal sources:

- Agent disk metric events.
- Failed update or scan events caused by insufficient disk.

Alerting:

- Use thresholds by OS and policy.
- Avoid alert storms by grouping per site/group and using cooldown.

## Multi-Tenancy And Isolation

Isolation controls:

- Tenant-aware auth at ingestion and API layers.
- Per-tenant quotas and burst budgets.
- Partitioning strategy that prevents one hot tenant from monopolizing processors.
- Separate high-volume tenant lanes for enterprise customers if needed.
- Resource usage and lag metrics tagged by tenant tier, with cardinality controls.
- Authorization filters applied server-side for site/group-scoped users.

Data protection:

- Encrypt in transit and at rest.
- Do not expose cross-tenant aggregate metadata in customer-visible APIs.
- Scrub sensitive endpoint metadata from logs.
- Store only compact alert evidence in transactional alert tables; raw event detail stays in controlled analytics storage.

## Resilience And Backpressure

Failure posture:

- If alerting is degraded, continue durable ingest.
- If state store is degraded, buffer and retry from the stream.
- If notification delivery fails, retry with idempotency and expose delivery status.
- If metadata lookup fails, process with cached metadata and mark confidence lower.

Backpressure controls:

- Per-tenant rate limiting at ingestion.
- Stream consumer lag alarms.
- Autoscaling on lag, CPU, and state-store write latency.
- Dead-letter queue for poison events.
- Circuit breakers around metadata, alert, and notification dependencies.

Replay strategy:

- Retain raw events for a defined period.
- Reprocess by tenant, time range, and rule version.
- Keep rule versions so historical alerts remain explainable.
- Support dry-run replay before enabling a rule globally.

## Observability

Golden signals:

- Ingest accepted/rejected events per second.
- Stream publish latency.
- Consumer lag by topic, partition, region, and tenant tier.
- Processing latency from event time and ingest time.
- State update success rate and latency.
- Alert candidate rate, dedupe rate, open/update/resolve counts.
- Notification success rate.
- API P50/P95/P99 latency and error rates.

Key SLOs:

- Ingestion availability: 99.99%.
- Health detection latency: P95 under 2 minutes for direct signals.
- Heartbeat anomaly detection: P95 under threshold + 2 minutes.
- Console API availability: 99.9%.
- Alert duplicate rate: under 0.1% for same condition per cooldown period.

Dashboards:

- Regional ingestion health.
- End-to-end event freshness.
- Rule-level alert volume and false-positive indicators.
- Tenant hot spots.
- State-store saturation.
- Notification backlog.

## Security

Controls:

- Agent identity validation and mTLS or equivalent.
- Signed events or authenticated transport.
- Tenant ID derived from credentials where possible, not blindly trusted from payload.
- Least privilege service accounts.
- Secrets managed through cloud secret manager and Kubernetes integration.
- Audit logs for suppression, acknowledgement, rule changes, and customer-visible config.
- RBAC for console actions.

Abuse cases:

- Compromised endpoint floods telemetry.
- Malformed payload attempts parser failure.
- Cross-tenant spoofed `tenant_id`.
- Replay of old disablement event.
- Alert API enumeration.

Mitigations:

- Rate limits, schema validation, idempotency, event age bounds, auth-derived tenancy, and cursor tokens scoped to tenant and user permission.

## Implementation Choices By Language

| Area | Preferred Language | Rationale |
| --- | --- | --- |
| Ingestion gateway | Go | High-throughput IO, low overhead, simple deployable services. |
| Stream processing | Java | Mature Kafka/Flink ecosystem and operational familiarity. |
| Rule analytics and threshold tuning | Python | Fast iteration for offline analysis and notebooks/jobs. |
| APIs and BFF | Java or Go | Match platform standards and service ownership. |
| Frontend | React | Existing console framework. |

## Deployment Architecture

- Kubernetes services deployed by Helm.
- Terraform provisions Kafka/Pub/Sub/Kinesis, state stores, object storage, IAM, networking, and observability sinks.
- ArgoCD manages environment promotion.
- GitHub Actions runs tests, schema compatibility checks, image builds, security scans, and Helm validation.
- Use canary deployments and feature flags per tenant, region, and rule.

## Rollout Plan

1. Internal dogfood with synthetic tenants and replayed historical telemetry.
2. Shadow mode: compute health state and alert candidates without customer-visible alerts.
3. Private preview: read-only console with limited tenants.
4. Alerting preview: notifications disabled by default, customer opt-in.
5. General availability: enable default high-confidence rules.
6. Expand rule coverage and grouped incident detection.

## Key Tradeoffs

### Streaming vs Batch

Streaming is required for timely alerting and current health state. Batch remains valuable for replay, analytics, and rule quality measurement.

### Deterministic Rules vs ML

Start deterministic. Customers need explainability and trust. Use ML or statistical methods later for fleet-level anomalies where deterministic thresholds are insufficient.

### Per-Agent Alerts vs Grouped Incidents

Per-agent alerts are precise but noisy. Grouped incidents are actionable during broad outages. The system should support both, with grouping as the default for high-cardinality conditions.

### Exactly-Once vs Effectively-Once

Exactly-once across streaming, state store, alerts, and external notifications is expensive and fragile. Use idempotent writes, idempotency keys, monotonic state versions, and dedupe windows.

