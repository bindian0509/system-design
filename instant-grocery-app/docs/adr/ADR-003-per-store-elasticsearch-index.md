# ADR-003: Per-Store Elasticsearch Index for Product Catalog

**Date:** 2026-02-22
**Status:** Accepted
**Deciders:** Platform Engineering

## Context

The product catalog for a single metro city spans 40 dark stores, each stocking approximately 5,000 SKUs. This produces 200,000 total documents across the city. However, inventory is fundamentally store-local: a product can be `in_stock=true` at store A and `in_stock=false` at store B simultaneously. Every customer search must return only products that are available at their assigned dark store. Returning an out-of-stock product in search results causes a picker failure downstream — the picker physically cannot fulfil the item, which triggers order edits, customer refunds, and NPS degradation.

At our operational scale, inventory fluctuates continuously. With 40 stores each processing roughly 2,500 orders per day, and assuming on average 8 inventory state transitions per SKU per store per day (OOS events, restock scans, price updates), the system generates approximately 800,000 inventory events per day, or roughly 9 write operations per second at steady state, with higher bursts during peak hours (500 orders/min equates to significantly more picker activity and stock depletion events).

A naive global index containing all 200,000 documents — with every document carrying a `store_id` field and a per-store `in_stock` flag — forces a re-index or partial update of a shared document every time any store changes stock. Elasticsearch documents are immutable internally; every update rewrites the document segment. At 9 updates/sec hitting the same index, merge pressure accumulates, causing segment merges to compete with search I/O. This degrades both indexing throughput and query latency under sustained load.

A global index also forces every search query to carry a `store_id` filter clause. Elasticsearch's query cache is keyed on the exact query structure. A `store_id` filter varies per customer request, effectively zeroing the query cache hit rate across the fleet. For a catalog where the same query ("chicken biryani kit") should resolve to near-identical results across all stores, losing the query cache means every query hits the shard-level Lucene reader directly, adding measurable latency at peak.

## Decision

We will maintain one Elasticsearch index per dark store, named `catalog_{store_id}` (e.g., `catalog_store_07`), yielding 40 indexes in the city. Each index contains exactly the ~5,000 SKUs stocked at that store. The `in_stock` field is store-local by construction: an OOS event at store A writes an update only to `catalog_store_A`. There is zero fan-out to any other store's index. A Kafka consumer subscribes to the `inventory.events` topic and routes each event to the single affected store's index. A nightly reconciliation job (run at 2:00 AM local time, outside peak hours) syncs product assortment changes — SKUs added or removed from a store's stocking list — from the Product Assortment Service into the appropriate per-store indexes.

This approach isolates write amplification entirely. Each inventory event touches exactly one index, one document. Query cache utilisation is maximised: a user searching `catalog_store_07` with no store_id filter clause produces a cacheable query key that can be reused by any subsequent customer assigned to store 07 with the same search terms.

## Alternatives Considered

### Option A: Per-store index (`catalog_{store_id}`) ✅
- Each of the 40 indexes contains ~5,000 documents scoped to that store's assortment and stock state
- An OOS write touches exactly one index, one document — O(1) fan-out regardless of fleet size
- No store_id filter clause on search queries; Elasticsearch query cache operates at full efficiency for all searches within a store
- Index lifecycle (alias rotation, schema migration, segment force-merge) is independent per store — a schema change can be rolled out store-by-store using blue/green alias swaps without a city-wide reindex
- Horizontal scalability: adding a new dark store means provisioning one additional index, not resizing a shared cluster

### Option B: Global index with `store_id` filter
- Operationally simpler: one index to manage, monitor, and back up
- Rejected because: at 9 inventory updates/sec hitting shared documents, Elasticsearch's internal segment write-ahead log accumulates faster than the merge scheduler can compact it, increasing heap pressure and GC pauses under peak load
- Rejected because: the mandatory `store_id` filter clause on every query prevents query cache hits; Elasticsearch's request cache is invalidated any time the index is refreshed, and with 9 writes/sec the cache is effectively cold at all times
- Rejected because: a single shard split or reindex operation impacts all 40 stores simultaneously, creating a city-wide degraded-search window during migrations

### Option C: Global index with store-specific nested sub-documents
- Attempts to avoid fan-out by embedding per-store stock state as a `nested` array field on each SKU document (e.g., `"store_stock": [{"store_id": "07", "in_stock": true}, ...]`)
- Rejected because: Elasticsearch nested queries are resolved by iterating over all nested documents within the parent; with 40 nested entries per document and 5,000 documents per shard, every query incurs an O(40 × 5,000) = O(200,000) nested evaluation pass, making it significantly slower than a flat document query
- Rejected because: nested filter paths are explicitly excluded from the Elasticsearch query cache, making caching impossible regardless of query structure
- Rejected because: updating a single store's stock entry still rewrites the entire parent document including all 40 nested entries, which is more byte-heavy than a targeted per-store document update

## Consequences

### Positive
- OOS and restock events write to exactly one index with zero cross-store fan-out, keeping write amplification constant as the fleet grows
- Query cache operates at maximum efficiency: all searches within a store share the same query key structure with no variable filter clauses
- Store-level index isolation means a single store's index can be taken offline for maintenance, force-merged, or migrated without affecting any other store's search availability
- Independent schema evolution: the blue/green alias pattern (write to `catalog_store_07_v2`, swap the `catalog_store_07` alias atomically) allows zero-downtime schema migrations on a per-store basis

### Negative (Trade-offs)
- 40 indexes to monitor, alert on, and operate instead of 1; observability dashboards must aggregate across indexes to provide a city-level view
- Product assortment changes — when a new SKU is introduced across multiple stores — require coordinated index updates to all affected store indexes; the nightly job handles bulk assortment sync, but urgent mid-day assortment changes require a targeted multi-index write operation
- Cluster shard count increases 40x compared to a global index; Elasticsearch recommends keeping shard sizes between 10–50 GB, and with 5,000 small documents per index, shards will be very small — we must explicitly configure 1 primary shard per store index and monitor total shard count against cluster node limits
- Bootstrapping a new dark store requires provisioning and populating a fresh index before the store goes live, adding an onboarding step to the dark store launch runbook

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Single store index becomes unavailable (node failure, index corruption) | Low | High | Circuit breaker in the Search Service detects Elasticsearch 5xx for a given store and falls back to PostgreSQL full-text search (`tsvector`) for that store; degraded but functional |
| Schema migration across 40 indexes takes too long and leaves indexes in mixed schema states | Med | Med | Blue/green alias pattern: create `catalog_{store_id}_v2` indexes in parallel, verify with canary traffic, atomically swap aliases store-by-store; rollback is alias pointer revert |
| Nightly assortment sync job fails, leaving new SKUs absent from store indexes | Med | Med | Alert if sync job has not completed by 03:00 AM; re-run is idempotent (upsert by SKU ID); critical new SKU additions can be triggered via a manual admin API endpoint |
| Elasticsearch cluster shard count exceeds recommended limits as store count grows | Low | Med | Monitor shard-to-node ratio; at 40 stores with 1 primary + 1 replica each = 80 shards total, well within typical cluster capacity; revisit if city fleet exceeds 200 stores |
| Kafka consumer lag causes OOS products to remain searchable after going out of stock | Med | High | Consumer group lag alerting (threshold: >30s); at 9 events/sec, a single-partition consumer processes this comfortably; add partition count to the `inventory.events` topic if lag grows |
