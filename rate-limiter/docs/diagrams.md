# Distributed Rate Limiter - Diagrams

This document contains all Mermaid diagrams for the distributed rate limiter system.

## Request Flow Sequence

```mermaid
sequenceDiagram
    participant Client
    participant Filter as RateLimitFilter
    participant Service as RateLimiterService
    participant Matcher as RuleMatcherService
    participant Cache as LocalCacheService
    participant Redis as Redis Cluster
    participant Backend as Backend Service

    Client->>Filter: HTTP Request
    Filter->>Filter: Extract userId, endpoint, IP
    Filter->>Service: checkRateLimit(userId, endpoint, ip)

    Service->>Matcher: getApplicableRules()
    Matcher-->>Service: List of rules

    loop For each rule in priority order
        Service->>Cache: getCount(key, window)

        alt Cache Hit
            Cache-->>Service: cached count
        else Cache Miss
            Cache->>Redis: GET count
            Redis-->>Cache: count value
            Cache-->>Service: count
        end

        Service->>Service: Calculate weighted count

        alt Count exceeds limit
            Service-->>Filter: RateLimitResult(rejected)
            Filter-->>Client: 429 Too Many Requests
        end
    end

    Service->>Cache: incrementLocal()
    Cache-->>Service: new count
    Service-->>Filter: RateLimitResult(allowed)
    Filter->>Backend: Forward request
    Backend-->>Filter: Response
    Filter-->>Client: Response + Rate Limit Headers

    Note over Cache,Redis: Async batch sync every 100ms
    Cache--)Redis: INCRBY (batched)
```

## Sliding Window Counter Algorithm

```mermaid
flowchart LR
    subgraph time [Time Flow]
        direction LR
        T1["t=0"] --> T2["t=30s"] --> T3["t=60s"] --> T4["t=90s"]
    end

    subgraph windows [Window Counters]
        W1["Window 0<br/>00:00-01:00<br/>Count: 80"]
        W2["Window 1<br/>01:00-02:00<br/>Count: 30"]
    end

    subgraph calculation [At t=01:30 - 50% into Window 1]
        Weights["Previous weight: 50%<br/>Current weight: 100%"]
        Formula["80 × 0.5 + 30 = 70"]
        Decision{70 < 100?}
    end

    W1 --> Weights
    W2 --> Weights
    Weights --> Formula --> Decision
    Decision -->|Yes| Allow[Allow Request]
    Decision -->|No| Reject[429 Reject]
```

## Multi-Level Rate Limiting

```mermaid
flowchart TD
    Request[Incoming Request] --> Extract[Extract User, Endpoint, IP]
    Extract --> Match[Match Applicable Rules]

    Match --> L1{Global Limit<br/>10M/min}
    L1 -->|Exceeded| R1[429 + Rule: global]
    L1 -->|OK| L2{Endpoint Limit<br/>100K/min}

    L2 -->|Exceeded| R2[429 + Rule: endpoint]
    L2 -->|OK| L3{User Limit<br/>1000/min}

    L3 -->|Exceeded| R3[429 + Rule: user]
    L3 -->|OK| L4{User+Endpoint<br/>100/min}

    L4 -->|Exceeded| R4[429 + Rule: user_endpoint]
    L4 -->|OK| Allow[Forward to Backend]

    style R1 fill:#ff6b6b
    style R2 fill:#ff6b6b
    style R3 fill:#ff6b6b
    style R4 fill:#ff6b6b
    style Allow fill:#51cf66
```

## Local Cache + Redis Architecture

```mermaid
flowchart TB
    subgraph Node1 [Rate Limiter Node 1]
        LC1[Local Cache<br/>Caffeine]
        SB1[Sync Buffer]
    end

    subgraph Node2 [Rate Limiter Node 2]
        LC2[Local Cache<br/>Caffeine]
        SB2[Sync Buffer]
    end

    subgraph Node3 [Rate Limiter Node N]
        LC3[Local Cache<br/>Caffeine]
        SB3[Sync Buffer]
    end

    subgraph Redis [Redis Cluster]
        RS1[(Shard 1)]
        RS2[(Shard 2)]
        RS3[(Shard 3)]
    end

    Request1[Requests] --> LC1
    Request2[Requests] --> LC2
    Request3[Requests] --> LC3

    LC1 <-.->|Cache Miss| RS1
    LC2 <-.->|Cache Miss| RS2
    LC3 <-.->|Cache Miss| RS3

    SB1 -->|100ms Sync| RS1
    SB2 -->|100ms Sync| RS2
    SB3 -->|100ms Sync| RS3
```

## Circuit Breaker State Machine

```mermaid
stateDiagram-v2
    [*] --> Closed

    Closed --> Open: Failure rate >= 50%
    Closed --> Closed: Success

    Open --> HalfOpen: Wait 30s

    HalfOpen --> Closed: 10 successful calls
    HalfOpen --> Open: Any failure

    state Open {
        [*] --> CheckFailureMode
        CheckFailureMode --> FailOpen: mode=FAIL_OPEN
        CheckFailureMode --> FailClosed: mode=FAIL_CLOSED
        FailOpen --> AllowRequests
        FailClosed --> RejectRequests
    }
```

## Deployment Architecture

```mermaid
flowchart TB
    subgraph Internet
        Clients[API Clients]
    end

    subgraph LoadBalancer [Load Balancer]
        LB[nginx/AWS ALB]
    end

    subgraph K8s [Kubernetes Cluster]
        subgraph Pods [Rate Limiter Pods]
            P1[Pod 1]
            P2[Pod 2]
            P3[Pod 3]
        end

        subgraph Services
            SVC[ClusterIP Service]
        end
    end

    subgraph Redis [Redis Cluster]
        Master[(Primary)]
        Replica1[(Replica 1)]
        Replica2[(Replica 2)]
    end

    subgraph Monitoring
        Prometheus[Prometheus]
        Grafana[Grafana]
    end

    Clients --> LB
    LB --> SVC
    SVC --> P1
    SVC --> P2
    SVC --> P3

    P1 --> Master
    P2 --> Master
    P3 --> Master

    Master -.-> Replica1
    Master -.-> Replica2

    P1 -.-> Prometheus
    P2 -.-> Prometheus
    P3 -.-> Prometheus
    Prometheus --> Grafana
```

## Rate Limit Key Structure

```mermaid
flowchart LR
    subgraph KeyFormat [Key Format]
        Prefix["rl:"] --> Scope["SCOPE:"] --> RuleId["rule_id:"] --> Identifier["user/endpoint"] --> Window[":window_start"]
    end

    subgraph Examples [Example Keys]
        E1["rl:GLOBAL:global-limit:*:1704067200"]
        E2["rl:USER:per-user:user123:1704067200"]
        E3["rl:ENDPOINT:per-endpoint:_api_orders:1704067200"]
        E4["rl:USER_ENDPOINT:combined:user123:_api_orders:1704067200"]
    end
```

## Metrics Dashboard Overview

```mermaid
flowchart TB
    subgraph Metrics [Collected Metrics]
        M1[ratelimit.requests.total]
        M2[ratelimit.requests.allowed]
        M3[ratelimit.requests.rejected]
        M4[ratelimit.check.latency]
        M5[ratelimit.cache.hit_rate]
        M6[ratelimit.redis.errors]
    end

    subgraph Pipeline [Metrics Pipeline]
        App[Rate Limiter App] --> Micrometer
        Micrometer --> Prometheus
        Prometheus --> Grafana
    end

    subgraph Alerts [Alert Rules]
        A1["High rejection rate > 10%"]
        A2["Redis latency p99 > 50ms"]
        A3["Circuit breaker open"]
        A4["Cache hit rate < 80%"]
    end

    M1 --> Micrometer
    M2 --> Micrometer
    M3 --> Micrometer
    M4 --> Micrometer
    M5 --> Micrometer
    M6 --> Micrometer

    Grafana --> A1
    Grafana --> A2
    Grafana --> A3
    Grafana --> A4
```

## Algorithm Comparison

```mermaid
flowchart TD
    Start[Choose Algorithm] --> Q1{Need burst allowance?}

    Q1 -->|Yes| TokenBucket["Token Bucket<br/>✓ Allows controlled bursts<br/>✓ O(1) memory"]

    Q1 -->|No| Q2{Need smooth output?}

    Q2 -->|Yes| LeakyBucket["Leaky Bucket<br/>✓ Constant output rate<br/>✗ Adds latency"]

    Q2 -->|No| Q3{Strict precision needed?}

    Q3 -->|Yes| Q4{High volume?}

    Q4 -->|No| SlidingLog["Sliding Window Log<br/>✓ 100% accurate<br/>✗ O(n) memory"]

    Q4 -->|Yes| SlidingCounter["Sliding Window Counter<br/>✓ 99.7% accurate<br/>✓ O(1) memory<br/>★ RECOMMENDED"]

    Q3 -->|No| FixedWindow["Fixed Window<br/>✓ Simplest<br/>✗ Edge case bursts"]

    style SlidingCounter fill:#51cf66
```
