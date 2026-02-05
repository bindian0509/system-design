# Data Flow

This document describes the request/response flows for key operations in the flight search system.

## 1. Flight Search Flow

### Overview

The search flow is optimized for low latency through parallel fan-out, progressive results, and intelligent caching.

### Sequence Diagram

```
┌──────┐     ┌───────┐     ┌────────┐     ┌────────┐     ┌─────────┐     ┌──────────┐
│Client│     │Gateway│     │ Search │     │ Redis  │     │Supplier │     │ Pricing  │
│      │     │       │     │Service │     │ Cache  │     │ Gateway │     │ Engine   │
└──┬───┘     └───┬───┘     └───┬────┘     └───┬────┘     └────┬────┘     └────┬─────┘
   │             │             │              │               │               │
   │ Search Req  │             │              │               │               │
   │────────────>│             │              │               │               │
   │             │ Validate &  │              │               │               │
   │             │ Rate Check  │              │               │               │
   │             │────────────>│              │               │               │
   │             │             │              │               │               │
   │             │             │ Check Cache  │               │               │
   │             │             │─────────────>│               │               │
   │             │             │              │               │               │
   │             │             │ Cache Miss   │               │               │
   │             │             │<─────────────│               │               │
   │             │             │              │               │               │
   │             │             │        Fan out to suppliers (parallel)       │
   │             │             │─────────────────────────────>│               │
   │             │             │                              │               │
   │             │             │          Supplier 1 results  │               │
   │             │             │<─────────────────────────────│               │
   │             │             │                              │               │
   │ SSE: First  │             │                              │               │
   │ batch (500ms)             │                              │               │
   │<────────────│<────────────│                              │               │
   │             │             │                              │               │
   │             │             │         More results arrive  │               │
   │             │             │<─────────────────────────────│               │
   │             │             │                              │               │
   │             │             │              Apply pricing   │               │
   │             │             │─────────────────────────────────────────────>│
   │             │             │              Priced results  │               │
   │             │             │<─────────────────────────────────────────────│
   │             │             │                              │               │
   │ SSE: More   │             │                              │               │
   │ results     │             │                              │               │
   │<────────────│<────────────│                              │               │
   │             │             │              │               │               │
   │             │             │ Cache results│               │               │
   │             │             │─────────────>│               │               │
   │             │             │              │               │               │
   │ SSE: Done   │             │              │               │               │
   │<────────────│<────────────│              │               │               │
   │             │             │              │               │               │
```

### Detailed Steps

1. **Request Reception** (0-10ms)
   - Client sends search request to API Gateway
   - Gateway validates JWT token
   - Rate limit check (token bucket)
   - Request forwarded to Search Service

2. **Cache Check** (10-20ms)
   - Generate cache key: `search:{hash(origin, dest, date, filters)}`
   - Check Redis for existing results
   - If cache hit with valid TTL → return immediately

3. **Supplier Fan-Out** (20ms - 2500ms)
   - Identify applicable suppliers for route
   - Create parallel requests to Supplier Gateway
   - Each supplier has independent timeout (2s default)
   - First batch returned at 500ms milestone

4. **Response Aggregation** (ongoing)
   - Normalize supplier responses to unified schema
   - Deduplicate identical flights (same flight number, times)
   - Apply dynamic pricing via Pricing Engine
   - Stream batches to client via SSE

5. **Cache Population** (background)
   - Store aggregated results in Redis
   - TTL based on departure date proximity:
     - < 3 days: 2 min TTL
     - 3-7 days: 5 min TTL
     - 7-30 days: 15 min TTL
     - > 30 days: 30 min TTL

6. **Analytics** (async)
   - Publish search event to Kafka
   - Used for ML model training
   - Business analytics

### Cache Hit Flow

```
┌──────┐     ┌───────┐     ┌────────┐     ┌────────┐
│Client│     │Gateway│     │ Search │     │ Redis  │
│      │     │       │     │Service │     │ Cache  │
└──┬───┘     └───┬───┘     └───┬────┘     └───┬────┘
   │             │             │              │
   │ Search Req  │             │              │
   │────────────>│             │              │
   │             │────────────>│              │
   │             │             │ Check Cache  │
   │             │             │─────────────>│
   │             │             │              │
   │             │             │ Cache HIT    │
   │             │             │<─────────────│
   │             │             │              │
   │ Cached      │             │              │
   │ Results     │             │              │
   │<────────────│<────────────│              │
   │   (50-100ms total)        │              │
```

---

## 2. Booking Flow

### Overview

The booking flow uses a saga pattern to coordinate the distributed transaction across payment, supplier, and booking systems.

### Sequence Diagram

```
┌──────┐  ┌───────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌──────┐
│Client│  │Gateway│  │Booking │  │Supplier│  │Payment │  │Postgres│  │Kafka │
│      │  │       │  │Service │  │Gateway │  │Gateway │  │        │  │      │
└──┬───┘  └───┬───┘  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘  └──┬───┘
   │          │          │           │           │           │          │
   │ Verify   │          │           │           │           │          │
   │ Request  │          │           │           │           │          │
   │─────────>│─────────>│           │           │           │          │
   │          │          │           │           │           │          │
   │          │          │ Real-time │           │           │          │
   │          │          │ price check           │           │          │
   │          │          │──────────>│           │           │          │
   │          │          │           │           │           │          │
   │          │          │ Verified  │           │           │          │
   │          │          │ price     │           │           │          │
   │          │          │<──────────│           │           │          │
   │          │          │           │           │           │          │
   │ Verified │          │           │           │           │          │
   │ quote    │          │           │           │           │          │
   │<─────────│<─────────│           │           │           │          │
   │          │          │           │           │           │          │
   │ Book     │          │           │           │           │          │
   │ Request  │          │           │           │           │          │
   │─────────>│─────────>│           │           │           │          │
   │          │          │           │           │           │          │
   │          │          │ Create pending booking            │          │
   │          │          │──────────────────────────────────>│          │
   │          │          │           │           │           │          │
   │          │          │ Process payment       │           │          │
   │          │          │──────────────────────>│           │          │
   │          │          │           │           │           │          │
   │          │          │ Payment success       │           │          │
   │          │          │<──────────────────────│           │          │
   │          │          │           │           │           │          │
   │          │          │ Confirm   │           │           │          │
   │          │          │ with supplier         │           │          │
   │          │          │──────────>│           │           │          │
   │          │          │           │           │           │          │
   │          │          │ PNR       │           │           │          │
   │          │          │<──────────│           │           │          │
   │          │          │           │           │           │          │
   │          │          │ Update booking status             │          │
   │          │          │──────────────────────────────────>│          │
   │          │          │           │           │           │          │
   │          │          │ Publish event         │           │          │
   │          │          │─────────────────────────────────────────────>│
   │          │          │           │           │           │          │
   │Confirmed │          │           │           │           │          │
   │<─────────│<─────────│           │           │           │          │
```

### Saga Compensation

If any step fails, compensation actions are triggered:

| Step | Compensation Action |
|------|---------------------|
| Payment charged, supplier fails | Refund payment |
| Booking created, supplier fails | Mark booking as failed, notify user |
| Partial failure | Rollback to last consistent state |

---

## 3. Price Alert Flow

### Creating an Alert

```
┌──────┐     ┌───────┐     ┌────────┐     ┌────────┐
│Client│     │Gateway│     │ Alerts │     │Postgres│
│      │     │       │     │Service │     │        │
└──┬───┘     └───┬───┘     └───┬────┘     └───┬────┘
   │             │             │              │
   │Create Alert │             │              │
   │────────────>│────────────>│              │
   │             │             │              │
   │             │             │ Validate     │
   │             │             │ (route exists, price reasonable)
   │             │             │              │
   │             │             │ Store alert  │
   │             │             │─────────────>│
   │             │             │              │
   │Alert Created│             │              │
   │<────────────│<────────────│              │
```

### Alert Processing (Background)

```
┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐
│ Kafka  │     │ Alerts │     │Postgres│     │ Search │     │ Notif. │
│        │     │Worker  │     │        │     │Service │     │Service │
└───┬────┘     └───┬────┘     └───┬────┘     └───┬────┘     └───┬────┘
    │              │              │              │              │
    │price-updates │              │              │              │
    │─────────────>│              │              │              │
    │              │              │              │              │
    │              │ Find matching│              │              │
    │              │ alerts       │              │              │
    │              │─────────────>│              │              │
    │              │              │              │              │
    │              │ Alert list   │              │              │
    │              │<─────────────│              │              │
    │              │              │              │              │
    │              │ Get current prices          │              │
    │              │─────────────────────────────>│              │
    │              │              │              │              │
    │              │ Current prices              │              │
    │              │<─────────────────────────────│              │
    │              │              │              │              │
    │              │ For each alert: price <= target            │
    │              │              │              │              │
    │              │ Trigger notification        │              │
    │              │─────────────────────────────────────────────>│
    │              │              │              │              │
    │              │ Update alert │              │              │
    │              │ status       │              │              │
    │              │─────────────>│              │              │
```

---

## 4. Supplier Integration Flow

### Request Normalization

```
┌────────────┐     ┌──────────────────────────────────────────────┐
│  Search    │     │              Supplier Gateway                 │
│  Service   │     │  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│            │────>│  │ Request  │─>│ Adapter  │─>│ External │   │
│            │     │  │ Router   │  │ (e.g.    │  │   API    │   │
│            │     │  │          │  │ Amadeus) │  │          │   │
│            │<────│  │          │<─│          │<─│          │   │
│            │     │  └──────────┘  └──────────┘  └──────────┘   │
└────────────┘     │                      │                       │
                   │              ┌───────┴───────┐               │
                   │              │  Normalizer   │               │
                   │              │  (to unified  │               │
                   │              │   schema)     │               │
                   │              └───────────────┘               │
                   └──────────────────────────────────────────────┘
```

### Unified Flight Schema

All supplier responses are normalized to:

```json
{
  "flight_id": "UA123-20240615-JFKLAX",
  "supplier_code": "amadeus",
  "segments": [
    {
      "flight_number": "UA123",
      "carrier": "UA",
      "origin": "JFK",
      "destination": "LAX",
      "departure_time": "2024-06-15T08:00:00Z",
      "arrival_time": "2024-06-15T11:30:00Z",
      "duration_minutes": 330,
      "aircraft": "Boeing 737-800",
      "cabin_class": "economy"
    }
  ],
  "pricing": {
    "base_price_cents": 29900,
    "taxes_cents": 4500,
    "total_cents": 34400,
    "currency": "USD"
  },
  "availability": {
    "seats_remaining": 7,
    "fare_class": "Y"
  },
  "baggage": {
    "carry_on": true,
    "checked_bags": 0
  }
}
```

---

## 5. Real-Time Price Verification Flow

Before booking, prices must be verified in real-time to ensure accuracy.

```
┌──────┐     ┌────────┐     ┌────────┐     ┌────────┐
│Client│     │Booking │     │Supplier│     │External│
│      │     │Service │     │Gateway │     │  API   │
└──┬───┘     └───┬────┘     └───┬────┘     └───┬────┘
   │             │              │              │
   │Verify Price │              │              │
   │────────────>│              │              │
   │             │              │              │
   │             │ Get latest   │              │
   │             │ price        │              │
   │             │─────────────>│──────────────>│
   │             │              │              │
   │             │              │<──────────────│
   │             │<─────────────│              │
   │             │              │              │
   │             │ Compare with │              │
   │             │ cached price │              │
   │             │              │              │
   │ Verified    │              │              │
   │ (or updated │              │              │
   │  price)     │              │              │
   │<────────────│              │              │
```

### Price Discrepancy Handling

| Scenario | Action |
|----------|--------|
| Price unchanged | Proceed with booking |
| Price decreased | Update quote, proceed |
| Price increased < 5% | Warn user, allow proceed |
| Price increased >= 5% | Require re-confirmation |
| Flight unavailable | Return error, suggest alternatives |

---

## 6. Event-Driven Data Flow

### Kafka Event Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Event Producers                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│  │  Search  │  │ Booking  │  │ Supplier │  │  Alerts  │                    │
│  │ Service  │  │ Service  │  │ Gateway  │  │ Service  │                    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                    │
│       │             │             │             │                           │
└───────┼─────────────┼─────────────┼─────────────┼───────────────────────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Kafka Cluster                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │search-events │  │booking-events│  │price-updates │  │alert-triggers│    │
│  │  (64 parts)  │  │  (32 parts)  │  │ (128 parts)  │  │  (16 parts)  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Event Consumers                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │Analytics │  │ Cache    │  │Prediction│  │  Alert   │  │ClickHouse│      │
│  │ Service  │  │ Warmer   │  │ Trainer  │  │ Processor│  │ Ingester │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Event Schemas

**Search Event:**
```json
{
  "event_type": "search_completed",
  "timestamp": "2024-06-15T10:30:00Z",
  "search_id": "srch_abc123",
  "user_id": "usr_xyz789",
  "origin": "JFK",
  "destination": "LAX",
  "departure_date": "2024-07-01",
  "results_count": 145,
  "lowest_price_cents": 29900,
  "latency_ms": 1250,
  "cache_hit": false
}
```

**Price Update Event:**
```json
{
  "event_type": "price_changed",
  "timestamp": "2024-06-15T10:30:00Z",
  "route_id": "JFK-LAX",
  "flight_id": "UA123-20240701",
  "previous_price_cents": 32900,
  "new_price_cents": 29900,
  "change_percentage": -9.12,
  "supplier_code": "amadeus"
}
```

**Booking Event:**
```json
{
  "event_type": "booking_confirmed",
  "timestamp": "2024-06-15T10:35:00Z",
  "booking_id": "bkg_def456",
  "user_id": "usr_xyz789",
  "flight_id": "UA123-20240701",
  "total_price_cents": 34400,
  "supplier_code": "amadeus",
  "pnr": "ABC123"
}
```
