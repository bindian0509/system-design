# ADR-006: Two-Phase ETA (Approximate Pre-Checkout + Precise Post-Assignment)

**Date:** 2026-02-22
**Status:** Accepted
**Deciders:** Platform Engineering

## Context

The app's core value proposition is a 10–15 minute delivery guarantee. ETA is surfaced to the customer in three distinct contexts, each with different latency budgets and accuracy requirements. On the cart page (pre-checkout) the customer has not yet placed an order; they need a fast approximate number to decide whether to order at all. No rider has been assigned, and the order does not yet exist in the system. On the order confirmation screen (post-placement) the order exists, a rider is being or has just been assigned, and the customer expects a more credible number. During live tracking (out-for-delivery state) the rider is en route and the ETA must reflect real GPS position, updating approximately every 30 seconds.

These three contexts differ significantly in what data is available and what the cost of computation is. A precise ETA requires at minimum a Maps API call (for real traffic-aware travel time) and ideally a live rider location lookup. At 100,000 sessions per day, triggering a full Maps API round-trip on every cart-page load would cost on the order of several thousand dollars per month at standard pricing and add 100–200ms to page load time — for a user who statistically converts to an order roughly 30–40% of the time. This means the majority of precise ETA calls would be for users who never place an order.

The congestion state of the dark store (how many active orders exist relative to available pickers) is a real signal that the ETA must reflect. A static label of "10–15 min" regardless of store state fails operationally: during peak hours when a store has 200 active orders and only 12 pickers, the pick time alone can exceed 8 minutes. Showing a static ETA in this scenario leads to SLA violations and customer complaints. The system therefore needs to encode congestion into even the cheapest pre-checkout estimate.

At 500 peak orders per minute, the post-order live-ETA update path must also be efficient. Recomputing a fresh Maps API travel time every 30 seconds per active order during peak would create a bursty API call pattern. A short cache keyed on store-to-zone pair (TTL 5 minutes) amortises this cost across concurrent orders targeting the same delivery zone.

## Decision

ETA is computed in two phases with different data sources, latency targets, and accuracy guarantees.

Phase 1 (pre-checkout, target latency under 100ms): The system uses only store-level signals, all pre-computed and cached in Redis. Pick time is estimated as `T_pick = (2 min + 0.5 min × item_count) × congestion_multiplier`, where `congestion_multiplier` is derived from `active_orders / picker_count` maintained as a Redis counter updated on each order state transition. Travel time is a cached zone-level value keyed on `(store_id, delivery_zone_id)` with a 5-minute TTL, populated from historical average or last Maps API result. The UI displays a range (eta_min to eta_max) to communicate inherent uncertainty. No Maps API call is made. No rider location is consulted.

Phase 2 (post-order and live tracking, target latency under 500ms): Once a rider is assigned, the ETA uses actual data. Rider wait time at the store is computed as `T_wait = distance(rider_position, store) / avg_speed`, where `rider_position` comes from Redis GEO and `avg_speed` is a configurable constant (15 km/h default, tunable per time-of-day). Travel time from store to customer uses a fresh Maps API call, falling back to the zone cache on API failure or rate limit. The resulting ETA is pushed to the customer via WebSocket or server-sent event. During OUT_FOR_DELIVERY state, ETA recalculates every 30 seconds. Delta suppression is applied: an update is only pushed to the customer if the new ETA differs from the displayed ETA by more than 2 minutes, preventing notification noise from minor fluctuations. The 2-minute threshold is overridden if the rider has been stationary for more than 2 minutes (possible delivery delay signal).

## Alternatives Considered

### Option A: Two-phase ETA with cached zone travel times for pre-checkout ✅
- Pre-checkout ETA costs approximately 5ms (two Redis reads: congestion counter and zone travel time cache) — compatible with any session volume without Maps API dependency
- Congestion multiplier encodes real store state without external API calls, giving approximate but directionally correct signals during peak hours
- Maps API cost and latency are incurred only after order placement, when the customer has already committed and the precision is operationally necessary
- Live ETA accuracy is highest exactly when the customer is most attentive — during the delivery wait — where it reduces support contacts about delivery status
- Delta suppression prevents WebSocket message floods during minor GPS jitter while still surfacing meaningful ETA changes

### Option B: Full precision ETA at pre-checkout (Maps API + rider location on every cart load)
- Adds 100–200ms latency to cart-page load, degrading a high-traffic UI surface where sub-100ms response is the baseline expectation
- Maps API costs scale linearly with session volume, not order volume; at 100,000 sessions/day and ~60% non-converting, roughly 60,000 expensive API calls per day produce no revenue
- Creates a dependency on rider location availability at the pre-checkout stage; if Redis GEO is unavailable, the cart page ETA call fails rather than degrading gracefully to a cached estimate

### Option C: Single static ETA (always display "10–15 min" with no computation)
- Zero infrastructure cost and zero latency, but provides no signal about store congestion; a store processing 200 simultaneous orders shows the same ETA as an idle store
- Leads directly to SLA violations during peak periods, increasing customer support volume and refund rate
- Eliminates the possibility of using ETA as a demand-smoothing signal (e.g., surfacing longer ETAs to the customer could shift some orders to off-peak slots)

## Consequences

### Positive
- Pre-checkout ETA is effectively free at any scale — two Redis reads with no external API dependency
- Maps API calls are gated behind order placement, aligning cost with revenue-generating events
- Live ETA accuracy is highest during OUT_FOR_DELIVERY, the period where customer anxiety and support contacts are highest; this directly reduces operational support load
- Delta suppression keeps WebSocket message rate proportional to meaningful ETA changes rather than GPS update frequency

### Negative (Trade-offs)
- Pre-checkout ETA can be off by ±3–4 minutes relative to actual delivery time; zone travel time cache may be up to 5 minutes stale; rider wait time at the store is not included in the pre-checkout estimate
- Congestion multiplier is an approximation; it does not account for picker skill variance, SKU location in the store, or substitution handling time
- Zone-level travel time granularity is coarser than address-level; a customer at the far edge of a zone may consistently see an optimistic ETA

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Zone travel time cache is cold on service startup, causing all pre-checkout ETAs to show a default fallback | Low | Medium | Warm the cache on startup by running a background job that loads historical average travel times per zone from the analytics database before the service begins serving traffic |
| Maps API rate limit hit or outage during peak causes Phase 2 ETA to degrade | Medium | Medium | Circuit breaker on Maps API client falls back to zone cache value; surface `eta_maps_api_fallback_rate` metric to ops dashboard; alert if fallback rate exceeds 5% |
| Delta suppression threshold of 2 minutes is too coarse, causing customers to see a stale ETA for an extended period | Low | Low | Override suppression unconditionally if the rider has been stationary for over 2 minutes (signals a potential delay); allow the threshold to be tuned via feature flag without a deployment |
| Congestion multiplier counter drifts if order state-transition events are lost (e.g., Kafka consumer lag) | Medium | Medium | Add a reconciliation job that recomputes the counter from the orders table every 5 minutes; alert if computed vs. cached value diverges by more than 20% |
