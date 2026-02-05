# Caching Strategy

## Overview

The flight search system employs a multi-layer caching strategy to achieve sub-2-second search latency while maintaining price accuracy. The challenge is balancing freshness (airline prices change frequently) with performance (external API calls take 1-5 seconds).

---

## Cache Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Layer                                 │
│    ┌─────────────────────────────────────────────────────────┐      │
│    │                  Browser Cache (L0)                      │      │
│    │              Airport data, static assets                 │      │
│    │                    TTL: 24 hours                         │      │
│    └─────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           CDN Layer                                  │
│    ┌─────────────────────────────────────────────────────────┐      │
│    │                      CDN (L1)                            │      │
│    │          Static reference data, popular routes           │      │
│    │                  TTL: 1-24 hours                         │      │
│    └─────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Application Layer                              │
│    ┌─────────────────────────────────────────────────────────┐      │
│    │                 Local Cache (L2)                         │      │
│    │            In-memory cache per service instance          │      │
│    │                   TTL: 30-60 seconds                     │      │
│    └─────────────────────────────────────────────────────────┘      │
│                                  │                                   │
│                                  ▼                                   │
│    ┌─────────────────────────────────────────────────────────┐      │
│    │                 Redis Cluster (L3)                       │      │
│    │          Search results, route prices, sessions          │      │
│    │                  TTL: 2-30 minutes                       │      │
│    └─────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Layer Details

### L0: Browser Cache

**Purpose:** Cache static assets and reference data on the client side.

**Cached Data:**
| Data Type | TTL | Cache-Control Header |
|-----------|-----|---------------------|
| Airport list | 24h | `public, max-age=86400` |
| Airline logos | 7d | `public, max-age=604800` |
| Static JS/CSS | 1y | `public, max-age=31536000, immutable` |
| API responses | 0 | `no-store` (dynamic data) |

### L1: CDN (CloudFront/Fastly)

**Purpose:** Edge caching for geographically distributed users and static content.

**Cached Data:**
| Data Type | TTL | Invalidation Strategy |
|-----------|-----|----------------------|
| Airport autocomplete | 24h | Manual when airport data changes |
| Airline metadata | 24h | Manual |
| Popular route stats | 1h | Scheduled |
| Price trends (summary) | 15min | Time-based |

**Configuration:**
```yaml
cdn_rules:
  - path: "/api/v1/airports/*"
    cache: true
    ttl: 86400
    vary: "Accept-Encoding"

  - path: "/api/v1/airlines/*"
    cache: true
    ttl: 86400

  - path: "/api/v1/flights/search*"
    cache: false  # Dynamic content, bypass CDN

  - path: "/static/*"
    cache: true
    ttl: 31536000
    immutable: true
```

### L2: Local In-Memory Cache

**Purpose:** Reduce Redis round-trips for frequently accessed data within a single service instance.

**Implementation:** Go `sync.Map` or `groupcache`

**Cached Data:**
| Data Type | TTL | Max Size |
|-----------|-----|----------|
| Hot route results | 60s | 1,000 entries |
| Supplier configs | 5min | 100 entries |
| Airport lookups | 5min | 10,000 entries |
| Circuit breaker states | 10s | 500 entries |

**Eviction Policy:** LRU with size limit

```go
type LocalCache struct {
    cache    *lru.Cache
    maxSize  int
    ttl      time.Duration
}

// Example usage
localCache := NewLocalCache(1000, 60*time.Second)
results, found := localCache.Get(cacheKey)
if !found {
    results = fetchFromRedis(cacheKey)
    localCache.Set(cacheKey, results)
}
```

### L3: Redis Cluster

**Purpose:** Shared distributed cache across all service instances.

**Deployment:**
- 6-node cluster (3 primary, 3 replica)
- 64 GB RAM per node
- 256 hash slots per node

**Data Structures:**

#### Search Results Cache

**Key Pattern:** `search:{hash}`

```
Hash = SHA256(origin + destination + date + passengers + cabin_class + sorted(filters))
```

**Example:**
```
search:a3f2c1b5e8d9... → {
  "search_id": "srch_abc123",
  "results": [...],
  "lowest_price": 29900,
  "cached_at": 1623456789
}
```

**TTL Calculation (Dynamic):**

```python
def calculate_ttl(departure_date: date) -> int:
    days_to_departure = (departure_date - date.today()).days

    if days_to_departure <= 3:
        return 120      # 2 minutes - prices change rapidly
    elif days_to_departure <= 7:
        return 300      # 5 minutes
    elif days_to_departure <= 30:
        return 900      # 15 minutes
    else:
        return 1800     # 30 minutes - prices relatively stable
```

#### Route Price Rankings

**Key Pattern:** `route_prices:{route_id}:{date}`

**Type:** Sorted Set

```redis
ZADD route_prices:JFK-LAX:2024-07-01 29900 "flt_001_json"
ZADD route_prices:JFK-LAX:2024-07-01 32500 "flt_002_json"
ZRANGEBYSCORE route_prices:JFK-LAX:2024-07-01 0 35000 LIMIT 0 20
```

#### Flight Availability

**Key Pattern:** `avail:{flight_id}`

**Type:** String (JSON)

```redis
SET avail:flt_ua123_20240701 '{"seats":7,"fare_class":"Y","price":29900}' EX 120
```

---

## Cache Patterns

### 1. Cache-Aside (Lazy Loading)

**Use Case:** Search results, flight details

```
┌──────┐     ┌───────┐     ┌───────┐     ┌──────────┐
│Client│────>│Service│────>│ Redis │     │ Supplier │
│      │     │       │     │       │     │ Gateway  │
└──────┘     └───┬───┘     └───┬───┘     └────┬─────┘
               │             │                │
               │ 1. GET key  │                │
               │────────────>│                │
               │             │                │
               │ 2a. Cache HIT               │
               │<────────────│                │
               │             │                │
               │ 2b. Cache MISS              │
               │<────────────│                │
               │             │                │
               │ 3. Fetch from source        │
               │────────────────────────────>│
               │             │                │
               │ 4. Response │                │
               │<────────────────────────────│
               │             │                │
               │ 5. SET key  │                │
               │────────────>│                │
```

### 2. Stale-While-Revalidate

**Use Case:** Search results where slight staleness is acceptable

```python
async def search_with_swr(cache_key: str, fetch_fn: Callable) -> SearchResults:
    cached = await redis.get(cache_key)

    if cached:
        result = deserialize(cached)
        ttl = await redis.ttl(cache_key)

        # If TTL is less than 20% of original, trigger background refresh
        if ttl < original_ttl * 0.2:
            asyncio.create_task(background_refresh(cache_key, fetch_fn))

        return result

    # Cache miss - fetch synchronously
    result = await fetch_fn()
    await redis.setex(cache_key, ttl, serialize(result))
    return result

async def background_refresh(cache_key: str, fetch_fn: Callable):
    try:
        result = await fetch_fn()
        await redis.setex(cache_key, calculate_ttl(), serialize(result))
    except Exception as e:
        log.warning(f"Background refresh failed: {e}")
        # Keep stale data, don't invalidate
```

### 3. Write-Through

**Use Case:** Booking confirmation, user preferences

```python
async def create_booking(booking_data: dict) -> Booking:
    # 1. Write to database
    booking = await db.bookings.insert(booking_data)

    # 2. Write to cache
    await redis.setex(
        f"booking:{booking.id}",
        86400,  # 24 hour TTL
        serialize(booking)
    )

    # 3. Invalidate related caches
    await redis.delete(f"user_bookings:{booking.user_id}")

    return booking
```

### 4. Cache Warming

**Use Case:** Popular routes, upcoming departures

```python
# Background job running every 5 minutes
async def warm_popular_routes():
    popular_routes = await get_top_routes(limit=1000)

    for route in popular_routes:
        for days_ahead in [1, 2, 3, 7, 14, 30]:
            departure_date = date.today() + timedelta(days=days_ahead)

            cache_key = generate_cache_key(
                route.origin, route.destination, departure_date
            )

            # Skip if cache exists and is fresh
            if await redis.ttl(cache_key) > 60:
                continue

            # Fetch and cache
            results = await search_suppliers(route, departure_date)
            await cache_results(cache_key, results)

            # Rate limit to avoid overloading suppliers
            await asyncio.sleep(0.1)
```

---

## Cache Invalidation

### Time-Based Invalidation (Primary)

Most cache entries use TTL-based expiration:

| Cache Type | TTL Strategy |
|------------|--------------|
| Search results | Dynamic (2-30 min based on departure) |
| Flight availability | 2 minutes |
| Price rankings | 5 minutes |
| User sessions | 24 hours |
| Static reference | 24 hours |

### Event-Based Invalidation

Certain events trigger immediate cache invalidation:

```python
# Kafka consumer for booking events
async def handle_booking_event(event: BookingEvent):
    if event.type == "booking_confirmed":
        flight_id = event.flight_id

        # Invalidate availability cache
        await redis.delete(f"avail:{flight_id}")

        # Invalidate search results containing this flight
        # (Only for imminent departures where seat count matters)
        if event.days_to_departure <= 3:
            pattern = f"search:*{event.route_id}*"
            keys = await redis.scan_iter(match=pattern)
            if keys:
                await redis.delete(*keys)
```

### Manual Invalidation

Admin API for emergency cache clearing:

```http
DELETE /admin/cache/search?route=JFK-LAX
DELETE /admin/cache/supplier/{supplier_code}
DELETE /admin/cache/all?confirm=true
```

---

## Cache Key Design

### Principles

1. **Deterministic:** Same input always produces same key
2. **Collision-free:** Different inputs produce different keys
3. **Readable (for debugging):** Include human-readable prefix

### Key Patterns

```
# Search Results
search:{sha256(normalized_params)}
Example: search:a3f2c1b5e8d9f4a1b2c3d4e5f6g7h8i9j0k1l2m3

# Route Prices
route_prices:{origin}-{destination}:{date}
Example: route_prices:JFK-LAX:2024-07-01

# Flight Availability
avail:{flight_id}
Example: avail:flt_ua123_20240701

# User Session
session:{session_id}
Example: session:sess_abc123def456

# Rate Limit
rate:{type}:{identifier}
Example: rate:ip:192.168.1.1
Example: rate:user:12345

# Circuit Breaker
circuit:{supplier_code}
Example: circuit:amadeus
```

### Normalization

Cache keys must be normalized to ensure consistency:

```python
def normalize_search_params(params: SearchParams) -> str:
    """Generate normalized cache key from search parameters."""
    normalized = {
        "origin": params.origin.upper(),
        "destination": params.destination.upper(),
        "departure_date": params.departure_date.isoformat(),
        "return_date": params.return_date.isoformat() if params.return_date else None,
        "adults": params.adults,
        "children": params.children,
        "infants": params.infants,
        "cabin_class": params.cabin_class.lower(),
        "direct_only": params.direct_only,
        "carriers": sorted(params.carriers) if params.carriers else None,
    }

    # Remove None values
    normalized = {k: v for k, v in normalized.items() if v is not None}

    # Create deterministic JSON string
    json_str = json.dumps(normalized, sort_keys=True, separators=(',', ':'))

    # Hash for key
    return hashlib.sha256(json_str.encode()).hexdigest()[:32]
```

---

## Performance Optimization

### Connection Pooling

```python
redis_pool = redis.ConnectionPool(
    host='redis-cluster.example.com',
    port=6379,
    max_connections=100,
    socket_timeout=0.5,
    socket_connect_timeout=0.5,
    retry_on_timeout=True
)
```

### Pipelining

Batch multiple Redis operations:

```python
async def get_multiple_flights(flight_ids: list[str]) -> dict:
    pipe = redis.pipeline()

    for flight_id in flight_ids:
        pipe.get(f"avail:{flight_id}")

    results = await pipe.execute()

    return {
        flight_id: deserialize(result)
        for flight_id, result in zip(flight_ids, results)
        if result is not None
    }
```

### Compression

Compress large payloads:

```python
import gzip
import json

COMPRESSION_THRESHOLD = 1024  # 1KB

def cache_results(key: str, results: dict, ttl: int):
    data = json.dumps(results)

    if len(data) > COMPRESSION_THRESHOLD:
        compressed = gzip.compress(data.encode())
        redis.setex(f"{key}:gz", ttl, compressed)
    else:
        redis.setex(key, ttl, data)

def get_cached(key: str) -> dict:
    # Try compressed first
    compressed = redis.get(f"{key}:gz")
    if compressed:
        return json.loads(gzip.decompress(compressed))

    # Fall back to uncompressed
    data = redis.get(key)
    if data:
        return json.loads(data)

    return None
```

---

## Monitoring & Metrics

### Key Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Cache hit rate | > 60% | < 40% |
| Cache latency (P99) | < 10ms | > 50ms |
| Memory usage | < 80% | > 90% |
| Eviction rate | < 100/s | > 1000/s |
| Connection pool usage | < 70% | > 90% |

### Prometheus Metrics

```python
cache_hits = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_type', 'layer']
)

cache_misses = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_type', 'layer']
)

cache_latency = Histogram(
    'cache_operation_duration_seconds',
    'Cache operation latency',
    ['operation', 'cache_type'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1]
)
```

### Grafana Dashboard

Key panels:
1. Cache hit rate over time (by cache type)
2. Cache latency percentiles
3. Memory usage per Redis node
4. Top cache keys by access frequency
5. Cache invalidation events

---

## Failure Handling

### Redis Cluster Failure

If Redis is unavailable, fall back gracefully:

```python
async def search_with_cache_fallback(params: SearchParams) -> SearchResults:
    try:
        # Try cache first
        cached = await redis.get(cache_key, timeout=0.5)
        if cached:
            return deserialize(cached)
    except (RedisError, TimeoutError) as e:
        log.warning(f"Redis unavailable: {e}")
        metrics.cache_errors.inc()

    # Proceed without cache
    results = await search_suppliers(params)

    # Try to cache (fire and forget)
    try:
        asyncio.create_task(
            redis.setex(cache_key, ttl, serialize(results))
        )
    except Exception:
        pass  # Cache write failure is non-critical

    return results
```

### Thundering Herd Prevention

Use distributed locks for expensive operations:

```python
async def search_with_lock(params: SearchParams) -> SearchResults:
    cache_key = generate_cache_key(params)
    lock_key = f"lock:{cache_key}"

    # Try cache
    cached = await redis.get(cache_key)
    if cached:
        return deserialize(cached)

    # Acquire lock
    lock_acquired = await redis.set(lock_key, "1", nx=True, ex=30)

    if lock_acquired:
        try:
            results = await search_suppliers(params)
            await redis.setex(cache_key, ttl, serialize(results))
            return results
        finally:
            await redis.delete(lock_key)
    else:
        # Wait for other request to populate cache
        for _ in range(10):
            await asyncio.sleep(0.5)
            cached = await redis.get(cache_key)
            if cached:
                return deserialize(cached)

        # Timeout - fetch ourselves
        return await search_suppliers(params)
```
