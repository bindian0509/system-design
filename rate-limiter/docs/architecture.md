# Distributed Rate Limiter - Architecture

## Overview

This document describes the architecture of a high-performance distributed rate limiter designed for API Gateway scenarios. The system supports 100K-1M requests per second with composite rate limiting keys (user + endpoint), best-effort consistency, and configurable failure behavior.

## System Context

```mermaid
C4Context
    title System Context Diagram - Distributed Rate Limiter

    Person(client, "API Client", "External consumers of the API")
    System(ratelimiter, "Distributed Rate Limiter", "Controls API request rates")
    System_Ext(backend, "Backend Services", "Protected API services")
    SystemDb_Ext(redis, "Redis Cluster", "Distributed counter storage")

    Rel(client, ratelimiter, "API Requests", "HTTPS")
    Rel(ratelimiter, backend, "Allowed Requests", "HTTP/gRPC")
    Rel(ratelimiter, redis, "Counter Operations", "Redis Protocol")
```

## High-Level Architecture

```mermaid
flowchart TB
    subgraph clients [Clients]
        C1[Client 1]
        C2[Client 2]
        C3[Client N]
    end

    subgraph gateway [API Gateway Layer]
        LB[Load Balancer]
        subgraph nodes [Rate Limiter Nodes]
            RL1[Rate Limiter 1]
            RL2[Rate Limiter 2]
            RL3[Rate Limiter N]
        end
    end

    subgraph storage [Distributed Storage]
        subgraph redis [Redis Cluster]
            RS1[(Shard 1)]
            RS2[(Shard 2)]
            RS3[(Shard 3)]
        end
    end

    subgraph backend [Backend Services]
        API1[API Service 1]
        API2[API Service 2]
    end

    C1 --> LB
    C2 --> LB
    C3 --> LB
    LB --> RL1
    LB --> RL2
    LB --> RL3
    RL1 <--> RS1
    RL1 <--> RS2
    RL2 <--> RS2
    RL2 <--> RS3
    RL3 <--> RS1
    RL3 <--> RS3
    RL1 --> API1
    RL2 --> API1
    RL3 --> API2
```

## Core Components

### 1. Rate Limiter Node

Stateless application instances that process incoming requests and enforce rate limits.

**Responsibilities:**
- Extract rate limit key from request (user ID, API key, IP, endpoint)
- Check rate limit against configured rules
- Return appropriate response headers (X-RateLimit-*)
- Forward allowed requests to backend services

**Key Classes:**
- `RateLimitFilter` - Spring filter that intercepts all requests
- `RateLimiterService` - Orchestrates multi-level rate limiting
- `RuleMatcherService` - Matches requests to applicable rules

### 2. Local Cache Layer (Caffeine)

In-memory cache that reduces Redis round-trips for high-throughput scenarios.

```mermaid
flowchart LR
    subgraph node [Rate Limiter Node]
        LocalCache["Local Cache<br/>(Caffeine)"]
        SyncBuffer["Sync Buffer<br/>(Batch Updates)"]
    end

    Request --> LocalCache
    LocalCache -->|Cache Hit| FastPath[Fast Decision]
    LocalCache -->|Cache Miss| Redis[(Redis)]
    Redis --> LocalCache
    SyncBuffer -->|"Every 100ms"| Redis
    LocalCache -->|Increment| SyncBuffer
```

**Configuration:**
- Max entries: 100,000
- TTL: Window size (typically 60 seconds)
- Sync interval: 100ms

### 3. Redis Cluster

Distributed storage for rate limit counters with automatic sharding.

**Key Features:**
- Horizontal scalability via sharding
- High availability with replicas
- Atomic operations via Lua scripts
- Automatic key distribution by consistent hashing

**Key Pattern:**
```
rl:{user_id}:{endpoint}:{window_start}
```

### 4. Rate Limit Rules Engine

Dynamic rule configuration supporting multiple scopes and priorities.

```mermaid
flowchart TD
    Request[Incoming Request] --> L1{Level 1: Global Limit}
    L1 -->|Exceeded| Reject1[429 Too Many Requests]
    L1 -->|OK| L2{Level 2: Per Endpoint}
    L2 -->|Exceeded| Reject2[429 Too Many Requests]
    L2 -->|OK| L3{Level 3: Per User}
    L3 -->|Exceeded| Reject3[429 Too Many Requests]
    L3 -->|OK| L4{Level 4: Per User + Endpoint}
    L4 -->|Exceeded| Reject4[429 Too Many Requests]
    L4 -->|OK| Allow[Forward to Backend]
```

## Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant Filter as RateLimitFilter
    participant Service as RateLimiterService
    participant Cache as LocalCacheService
    participant Redis as Redis Cluster
    participant Backend as Backend Service

    Client->>Filter: HTTP Request
    Filter->>Service: checkRateLimit(key)
    Service->>Cache: getCounter(key)

    alt Cache Hit
        Cache-->>Service: counter value
    else Cache Miss
        Cache->>Redis: GET counter
        Redis-->>Cache: counter value
        Cache-->>Service: counter value
    end

    Service->>Service: evaluate rules

    alt Rate Limit OK
        Service->>Cache: incrementCounter(key)
        Cache->>Cache: buffer increment
        Service-->>Filter: RateLimitResult(allowed=true)
        Filter->>Backend: Forward Request
        Backend-->>Filter: Response
        Filter-->>Client: Response + Rate Limit Headers
    else Rate Limit Exceeded
        Service-->>Filter: RateLimitResult(allowed=false)
        Filter-->>Client: 429 Too Many Requests
    end

    Note over Cache,Redis: Async batch sync every 100ms
    Cache->>Redis: INCRBY (batched)
```

## Failure Handling

### State Machine

```mermaid
stateDiagram-v2
    [*] --> Healthy
    Healthy --> Degraded: Redis latency > 50ms
    Healthy --> Unavailable: Redis connection lost
    Degraded --> Healthy: Latency normal
    Degraded --> Unavailable: Connection lost
    Unavailable --> Healthy: Connection restored

    state Unavailable {
        [*] --> CheckConfig
        CheckConfig --> FailOpen: config.failOpen=true
        CheckConfig --> FailClosed: config.failOpen=false
        FailOpen --> AllowAll: Allow requests
        FailClosed --> RejectAll: Reject requests
    }
```

### Circuit Breaker Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| Failure threshold | 50% | Open circuit after 50% failures |
| Wait duration | 30s | Time before attempting recovery |
| Permitted calls | 10 | Test calls in half-open state |
| Sliding window | 100 calls | Sample size for failure rate |

## Scalability

### Horizontal Scaling

- **Rate Limiter Nodes**: Stateless, scale based on CPU/memory
- **Redis Cluster**: Add shards for more capacity
- **Local Cache**: Reduces Redis load proportionally

### Capacity Planning

| Component | Metric | Target |
|-----------|--------|--------|
| Rate Limiter Node | RPS | 50,000 per instance |
| Redis Shard | Operations/sec | 100,000 per shard |
| Local Cache | Hit Rate | > 90% |
| Network | Latency to Redis | < 5ms p99 |

### Scaling Formula

```
Required Nodes = Peak RPS / 50,000
Required Redis Shards = (Peak RPS × Miss Rate) / 100,000
```

## Deployment Architecture

```mermaid
flowchart TB
    subgraph az1 [Availability Zone 1]
        RL1[Rate Limiter Pod]
        RL2[Rate Limiter Pod]
        RS1[(Redis Primary)]
    end

    subgraph az2 [Availability Zone 2]
        RL3[Rate Limiter Pod]
        RL4[Rate Limiter Pod]
        RS2[(Redis Replica)]
    end

    subgraph az3 [Availability Zone 3]
        RL5[Rate Limiter Pod]
        RL6[Rate Limiter Pod]
        RS3[(Redis Replica)]
    end

    LB[Load Balancer] --> RL1
    LB --> RL2
    LB --> RL3
    LB --> RL4
    LB --> RL5
    LB --> RL6

    RS1 -.->|Replication| RS2
    RS1 -.->|Replication| RS3
```

## Monitoring

### Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `ratelimit.requests.total` | Counter | Total requests processed |
| `ratelimit.requests.allowed` | Counter | Requests that passed rate limit |
| `ratelimit.requests.rejected` | Counter | Requests rejected (429) |
| `ratelimit.check.latency` | Histogram | Rate limit check duration |
| `ratelimit.cache.hits` | Counter | Local cache hits |
| `ratelimit.cache.misses` | Counter | Local cache misses |
| `ratelimit.redis.errors` | Counter | Redis operation failures |

### Alerting Rules

1. **High Rejection Rate**: > 10% requests rejected in 5 minutes
2. **Redis Latency**: p99 > 50ms for 2 minutes
3. **Circuit Open**: Any circuit breaker opens
4. **Cache Hit Rate Low**: < 80% hit rate for 5 minutes

## Security Considerations

1. **Key Extraction**: Validate user identity before rate limiting
2. **IP Spoofing**: Use trusted proxy headers only
3. **Redis Access**: Network isolation, authentication enabled
4. **DoS Protection**: Global rate limits protect the rate limiter itself
