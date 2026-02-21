# ADR-002: Redis Atomic Lua Scripts for Inventory Reservation

**Date:** 2026-02-22
**Status:** Accepted
**Deciders:** Platform Engineering

## Context

Inventory reservation is the most write-contention-heavy operation in the system. At 500 orders per minute with an average basket of 8 items, the Inventory Service must execute 4,000 stock check-and-decrement operations per minute — all targeting the same finite set of SKU counters distributed across 40 dark stores. Critically, many of these operations contend on the same hot SKUs: a flash sale on Amul Butter or a restock notification push can drive hundreds of concurrent requests at the exact same inventory cell within a short window.

The zero-oversell requirement is absolute. Two concurrent orders for the last unit of a SKU must not both receive a success response. One must succeed; the other must receive an explicit "out of stock" rejection so the customer can be informed immediately. There is no acceptable eventual-consistency model here — a rider showing up to a dark store to find zero units is a failed delivery, a customer refund, and a trust erosion event at scale.

A naive PostgreSQL row-level lock approach using `SELECT ... FOR UPDATE` on the inventory row is straightforward to reason about: acquire the row lock, read the quantity, decrement if sufficient, commit. Under low traffic this works correctly. Under 500 concurrent order placements, however, all contending on the same hot SKU rows, the PostgreSQL lock queue builds up. Transactions stack behind the lock holder, lock wait timeouts begin firing (typically at 50-200ms), and the p99 latency of the inventory reservation step alone can breach the entire 500ms order placement budget. PostgreSQL connection pool exhaustion compounds the problem: each waiting transaction holds a connection, and connection pools on the order of 100-200 connections are consumed rapidly at this contention level.

Redis DECRBY is atomic by design: the Redis event loop processes one command at a time with no preemption. Two concurrent DECRBY calls on the same key are serialized at the Redis level without any application-layer locking. The challenge is that Redis is an in-memory store — a Redis process restart or failure mid-operation raises questions about durability and what stock level to recover to. This durability gap must be addressed explicitly.

## Decision

We implement a two-layer inventory model. The hot layer is Redis: each store-SKU pair is stored as a Redis Hash keyed `inv:{store_id}:{sku_id}` with two fields, `qty_available` and `qty_reserved`. This is the authoritative real-time counter used during order placement. The cold layer is PostgreSQL: the canonical durable record of stock levels, updated asynchronously via a Kafka write-behind consumer with an acceptable lag of approximately 5 seconds.

Inventory reservation executes a Redis Lua script. Lua scripts run atomically and in a single-threaded manner within Redis — the entire script executes as an indivisible unit before any other command is processed. The script reads `qty_available`, compares against the requested quantity, and if sufficient atomically decrements `qty_available` and increments `qty_reserved`. It returns 1 on success and 0 on insufficient stock. No WATCH/MULTI/EXEC optimistic locking is needed; the Lua atomicity guarantee eliminates the compare-and-swap race condition entirely.

On order confirmation, `inventory.reserved` is published to Kafka. A write-behind consumer reads this event and applies the decrement to PostgreSQL within approximately 5 seconds. On Redis restart, stock levels are rehydrated from PostgreSQL, accepting a brief window where the in-memory state may be slightly stale (bounded by the write-behind lag). Redis is configured with AOF persistence and Redis Sentinel for high availability to minimise the restart scenario.

The memory footprint is trivially small: 40 stores × 5,000 SKUs × approximately 100 bytes per hash entry yields approximately 20MB of Redis memory for the entire inventory hot layer — well within any production Redis instance's capacity.

## Alternatives Considered

### Option A: Redis Lua scripts with PostgreSQL write-behind ✅

- DECRBY and Lua atomicity in Redis eliminates explicit locking at the application layer; the Redis event loop serializes concurrent operations on the same key by design
- Sub-millisecond reservation latency under load: Redis command execution is typically 0.1-0.5ms; the Lua script adds negligible overhead; p99 reservation latency stays well within the 500ms order placement budget
- Zero oversell is guaranteed by Lua atomicity: the qty check and decrement are a single indivisible operation; no two scripts can observe the same pre-decrement qty_available for the same key
- PostgreSQL write-behind via Kafka decouples the durable write from the hot path; the write-behind consumer can scale independently and absorb bursts without affecting order placement latency
- Memory footprint for the full 40-store, 5,000-SKU inventory is approximately 20MB — negligible, and leaves ample headroom for Redis to serve other caching workloads

### Option B: PostgreSQL with SELECT FOR UPDATE (pessimistic locking)

Correct at low scale and straightforward to implement. Rejected because at 4,000 operations per minute with hot SKU contention, lock queue buildup creates p99 latency spikes that breach the 500ms order placement budget. Each waiting transaction holds a PostgreSQL connection for its lock wait duration; with a 100-200 connection pool, pool exhaustion begins before the lock queue fully drains. PostgreSQL IOPS cost for frequent small updates on hot rows is also disproportionately high — WAL write amplification for thousands of single-row updates per minute strains disk I/O on standard provisioned-IOPS volumes.

### Option C: PostgreSQL with optimistic locking (version column)

Better than pessimistic locking under moderate contention: no lock held during the read phase, transactions only fail at commit time on version conflict. Rejected because under high contention — multiple orders competing for the last unit of a hot SKU — the conflict rate approaches 100% for all but the first committer. Each conflict triggers an application-layer retry, and the retry storm amplifies load on PostgreSQL exactly when it is already under stress. The retry backoff must be tuned carefully to avoid thundering herd, which introduces configuration complexity with no guaranteed upper bound on per-request latency under sustained high contention.

## Consequences

### Positive

- Sub-millisecond reservation latency keeps the inventory step well within the 500ms order placement budget, with margin for the gRPC call overhead and payment authorization
- Zero oversell is guaranteed by Redis Lua atomicity; no application-layer coordination or retry logic is needed to prevent concurrent oversell
- Lua scripts eliminate the WATCH/MULTI/EXEC optimistic retry loop, simplifying the Inventory Service code path and removing a class of retry-induced load amplification
- The 20MB memory footprint for the full inventory hot layer means Redis capacity is not a meaningful operational concern for this workload
- Write-behind via Kafka decouples durable persistence from the hot path; PostgreSQL absorbs write-behind updates at a sustainable rate without impacting order latency

### Negative (Trade-offs)

- A Redis crash during the approximately 5-second write-behind window means the Lua decrement has occurred in memory but the PostgreSQL record has not yet been updated; on rehydration from PostgreSQL, that reservation is lost and the unit appears available again, creating a brief oversell risk until the Kafka consumer catches up and reconciles
- Redis memory must be explicitly sized, monitored, and kept below eviction thresholds; if `maxmemory-policy` is set to `allkeys-lru` and inventory keys are evicted, stock levels silently become 0 on the next read, causing false out-of-stock responses
- The two-layer model introduces a synchronization protocol between Redis and PostgreSQL that must be explicitly tested for failure modes: Redis restart, Kafka consumer lag, and write-behind consumer crash all require specific recovery procedures
- Operational teams must understand Lua scripting semantics in Redis to diagnose issues; this is a less common skill than SQL debugging

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Redis instance failure mid-reservation causing reservation loss and potential brief oversell | Low | High | Redis Sentinel for automatic failover (sub-30s), AOF persistence with `appendfsync everysec` to bound data loss to 1 second; reconciliation job compares Redis and PostgreSQL every 60 seconds and re-applies deltas |
| Redis memory exhaustion causing inventory key eviction and false out-of-stock responses | Low | High | Set `maxmemory-policy noeviction` for the inventory Redis instance; alert when `redis_memory_usage_pct` exceeds 80%; size instance at 5x current footprint (100MB minimum for 20MB working set) |
| Write-behind Kafka consumer lag exceeding acceptable window, causing PostgreSQL to lag significantly behind Redis | Medium | Medium | Alert when `kafka_consumer_lag` on the inventory write-behind consumer exceeds 1,000 messages; auto-scale consumer instances against lag metric |
| Lua script regression causing silent incorrect decrement behavior | Low | High | Lua scripts are unit-tested against an embedded Redis instance in CI; the Lua script is treated as production code with code review and test coverage requirements |
| Hot SKU causing Redis single-key hotspot under extreme flash sale traffic | Low | Medium | Shard hot SKUs across multiple Redis hash slots using a counter-sharding pattern (N shards per SKU, sum on read); activate only for SKUs observed above a configured RPS threshold |
