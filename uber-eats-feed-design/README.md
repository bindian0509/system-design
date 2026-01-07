# Uber Eats Restaurant Feed System

## Overview

A high-performance backend system that delivers personalized, ranked restaurant feeds to eaters based on their delivery location. The system handles 10M+ restaurants globally with 10K+ views/second, using spatial indexing for efficient geo-queries and supporting dynamic filtering for real-time restaurant availability.

## System Architecture (High-Level)

```mermaid
flowchart LR
    subgraph Sources ["📱 Clients"]
        Mobile[Mobile App]
        Web[Web App]
    end

    subgraph Gateway ["🚪 API Gateway"]
        LB[Load Balancer]
        API[Feed API]
        RateLimit[Rate Limiter]
    end

    subgraph GeoSearch ["🗺️ Geo Search Layer"]
        GeoIndex[(Geo Index<br/>ElasticSearch)]
        GeoCache[(Geo Cache<br/>Redis)]
    end

    subgraph Ranking ["📊 Ranking Layer"]
        RankSvc[Ranking Service]
        MLModel[ML Scorer]
    end

    subgraph Storage ["💾 Storage Layer"]
        RestDB[(Restaurant DB<br/>PostgreSQL)]
        StateCache[(State Cache<br/>Redis)]
    end

    Mobile & Web --> LB --> RateLimit --> API
    API --> GeoCache
    GeoCache --> GeoIndex
    GeoIndex --> RankSvc
    RankSvc <--> MLModel
    RankSvc --> RestDB
    RankSvc --> StateCache
```

## End-to-End Request Flow

```mermaid
sequenceDiagram
    participant E as 📱 Eater App
    participant G as 🚪 API Gateway
    participant C as ⚡ Cache
    participant S as 🗺️ Geo Search
    participant R as 📊 Ranker
    participant D as 💾 Restaurant DB

    E->>G: GET /feed?lat=40.7&lng=-74.0
    G->>C: Check geo-cache (geohash: dr5ru)

    alt Cache Hit
        C-->>G: Cached restaurant IDs
    else Cache Miss
        G->>S: Geo query (lat, lng, radius)
        S->>S: Geohash lookup + neighbors
        S-->>G: Restaurant IDs in range
        G->>C: Cache results (TTL: 60s)
    end

    G->>R: Rank restaurants for user
    R->>D: Fetch restaurant details (batch)
    R->>R: Apply scoring (distance, rating, ETA)
    R-->>G: Ranked restaurant list
    G-->>E: Paginated feed response

    Note over E,D: Total: < 200ms P99
```

## Business Context

### Problem Statement
- Eaters need to discover restaurants that can deliver to their location
- Restaurant availability changes dynamically (breaks, closures, geo-restrictions)
- Dense urban areas (Manhattan, Mumbai) have thousands of restaurants per square mile
- Feed must be personalized and ranked for relevance

### Goals
1. **Fast Discovery**: Return ranked feed in < 200ms P99
2. **Accurate Delivery**: Only show restaurants that can actually deliver
3. **Smart Ranking**: Personalized ordering based on relevance signals
4. **High Availability**: 99.9% uptime for read operations
5. **Scalable**: Handle traffic spikes during meal times (3-5x baseline)

## Scale Parameters

| Metric | Value |
|--------|-------|
| Total Restaurants | 10,000,000 |
| Read QPS (baseline) | 10,000 |
| Read QPS (peak) | 50,000 |
| P99 Latency Target | < 200ms |
| Avg Restaurants per Query | 50-200 |
| Restaurant Addition Rate | ~1,000/day |
| Geo Coverage | Global (200+ cities) |

## Key Design Decisions

### 1. Spatial Indexing: Geohashing with Adaptive Precision

```
┌─────────────────────────────────────────────────────────────┐
│  Geohash Precision Selection                                 │
├─────────────────────────────────────────────────────────────┤
│  Precision 5: ~4.9km × 4.9km  → Rural areas                 │
│  Precision 6: ~1.2km × 0.6km  → Suburban areas              │
│  Precision 7: ~153m × 153m    → Urban areas (Manhattan)     │
│  Precision 8: ~38m × 19m      → Hyper-dense zones           │
└─────────────────────────────────────────────────────────────┘
```

**Why Geohashing over K-d Trees:**
- O(1) lookup vs O(log n) for K-d trees
- Natural sharding via geohash prefix
- Easy neighbor computation (8 adjacent cells)
- Pre-computable offline

### 2. Hybrid Sharding Strategy

| Data Type | Sharding Key | Strategy |
|-----------|--------------|----------|
| Geo Index | Geohash prefix (2-3 chars) | Location-based |
| Restaurant Details | Restaurant ID | Consistent hashing |
| User Preferences | User ID | Consistent hashing |

### 3. Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│  Cache Layer                     TTL        Hit Rate        │
├─────────────────────────────────────────────────────────────┤
│  L1: CDN (static assets)         24h        95%            │
│  L2: Geo-cell restaurant IDs     60s        80%            │
│  L3: Restaurant details          5min       90%            │
│  L4: User preferences            30min      85%            │
└─────────────────────────────────────────────────────────────┘
```

## Documentation Structure

1. [System Architecture](./system-architecture.md) - Component design, data flow, technology choices
2. [API Contracts](./api-contracts.md) - RESTful endpoints, pagination, error handling
3. [Data Models](./data-models.md) - Restaurant, geolocation, delivery zone schemas
4. [Spatial Indexing](./spatial-indexing.md) - Geohashing mechanics, K-d tree comparison
5. [Ranking System](./ranking-system.md) - Scoring factors, ML integration
6. [Scaling & Sharding](./scaling-sharding.md) - Hotspot handling, capacity planning
7. [Dynamic Filtering](./dynamic-filtering.md) - Real-time availability, geo-restrictions
8. [Architecture Diagrams](./diagrams/architecture-diagrams.md) - Visual representations

## Technology Stack

| Layer | Primary Technology | Purpose |
|-------|-------------------|---------|
| API Gateway | Kong / AWS API Gateway | Rate limiting, auth, routing |
| Geo Search | ElasticSearch | geo_point queries, geohash aggregations |
| Cache | Redis Cluster | Geo-cell cache, restaurant state |
| Primary DB | PostgreSQL | Restaurant data, delivery zones |
| Message Queue | Kafka | State change propagation |
| ML Serving | TensorFlow Serving | Real-time ranking scores |
| CDN | CloudFront | Static assets, API caching |

## Quick Links

- [API Endpoint Reference](./api-contracts.md#api-endpoints)
- [Geohash Deep Dive](./spatial-indexing.md#geohashing)
- [Ranking Formula](./ranking-system.md#scoring-algorithm)
- [Hotspot Mitigation](./scaling-sharding.md#hotspot-handling)

