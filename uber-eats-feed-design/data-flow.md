# Data Flow Diagrams

This document provides comprehensive data flow diagrams for the Uber Eats Feed System, showing how data moves between entities, events, and scheduled jobs using **H3 hexagonal indexing** as the geospatial strategy.

---

## 1. System Overview: Complete Data Flow

```mermaid
flowchart TB
    subgraph Clients ["📱 Clients"]
        EaterApp[Eater App]
        RestApp[Restaurant App]
        AdminPortal[Admin Portal]
    end

    subgraph Realtime ["⚡ Real-time Data Flow"]
        API[API Gateway]
        FeedSvc[Feed Service]
        StateSvc[State Service]
    end

    subgraph H3Layer ["🔷 H3 Geo Layer"]
        H3Resolver[H3 Resolver]
        H3Cache[(H3 Cell Cache<br/>Redis)]
    end

    subgraph Search ["🔍 Search"]
        ES[(ElasticSearch<br/>H3 Indexed)]
    end

    subgraph State ["📊 State Management"]
        StateCache[(State Cache<br/>Redis)]
        Ranking[Ranking Service]
    end

    subgraph Persistence ["💾 Persistence"]
        PG[(PostgreSQL)]
    end

    subgraph Events ["📨 Event Streaming"]
        Kafka[(Kafka)]
    end

    subgraph Background ["⏰ Background Jobs"]
        H3Indexer[H3 Index Builder]
        CacheWarmer[Cache Warmer]
        DensityCalc[Density Calculator]
    end

    %% Read Flow
    EaterApp -->|1. Feed Request| API
    API -->|2. Forward| FeedSvc
    FeedSvc -->|3. Resolve H3| H3Resolver
    H3Resolver -->|4. Check Cache| H3Cache
    H3Cache -->|5. Miss| ES
    FeedSvc -->|6. Get State| StateCache
    FeedSvc -->|7. Rank| Ranking
    Ranking -->|8. Fetch Details| PG

    %% Write Flow
    RestApp -->|A. Update Status| API
    API -->|B. Process| StateSvc
    StateSvc -->|C. Write| PG
    StateSvc -->|D. Publish| Kafka

    %% Event Flow
    Kafka -->|E. Consume| H3Indexer
    Kafka -->|F. Consume| StateCache
    H3Indexer -->|G. Update| ES
    H3Indexer -->|H. Invalidate| H3Cache

    %% Background Jobs
    DensityCalc -->|Scheduled| PG
    DensityCalc -->|Update| H3Resolver
    CacheWarmer -->|Scheduled| H3Cache
```

---

## 2. Read Path: Feed Request Flow

### Complete Read Flow with H3

```mermaid
sequenceDiagram
    autonumber

    participant E as 📱 Eater App
    participant G as 🚪 API Gateway
    participant F as 🍽️ Feed Service
    participant H3 as 🔷 H3 Resolver
    participant RC as ⚡ Redis H3 Cache
    participant ES as 🔍 ElasticSearch
    participant SC as 📊 State Cache
    participant R as 📈 Ranking Service
    participant ML as 🤖 ML Service
    participant DB as 💾 PostgreSQL

    E->>G: GET /v1/feed/restaurants<br/>lat=40.7128, lng=-74.0060, radius=5km
    G->>G: Validate JWT, Rate Limit
    G->>F: Forward Request

    rect rgb(230, 245, 255)
        Note over F,ES: H3 Geo Resolution Phase
        F->>H3: Resolve location to H3
        H3->>H3: Select resolution (density-based)<br/>Resolution 8 for urban NYC
        H3->>H3: Compute user cell: 8928308280fffff
        H3->>H3: Compute k-ring (k=11 for 5km)<br/>~270 cells
    end

    rect rgb(255, 245, 230)
        Note over H3,ES: H3 Cell Lookup Phase
        H3->>RC: MGET h3:cell:{cell_id} for all 270 cells

        alt Cache Hit (80% of requests)
            RC-->>H3: Restaurant IDs from cached cells
        else Cache Miss
            H3->>ES: Query with H3 terms filter<br/>+ geo_distance refinement
            ES-->>H3: Restaurant IDs
            H3->>RC: Cache results (TTL: 60s)
        end
    end

    H3-->>F: 500 candidate restaurant IDs

    rect rgb(245, 255, 230)
        Note over F,SC: State Filtering Phase
        F->>SC: MGET restaurant:state:{id} (batch)
        SC-->>F: State for each restaurant
        F->>F: Filter: accepting_orders=true<br/>Filter: wait_time<60min<br/>Filter: no geo_restrictions
    end

    F-->>F: 350 filtered restaurant IDs

    rect rgb(255, 230, 245)
        Note over F,DB: Ranking Phase
        F->>R: Rank restaurants (user_id, restaurant_ids)

        par Parallel Data Fetch
            R->>ML: Get personalization scores
            R->>DB: Batch fetch restaurant details
        end

        ML-->>R: ML scores
        DB-->>R: Restaurant data

        R->>R: Compute final scores<br/>Sort by score
        R-->>F: Top 200 ranked restaurants
    end

    F->>F: Apply pagination (cursor-based)
    F-->>G: Paginated response (20 items)
    G-->>E: 200 OK + JSON

    Note over E,DB: Total Latency: P50=45ms, P99=180ms
```

### Read Flow: Latency Breakdown

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        READ PATH LATENCY BREAKDOWN                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ PHASE                        │ P50      │ P99      │ NOTES           │   │
│  ├──────────────────────────────┼──────────┼──────────┼─────────────────┤   │
│  │ API Gateway                  │ 2ms      │ 5ms      │ Auth + routing  │   │
│  │ H3 Cell Computation          │ 0.1ms    │ 0.5ms    │ CPU-bound       │   │
│  │ K-ring Computation           │ 0.2ms    │ 1ms      │ ~270 cells      │   │
│  │ Redis H3 Cache Lookup        │ 3ms      │ 10ms     │ MGET batch      │   │
│  │ ElasticSearch (on miss)      │ 25ms     │ 80ms     │ H3 terms query  │   │
│  │ State Cache Lookup           │ 2ms      │ 8ms      │ MGET batch      │   │
│  │ Online Filtering             │ 1ms      │ 3ms      │ In-memory       │   │
│  │ Ranking + ML                 │ 15ms     │ 50ms     │ Parallel fetch  │   │
│  │ Pagination                   │ 0.5ms    │ 2ms      │ Cursor encode   │   │
│  ├──────────────────────────────┼──────────┼──────────┼─────────────────┤   │
│  │ TOTAL (Cache Hit)            │ 25ms     │ 80ms     │ 80% of traffic  │   │
│  │ TOTAL (Cache Miss)           │ 50ms     │ 180ms    │ 20% of traffic  │   │
│  └──────────────────────────────┴──────────┴──────────┴─────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Write Path: Restaurant Updates

### Restaurant State Change Flow

```mermaid
sequenceDiagram
    autonumber

    participant R as 🍕 Restaurant App
    participant G as 🚪 API Gateway
    participant S as 📊 State Service
    participant DB as 💾 PostgreSQL
    participant K as 📨 Kafka
    participant Sync as 🔄 Sync Service
    participant RC as ⚡ Redis Cache
    participant ES as 🔍 ElasticSearch
    participant H3C as 🔷 H3 Cell Cache

    R->>G: PUT /v1/restaurants/{id}/status<br/>accepting_orders: false
    G->>S: Forward request

    rect rgb(255, 245, 230)
        Note over S,K: Synchronous Write Phase
        S->>DB: BEGIN TRANSACTION
        S->>DB: UPDATE restaurant_state SET accepting_orders=false
        S->>DB: INSERT INTO state_audit_log
        S->>DB: COMMIT
        S->>K: Publish: restaurant.state.changed<br/>{restaurant_id, old_state, new_state}
    end

    S-->>G: 200 OK (async propagation started)
    G-->>R: 200 OK

    rect rgb(230, 245, 255)
        Note over K,H3C: Async Propagation Phase
        K->>Sync: Consume event

        par Parallel Updates
            Sync->>RC: HSET restaurant:state:{id}<br/>accepting_orders=0
            Note over RC: Immediate (~10ms)
        and
            Sync->>ES: Update document<br/>accepting_orders=false
            Note over ES: Near real-time (~2s)
        and
            Sync->>H3C: Invalidate affected H3 cells
            Note over H3C: Cache invalidation
        end
    end

    Note over R,H3C: State visible to new queries within 2 seconds
```

### Restaurant Creation/Update Flow

```mermaid
sequenceDiagram
    autonumber

    participant A as 👤 Admin Portal
    participant G as 🚪 API Gateway
    participant RS as 🍽️ Restaurant Service
    participant H3 as 🔷 H3 Indexer
    participant DB as 💾 PostgreSQL
    participant K as 📨 Kafka
    participant ES as 🔍 ElasticSearch
    participant RC as ⚡ Redis

    A->>G: POST /v1/restaurants<br/>{name, location, delivery_radius, ...}
    G->>RS: Forward request

    rect rgb(255, 245, 230)
        Note over RS,DB: Restaurant Creation
        RS->>DB: BEGIN TRANSACTION
        RS->>DB: INSERT INTO restaurants
        RS->>DB: INSERT INTO delivery_zones
        RS->>DB: INSERT INTO operating_hours
        RS->>DB: COMMIT
    end

    RS->>K: Publish: restaurant.created<br/>{restaurant_id, location, delivery_radius}
    RS-->>G: 201 Created
    G-->>A: 201 Created + restaurant_id

    rect rgb(230, 255, 245)
        Note over K,RC: H3 Index Building (Async)
        K->>H3: Consume restaurant.created

        H3->>H3: Compute H3 cells at res 6,7,8,9<br/>for restaurant location
        H3->>H3: Compute delivery coverage cells<br/>k-ring based on delivery_radius

        H3->>ES: Index document with H3 fields:<br/>h3_res6, h3_res7, h3_res8, h3_res9,<br/>h3_delivery_cells_res7, h3_delivery_cells_res8

        H3->>RC: Cache restaurant → H3 mapping<br/>SET h3:restaurant:{id} {cells_json}

        H3->>RC: Add restaurant to each delivery cell<br/>SADD h3:cell:{cell_id} {restaurant_id}
    end

    Note over A,RC: Restaurant searchable within 5 seconds
```

---

## 4. Event Flow: Kafka Events

### Event Topics and Consumers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           KAFKA EVENT TOPOLOGY                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PRODUCERS                    TOPICS                    CONSUMERS            │
│  ──────────                   ──────                    ─────────            │
│                                                                              │
│  ┌─────────────┐         ┌─────────────────────┐    ┌──────────────────┐    │
│  │ State       │────────▶│ restaurant.state    │───▶│ State Sync Svc   │    │
│  │ Service     │         │ .changed            │    │ (Redis update)   │    │
│  └─────────────┘         │                     │───▶│ ES Sync Svc      │    │
│                          │ Partitions: 16      │    │ (Index update)   │    │
│                          │ Key: restaurant_id  │───▶│ H3 Cache Svc     │    │
│                          └─────────────────────┘    │ (Invalidation)   │    │
│                                                     └──────────────────┘    │
│                                                                              │
│  ┌─────────────┐         ┌─────────────────────┐    ┌──────────────────┐    │
│  │ Restaurant  │────────▶│ restaurant.created  │───▶│ H3 Indexer       │    │
│  │ Service     │         │ restaurant.updated  │    │ (Build H3 index) │    │
│  └─────────────┘         │ restaurant.deleted  │───▶│ Search Indexer   │    │
│                          │                     │    │ (ES document)    │    │
│                          │ Partitions: 8       │───▶│ Analytics Svc    │    │
│                          │ Key: restaurant_id  │    │ (Data warehouse) │    │
│                          └─────────────────────┘    └──────────────────┘    │
│                                                                              │
│  ┌─────────────┐         ┌─────────────────────┐    ┌──────────────────┐    │
│  │ Delivery    │────────▶│ delivery.zone       │───▶│ H3 Coverage      │    │
│  │ Zone Svc    │         │ .changed            │    │ Recalculator     │    │
│  └─────────────┘         │                     │───▶│ Cache Invalidator│    │
│                          │ Partitions: 4       │    │                  │    │
│                          │ Key: restaurant_id  │    └──────────────────┘    │
│                          └─────────────────────┘                            │
│                                                                              │
│  ┌─────────────┐         ┌─────────────────────┐    ┌──────────────────┐    │
│  │ Geo         │────────▶│ geo.restriction     │───▶│ State Cache Svc  │    │
│  │ Restriction │         │ .added/.removed     │    │                  │    │
│  │ Service     │         │                     │───▶│ Feed Filter Svc  │    │
│  └─────────────┘         │ Partitions: 4       │    │                  │    │
│                          │ Key: restaurant_id  │    └──────────────────┘    │
│                          └─────────────────────┘                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Event Schema Examples

```json
// restaurant.state.changed
{
  "event_id": "evt_20260108_001",
  "event_type": "restaurant.state.changed",
  "timestamp": "2026-01-08T14:30:00Z",
  "restaurant_id": "rest_abc123",
  "payload": {
    "field": "accepting_orders",
    "old_value": true,
    "new_value": false,
    "reason": "kitchen_closed",
    "estimated_reopen_at": "2026-01-08T18:00:00Z"
  },
  "metadata": {
    "source": "restaurant_app",
    "actor_id": "rest_admin_123",
    "correlation_id": "corr_abc123"
  }
}

// restaurant.created
{
  "event_id": "evt_20260108_002",
  "event_type": "restaurant.created",
  "timestamp": "2026-01-08T14:30:00Z",
  "restaurant_id": "rest_xyz789",
  "payload": {
    "name": "Mario's Pizza",
    "location": {
      "lat": 40.7128,
      "lng": -74.0060
    },
    "delivery_radius_km": 5.0,
    "cuisine_types": ["pizza", "italian"],
    "h3_cells": {
      "res6": "862a1070fffffff",
      "res7": "872a10706ffffff",
      "res8": "882a10706dfffff",
      "res9": "892a10706d3ffff"
    }
  }
}

// delivery.zone.changed
{
  "event_id": "evt_20260108_003",
  "event_type": "delivery.zone.changed",
  "timestamp": "2026-01-08T14:30:00Z",
  "restaurant_id": "rest_abc123",
  "payload": {
    "old_radius_km": 5.0,
    "new_radius_km": 7.0,
    "old_h3_coverage_count": 270,
    "new_h3_coverage_count": 520,
    "added_cells": ["882a10706e1ffff", "882a10706e3ffff", ...],
    "removed_cells": []
  }
}
```

### Event Processing Flow

```mermaid
flowchart TB
    subgraph Producers [Event Producers]
        RestSvc[Restaurant Service]
        StateSvc[State Service]
        GeoSvc[Geo Restriction Service]
    end

    subgraph Kafka [Kafka Cluster]
        Topic1[(restaurant.state.changed)]
        Topic2[(restaurant.created/updated)]
        Topic3[(delivery.zone.changed)]
        Topic4[(geo.restriction.changed)]
    end

    subgraph Consumers [Event Consumers]
        subgraph StateSyncGroup [State Sync Consumer Group]
            SS1[State Sync 1]
            SS2[State Sync 2]
        end

        subgraph H3IndexGroup [H3 Index Consumer Group]
            H3I1[H3 Indexer 1]
            H3I2[H3 Indexer 2]
        end

        subgraph CacheGroup [Cache Consumer Group]
            CI1[Cache Invalidator 1]
            CI2[Cache Invalidator 2]
        end
    end

    subgraph Targets [Update Targets]
        Redis[(Redis)]
        ES[(ElasticSearch)]
        H3Cache[(H3 Cell Cache)]
    end

    RestSvc --> Topic2
    StateSvc --> Topic1
    GeoSvc --> Topic4
    RestSvc --> Topic3

    Topic1 --> StateSyncGroup
    Topic2 --> H3IndexGroup
    Topic3 --> H3IndexGroup
    Topic4 --> CacheGroup

    SS1 & SS2 --> Redis
    H3I1 & H3I2 --> ES
    CI1 & CI2 --> H3Cache
```

---

## 5. Scheduled Jobs

### Job Schedule Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SCHEDULED JOBS                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  JOB NAME                 │ SCHEDULE        │ PURPOSE                       │
│  ─────────────────────────┼─────────────────┼────────────────────────────── │
│  H3 Density Calculator    │ Daily @ 3:00 AM │ Compute restaurant density    │
│                           │                 │ per H3 cell for resolution    │
│                           │                 │ selection                     │
│  ─────────────────────────┼─────────────────┼────────────────────────────── │
│  H3 Cache Warmer          │ Every 15 min    │ Pre-populate cache for        │
│                           │                 │ high-traffic H3 cells         │
│  ─────────────────────────┼─────────────────┼────────────────────────────── │
│  Operating Hours Sync     │ Every 5 min     │ Update is_open status based   │
│                           │                 │ on restaurant schedules       │
│  ─────────────────────────┼─────────────────┼────────────────────────────── │
│  ES Index Optimizer       │ Daily @ 4:00 AM │ Force merge, optimize         │
│                           │                 │ ElasticSearch segments        │
│  ─────────────────────────┼─────────────────┼────────────────────────────── │
│  Stale State Cleanup      │ Hourly          │ Remove expired geo-           │
│                           │                 │ restrictions, reset stuck     │
│                           │                 │ states                        │
│  ─────────────────────────┼─────────────────┼────────────────────────────── │
│  H3 Coverage Recompute    │ Daily @ 2:00 AM │ Recompute H3 delivery         │
│                           │                 │ coverage for all restaurants  │
│  ─────────────────────────┼─────────────────┼────────────────────────────── │
│  Analytics Aggregation    │ Hourly          │ Aggregate feed metrics        │
│                           │                 │ per H3 cell                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### H3 Density Calculator Job

```mermaid
sequenceDiagram
    autonumber

    participant Cron as ⏰ Cron Scheduler
    participant Job as 🔄 Density Calculator Job
    participant DB as 💾 PostgreSQL
    participant H3 as 🔷 H3 Library
    participant Redis as ⚡ Redis
    participant ES as 🔍 ElasticSearch

    Cron->>Job: Trigger (Daily @ 3:00 AM)

    rect rgb(230, 245, 255)
        Note over Job,DB: Phase 1: Collect Restaurant Locations
        Job->>DB: SELECT id, lat, lng FROM restaurants<br/>WHERE is_active = true
        DB-->>Job: 10M restaurant locations
    end

    rect rgb(255, 245, 230)
        Note over Job,H3: Phase 2: Compute H3 Cells & Density
        loop For each restaurant
            Job->>H3: geo_to_h3(lat, lng, resolution=4)
            H3-->>Job: H3 cell at res 4 (~22km)
        end
        Job->>Job: Aggregate: Count restaurants per H3 cell
        Job->>Job: Classify cells:<br/>hyper_dense (>500/km²) → res 9<br/>urban (>100/km²) → res 8<br/>suburban (>20/km²) → res 7<br/>rural → res 6
    end

    rect rgb(245, 255, 230)
        Note over Job,Redis: Phase 3: Store Density Map
        Job->>Redis: HSET density:map {h3_cell: density}
        Job->>Redis: HSET resolution:map {h3_cell: recommended_resolution}
    end

    rect rgb(255, 230, 245)
        Note over Job,ES: Phase 4: Update ES Routing
        Job->>ES: Update index settings with<br/>new density-based routing hints
    end

    Job-->>Cron: Job complete
```

### Cache Warmer Job

```mermaid
sequenceDiagram
    autonumber

    participant Cron as ⏰ Cron Scheduler
    participant Job as 🔥 Cache Warmer Job
    participant Analytics as 📊 Analytics DB
    participant H3 as 🔷 H3 Resolver
    participant ES as 🔍 ElasticSearch
    participant Redis as ⚡ Redis

    Cron->>Job: Trigger (Every 15 min)

    rect rgb(230, 245, 255)
        Note over Job,Analytics: Identify Hot Cells
        Job->>Analytics: SELECT h3_cell, query_count<br/>FROM feed_queries_last_hour<br/>ORDER BY query_count DESC<br/>LIMIT 1000
        Analytics-->>Job: Top 1000 H3 cells by traffic
    end

    rect rgb(255, 245, 230)
        Note over Job,Redis: Warm Cache for Hot Cells
        loop For each hot H3 cell
            Job->>Redis: EXISTS h3:cell:{cell_id}

            alt Cache Miss
                Job->>H3: Get k-ring cells
                Job->>ES: Query restaurants in cells
                ES-->>Job: Restaurant IDs
                Job->>Redis: SADD h3:cell:{cell_id} {restaurant_ids}
                Job->>Redis: EXPIRE h3:cell:{cell_id} 300
            end
        end
    end

    Job-->>Cron: Warmed 850 cells (150 already cached)
```

### Operating Hours Sync Job

```mermaid
sequenceDiagram
    autonumber

    participant Cron as ⏰ Cron Scheduler
    participant Job as 🕐 Hours Sync Job
    participant DB as 💾 PostgreSQL
    participant Redis as ⚡ Redis
    participant Kafka as 📨 Kafka

    Cron->>Job: Trigger (Every 5 min)

    Job->>Job: current_time = NOW()<br/>current_day = WEDNESDAY

    rect rgb(230, 245, 255)
        Note over Job,DB: Find Restaurants Changing Status
        Job->>DB: SELECT r.id, rs.is_open, oh.periods<br/>FROM restaurants r<br/>JOIN restaurant_state rs<br/>JOIN operating_hours oh<br/>WHERE oh.day_of_week = current_day
        DB-->>Job: Restaurants with schedules

        Job->>Job: For each restaurant:<br/>- Check if current_time in any period<br/>- Compare with current is_open state<br/>- Identify status changes needed
    end

    rect rgb(255, 245, 230)
        Note over Job,Kafka: Update Changed Restaurants
        loop For each status change
            Job->>DB: UPDATE restaurant_state<br/>SET is_open = new_status
            Job->>Redis: HSET restaurant:state:{id} is_open {0|1}
            Job->>Kafka: Publish restaurant.state.changed
        end
    end

    Job-->>Cron: Updated 1,234 restaurants
```

---

## 6. H3 Index Management Flow

### H3 Index Build Pipeline

```mermaid
flowchart TB
    subgraph Input [Data Sources]
        RestaurantDB[(PostgreSQL<br/>Restaurants)]
        DeliveryZones[(PostgreSQL<br/>Delivery Zones)]
    end

    subgraph H3Compute [H3 Computation]
        LocationH3[Compute Location H3<br/>res 6,7,8,9]
        CoverageH3[Compute Delivery Coverage<br/>k-ring at appropriate res]
    end

    subgraph Index [Index Building]
        ESDoc[Build ES Document]
        ESBulk[Bulk Index to ES]
    end

    subgraph Cache [Cache Population]
        CellCache[Populate H3 Cell Cache]
        CoverageCache[Populate Coverage Cache]
    end

    RestaurantDB --> LocationH3
    DeliveryZones --> CoverageH3

    LocationH3 --> ESDoc
    CoverageH3 --> ESDoc

    ESDoc --> ESBulk

    ESBulk --> CellCache
    ESBulk --> CoverageCache
```

### H3 Cell Cache Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        H3 CACHE DATA STRUCTURES                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. H3 CELL → RESTAURANT IDs                                                │
│  ────────────────────────────────────────────────────────────────────────── │
│  Key:     h3:cell:{h3_index}                                                │
│  Type:    SET                                                               │
│  Value:   {restaurant_id_1, restaurant_id_2, ...}                           │
│  TTL:     60 seconds                                                        │
│                                                                              │
│  Example:                                                                   │
│  h3:cell:8928308280fffff → {"rest_001", "rest_002", "rest_003"}            │
│                                                                              │
│  2. RESTAURANT → H3 CELLS (Location)                                       │
│  ────────────────────────────────────────────────────────────────────────── │
│  Key:     h3:location:{restaurant_id}                                       │
│  Type:    HASH                                                              │
│  Value:   {res6: cell, res7: cell, res8: cell, res9: cell}                 │
│  TTL:     None (invalidated on update)                                      │
│                                                                              │
│  Example:                                                                   │
│  h3:location:rest_001 → {                                                   │
│    "res6": "862a1070fffffff",                                               │
│    "res7": "872a10706ffffff",                                               │
│    "res8": "882a10706dfffff",                                               │
│    "res9": "892a10706d3ffff"                                                │
│  }                                                                          │
│                                                                              │
│  3. RESTAURANT → DELIVERY COVERAGE H3 CELLS                                │
│  ────────────────────────────────────────────────────────────────────────── │
│  Key:     h3:coverage:{restaurant_id}:{resolution}                          │
│  Type:    SET                                                               │
│  Value:   {h3_cell_1, h3_cell_2, ...} (all cells restaurant delivers to)   │
│  TTL:     5 minutes                                                         │
│                                                                              │
│  Example:                                                                   │
│  h3:coverage:rest_001:8 → {"8928308280fffff", "8928308281fffff", ...}      │
│  (Contains ~270 cells for 5km delivery radius at resolution 8)              │
│                                                                              │
│  4. DENSITY MAP                                                             │
│  ────────────────────────────────────────────────────────────────────────── │
│  Key:     h3:density:map                                                    │
│  Type:    HASH                                                              │
│  Value:   {h3_cell_res4: restaurants_per_km2}                               │
│  TTL:     None (updated daily by job)                                       │
│                                                                              │
│  Example:                                                                   │
│  h3:density:map → {                                                         │
│    "842a100ffffffff": "523",  // Manhattan - hyper dense                   │
│    "842a107ffffffff": "89",   // Brooklyn - urban                          │
│    "842a10fffffffff": "12"    // Suburbs - low density                     │
│  }                                                                          │
│                                                                              │
│  5. RESOLUTION MAP                                                          │
│  ────────────────────────────────────────────────────────────────────────── │
│  Key:     h3:resolution:map                                                 │
│  Type:    HASH                                                              │
│  Value:   {h3_cell_res4: recommended_resolution}                            │
│  TTL:     None (updated daily by job)                                       │
│                                                                              │
│  Example:                                                                   │
│  h3:resolution:map → {                                                      │
│    "842a100ffffffff": "9",    // Manhattan - use res 9                     │
│    "842a107ffffffff": "8",    // Brooklyn - use res 8                      │
│    "842a10fffffffff": "7"     // Suburbs - use res 7                       │
│  }                                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Cache Invalidation Flow

### Invalidation Triggers and Propagation

```mermaid
flowchart TB
    subgraph Triggers [Invalidation Triggers]
        T1[Restaurant goes offline]
        T2[Delivery radius changed]
        T3[Restaurant location moved]
        T4[Geo-restriction added]
        T5[Restaurant deleted]
    end

    subgraph Kafka [Event Bus]
        Event[(Kafka Event)]
    end

    subgraph Invalidator [Cache Invalidator Service]
        Handler[Event Handler]
        H3Compute[Compute Affected H3 Cells]
        Strategy[Select Invalidation Strategy]
    end

    subgraph Actions [Invalidation Actions]
        A1[Delete specific cell keys]
        A2[Delete restaurant from all cells]
        A3[Recompute coverage + update cells]
        A4[Flush regional cache]
    end

    subgraph Cache [Redis Cache]
        H3Cache[(H3 Cell Cache)]
        CoverageCache[(Coverage Cache)]
        StateCache[(State Cache)]
    end

    T1 & T2 & T3 & T4 & T5 --> Event
    Event --> Handler
    Handler --> H3Compute --> Strategy

    Strategy -->|Minor change| A1
    Strategy -->|Status change| A2
    Strategy -->|Zone change| A3
    Strategy -->|Mass event| A4

    A1 & A2 & A3 & A4 --> H3Cache
    A2 & A3 --> CoverageCache
    A1 & A2 --> StateCache
```

### Invalidation Strategy Matrix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CACHE INVALIDATION STRATEGIES                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TRIGGER                   │ STRATEGY              │ AFFECTED KEYS          │
│  ──────────────────────────┼───────────────────────┼─────────────────────── │
│  Restaurant goes offline   │ State update only     │ restaurant:state:{id}  │
│                            │ No cell invalidation  │                        │
│                            │ (filtered at query)   │                        │
│  ──────────────────────────┼───────────────────────┼─────────────────────── │
│  Delivery radius increased │ Compute new cells     │ h3:coverage:{id}:*     │
│                            │ Add to new cells      │ h3:cell:{new_cells}    │
│                            │ Keep old cells        │                        │
│  ──────────────────────────┼───────────────────────┼─────────────────────── │
│  Delivery radius decreased │ Compute removed cells │ h3:coverage:{id}:*     │
│                            │ SREM from old cells   │ h3:cell:{old_cells}    │
│  ──────────────────────────┼───────────────────────┼─────────────────────── │
│  Restaurant location moved │ Full recompute        │ h3:location:{id}       │
│                            │ Remove from old cells │ h3:coverage:{id}:*     │
│                            │ Add to new cells      │ h3:cell:{all_cells}    │
│  ──────────────────────────┼───────────────────────┼─────────────────────── │
│  Restaurant deleted        │ Full removal          │ h3:location:{id}       │
│                            │                       │ h3:coverage:{id}:*     │
│                            │                       │ h3:cell:{all_cells}    │
│                            │                       │ restaurant:state:{id}  │
│  ──────────────────────────┼───────────────────────┼─────────────────────── │
│  Mass outage (>100 rest)   │ Regional flush        │ h3:cell:* (pattern)    │
│                            │                       │ (by H3 prefix)         │
│  ──────────────────────────┼───────────────────────┼─────────────────────── │
│  Index rebuild             │ Full cache flush      │ FLUSHDB                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Complete System Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    UBER EATS FEED - COMPLETE DATA FLOW                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                           READ PATH                                      ││
│  │                                                                          ││
│  │  📱 Eater App                                                            ││
│  │      │                                                                   ││
│  │      ▼                                                                   ││
│  │  🚪 API Gateway ──▶ 🍽️ Feed Service                                      ││
│  │                          │                                               ││
│  │                          ├──▶ 🔷 H3 Resolver ──▶ ⚡ Redis H3 Cache       ││
│  │                          │         │                    │                ││
│  │                          │         │              (miss)▼                ││
│  │                          │         └──────────▶ 🔍 ElasticSearch         ││
│  │                          │                                               ││
│  │                          ├──▶ 📊 State Cache (Redis)                     ││
│  │                          │                                               ││
│  │                          └──▶ 📈 Ranking Service ──▶ 💾 PostgreSQL       ││
│  │                                      │                                   ││
│  │                                      └──▶ 🤖 ML Service                  ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                          WRITE PATH                                      ││
│  │                                                                          ││
│  │  🍕 Restaurant App / 👤 Admin Portal                                     ││
│  │      │                                                                   ││
│  │      ▼                                                                   ││
│  │  🚪 API Gateway ──▶ 📊 State Service / 🍽️ Restaurant Service            ││
│  │                          │                                               ││
│  │                          ├──▶ 💾 PostgreSQL (source of truth)            ││
│  │                          │                                               ││
│  │                          └──▶ 📨 Kafka (events)                          ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                          EVENT PATH                                      ││
│  │                                                                          ││
│  │  📨 Kafka                                                                ││
│  │      │                                                                   ││
│  │      ├──▶ 🔄 State Sync ──▶ ⚡ Redis State Cache                         ││
│  │      │                                                                   ││
│  │      ├──▶ 🔷 H3 Indexer ──▶ 🔍 ElasticSearch                            ││
│  │      │         │                                                         ││
│  │      │         └──▶ ⚡ Redis H3 Cache (invalidation)                     ││
│  │      │                                                                   ││
│  │      └──▶ 📊 Analytics ──▶ 📈 Data Warehouse                            ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        SCHEDULED JOBS                                    ││
│  │                                                                          ││
│  │  ⏰ Cron                                                                 ││
│  │      │                                                                   ││
│  │      ├──▶ 🔷 H3 Density Calculator (daily) ──▶ ⚡ Redis density map     ││
│  │      │                                                                   ││
│  │      ├──▶ 🔥 Cache Warmer (15 min) ──▶ ⚡ Redis H3 Cache                 ││
│  │      │                                                                   ││
│  │      ├──▶ 🕐 Operating Hours Sync (5 min) ──▶ ⚡ Redis + 📨 Kafka       ││
│  │      │                                                                   ││
│  │      └──▶ 🧹 Stale State Cleanup (hourly) ──▶ ⚡ Redis + 💾 PostgreSQL  ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  LEGEND:                                                                    │
│  ──────                                                                     │
│  📱 Client Apps     🚪 API Gateway    🍽️ Feed Service    🔷 H3 Components   │
│  ⚡ Redis           🔍 ElasticSearch  💾 PostgreSQL      📨 Kafka           │
│  📊 State/Analytics 📈 Ranking/ML     ⏰ Scheduled Jobs  🔄 Sync Services   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

