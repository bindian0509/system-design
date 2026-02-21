# Instant Grocery Delivery App — System Design

**Reference:** Blinkit/Zepto scale, single metro city (Pune / Bengaluru)
**Date:** 2026-02-22

---

## 1. Scale Assumptions & Requirements

### Functional Requirements

- **Customer:** browse catalog, search products, place order, real-time order tracking
- **Dark store ops:** manage stock, receive pick-list, mark items packed
- **Dispatch:** assign delivery agent, navigate store → customer
- **ETA:** promised delivery window before checkout, live updates during delivery

### Non-Functional Requirements

| Requirement | Target |
|---|---|
| Delivery SLA | 10–15 min from order placement |
| Order placement availability | 99.9% |
| Catalog browse availability | 99.5% |
| Inventory consistency | Strongly consistent (no oversell) |
| ETA consistency | Eventually consistent |
| Search latency | p99 < 200ms |
| Order placement latency | p99 < 500ms |
| Dispatch assignment | < 2s after order confirmed |

### Back-of-Envelope Numbers

| Metric | Value |
|---|---|
| Dark stores in city | 40 |
| Orders / day | 100,000 |
| Peak orders / min | 500 (≈ 5–6 per store) |
| Avg items per order | 8 |
| Catalog per store | ~5,000 SKUs |
| Concurrent riders | 10,000 |
| Rider location updates | Every 5s → **2,000 writes/sec** |
| Inventory writes (pick events) | ~800,000/day |

---

## 2. High-Level Architecture & Service Decomposition

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway / BFF                         │
│          (rate limiting, auth, routing, mobile vs web)           │
└──────┬──────────┬──────────┬──────────┬──────────┬─────────────┘
       │          │          │          │          │
   Order      Catalog    Inventory  Dispatch    ETA
   Service    Service    Service    Service     Service
       │          │          │          │          │
  PostgreSQL  Elasticsearch  Redis +   PostgreSQL  Redis +
  (orders)   + S3 (images)  PostgreSQL (dispatch)  ML model
                            (inventory)
```

### Service Responsibilities

| Service | Owns | DB Choice | Why |
|---|---|---|---|
| **Order Service** | Order lifecycle, payment orchestration | PostgreSQL (ACID) | Transactional, no oversell |
| **Catalog Service** | SKU master, pricing, images, categories | PostgreSQL + Elasticsearch | Search needs inverted index |
| **Inventory Service** | Per-store stock levels, reservations | Redis (hot) + PostgreSQL (durable) | Sub-ms stock checks at peak |
| **Dispatch Service** | Rider pool, order-rider assignment, routing | PostgreSQL + PostGIS | Consistent assignment, no double-assign |
| **ETA Service** | Delivery window prediction, live tracking | Redis (rider location) + ML model | High read, low write latency |
| **Notification Service** | Push, SMS, WhatsApp | Kafka consumer | Fire-and-forget, async |
| **User Service** | Auth, profile, addresses | PostgreSQL | Standard CRUD |

### Async Backbone — Kafka Topics

```
order.placed          → Inventory Service (reserve stock)
                      → Dispatch Service (start rider search)
                      → Notification Service (confirm to user)

inventory.reserved    → Order Service (mark payment capturable)
inventory.failed      → Order Service (cancel, refund)

rider.assigned        → ETA Service (start live tracking)
                      → Notification Service (rider name/photo to user)

order.packed          → Dispatch Service (rider can now pick up)

order.delivered       → Inventory Service (finalize deduction)
                      → Analytics pipeline
```

---

## 3. Order Lifecycle & Dispatch

### Order State Machine

```
CART_LOCKED → PAYMENT_PENDING → PAYMENT_CONFIRMED
    → INVENTORY_RESERVED → PICKING → PACKED
    → RIDER_ASSIGNED → OUT_FOR_DELIVERY → DELIVERED
                                        → FAILED / CANCELLED
```

### Critical Path — Order Placement (synchronous, < 500ms)

```
1. POST /orders
2. API Gateway → Order Service
3. Order Service calls Inventory Service (sync gRPC) — reserve stock
   └─ Inventory Service: Redis DECRBY per SKU per store_id (Lua script)
      If stock >= qty: reserve → enqueue Kafka (async PG write-behind)
      If stock < qty: return INSUFFICIENT_STOCK immediately
4. Order Service calls Payment Service (sync) — authorize charge
5. On success: write order row to PostgreSQL, publish order.placed to Kafka
6. Return order_id + ETA to customer
```

### Dispatch — Rider Assignment (async, < 2s after order.placed)

```
Dispatch Service consumes order.placed:
1. Query rider pool: AVAILABLE riders within 3km of dark store
   (PostGIS GEORADIUS on PostgreSQL, GiST index on rider location)
2. Score riders: proximity + current load + avg delivery time
3. Send push to top-3 riders (first-accept wins)
4. On acceptance: write rider_assignment, publish rider.assigned
5. No acceptance in 30s → expand radius to 5km, retry
6. 3 consecutive failures → circuit breaker opens → escalate to ops
```

### Preventing Double Assignment

Optimistic lock on assignment table:
```sql
UPDATE riders SET status='ON_DELIVERY'
WHERE rider_id = ? AND status = 'AVAILABLE'
RETURNING *;
```
Only one concurrent transaction succeeds; others get empty result and skip.

### Dark Store Pick-List Flow

```
order.placed → store ops tablet shows pick-list (WebSocket push)
Picker marks each item → inventory.picked event per item
All items picked → order.packed → Dispatch notified → rider dispatched
```

---

## 4. Inventory & Catalog

### Inventory — Two-Layer Model

```
Hot layer:  Redis Hash per store
  Key:    inv:{store_id}:{sku_id}
  Fields: qty_available, qty_reserved

Cold layer: PostgreSQL
  Table:  inventory(store_id, sku_id, qty, version)
  Updated via Kafka consumer (write-behind, ~5s lag)
```

### Atomic Reservation — Redis Lua Script

```lua
local qty = redis.call('HGET', key, 'qty_available')
if tonumber(qty) >= tonumber(requested) then
  redis.call('HDECRBY', key, 'qty_available', requested)
  redis.call('HINCRBY', key, 'qty_reserved', requested)
  return 1
else
  return 0
end
```
Lua scripts execute atomically — no WATCH/MULTI needed, no race conditions.

### Stock Update Flows

| Event | Flow |
|---|---|
| Inbound restock | Staff scans → Redis INCRBY + async PG write |
| Pick deduction | inventory.picked → Redis DECRBY qty_reserved → async PG |
| Spoilage / write-off | Staff marks → dual write (Redis + PG synchronous) |

### Catalog Architecture

```
PostgreSQL:      SKU master (sku_id, name, brand, category, price, weight)
Elasticsearch:   Per-store index — catalog_{store_id}
                 5,000 docs × 40 stores = 200k total (very manageable)
S3 + CDN:        Product images (served at edge, CDN cache invalidated on update)
```

**Why per-store Elasticsearch index:** Stock availability (`in_stock`) is store-specific.
A global index cannot filter cheaply at this latency. OOS update at store A touches
only `catalog_{store_A}` — no cross-store write fan-out.

### Search Flow (p99 < 200ms)

```
GET /search?q=amul+butter&store_id=42

1. Elasticsearch query on catalog_42:
   - fuzzy match (fuzziness: AUTO) on name^3, brand^2, tags^1
   - filter: in_stock = true
   - boost: sponsored, high-margin SKUs
2. Re-rank (lightweight in-process model):
   - boost: items this user purchased before
3. Price fetch from Redis (TTL 60s)
4. Return top 20 results

Latency budget:
  Elasticsearch: ~40ms | Re-rank: ~10ms | Redis: ~5ms | Net: ~20ms
  Total p50: ~75ms ✓
```

### Type-Ahead / Autocomplete

```
Redis Sorted Set per store: autocomplete:{store_id}
  ZRANGEBYLEX "amul b" → ["amul butter", "amul buttermilk", ...]
  Response < 10ms — no Elasticsearch involved
  Updated nightly from search logs
```

---

## 5. ETA & Slot Estimation

### Three ETA Phases

| Phase | Trigger | Latency | Accuracy |
|---|---|---|---|
| Pre-checkout | Cart page load | < 100ms | Approximate (store load based) |
| Post-order | After rider assigned | < 500ms | Precise (actual rider location) |
| Live ETA | Every 30s during delivery | < 50ms | Real-time (GPS + traffic) |

### ETA Formula

```
Total ETA = T_pick + T_wait_for_rider + T_travel

T_pick  = baseline (2 min + 0.5 min/item)
          × congestion multiplier (active_orders / picker_count)

T_wait  = distance(rider, store) / avg_rider_speed(time_of_day)

T_travel = OSRM / Google Maps Distance Matrix API result
           (cached per store→zone pair, TTL 5 min)
```

### Rider Location Tracking Pipeline

```
Rider app → GPS every 5s → POST /rider/location
→ Location Ingestor (stateless, horizontally scaled)
→ Redis GEO: GEOADD riders:{city} lng lat rider_id   (overwrites previous)
→ Kafka: rider.location.updated → ETA Service

ETA Service:
  if order is OUT_FOR_DELIVERY AND |new_ETA - shown_ETA| > 2min:
    push ETA update to customer (WebSocket / push notification)
```

**Why Redis GEO:** 10,000 riders × 5s updates = 2,000 writes/sec. Rider location
is ephemeral — durability not needed. GEODIST / GEORADIUS queries run in-memory.

### Dark Store Load Signal

```
Redis counters per store:
  store:{store_id}:active_orders   (INCR on order.placed, DECR on order.packed)
  store:{store_id}:picker_count    (updated by store ops app)

Congestion multiplier:
  active_orders / picker_count > 10  → T_pick × 1.5
  active_orders / picker_count > 20  → show "Slightly delayed" banner
```

### ETA Caching

| Data | Cache | TTL |
|---|---|---|
| Store→zone travel time | Redis | 5 min |
| Pre-checkout ETA per store | Redis | 30s |
| Rider live location | Redis GEO | Evicted on next update |
| Historical pick time model | In-memory | 1 hour |

---

## 6. Search & Recommendations

### Recommendations — Homepage Feed

```
Offline pipeline (nightly batch — Spark / Flink):
  Input:  order history, search clicks, category affinity per user
  Output: top-50 personalised SKU list per user_id
  Store:  Redis Hash  reco:{user_id} → [sku_id, ...]  TTL 24h

Online serving (no ML inference at request time):
  GET /feed?user_id=U&store_id=42
  → fetch reco:{U} from Redis
  → filter: only SKUs in_stock at store 42
  → return ranked, in-stock feed
  → cold start fallback: bestsellers at store 42 (updated hourly)
```

**Why offline pre-computation:** Grocery preferences change slowly.
24h staleness is acceptable. Real-time stock filtering keeps results actionable.
Avoids ML serving fleet cost at this scale.

### Substitution Logic (OOS During Picking)

```
Picker marks item OOS mid-pick → inventory.oos_during_pick event
→ Catalog Service finds substitutes:
    1. Same brand, same category, similar weight/price
    2. Fallback: different brand, same category
    (Elasticsearch query on catalog_{store_id}, filter in_stock=true)
→ Dispatch Service pauses rider assignment (if not yet assigned)
→ Customer notified: "We substituted X with Y — OK?"
→ Customer has 60s to reject; auto-accepts if no response
```

---

## 7. Resiliency & Failure Modes

### Circuit Breaker Placement

| Call | Fallback |
|---|---|
| Order → Inventory Service | Soft reservation (allow order, check at pick time) |
| Order → Payment Service | Async reconciliation job (runs every 5 min) |
| Catalog → Elasticsearch | PostgreSQL full-text search (slower, still functional) |
| ETA → Maps API | Cached zone-level ETAs (5 min TTL) |
| Any → Notification Service | Fire-and-forget, no circuit breaker needed |

### Key Failure Scenarios

**Inventory Redis down:**
Circuit breaker OPEN → soft reservation fallback. Orders continue.
True OOS caught at pick time → triggers substitution flow.

**Payment timeout:**
Order written as `PAYMENT_PENDING` before calling Payment Service (idempotency key = order_id).
Reconciliation job resolves within 10 min.

**Kafka consumer lag (Dispatch):**
Alert at lag > 500 msgs. Dispatch workers auto-scale horizontally (stateless, partition-per-worker).
Dead letter queue for 3x retry failures → ops review.

**Dark store network outage:**
Store tablet caches pick-lists offline (offline-first PWA).
Order stuck in PICKING > 8 min → ops alert.

**Rider GPS stale (> 60s no update):**
ETA Service marks rider STALE_GPS → show "Tracking unavailable" to customer.
Dispatch escalates if order not delivered within 20 min.

---

## 8. Observability

### Structured Logging (all services)

```json
{
  "timestamp": "2026-02-22T10:05:33Z",
  "service": "order-service",
  "trace_id": "abc-123",
  "span_id": "def-456",
  "level": "INFO",
  "event": "order.placed",
  "order_id": "ORD-789",
  "store_id": 42,
  "item_count": 8,
  "duration_ms": 312
}
```

`trace_id` propagated via HTTP headers and Kafka message headers for end-to-end tracing.

### Key Metrics (Prometheus + Grafana)

| Metric | Alert Threshold |
|---|---|
| `order_placement_latency_p99` | > 800ms |
| `inventory_reservation_failure_rate` | > 1% |
| `dispatch_assignment_latency_p99` | > 3s |
| `rider_assignment_success_rate` | < 95% |
| `kafka_consumer_lag{group=dispatch}` | > 500 msgs |
| `search_latency_p99` | > 300ms |
| `redis_memory_usage_pct` | > 80% |
| `orders_in_picking_gt_8min` | > 5 |

### Distributed Traces (OpenTelemetry → Jaeger)

```
Trace: order placement critical path
  span: api-gateway.route              2ms
  span: order-service.validate         5ms
  span: inventory-service.reserve     45ms
    span: redis.lua-script             3ms
    span: kafka.publish               12ms
  span: payment-service.authorize    180ms
  span: order-service.persist-pg     25ms
  span: kafka.publish(order.placed)  10ms
  ─────────────────────────────────────────
  Total:                             282ms
```

### Health Check Endpoints (all services)

```
GET /health/live   → 200 if process running    (K8s liveness probe)
GET /health/ready  → 200 if DB + Redis healthy  (K8s readiness probe)
```

---

## 9. Key Design Decisions & Trade-offs

### 1. Redis for inventory reservation (not PostgreSQL)

> At 4,000 stock ops/min, PostgreSQL row-level lock contention under concurrent
> orders would spike latency. Redis atomic Lua scripts handle this with sub-ms
> latency. **Trade-off:** write-behind means a Redis crash in a ~5s window could
> lose a reservation. Mitigated by Redis AOF persistence and soft-reservation
> circuit breaker fallback.

### 2. Per-store Elasticsearch index

> Coupling stock availability (`in_stock`) into a global index requires a
> store-scoped filter on every query and makes OOS updates fan out across all
> stores. Per-store indexes isolate writes. **Trade-off:** 40 indexes to manage
> vs 1. Accepted because 40 × 5k = 200k documents is operationally trivial.

### 3. Async Kafka backbone with synchronous critical path only

> Order placement is synchronous (inventory + payment) because the customer is
> waiting for a definitive answer. All downstream work (dispatch, notifications,
> analytics) is async. **Trade-off:** eventual consistency between order state
> and rider assignment. Bounded by 2s dispatch SLA alert.

### 4. Offline recommendation pre-computation

> Running ML inference at request time for 100k daily users at 500 orders/min
> peak requires a significant serving fleet. Grocery preferences change slowly.
> **Trade-off:** 24h staleness on personalisation. Mitigated by real-time
> in-stock filtering so stale recommendations don't show OOS items.

### 5. PostGIS for rider geospatial queries (not a dedicated geo service)

> PostGIS with a GiST index handles GEORADIUS-style queries well up to ~10k
> active riders. No dedicated geo-service needed at this scale. Redis GEO handles
> the write-heavy live location stream; PostGIS handles nearest-rider lookups
> (one query per order). **Trade-off:** at 100k+ concurrent riders city-wide,
> revisit with H3-based geo-sharding.

---

## Out of Scope (flag proactively in interviews)

- Surge pricing / dynamic delivery fees
- Multi-store order splitting
- Returns and refunds flow
- Seller / vendor onboarding portal
- Cross-city federation
- Payment gateway internals
