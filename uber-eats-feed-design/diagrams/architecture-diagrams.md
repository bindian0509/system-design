# Architecture Diagrams

This document contains detailed visual representations of the Uber Eats Feed System architecture.

## 1. High-Level System Architecture

### Mermaid Diagram

```mermaid
flowchart TB
    subgraph Clients ["📱 Client Applications"]
        iOS[iOS App]
        Android[Android App]
        Web[Web App]
    end

    subgraph Edge ["🌐 Edge Layer"]
        CDN[CloudFront CDN]
        WAF[AWS WAF]
        Shield[AWS Shield]
    end

    subgraph Gateway ["🚪 API Gateway"]
        ALB[Application<br/>Load Balancer]
        Kong[Kong Gateway]
        Auth[Auth Service]
        RateLimit[Rate Limiter]
    end

    subgraph Core ["🍽️ Core Services"]
        FeedAPI[Feed API<br/>Service]
        GeoResolver[Geo Resolver<br/>Service]
        RankingSvc[Ranking<br/>Service]
        FilterSvc[Filter<br/>Service]
    end

    subgraph Search ["🔍 Search Infrastructure"]
        ES[(ElasticSearch<br/>Cluster)]
        GeoCache[(Redis<br/>Geo Cache)]
    end

    subgraph ML ["🤖 ML Infrastructure"]
        TFServing[TensorFlow<br/>Serving]
        FeatureStore[(Feature<br/>Store)]
    end

    subgraph Data ["💾 Data Layer"]
        PG[(PostgreSQL<br/>Sharded)]
        StateCache[(Redis<br/>State Cache)]
    end

    subgraph Events ["📨 Event Streaming"]
        Kafka[(Apache Kafka)]
    end

    Clients --> CDN --> WAF --> Shield --> ALB
    ALB --> Kong --> Auth & RateLimit
    Kong --> FeedAPI

    FeedAPI --> GeoResolver
    FeedAPI --> FilterSvc
    GeoResolver --> GeoCache
    GeoCache --> ES

    FeedAPI --> RankingSvc
    RankingSvc --> TFServing
    RankingSvc --> FeatureStore
    RankingSvc --> PG

    FilterSvc --> StateCache

    PG --> Kafka
    Kafka --> ES
    Kafka --> StateCache
```

### ASCII Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                              UBER EATS FEED SYSTEM                               ║
╠══════════════════════════════════════════════════════════════════════════════════╣
║                                                                                  ║
║  ┌──────────────────────────────────────────────────────────────────────────┐    ║
║  │                           CLIENT LAYER                                    │    ║
║  │   ┌─────────┐    ┌─────────┐    ┌─────────┐                              │    ║
║  │   │   iOS   │    │ Android │    │   Web   │                              │    ║
║  │   └────┬────┘    └────┬────┘    └────┬────┘                              │    ║
║  └────────┼──────────────┼──────────────┼───────────────────────────────────┘    ║
║           └──────────────┼──────────────┘                                        ║
║                          ▼                                                       ║
║  ┌──────────────────────────────────────────────────────────────────────────┐    ║
║  │                            EDGE LAYER                                     │    ║
║  │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │    ║
║  │   │ CloudFront   │───▶│    WAF       │───▶│   Shield     │               │    ║
║  │   │ (CDN)        │    │ (Firewall)   │    │ (DDoS)       │               │    ║
║  │   └──────────────┘    └──────────────┘    └──────┬───────┘               │    ║
║  └──────────────────────────────────────────────────┼───────────────────────┘    ║
║                                                     ▼                            ║
║  ┌──────────────────────────────────────────────────────────────────────────┐    ║
║  │                          API GATEWAY LAYER                                │    ║
║  │   ┌─────────────────────────────────────────────────────────────────┐    │    ║
║  │   │                    Kong API Gateway                              │    │    ║
║  │   │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │    │    ║
║  │   │  │  Auth   │  │  Rate   │  │ Circuit │  │ Request │            │    │    ║
║  │   │  │ Plugin  │  │ Limiter │  │ Breaker │  │ Logger  │            │    │    ║
║  │   │  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │    │    ║
║  │   └─────────────────────────────────────────────────────────────────┘    │    ║
║  └──────────────────────────────────────────────────┬───────────────────────┘    ║
║                                                     ▼                            ║
║  ┌──────────────────────────────────────────────────────────────────────────┐    ║
║  │                         CORE SERVICES LAYER                               │    ║
║  │                                                                           │    ║
║  │   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐      │    ║
║  │   │   Feed API      │───▶│  Geo Resolver   │───▶│   Filter        │      │    ║
║  │   │   Service       │    │  Service        │    │   Service       │      │    ║
║  │   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘      │    ║
║  │            │                      │                      │                │    ║
║  │            ▼                      ▼                      ▼                │    ║
║  │   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐      │    ║
║  │   │   Ranking       │    │   Geo Cache     │    │   State Cache   │      │    ║
║  │   │   Service       │    │   (Redis)       │    │   (Redis)       │      │    ║
║  │   └────────┬────────┘    └────────┬────────┘    └─────────────────┘      │    ║
║  └────────────┼──────────────────────┼──────────────────────────────────────┘    ║
║               │                      │                                           ║
║               ▼                      ▼                                           ║
║  ┌────────────────────────┐    ┌────────────────────────────────────────────┐    ║
║  │     ML LAYER           │    │           SEARCH LAYER                     │    ║
║  │  ┌─────────────────┐   │    │   ┌────────────────────────────────────┐   │    ║
║  │  │ TensorFlow      │   │    │   │        ElasticSearch Cluster       │   │    ║
║  │  │ Serving         │   │    │   │   ┌──────┐ ┌──────┐ ┌──────┐      │   │    ║
║  │  └─────────────────┘   │    │   │   │Shard1│ │Shard2│ │Shard3│ ...  │   │    ║
║  │  ┌─────────────────┐   │    │   │   └──────┘ └──────┘ └──────┘      │   │    ║
║  │  │ Feature Store   │   │    │   └────────────────────────────────────┘   │    ║
║  │  └─────────────────┘   │    └────────────────────────────────────────────┘    ║
║  └────────────────────────┘                                                      ║
║               │                                                                  ║
║               ▼                                                                  ║
║  ┌──────────────────────────────────────────────────────────────────────────┐    ║
║  │                           DATA LAYER                                      │    ║
║  │   ┌──────────────────────────────────────────────────────────────────┐   │    ║
║  │   │              PostgreSQL (Sharded by Restaurant ID)                │   │    ║
║  │   │   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐                 │   │    ║
║  │   │   │Shard 0 │  │Shard 1 │  │Shard 2 │  │  ...   │                 │   │    ║
║  │   │   └────────┘  └────────┘  └────────┘  └────────┘                 │   │    ║
║  │   └──────────────────────────────────────────────────────────────────┘   │    ║
║  └──────────────────────────────────────────────────────────────────────────┘    ║
║                                                                                  ║
╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## 2. Request Flow Sequence

### Feed Request Flow

```mermaid
sequenceDiagram
    autonumber

    participant C as Client
    participant G as API Gateway
    participant F as Feed Service
    participant GC as Geo Cache
    participant ES as ElasticSearch
    participant SC as State Cache
    participant R as Ranking Service
    participant ML as ML Service
    participant DB as PostgreSQL

    C->>G: GET /v1/feed/restaurants?lat=40.7&lng=-74.0
    G->>G: Validate JWT, Check Rate Limit
    G->>F: Forward Request

    F->>F: Compute Geohash (dr5ru7)
    F->>GC: GET geo:cell:dr5ru7:5km

    alt Cache Hit
        GC-->>F: Restaurant IDs [r1, r2, r3...]
    else Cache Miss
        F->>ES: geo_distance query
        ES-->>F: Restaurant IDs
        F->>GC: SET geo:cell:dr5ru7:5km (TTL 60s)
    end

    F->>SC: MGET restaurant:state:* (batch)
    SC-->>F: State for each restaurant

    F->>F: Apply Online Filters
    Note over F: Filter: accepting_orders=true<br/>Filter: wait_time<60min

    F->>R: Rank restaurants
    R->>ML: Get personalization scores
    ML-->>R: ML scores
    R->>DB: Batch fetch restaurant details
    DB-->>R: Restaurant data
    R->>R: Compute final scores
    R-->>F: Ranked list

    F->>F: Apply pagination (cursor-based)
    F-->>G: Feed response
    G-->>C: 200 OK + JSON payload
```

---

## 3. Geo Search Architecture

### H3 Hexagonal Search Flow

```mermaid
flowchart TB
    subgraph Input [User Input]
        Loc["Location<br/>lat: 40.7128<br/>lng: -74.0060"]
        Radius["Radius: 5km"]
    end

    subgraph H3Compute [H3 Computation]
        Resolution[Select Resolution<br/>based on density]
        Cell[Compute H3 Cell<br/>8928308280fffff]
        KRing[Compute K-Ring<br/>k=11 for 5km at res 8]
    end

    subgraph Cells [H3 Cells to Query]
        Center["Center Cell"]
        Ring1["K=1 Ring<br/>6 cells"]
        Ring2["K=2 Ring<br/>12 cells"]
        RingN["K=N Rings<br/>~270 cells total"]
    end

    subgraph Cache [Cache Layer]
        Redis[(Redis H3 Cache)]
    end

    subgraph Search [Search Layer]
        ES[(ElasticSearch<br/>H3 terms + geo_distance)]
    end

    subgraph Filter [Post-Processing]
        Merge[Merge Results]
        DistCalc[Exact Distance Filter]
        Output[Final Results]
    end

    Loc --> Resolution --> Cell --> KRing
    Radius --> KRing

    KRing --> Center & Ring1 & Ring2 & RingN

    Center --> Redis
    Ring1 & Ring2 & RingN --> Redis

    Redis -->|Miss| ES
    ES --> Redis
    Redis --> Merge

    Merge --> DistCalc --> Output
```

### H3 Hexagonal Grid Visualization

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      H3 HEXAGONAL GRID (Resolution 8)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                          ╱╲     ╱╲     ╱╲                                   │
│                        ╱    ╲ ╱    ╲ ╱    ╲                                 │
│                       │  k=2 │  k=2 │  k=2 │                                │
│                        ╲    ╱ ╲    ╱ ╲    ╱                                 │
│                    ╱╲   ╲╱     ╲╱     ╲╱   ╱╲                               │
│                  ╱    ╲ ╱╲     ╱╲     ╱╲ ╱    ╲                             │
│                 │  k=2 │  k=1 │  k=1 │  k=1 │  k=2 │                        │
│                  ╲    ╱ ╲    ╱ ╲    ╱ ╲    ╱ ╲    ╱                         │
│                    ╲╱     ╲╱     ╲╱     ╲╱     ╲╱                           │
│                  ╱    ╲ ╱    ╲ ╱    ╲ ╱    ╲ ╱    ╲                         │
│                 │  k=2 │  k=1 │  ●   │  k=1 │  k=2 │  ● = User              │
│                  ╲    ╱ ╲    ╱ ╲ k=0╱ ╲    ╱ ╲    ╱                         │
│                    ╲╱     ╲╱     ╲╱     ╲╱     ╲╱                           │
│                  ╱    ╲ ╱    ╲ ╱    ╲ ╱    ╲ ╱    ╲                         │
│                 │  k=2 │  k=1 │  k=1 │  k=1 │  k=2 │                        │
│                  ╲    ╱ ╲    ╱ ╲    ╱ ╲    ╱ ╲    ╱                         │
│                    ╲╱     ╲╱     ╲╱     ╲╱     ╲╱                           │
│                        ╲    ╱ ╲    ╱ ╲    ╱                                 │
│                         │  k=2 │  k=2 │  k=2 │                              │
│                          ╲    ╱ ╲    ╱ ╲    ╱                               │
│                            ╲╱     ╲╱     ╲╱                                 │
│                                                                              │
│     Key Advantage: All 6 neighbors are EQUIDISTANT from center!             │
│     Each cell: ~461m edge at resolution 8                                   │
│     K-ring(k=11) covers ~5km radius with ~270 cells                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why H3 Over Geohash

```
┌────────────────────────────────┬────────────────────────────────┐
│       GEOHASH (Rectangles)     │         H3 (Hexagons)          │
├────────────────────────────────┼────────────────────────────────┤
│                                │                                │
│   ┌───┬───┬───┐                │       ╱╲     ╱╲     ╱╲        │
│   │   │   │   │     5km        │     ╱    ╲ ╱    ╲ ╱    ╲      │
│   ├───┼───┼───┤    radius      │    │      │      │      │      │
│   │   │ ● │   │      ↓         │     ╲    ╱ ╲  ● ╱ ╲    ╱      │
│   ├───┼───┼───┤   ┌─────┐      │       ╲╱     ╲╱     ╲╱        │
│   │   │   │   │   │ ○   │      │     ╱    ╲ ╱    ╲ ╱    ╲      │
│   └───┴───┴───┘   └─────┘      │    │      │      │      │      │
│                                │     ╲    ╱ ╲    ╱ ╲    ╱      │
│   ✗ Corner distance ≠ edge    │       ╲╱     ╲╱     ╲╱        │
│   ✗ Poor circular fit          │                                │
│   ✗ 8 neighbors (uneven)       │   ✓ All 6 neighbors equal     │
│                                │   ✓ Better circular fit        │
│                                │   ✓ Native k-ring queries      │
│                                │   ✓ Uber's battle-tested tech  │
└────────────────────────────────┴────────────────────────────────┘
```

---

## 4. Sharding Architecture

### PostgreSQL Sharding (Consistent Hashing)

```mermaid
flowchart TB
    subgraph Query [Incoming Query]
        RestID["restaurant_id: rest_abc123"]
    end

    subgraph HashRing [Consistent Hash Ring]
        Hash[Hash Function<br/>MD5]
        Ring[Hash Ring<br/>0 to 2^128]
    end

    subgraph Shards [PostgreSQL Shards]
        S0[(Shard 0<br/>Hash: 0-16B)]
        S1[(Shard 1<br/>Hash: 16B-32B)]
        S2[(Shard 2<br/>Hash: 32B-48B)]
        S3[(Shard 3<br/>Hash: 48B-64B)]
        Sdot[...]
        S15[(Shard 15<br/>Hash: 240B-256B)]
    end

    subgraph Replicas [Read Replicas]
        R0a[Replica 0a]
        R0b[Replica 0b]
        R1a[Replica 1a]
        R1b[Replica 1b]
    end

    RestID --> Hash --> Ring
    Ring -->|Route| S0
    Ring -->|Route| S1
    Ring -->|Route| S2
    Ring -->|Route| S3

    S0 --> R0a & R0b
    S1 --> R1a & R1b
```

### Hash Ring Visualization

```
                         ┌─────────────────────────────────────┐
                         │       CONSISTENT HASH RING          │
                         └─────────────────────────────────────┘

                                        0°
                                        │
                              Shard 0   │   Shard 15
                                   \    │    /
                                    \   │   /
                         45°  ───────\──┼──/─────── 315°
                              Shard 1 \ │ / Shard 14
                                       \│/
                                  ──────●──────
                                       /│\
                              Shard 2 / │ \ Shard 13
                         90°  ───────/──┼──\─────── 270°
                                    /   │   \
                              Shard 3   │   Shard 12
                                        │
                                       180°

                    ┌────────────────────────────────────────────┐
                    │  restaurant_id → MD5 → position on ring   │
                    │  → route to nearest clockwise shard        │
                    └────────────────────────────────────────────┘
```

---

## 5. Multi-Region Architecture

```mermaid
flowchart TB
    subgraph Global [Global Layer]
        DNS[Route 53<br/>Latency-based Routing]
    end

    subgraph USEast [US-EAST Region]
        US_LB[Load Balancer]
        US_API[Feed API Cluster]
        US_ES[(ES Cluster)]
        US_Redis[(Redis Cluster)]
        US_PG[(PostgreSQL<br/>PRIMARY)]
    end

    subgraph EUWest [EU-WEST Region]
        EU_LB[Load Balancer]
        EU_API[Feed API Cluster]
        EU_ES[(ES Cluster)]
        EU_Redis[(Redis Cluster)]
        EU_PG[(PostgreSQL<br/>REPLICA)]
    end

    subgraph APSouth [AP-SOUTH Region]
        AP_LB[Load Balancer]
        AP_API[Feed API Cluster]
        AP_ES[(ES Cluster)]
        AP_Redis[(Redis Cluster)]
        AP_PG[(PostgreSQL<br/>REPLICA)]
    end

    subgraph Sync [Cross-Region Sync]
        Kafka[(Kafka<br/>MirrorMaker)]
    end

    DNS -->|US Users| US_LB
    DNS -->|EU Users| EU_LB
    DNS -->|APAC Users| AP_LB

    US_LB --> US_API --> US_ES & US_Redis & US_PG
    EU_LB --> EU_API --> EU_ES & EU_Redis & EU_PG
    AP_LB --> AP_API --> AP_ES & AP_Redis & AP_PG

    US_PG -.->|Async Replication| EU_PG
    US_PG -.->|Async Replication| AP_PG

    US_ES <-.->|Sync| Kafka
    EU_ES <-.->|Sync| Kafka
    AP_ES <-.->|Sync| Kafka
```

---

## 6. Ranking Pipeline

```mermaid
flowchart LR
    subgraph Input [Input Features]
        UserF[User Features<br/>• Order history<br/>• Preferences<br/>• Location]
        RestF[Restaurant Features<br/>• Rating<br/>• Cuisine<br/>• Distance]
        CtxF[Context Features<br/>• Time of day<br/>• Weather<br/>• Device]
    end

    subgraph FeatureEng [Feature Engineering]
        FE[Feature<br/>Extraction]
        Norm[Normalization]
        Cross[Cross<br/>Features]
    end

    subgraph Scoring [Scoring]
        RuleScore[Rule-Based<br/>Score]
        MLScore[ML Model<br/>Score]
        Blend[Score<br/>Blending]
    end

    subgraph Output [Output]
        Sort[Sort by<br/>Score]
        Diversify[Diversity<br/>Injection]
        Paginate[Pagination]
    end

    UserF & RestF & CtxF --> FE
    FE --> Norm --> Cross

    Cross --> RuleScore
    Cross --> MLScore

    RuleScore --> Blend
    MLScore --> Blend

    Blend --> Sort --> Diversify --> Paginate
```

---

## 7. State Propagation Flow

```mermaid
sequenceDiagram
    participant R as Restaurant App
    participant API as State API
    participant PG as PostgreSQL
    participant K as Kafka
    participant Sync as Sync Service
    participant Redis as Redis Cache
    participant ES as ElasticSearch

    R->>API: PUT /status (going_offline)
    API->>PG: Write state change
    API->>K: Publish event
    API-->>R: 200 OK (async ack)

    Note over K,ES: Async Propagation

    K->>Sync: Consume event

    par Update Redis (Immediate)
        Sync->>Redis: HSET restaurant:state:*
        Redis-->>Sync: OK
    and Update ES (Async)
        Sync->>ES: Update document
        ES-->>Sync: OK
    end

    Note over Redis,ES: Latency: Redis ~100ms, ES ~2s
```

---

## 8. Cache Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CACHE ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         L1: CDN CACHE (CloudFront)                      │ │
│  │  • Static assets (images, JS, CSS)                                      │ │
│  │  • TTL: 24 hours                                                        │ │
│  │  • Hit Rate: 95%                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      L2: GEO CELL CACHE (Redis)                         │ │
│  │  • Key: geo:cell:{geohash}:{radius}                                     │ │
│  │  • Value: Set of restaurant IDs                                         │ │
│  │  • TTL: 60 seconds                                                      │ │
│  │  • Hit Rate: 80%                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                   L3: RESTAURANT DETAILS CACHE (Redis)                  │ │
│  │  • Key: restaurant:details:{id}                                         │ │
│  │  • Value: Restaurant JSON                                               │ │
│  │  • TTL: 5 minutes                                                       │ │
│  │  • Hit Rate: 90%                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    L4: RESTAURANT STATE CACHE (Redis)                   │ │
│  │  • Key: restaurant:state:{id}                                           │ │
│  │  • Value: Hash (is_open, accepting_orders, wait_time, etc.)            │ │
│  │  • TTL: None (event-driven invalidation)                                │ │
│  │  • Hit Rate: 99%                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                     L5: USER PREFERENCES CACHE (Redis)                  │ │
│  │  • Key: user:prefs:{id}                                                 │ │
│  │  • Value: Hash (cuisines, price_range, dietary, history)               │ │
│  │  • TTL: 30 minutes                                                      │ │
│  │  • Hit Rate: 85%                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Monitoring Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FEED SERVICE MONITORING DASHBOARD                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐           │
│  │     REQUEST RATE (QPS)      │  │      LATENCY (P99)          │           │
│  │  ┌─────────────────────┐    │  │  ┌─────────────────────┐    │           │
│  │  │    ▄▄▄▄▄▄▄▄▄▄▄▄    │    │  │  │         ▄▄▄▄▄      │    │           │
│  │  │ ▄▄█            █▄▄ │    │  │  │    ▄▄▄██     ██▄   │    │           │
│  │  │█                  █│    │  │  │▄▄██             █▄▄│    │           │
│  │  └─────────────────────┘    │  │  └─────────────────────┘    │           │
│  │  Current: 35,420 QPS        │  │  Current: 142ms             │           │
│  │  Peak: 48,000 QPS           │  │  Target: <200ms ✓           │           │
│  └─────────────────────────────┘  └─────────────────────────────┘           │
│                                                                              │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐           │
│  │     CACHE HIT RATES         │  │    ERROR RATE               │           │
│  │  ┌─────────────────────┐    │  │  ┌─────────────────────┐    │           │
│  │  │ Geo Cache:    82%   │    │  │  │    ─────────────    │    │           │
│  │  │ Details:      91%   │    │  │  │                     │    │           │
│  │  │ State:        99%   │    │  │  │                     │    │           │
│  │  │ User Prefs:   86%   │    │  │  └─────────────────────┘    │           │
│  │  └─────────────────────┘    │  │  Current: 0.02%             │           │
│  │  Overall: 89%               │  │  Target: <0.1% ✓            │           │
│  └─────────────────────────────┘  └─────────────────────────────┘           │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    REGIONAL TRAFFIC DISTRIBUTION                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  US-EAST: ████████████████████████████████████ 45%               │  │  │
│  │  │  EU-WEST: ████████████████████████ 28%                           │  │  │
│  │  │  AP-SOUTH: ██████████████████████ 27%                            │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      SERVICE HEALTH STATUS                             │  │
│  │  ┌──────────────┬──────────────┬──────────────┬──────────────┐        │  │
│  │  │  Feed API    │  Geo Service │  Ranking     │  Filter      │        │  │
│  │  │  ● HEALTHY   │  ● HEALTHY   │  ● HEALTHY   │  ● HEALTHY   │        │  │
│  │  │  Pods: 42/50 │  Pods: 20/20 │  Pods: 15/15 │  Pods: 10/10 │        │  │
│  │  └──────────────┴──────────────┴──────────────┴──────────────┘        │  │
│  │  ┌──────────────┬──────────────┬──────────────┬──────────────┐        │  │
│  │  │  ElasticS    │  Redis       │  PostgreSQL  │  Kafka       │        │  │
│  │  │  ● HEALTHY   │  ● HEALTHY   │  ● HEALTHY   │  ● HEALTHY   │        │  │
│  │  │  Nodes: 15   │  Nodes: 6    │  Shards: 16  │  Brokers: 9  │        │  │
│  │  └──────────────┴──────────────┴──────────────┴──────────────┘        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Data Flow Summary

```
                    ┌─────────────────────────────────────────────────────┐
                    │                 END-TO-END DATA FLOW                 │
                    └─────────────────────────────────────────────────────┘

┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ CLIENT  │───▶│ GATEWAY │───▶│  FEED   │───▶│  GEO    │───▶│ CACHE   │
│         │    │         │    │ SERVICE │    │ SEARCH  │    │ (Redis) │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
                                   │              │              │
                                   │              │    ┌─────────▼─────────┐
                                   │              └───▶│   ElasticSearch   │
                                   │                   │   (geo_distance)  │
                                   │                   └───────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────┐
                    │         FILTER SERVICE          │
                    │   (Online state filtering)      │
                    └─────────────────┬───────────────┘
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                  ┌─────────────┐           ┌─────────────┐
                  │ State Cache │           │   Ranking   │
                  │   (Redis)   │           │   Service   │
                  └─────────────┘           └──────┬──────┘
                                                   │
                              ┌────────────────────┼────────────────────┐
                              ▼                    ▼                    ▼
                       ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
                       │ PostgreSQL  │      │ ML Service  │      │   Feature   │
                       │ (details)   │      │ (scoring)   │      │   Store     │
                       └─────────────┘      └─────────────┘      └─────────────┘

                    ═══════════════════════════════════════════════════════════
                    Total Latency: < 200ms P99
                    ═══════════════════════════════════════════════════════════
```

