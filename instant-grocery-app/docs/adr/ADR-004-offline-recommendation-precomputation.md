# ADR-004: Offline Pre-Computed Recommendations (Not Real-Time ML Inference)

**Date:** 2026-02-22
**Status:** Accepted
**Deciders:** Platform Engineering

## Context

The app homepage presents a personalised product feed to each user on every session open. With 100,000 daily active users and a peak throughput of 500 orders per minute, the homepage is one of the highest-frequency surfaces in the system. A recommendation request is issued on every app open, every category browse, and every search result page — easily 3–5 recommendation calls per session per user. At peak, this translates to several thousand recommendation serving requests per minute.

Grocery purchasing behaviour is strongly habitual. Analysis of order history data shows that the majority of a customer's weekly basket consists of recurring items: the same brand of milk, eggs, bread, and cleaning products purchased on roughly the same cadence. Taste and brand preferences in grocery rarely shift within a 24-hour window. This observation is critical: it means the freshness requirement for recommendations is measured in hours, not seconds. A recommendation computed at midnight reflecting yesterday's order history will still be highly relevant at 8:00 PM the following evening for the vast majority of users.

Running real-time ML inference on each homepage load would require a dedicated model serving fleet. A typical collaborative filtering or embedding-based recommendation model requires 50–200ms of compute per request on CPU instances (or 10–50ms on GPU with batching). At our traffic volumes, this would demand either a sizeable fleet of large CPU instances or GPU-accelerated inference nodes — representing significant additional infrastructure cost and operational complexity. More critically, this would introduce a new latency-critical synchronous dependency on the serving path. Any degradation in the ML serving layer would directly raise homepage load times and risk causing widespread user-facing timeouts.

A separate problem is in-stock filtering. Even if personalised rankings were computed real-time, the recommendation list must still be filtered against live inventory at the customer's assigned dark store before being returned. Inventory state changes within seconds (a popular item goes OOS after 10 rapid orders). This filtering step is inherently real-time and cannot be pre-computed. A hybrid architecture — offline ranking, real-time stock filtering — is therefore the natural design.

## Decision

We will implement a two-phase recommendation architecture. Phase one is an offline batch pipeline that runs nightly at 01:00 AM, consuming 90 days of rolling order history, search click events, and category affinity signals from the data warehouse. The pipeline is implemented in Spark, running on the existing data platform cluster. Its output is a ranked list of the top-50 personalised SKUs per user, written to Redis as a Hash keyed by `reco:{user_id}` with a TTL of 28 hours (24h base + up to 4h jitter applied per user to spread cache expiry across the morning). Phase two is online serving: when the Recommendation Service receives a request, it fetches the pre-computed list from Redis (single network round-trip, sub-millisecond), then issues a batch in-stock lookup to the Inventory Service for the customer's assigned store, filters the list to in-stock items, and returns the top-N results. The entire serving path — Redis read plus inventory filter — completes in under 20ms at p50.

For new users with no purchase history (cold-start), the Redis key will be absent. The Recommendation Service detects the cache miss and falls back to a store-level bestseller list, which is pre-computed hourly from order counts at each dark store and cached in Redis under `bestsellers:{store_id}` with a 1-hour TTL. This gives new users a contextually relevant, store-appropriate list without requiring any personalisation infrastructure.

## Alternatives Considered

### Option A: Offline batch pre-computation + real-time stock filter ✅
- Nightly Spark job computes top-50 personalised SKUs per user from 90-day rolling order history, search clicks, and category affinity; output stored in Redis with 28h TTL (24h base + ±4h jitter)
- Online serving path: Redis fetch (sub-millisecond) + Inventory Service batch lookup (< 15ms) = p50 serving latency under 20ms with no ML infrastructure on the hot path
- Zero GPU or large-CPU inference fleet required; recommendations are served from the existing Redis cluster already used for session data and cart state
- Cold-start handled by a separate hourly bestseller pipeline per store — a simpler offline job with no personalisation model required
- Graceful degradation by design: if the batch pipeline fails, the previous night's recommendations remain in Redis until TTL expiry; users see slightly stale but still relevant results rather than errors

### Option B: Real-time ML inference on every homepage load
- Would produce the freshest possible rankings, incorporating orders placed hours ago and real-time browse signals
- Rejected because: inference latency of 50–200ms per request would be the single largest contributor to homepage load time, violating the product requirement of a sub-300ms time-to-interactive for the homepage feed; this latency is inherent to model evaluation and cannot be cached away without reintroducing offline computation
- Rejected because: a dedicated GPU inference fleet or large-CPU serving cluster adds significant recurring infrastructure cost that is difficult to justify given that grocery preferences are stable within a 24h window; the marginal recommendation quality improvement does not offset the cost and complexity
- Rejected because: the real-time inference service becomes a new hard dependency on the critical homepage path; any model serving degradation (OOM, deployment rollout, traffic spike) directly causes homepage load failures, requiring tight SLA guarantees on an inherently less predictable ML system

### Option C: User-user collaborative filtering pre-computed per user pair
- Computes similarity between every pair of users based on shared purchase history, then recommends items liked by similar users; classically more accurate for sparse preference data than item-item approaches
- Rejected because: user-user CF scales as O(n²) in the number of users; at 100,000 DAU the similarity matrix requires computing and storing 10 billion user-pair scores nightly, which is computationally prohibitive within a nightly batch window on a shared Spark cluster
- Rejected because: item-item collaborative filtering (effectively what we implement via category affinity and co-purchase signals) scales as O(items²); with ~5,000 SKUs the item similarity matrix is 25 million pairs — three orders of magnitude smaller and entirely tractable in a nightly job
- Rejected because: the marginal recommendation accuracy improvement of user-user CF over item-item CF in a grocery context is minimal given the strong habit-driven nature of grocery purchasing; the accuracy gain does not justify the compute cost increase

## Consequences

### Positive
- Zero ML model inference on the recommendation serving path; p50 serving latency under 20ms, meeting the homepage performance budget without any new latency-critical infrastructure
- No GPU inference fleet or oversized CPU instances required; the batch pipeline runs on the existing data platform cluster during off-peak hours (01:00–05:00 AM), adding no marginal infrastructure cost
- Fault-tolerant by design: the serving path has no real-time ML dependency; if the batch pipeline fails on a given night, the previous recommendations remain valid until TTL expiry and users experience no observable degradation
- Cold-start is handled cleanly with a dedicated hourly bestseller cache; new user onboarding does not require any special-casing in the serving layer
- The offline pipeline is independently deployable and testable; model changes, feature additions, and retraining cycles do not require any changes to the online serving path

### Negative (Trade-offs)
- Up to 24 hours of recommendation staleness: a user who places a first-time order of baby formula at 10:00 PM will not see baby-related recommendations personalised to that new preference signal until the following night's batch run; existing users with stable baskets are unaffected, but users in an active preference-shift window will see a lag
- New products added to a store's catalog mid-day will not appear in personalised recommendation feeds until the next nightly batch, even if they are in stock and relevant to user preferences; the hourly bestseller fallback will surface new popular items faster, but personalised placement is delayed
- The batch pipeline introduces a hard dependency on the data platform scheduler; a Spark cluster failure during the nightly window could leave all users on stale recommendations beyond the normal TTL period
- Redis memory footprint is non-trivial: 100,000 users × 50 SKU IDs (each ~8 bytes as an integer) = ~40 MB of recommendation data at minimum, plus Redis overhead; this is manageable on the current cluster but must be monitored as the user base grows

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Nightly batch pipeline fails; users see stale or missing recommendations after TTL expiry | Med | Med | Alert if batch job has not completed by 06:00 AM local time; serving layer falls back to hourly bestsellers on Redis cache miss; batch job reruns are idempotent (upsert by user_id) |
| Redis TTL expiry causes a synchronised cache miss storm at 24h mark for all users | Med | High | Apply per-user TTL jitter of ±4 hours (uniform random) at write time, spreading expiry across a 4-hour window rather than a single point; reduces thundering herd by ~8x |
| Inventory Service latency spike causes recommendation serving to exceed SLA | Low | High | Circuit breaker on the Inventory Service call; on timeout or error, return the pre-computed list unfiltered with a client-side "may be unavailable" flag rather than failing the entire request |
| Redis cluster unavailability causes total recommendation serving failure | Low | High | Recommendation Service falls back to the hourly bestseller list served directly from PostgreSQL materialised view if Redis is unreachable; adds ~50ms latency but maintains availability |
| Batch pipeline computes stale recommendations using corrupted or incomplete order data | Low | High | Data quality checks at pipeline entry: assert row counts within 20% of prior day before proceeding; alert and abort if validation fails; previous night's Redis entries remain until their TTL expires |
