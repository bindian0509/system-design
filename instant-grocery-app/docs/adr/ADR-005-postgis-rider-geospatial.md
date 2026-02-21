# ADR-005: PostGIS for Rider Geospatial Queries (Not a Dedicated Geo Service)

**Date:** 2026-02-22
**Status:** Accepted
**Deciders:** Platform Engineering

## Context

The Dispatch Service must find the nearest available rider to a dark store every time an order is placed. At peak load this is 500 orders/minute, which translates to 500 geospatial nearest-rider queries per minute (~8/sec). The city has 10,000 concurrent riders across 40 dark stores in a single metro area (Bengaluru). Each rider publishes a GPS update every 5 seconds, producing 2,000 location writes per second at peak across the fleet. These two workloads — high-write location ingestion and lower-volume nearest-rider reads — have fundamentally different characteristics and should not be served by the same storage primitive.

The location writes are ephemeral by nature. A rider's position from 10 seconds ago has no operational value once the next ping arrives. Durability, replication lag, and write amplification costs associated with a durable datastore are wasted for this workload. What is needed is a sub-millisecond, in-memory atomic overwrite of a 2D coordinate — a property Redis GEOADD provides natively. Rider assignment, on the other hand, requires radius search with distance scoring, joining against structured metadata (vehicle type, active delivery count, availability status), and an atomic status transition to prevent two dispatch attempts from assigning the same rider simultaneously. These are properties that a relational database with geospatial extensions handles well.

The key question was whether to consolidate both workloads in a single system or to split by workload type. Three options were evaluated: a dedicated geo service (Uber H3, Tile38, or equivalent), Redis GEO for the full problem, and a split approach where Redis GEO owns writes and PostgreSQL + PostGIS owns reads and assignment locking.

At our current scale of 10,000 concurrent riders, the read volume of ~8 nearest-rider queries per second is trivial for a PostGIS GiST spatial index. Introducing a new stateful geo service (Tile38, H3-based custom service) purely to avoid PostGIS would add operational overhead — container management, on-call runbooks, failover procedures — with no throughput benefit at this scale.

## Decision

Rider location writes (2,000/sec) are handled exclusively by Redis GEO. Each `GEOADD riders <lng> <lat> <rider_id>` call atomically overwrites the previous position. No TTL, no persistence (`appendfsync no` is acceptable) — the data is ephemeral and riders repopulate it on their next 5-second ping. Redis can sustain this write rate in-memory without batching.

Nearest-rider queries and rider assignment are handled by PostgreSQL with the PostGIS extension. The `riders` table has a `GEOGRAPHY(POINT, 4326)` column indexed with a GiST spatial index. The Dispatch Service runs `ST_DWithin` radius search (3 km initially, expanding to 5 km on a 200ms timeout) to find available riders sorted by `ST_Distance`. Rider assignment uses an optimistic lock: `UPDATE riders SET status = 'ON_DELIVERY' WHERE rider_id = $1 AND status = 'AVAILABLE' RETURNING *`. If zero rows are returned, the rider was concurrently assigned; the Dispatch Service moves to the next candidate. Rider location in the PostgreSQL table is kept fresh by the Dispatch Service reading the coordinate from Redis GEO (via `GEOPOS`) at query time and joining it with PG metadata in application code, or via a lightweight sync process that propagates Redis GEO positions into the PostGIS column on each location update.

## Alternatives Considered

### Option A: Redis GEO (writes) + PostGIS (reads + assignment lock) ✅
- Redis GEOADD handles 2,000 writes/sec in-memory with sub-millisecond latency; no disk I/O, no replication lag on the write path
- PostGIS GiST index on 10,000 rider rows executes `ST_DWithin` + `ORDER BY ST_Distance` in under 10ms — far below the 100ms dispatch SLA
- Optimistic-lock assignment (`UPDATE ... WHERE status = 'AVAILABLE' RETURNING *`) is a well-understood SQL primitive with no custom scripting required
- No new stateful service to deploy, monitor, or page on-call for
- Clear separation of concerns: Redis owns ephemeral state, PostgreSQL owns durable state and business logic transitions

### Option B: Redis GEO for everything (writes + reads + assignment)
- `GEORADIUS` / `GEOSEARCH` can return nearby riders, but cannot atomically join against metadata (vehicle type, active delivery count) stored in Redis hashes without a Lua script, increasing lock surface and making the assignment logic hard to reason about and test
- Atomic rider assignment requires a Lua script combining `GEOSEARCH` + metadata check + status CAS in one round-trip; any bug in that script is difficult to roll back safely without a Redis restart
- Redis Cluster sharding complicates `GEOSEARCH` because geo keys must co-locate on the same slot; requires careful key-space design that becomes a maintenance burden

### Option C: Dedicated geo service (Uber H3, Tile38, or similar)
- Justified when concurrent rider counts exceed 100k city-wide; at 10k riders, a dedicated geo service is operational overhead without throughput benefit
- Tile38 is a separate stateful process requiring its own persistence, replication, backup, and on-call runbook — all for a read workload that PostGIS handles at ~8 qps with existing infrastructure
- H3 hexagonal sharding adds indexing complexity (choosing resolution, handling edge cells) that provides value only when PostGIS query latency becomes a bottleneck, which does not occur until well beyond 50k riders on modern hardware

## Consequences

### Positive
- No new service to deploy or operate; PostGIS runs inside the existing PostgreSQL cluster
- GiST spatial index handles 10,000-rider radius queries in under 10ms, well within dispatch SLA
- Redis GEO absorbs the 2,000 writes/sec spike with no persistence overhead
- Optimistic lock assignment (`RETURNING *`) eliminates double-assignment races without distributed locks
- Clear operational model: Redis loss means stale location for at most 5 seconds; PostgreSQL loss means dispatch is down (already a P0 dependency)

### Negative (Trade-offs)
- Rider location exists in two places — Redis (live GPS) and PostgreSQL (used for assignment queries) — requiring a synchronisation step; if the sync lags, radius queries may use slightly stale coordinates
- Redis restart causes total loss of live rider positions; riders repopulate within 5 seconds on the next ping, but any dispatch query in that window works from the PostgreSQL column's last-written value
- The sync process (Redis → PostGIS) is an additional moving part that must be monitored and has its own failure mode

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PostGIS query latency grows as rider count scales past 50k | Low | High | Re-evaluate with H3 hexagonal geo-sharding or Tile38 at that inflection point; GiST index partitioning by city zone is a mid-term option |
| Redis GEO data loss on restart clears all live locations | Medium | Medium | Acceptable — 5-second maximum staleness; riders repopulate on next GPS ping; circuit breaker falls back to last-known PostgreSQL position |
| Optimistic lock contention under very high simultaneous acceptance rates | Low | Medium | Enforce a top-3 candidate notification limit per dispatch event to bound concurrent acceptors; exponential backoff on failed lock with fallback to next candidate |
| Sync process falls behind under write bursts, causing stale PostGIS coordinates | Medium | Low | Monitor replication lag metric; alert if lag exceeds 10 seconds; at-peak the Dispatch Service can read coordinate directly from Redis GEOPOS and skip the PostGIS column for the location component |
