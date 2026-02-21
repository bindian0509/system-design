# ADR-007: Write-Ahead Order Row + Idempotency Key for Payment Safety

**Date:** 2026-02-22
**Status:** Accepted
**Deciders:** Platform Engineering

## Context

Payment authorisation is the highest-risk step in the order placement flow. The fundamental hazard is a network timeout that occurs after the Payment Service has successfully charged the customer but before the Order Service receives and processes the HTTP response. In this scenario the customer has been debited but no order record exists in the system — a "ghost charge." The customer receives no confirmation, the operations team has no order to fulfil, and the charge appears on the customer's payment instrument with no corresponding activity. At 100,000 orders per day, even a 0.1% network timeout rate produces 100 ghost charges daily. At the system's peak of 500 orders per minute, a 30-second payment provider degradation event can affect 250 in-flight payment calls simultaneously.

The problem has two distinct sub-problems that must both be solved. First, safe retries: if the Order Service times out and retries the payment call, the Payment Service must recognise the retry and return the cached result of the first attempt rather than authorising a second charge. Without this, every retry is a potential duplicate charge. Second, order recovery: even if retries are made safe, there must be a record of the in-flight order that can be inspected and resolved when the outcome of the payment call is ambiguous. Without a pre-existing order record, a timed-out payment call leaves no artefact to reconcile against.

The standard distributed systems approaches to cross-service consistency — Saga pattern with compensating transactions, and two-phase commit — each have significant drawbacks in this context. The Payment Service is an external provider (Razorpay, Stripe, or equivalent) operating outside our transaction boundary, which eliminates 2PC as a viable option. The Saga pattern, while architecturally sound, adds an asynchronous Kafka round-trip to an already latency-sensitive checkout path and shifts the reconciliation problem from a simple SQL query to event log archaeology.

The chosen approach must satisfy three properties: it must prevent duplicate charges on retry, it must ensure a recoverable artefact exists regardless of what happens to the payment call, and it must degrade gracefully from the customer's perspective — showing a "processing" state rather than an error when resolution is pending.

## Decision

Three mechanisms are combined to cover the full failure surface.

Idempotency key: Before calling the Payment Service, the Order Service generates a UUID and stores it on the order row as `idempotency_key`. This UUID is sent as an `Idempotency-Key` HTTP header on every payment call for that order, including retries. The Payment Service stores `(idempotency_key, result)` and returns the cached result on any subsequent call with the same key without re-authorising the charge. This makes the payment call safe to retry unconditionally.

Write-ahead order row: Before the payment call is made, Order Service writes the order to PostgreSQL with `status = 'PAYMENT_PENDING'`. The row includes all order data — items, amounts, customer ID, store ID, idempotency key — so that the order is fully reconstructable from the database alone. This ensures that even if the payment call hangs indefinitely and the Order Service process dies, the order record survives and can be acted upon.

Async reconciliation job: A scheduled job runs every 5 minutes and executes `SELECT * FROM orders WHERE status = 'PAYMENT_PENDING' AND created_at < NOW() - INTERVAL '5 minutes'`. For each row found, the job re-queries the Payment Service using the stored `idempotency_key` to retrieve the actual outcome of the original charge attempt. If the payment was authorised, the job transitions the order to `PAYMENT_CONFIRMED` and enqueues it for picking. If the payment failed or was never initiated, the job transitions to `PAYMENT_FAILED` and triggers a customer notification confirming no charge was made. The job is idempotent: re-running it on the same stuck orders is safe.

Customer-facing behaviour: while an order sits in `PAYMENT_PENDING`, the app displays "Processing your order…" rather than an error. The maximum customer-visible delay before resolution is 10 minutes (5-minute job interval plus up to 5 minutes of processing time). If resolved successfully, the order flow continues normally. If resolved as failed, the customer receives a push notification and in-app message confirming no charge occurred.

## Alternatives Considered

### Option A: Write-ahead order row + idempotency key + async reconciliation job ✅
- Idempotency key makes the payment call safe to retry without any coordination beyond storing a UUID — no distributed lock, no event bus, no two-system atomicity required
- Write-ahead row ensures the order is recoverable from PostgreSQL alone; even total Order Service failure leaves a resolvable artefact
- Reconciliation job is simple, observable, and independently deployable; it is a plain SQL query against a well-understood table, not a complex event replay
- Customer experience degrades to a "processing" state rather than a hard error, which is a significantly better outcome than showing an error that might not reflect reality
- Relies on Payment Service honouring the idempotency key contract, which is a standard feature of all major payment providers (Razorpay, Stripe, Cashfree)

### Option B: Saga pattern with compensating transactions
- Adds a Kafka publish + consume round-trip to the critical checkout path; at p99 Kafka latency of 50–100ms this pushes total checkout latency closer to the 1-second boundary that measurably impacts conversion
- Event loss or consumer lag during a Kafka outage means the Order Service may never receive the payment result event, requiring its own dead-letter queue reconciliation — the same reconciliation problem exists, just with more infrastructure
- Compensating transactions (charge reversal on failure) require the Payment Service to support reversals, which is a stronger API contract than idempotency key support alone; some payment methods (UPI, net banking) have non-trivial reversal SLAs

### Option C: Two-phase commit (2PC) across Order DB and Payment Service
- Payment Service is an external provider operating outside our transaction boundary and does not implement the 2PC protocol; this option is architecturally impossible without wrapping the external provider in a proxy that emulates prepare/commit, which introduces more complexity than it solves
- 2PC is a blocking protocol: the coordinator holds locks across a network boundary while waiting for participant votes; under network partition this produces indefinite lock hold, which is catastrophic for the orders table at 500 writes/minute
- Even within systems that support 2PC (e.g., XA transactions), the protocol is known to cause latency spikes and is widely avoided in high-throughput OLTP workloads

## Consequences

### Positive
- Ghost charges are prevented: any retry of a timed-out payment call returns the cached result from the first attempt, not a second authorisation
- Write-ahead row guarantees that every payment attempt has a corresponding database record; there are no invisible in-flight orders
- Reconciliation job logic is a plain SQL query against a standard table — easily auditable, testable, and re-runnable by operations without special tooling
- Customer experience during ambiguity is a neutral "processing" state, not an error message that may prompt unnecessary support contacts or re-order attempts (which would themselves create new idempotency key calls, safe but confusing)
- `orders_payment_pending_gt_10min` can be surfaced as a first-class SLO metric, giving operations a leading indicator of payment provider degradation

### Negative (Trade-offs)
- Orders can remain in `PAYMENT_PENDING` for up to 10 minutes before resolution; during a sustained payment provider outage this window may extend further and the pending order backlog will grow
- Reconciliation job adds an operational dependency: it must be deployed, monitored, and included in on-call runbooks as a separate concern from the Order Service itself
- The solution depends on the Payment Service correctly implementing the idempotency key contract; if the provider does not honour it, the safety guarantee is broken and duplicate charges become possible on retry

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Reconciliation job itself fails or is not deployed, leaving PAYMENT_PENDING orders permanently stuck | Low | High | Alert fires if any order remains in PAYMENT_PENDING for more than 15 minutes; job is idempotent so safe to trigger manually; include in deployment checklist and smoke test suite |
| Payment Service does not honour idempotency key, causing duplicate charges on retry | Low | High | Contract test against payment provider sandbox as part of CI pipeline; if idempotency is absent, disable automatic retry and route stuck orders to manual ops review queue instead |
| High volume of PAYMENT_PENDING orders during a payment provider outage overwhelms the reconciliation job on recovery | Medium | Medium | Circuit breaker on the Payment Service call stops new payment attempts after 5 consecutive failures, preventing further PAYMENT_PENDING accumulation; circuit breaker half-open probe rate controls recovery pace |
| Customer attempts to re-place the same order during the PAYMENT_PENDING window, creating a duplicate order | Medium | Medium | UI disables the checkout button and shows the processing state for the active session; session cookie links to the existing PAYMENT_PENDING order; duplicate detection on (customer_id, cart_hash, created_at window) blocks duplicate inserts at the database layer |
