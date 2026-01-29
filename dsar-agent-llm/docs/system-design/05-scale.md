# Scale Considerations

## Load Analysis

### Expected Traffic

| Metric | Value | Basis |
|--------|-------|-------|
| Support agents | 50-200 | Typical enterprise support team |
| Requests per agent per day | 20-50 | DSAR volume estimates |
| Peak requests per hour | 500-1000 | Business hours concentration |
| Daily request volume | 1,000-10,000 | Team size × requests/agent |
| Monthly request volume | 30,000-300,000 | Growth projection |

### Request Characteristics

| Characteristic | Value |
|----------------|-------|
| Request payload size | ~500 bytes |
| Response payload size | ~2KB |
| LLM prompt tokens | ~1,500 |
| LLM completion tokens | ~300 |
| LLM latency (p50) | 2-4 seconds |
| LLM latency (p99) | 8-12 seconds |

---

## Bottleneck Analysis

### Primary Bottleneck: LLM API Latency

```
Request Timeline (typical):
├── Network + Auth:     50ms
├── Prompt Building:    10ms
├── LLM API Call:       3000ms  ◀── DOMINANT FACTOR
├── Response Parsing:   10ms
├── SQL Validation:     20ms
├── Audit Logging:      30ms
└── Total:              ~3120ms
```

**Implications:**
- CPU is not the bottleneck
- Memory is not the bottleneck
- I/O-bound workload → async handling is critical
- Scaling by adding replicas works well

### Secondary Bottleneck: LLM Rate Limits

| Provider | Rate Limit | Our Headroom |
|----------|------------|--------------|
| OpenAI GPT-4 | 10,000 RPM (Tier 5) | Comfortable for projected load |
| Anthropic Claude | Varies by tier | May need enterprise tier |

**Mitigation:**
- Multi-provider failover
- Request queuing with backpressure
- Caching for identical requests (rare in practice)

---

## Scaling Strategy

### Horizontal Scaling

```
┌─────────────────────────────────────────────────────────────────┐
│                        Load Balancer                             │
└─────────────────────────────────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│    Pod 1      │      │    Pod 2      │      │    Pod 3      │
│  (Stateless)  │      │  (Stateless)  │      │  (Stateless)  │
└───────────────┘      └───────────────┘      └───────────────┘
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  LLM Provider API   │
                    │  (Shared resource)  │
                    └─────────────────────┘
```

**Configuration:**

```yaml
# Kubernetes HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: External
      external:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: 50
```

### Capacity Planning

| Load Level | Replicas | Requests/min | LLM Calls/min |
|------------|----------|--------------|---------------|
| Low | 2 | 20 | 20 |
| Normal | 3 | 100 | 100 |
| High | 5 | 300 | 300 |
| Peak | 10 | 600 | 600 |

**Calculation:**
- Each pod handles ~100 concurrent requests (async)
- Average request duration: 4 seconds
- Throughput per pod: ~25 requests/second (theoretical)
- Practical throughput: ~10-15 requests/second (with headroom)

---

## Component Scaling

### Schema Registry

| Aspect | Strategy |
|--------|----------|
| Size | 100+ tables, 1000+ columns fit in memory (~1MB) |
| Updates | Hot-reload via ConfigMap change |
| Scaling | In-memory per pod; no shared state needed |

### Audit Logger

| Aspect | Strategy |
|--------|----------|
| Write Volume | 10,000+ writes/day |
| Storage | Append-only JSONL or database |
| Scaling | Async writes, buffer with flush |

**Options by scale:**

| Scale | Storage | Rationale |
|-------|---------|-----------|
| <10K/day | File (JSONL) | Simple, sufficient |
| 10K-100K/day | PostgreSQL | Queryable, reliable |
| >100K/day | TimescaleDB / ClickHouse | Time-series optimized |

### Rate Limiter

| Aspect | Strategy |
|--------|----------|
| Single Pod | In-memory sliding window |
| Multi-Pod | Redis shared counter |
| Distributed | Token bucket in Redis |

**Redis implementation:**

```python
# Distributed rate limiting with Redis
async def check_rate_limit(agent_id: str) -> bool:
    key = f"rate:{agent_id}"
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, 3600)  # 1 hour window
    return current <= 100  # 100 requests/hour limit
```

---

## Performance Optimizations

### 1. Async Everywhere

```python
# All I/O operations are async
async def generate_query(request: DSARRequest) -> DSARResponse:
    messages = prompt_builder.build_messages(...)
    response = await llm_client.complete(messages)  # Non-blocking
    validation = await validator.validate(response)  # Non-blocking
    await audit_logger.log(...)  # Non-blocking
    return response
```

### 2. Connection Pooling

```python
# Reuse HTTP connections to LLM providers
http_client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=50,
    ),
    timeout=httpx.Timeout(30.0),
)
```

### 3. Schema Caching

```python
# Load schema once, cache in memory
@lru_cache(maxsize=1)
def get_schema_registry() -> SchemaRegistry:
    return load_schema_from_file()

# Hot-reload on file change (optional)
def reload_schema():
    get_schema_registry.cache_clear()
```

### 4. Response Streaming (Future)

For very long queries, stream the LLM response:

```python
async def generate_query_streaming(request: DSARRequest):
    async for chunk in llm_client.stream(messages):
        yield chunk
    # Validate complete response
```

---

## Failure Modes and Resilience

### LLM Provider Outage

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Primary   │────▶│  Fallback   │────▶│   Error     │
│   (GPT-4)   │     │  (Claude)   │     │  Response   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                  │
       │ Timeout/Error    │ Timeout/Error
       ▼                  ▼
   Try Fallback     Return Error
```

**Circuit breaker pattern:**

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
async def call_llm_with_retry(messages):
    try:
        return await primary_llm.complete(messages)
    except LLMError:
        return await fallback_llm.complete(messages)
```

### Database Outage (Audit Logger)

- Buffer logs in memory (limited size)
- Flush to file as backup
- Alert on persistent failures
- Never block main request path

---

## Cost Projections

### LLM Costs

| Volume | Tokens/Request | Monthly Cost (GPT-4) | Monthly Cost (Claude) |
|--------|----------------|----------------------|-----------------------|
| 1,000/day | ~2,000 | ~$600 | ~$360 |
| 10,000/day | ~2,000 | ~$6,000 | ~$3,600 |
| 100,000/day | ~2,000 | ~$60,000 | ~$36,000 |

**Optimization strategies:**
- Cache common patterns (limited effectiveness)
- Shorter prompts (risk: lower accuracy)
- Smaller models for simple queries (risk: accuracy)

### Infrastructure Costs

| Component | Monthly Cost (Estimate) |
|-----------|-------------------------|
| Kubernetes (3 pods) | ~$200 |
| Load Balancer | ~$20 |
| Redis (rate limiting) | ~$50 |
| Logging/Monitoring | ~$100 |
| **Total (excluding LLM)** | **~$370** |

---

## Monitoring and Alerts

### Key Metrics

| Metric | Alert Threshold |
|--------|-----------------|
| Request latency (p99) | > 15 seconds |
| Error rate | > 1% |
| LLM call failures | > 5% |
| Rate limit hits | > 10/hour |
| Validation failures | > 20% |

### Dashboard Panels

1. Request volume (per minute)
2. Latency percentiles (p50, p95, p99)
3. Error rate by type
4. LLM token usage
5. Cache hit rate
6. Rate limit status per agent
