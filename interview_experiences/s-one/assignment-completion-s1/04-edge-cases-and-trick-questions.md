# Edge Cases And Trick Questions

This file is designed for interview prep. The best answers show that you can protect customer trust, operate at scale, and think through distributed-system ambiguity.

## Event Ordering

### Trick Question

What if an agent sends `anti_tamper_disabled` and then `anti_tamper_enabled`, but the events arrive in the reverse order?

### Strong Answer

Use event time, sequence number where available, and bounded out-of-order windows. The state updater should not blindly apply the latest ingested event. It should use a per-agent state version and reject stale transitions unless the event is explicitly marked as a correction. If ordering cannot be trusted, mark confidence lower and wait for the next heartbeat snapshot.

## Duplicate Events

### Trick Question

How do you avoid duplicate alerts if the same event is retried by the agent or replayed by the stream processor?

### Strong Answer

Deduplicate raw events by `tenant_id + event_id`, then deduplicate alerts with a stable idempotency key such as `tenant_id + rule_id + agent_id + condition_fingerprint`. External notification calls also need idempotency keys because downstream systems may retry independently.

## Missing Heartbeat

### Trick Question

If an agent stops sending heartbeat, how do you know whether the endpoint is unhealthy or your ingestion pipeline is down?

### Strong Answer

Correlate missing heartbeats with regional ingest freshness, stream lag, and other agents in the same tenant/site/region. If pipeline freshness is degraded, suppress endpoint-specific connectivity alerts and surface a platform freshness state internally. Missing data must not automatically equal endpoint failure.

## Clock Skew

### Trick Question

What if agent clocks are wrong by hours or days?

### Strong Answer

Store both `event_time` and `ingest_time`. Use event time for ordering only within an acceptable skew bound. If skew exceeds the bound, use ingest time for freshness and flag the agent for clock skew. Very old events should not reopen resolved alerts unless processed as explicit replay or correction.

## Hot Tenant

### Trick Question

One enterprise tenant sends 30% of all events. What breaks?

### Strong Answer

If partitioning is only by tenant, that tenant creates hot partitions. Partition by `tenant_id + hash(agent_id)` and apply tenant quotas, dedicated lanes for very large tenants, and autoscaling on lag. Preserve tenant-level isolation so a noisy tenant cannot delay health detection for everyone else.

## Alert Storm

### Trick Question

A regional network outage causes 500,000 agents to look disconnected. Do you create 500,000 alerts?

### Strong Answer

No. Detect correlated scope and create a grouped incident with affected count, representative agents, and scope breakdown. Keep per-agent state queryable, but customer-facing alerting should be grouped and deduplicated. Also check whether the cause is SentinelOne platform freshness before notifying customers.

## Anti-Tamper Disabled By Policy

### Trick Question

Should anti-tamper disabled always be critical?

### Strong Answer

No. It is critical only when it violates expected policy or appears unexpected for an active endpoint. Some tenants or groups may intentionally disable it for troubleshooting, maintenance, or compatibility. The rule engine must be policy-aware and audit configuration changes.

## Agent Disabled During Maintenance

### Trick Question

How do you avoid alerting during customer-approved maintenance?

### Strong Answer

Support maintenance windows and suppressions scoped by tenant, site, group, rule, or agent. Suppression actions must be RBAC-controlled and audited. Suppressed candidates should still be retained for analytics and post-incident review.

## Decommissioned Or Uninstalled Agents

### Trick Question

An endpoint disappears forever. Is that a connectivity loss?

### Strong Answer

Not necessarily. The state engine needs lifecycle metadata. Decommissioned, duplicate, or intentionally uninstalled agents should not create ongoing connectivity alerts. Unknown disappearance might start as connectivity loss, then age into stale inventory handling based on product policy.

## Replay

### Trick Question

You changed a rule threshold. How do you know what would have happened last week?

### Strong Answer

Retain raw events and append-only state changes. Rules are versioned and replayable by tenant and time range. Run the new rule in dry-run against historical data before enabling it. Keep historical alerts tied to the rule version that created them.

## Exactly-Once Processing

### Trick Question

Can you guarantee exactly-once alerts?

### Strong Answer

I would not promise end-to-end exactly-once across agents, streams, state stores, alert DBs, and external integrations. I would design for effectively-once behavior using idempotent producers, idempotency keys, transactional or conditional writes where available, monotonic state versions, and dedupe windows.

## Poison Events

### Trick Question

What if one malformed event crashes the parser repeatedly?

### Strong Answer

Validation happens at ingestion and normalization. Bad records go to a dead-letter topic with bounded retention and sampled payloads. Consumers must isolate poison records so one malformed event cannot block an entire partition indefinitely.

## Metadata Lag

### Trick Question

The agent sends a policy ID that the metadata service has not seen yet. Do you alert on policy drift?

### Strong Answer

Not immediately. Treat metadata freshness as part of confidence. Cache metadata but include revision and freshness. If policy metadata is unavailable or stale, avoid high-severity drift alerts and retry evaluation when metadata catches up.

## Endpoint Identity Collision

### Trick Question

Two machines appear to have the same agent ID. What happens?

### Strong Answer

Detect impossible transitions such as rapid OS/hostname/site changes, conflicting sequence streams, or simultaneous heartbeats from different fingerprints. Mark identity conflict and avoid corrupting authoritative health state until resolved. This is also a security signal and support workflow.

## Backpressure

### Trick Question

If the state store is throttling, should agents stop sending telemetry?

### Strong Answer

No, not immediately. Ingestion should remain decoupled from state processing through durable streams. Slow consumers, scale processors if the store can handle it, shed low-priority processing, and protect high-priority health signals. Apply agent-facing throttles only if durable ingest itself is at risk.

## Customer Permissions

### Trick Question

A console user has access to only one site. Can they see tenant-wide health counts?

### Strong Answer

Only if the product's RBAC explicitly allows it. Aggregates can leak information. Server-side authorization must filter both detail rows and aggregate counts by the user's permitted scope.

## Search And Export

### Trick Question

Can the UI support arbitrary filters over billions of events?

### Strong Answer

Not directly from the hot path. The console should query precomputed health state and alert read models with bounded filters and cursor pagination. Deep historical search should use analytics/search infrastructure with async export jobs.

## Regional Failover

### Trick Question

If a region fails, do agents automatically fail over to another region?

### Strong Answer

That depends on existing agent routing. The Health Center should not assume cross-region failover unless the platform supports it. It should detect regional freshness degradation, prevent false endpoint alerts, and replay retained events after recovery.

## Low Disk Noise

### Trick Question

Low disk can flap around a threshold. How do you prevent alert churn?

### Strong Answer

Use hysteresis and grace periods. For example, open below 5%, resolve only after above 8% for a sustained window. Group alerts for broad impact and limit notification frequency with cooldowns.

## Version Rollout

### Trick Question

Old agents do not emit the new telemetry field. Does Health Center show them as unhealthy?

### Strong Answer

No. Unknown and unhealthy are different states. Schema and normalizers must be version-aware. Show confidence and telemetry coverage so customers understand whether a status is known, unknown, or truly unhealthy.

## Data Retention

### Trick Question

Do you keep all raw endpoint telemetry forever?

### Strong Answer

No. Retention should match product, compliance, cost, and replay needs. Keep hot state compact, state changes longer for audit, and raw telemetry in lower-cost object storage for a bounded period. Apply tenant and regulatory requirements.

## Rule Explosion

### Trick Question

Every customer wants custom thresholds. How do you keep the system maintainable?

### Strong Answer

Separate rule definitions from tenant-specific parameters. Keep a controlled set of product-owned rules with configurable thresholds and suppressions. Avoid arbitrary customer code execution in the detection path.

## Privacy

### Trick Question

Can engineers inspect raw endpoint telemetry when debugging?

### Strong Answer

Access should be least privilege, audited, and ideally through redacted tooling. Customer-sensitive fields should not appear in logs. Debug access should use approved break-glass workflows.

## Cost Control

### Trick Question

What is the most likely cost runaway?

### Strong Answer

High-cardinality metrics, unbounded alert evidence, excessive search indexing, and per-event synchronous writes. Keep hot state compact, sample logs, control metric cardinality, write raw events to object storage, and index only what the product needs.

## Interview One-Liners

- Missing data is a signal, but it is not proof of endpoint failure.
- Unknown, unhealthy, and non-compliant must be separate states.
- Customer trust depends more on dedupe and explainability than on detecting every possible signal on day one.
- The ingestion path should be durable and boring; intelligence can evolve behind the stream.
- Rule changes must be versioned, replayable, and measurable before customer-visible rollout.
- Group broad incidents; do not page customers with one alert per endpoint during fleet-wide events.

