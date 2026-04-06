# Requirements

## Functional Requirements

### Core (P0)

1. **Increment view count** — When a user watches a video, record the view event. A "qualified view" is defined as watching >=30 seconds OR the full video if shorter than 30 seconds.

2. **Serve view count** — Return the current view count for any video with low latency. This is the number displayed on the video page.

3. **Deduplicate views** — Same user watching the same video repeatedly within a 12-hour window should count as one view. Prevents inflation from refreshes, replays, and accidental double-fires.

4. **Near-real-time counting** — Views should be reflected in the count within ~5-10 seconds for most videos. Users expect to see the counter move when they and others are watching.

5. **Exact batch reconciliation** — Hourly and daily batch jobs produce the authoritative "true count" by performing exact deduplication over the raw event log. The real-time count is approximate; the batch count is the source of truth.

### Analytics (P1)

6. **Slice views by dimensions** — Break down views by geography (country, region), device type (mobile, desktop, TV), time window (hourly, daily), referral source (search, suggested, external, ads), and user demographics.

7. **Creator analytics dashboard** — Provide creators with views over time, audience geography heat maps, peak viewing hours, watch time metrics, and audience retention curves.

8. **Trending signals** — Feed view velocity (views/hour), acceleration (rate of change), geographic spread, and referral diversity to the recommendation and trending systems.

9. **Ad monetization validation** — Distinguish organic views from paid/bot views. Only "qualified, non-bot" views count toward ad revenue. This has direct financial implications — accuracy is critical.

## Non-Functional Requirements

| Requirement | Target | Rationale |
|-------------|--------|-----------|
| **Throughput** | ~115K events/sec avg, ~500K/sec peak | 10B events/day with 4-5x peak-to-avg ratio |
| **Read latency** (view count API) | P50 < 20ms, P99 < 100ms | Video page load budget |
| **Write latency** (event ingestion) | P99 < 200ms (ack to client) | Don't block video playback |
| **Freshness** (real-time path) | Views visible within 5-10 seconds | User experience expectation |
| **Freshness** (batch/exact) | Hourly reconciliation, daily authoritative | Creator dashboard and monetization |
| **Accuracy** | +/-0.1% for batch counts; real-time can be approximate | Financial accuracy for ad revenue |
| **Availability** | 99.99% for reads, 99.95% for writes | View count display is critical UX element |
| **Durability** | Zero event loss after acknowledgment | Every view = potential ad revenue |
| **Data retention** | Raw events: 30 days hot, 1 year cold. Aggregates: indefinite | Reprocessing window + long-term analytics |

## Scale Parameters

| Metric | Value |
|--------|-------|
| Daily view events | ~10B |
| Avg event size | ~500 bytes (raw), ~200 bytes (compressed) |
| Daily raw ingestion | ~5 TB/day (uncompressed), ~2 TB/day (compressed) |
| Total videos on platform | ~1B |
| Videos with views in any given day | ~100M |
| Concurrent viewers on a viral video | ~5M+ |
| Geographic presence | 100+ countries, 6 continents |
| Peak-to-average traffic ratio | ~4-5x (evening hours, viral events, global holidays) |

## Interview Talking Points

### Why Lambda Architecture?

The core tension is **freshness vs. accuracy**. Users on the video page want to see the counter update in real-time (freshness). Creators and the ad monetization system need exact, reconciled numbers (accuracy). A single-path architecture forces you to choose one or compromise both.

Lambda solves this cleanly:
- **Speed layer** (Flink): ~99.5% accurate, <10s latency. Good enough for the video page.
- **Batch layer** (Spark): 100% accurate, ~1 hour latency. Authoritative for dashboards and payouts.
- **Serving layer**: Merges both, with the batch count overwriting real-time drift hourly.

### Why This Is a Data Engineering Problem, Not Just an API Problem

At 115K events/sec, you cannot do per-event database writes. This is fundamentally a **streaming ETL + OLAP** problem:
- **E**xtract: Capture events at edge PoPs globally
- **T**ransform: Deduplicate, enrich with geo/device dimensions, detect bots
- **L**oad: Into both a real-time serving layer and a columnar OLAP store

The API (serving view counts) is the easy part. The hard part is the pipeline that ensures those counts are accurate, fresh, and queryable across dozens of dimensions.

### What Makes a Top 20% Answer?

1. **Recognizing the dual-path need** — not just "put it in a database"
2. **Dedup at multiple layers** — client, edge, streaming, batch
3. **Geo-aware architecture** — data residency, regional processing, clock skew
4. **Bot detection integrated into the pipeline** — not an afterthought
5. **Cost awareness** — knowing that Kafka + Flink dominate the bill
6. **OLAP modeling** — star schema, materialized views, pre-computed cubes
7. **Data quality monitoring** — not just system metrics, but data metrics
