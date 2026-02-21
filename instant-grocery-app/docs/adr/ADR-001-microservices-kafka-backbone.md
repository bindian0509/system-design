# ADR-001: Domain-Partitioned Microservices with Kafka Async Backbone

**Date:** 2026-02-22
**Status:** Accepted
**Deciders:** Platform Engineering

## Context

The instant grocery platform operates across 40 dark stores in a single metro, handling 100,000 orders per day with a peak throughput of 500 orders per minute and 10,000 concurrent active riders. The system encompasses seven distinct business domains: ordering, catalog, inventory, dispatch, ETA, notifications, and users. Each domain has meaningfully different read/write ratios, scaling characteristics, latency budgets, and team ownership boundaries. Catalog is read-heavy with infrequent writes; dispatch is event-driven with high fanout; inventory is write-contention-heavy at peak.

At 500 orders per minute, a single process handling all seven concerns creates dangerous resource contention. A catalog search spike — triggered by a flash sale or regional push notification — would compete for CPU, memory, and database connection pool slots against order placement. This is unacceptable: a customer in the order confirmation flow must receive a definitive response within 500ms. A search-induced CPU saturation event on a monolith would blow that budget with no isolation boundary to contain the blast.

The order placement critical path specifically requires synchronous coordination: inventory must be reserved and payment authorized before the customer receives an "Order Confirmed" response. Both operations are user-blocking and must complete within the 500ms window. Returning a provisional "we'll confirm shortly" response for payment is not acceptable for the customer experience at this scale. However, everything downstream — notifying the picker, assigning a rider, computing an ETA, sending an SMS — can tolerate seconds of delay without affecting UX.

The dispatch team ships updates 4-5 times per week, iteration cycles that are blocked when dispatch code is entangled with catalog or user code. Independent deploy cadence requires independent deployable units. The team also needs to scale Dispatch workers to 10,000 concurrent riders without proportionally scaling catalog replicas, which serve a fundamentally different traffic pattern.

## Decision

We decompose the platform into seven microservices, each owning its own database and deployed independently: Order Service, Catalog Service, Inventory Service, Dispatch Service, ETA Service, Notification Service, and User Service. Services communicate via Kafka for all asynchronous flows. The sole exception is the order placement critical path — Order Service calls Inventory Service via gRPC and calls Payment Gateway synchronously, because the customer is actively waiting and needs a deterministic answer before the response is returned.

Kafka serves as the async event bus for all post-confirmation flows. The canonical topics are `order.placed`, `inventory.reserved`, `inventory.failed`, `rider.assigned`, `order.packed`, and `order.delivered`. Each downstream consumer (Dispatch, Notification, ETA, Analytics) subscribes independently, processes at its own pace, and fails in isolation without affecting other consumers or the order placement path.

## Alternatives Considered

### Option A: Domain microservices with selective synchronous critical path ✅

- Seven services each own a dedicated database; schema changes in one domain never require coordinated migrations across others
- Kafka decouples producers from consumers: if Notification Service goes down during a peak, orders continue to flow; notifications drain from the topic when the service recovers
- The critical path (Order → Inventory gRPC, Order → Payment sync) is synchronous only where the customer is blocked, minimizing blast radius of async failure modes
- Each service scales independently: Dispatch workers can be auto-scaled against Kafka consumer lag without scaling Catalog replicas
- Independent deploy pipelines mean a Dispatch hotfix ships in minutes without a full platform regression cycle

### Option B: Monolith or three coarse-grained services

Simpler to operate initially: one deployment, one database, no distributed tracing overhead. Rejected because at 500 orders per minute a search spike — driven by a marketing push or flash sale — would contend for the same process and database connection pool as order placement. There is no isolation boundary: a slow catalog query holds a connection that could have served an inventory reservation. Independent scaling of Dispatch from Search is impossible in a single deployable unit; to handle 10,000 concurrent riders the entire monolith must be scaled, which is economically wasteful and operationally risky.

### Option C: Full event sourcing and CQRS across all services

Provides an excellent audit trail and enables temporal queries (replay state to any point in time), which is genuinely valuable for the Order and Inventory domains. Rejected because the operational overhead — event store management, projection rebuilding, eventual read-model consistency — is disproportionate for services like Catalog and User where write volume is low and the query model closely mirrors the write model. CQRS provides marginal benefit for a catalog where product updates happen dozens of times per day, not thousands. The team would absorb significant complexity for tooling that benefits at most two of seven services.

## Consequences

### Positive

- Each service can be scaled to match its specific traffic pattern: Dispatch workers scale against Kafka lag, Catalog scales against HTTP search RPS, Order scales against order placement TPS
- A Dispatch Service outage does not affect order placement or catalog browsing; Kafka buffers rider assignment events until Dispatch recovers
- Teams can ship independently without coordinating cross-service releases; a catalog schema migration does not block a dispatch hotfix
- Consumer lag on individual Kafka topics provides a clear, measurable SLA signal per domain; alerting is straightforward
- Blast radius of a bug or deployment failure is bounded to the owning service and its consumers

### Negative (Trade-offs)

- Seven services to operate, monitor, and on-call for; the operational burden is meaningfully higher than a monolith
- Distributed tracing (OpenTelemetry with a correlation trace ID propagated through Kafka message headers) is required to reconstruct the end-to-end order journey across service boundaries
- Eventual consistency between Order state and rider assignment: after `order.placed` is published, there is a window (typically under 2 seconds) where the order exists but no rider is assigned; the UX must handle this gracefully (show "Finding a rider..." state)
- Schema changes to Kafka event payloads require backward-compatible versioning discipline; a breaking change to `order.placed` would require coordinated consumer updates across Dispatch, Notification, ETA, and Analytics simultaneously
- Local development requires running Kafka and multiple service instances, increasing developer environment complexity

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Kafka consumer lag spike during peak causing Dispatch SLA breach | Medium | High | Auto-scale Dispatch worker pods against `kafka_consumer_lag` metric; alert at lag > 500 messages on `order.placed` topic |
| Network partition between Order Service and Inventory Service during critical path | Low | High | Circuit breaker on Inventory gRPC client; on open circuit, fall back to soft reservation with reconciliation job catching oversell |
| `order.placed` event schema breaking change deployed without consumer coordination | Medium | High | Enforce schema registry validation on all Kafka producers; consumers subscribe to versioned schema and reject incompatible payloads with dead-letter routing |
| Single Kafka cluster becomes a single point of failure | Low | High | Kafka cluster runs with replication factor 3 across 3 availability zones; topic durability configured with `min.insync.replicas=2` |
| Distributed tracing gaps making incident triage slow | Medium | Medium | Enforce trace ID propagation in all service SDKs; integration test suite validates header forwarding before merge |
