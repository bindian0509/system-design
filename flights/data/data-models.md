# Data Models

## Overview

This document defines the data models for PostgreSQL (primary OLTP), Redis (caching), ClickHouse (analytics), and Kafka (event streaming).

---

## PostgreSQL Schema

### Core Tables

#### Users

```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    email_verified BOOLEAN DEFAULT FALSE,
    password_hash VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    phone_verified BOOLEAN DEFAULT FALSE,
    preferred_currency VARCHAR(3) DEFAULT 'USD',
    preferred_language VARCHAR(5) DEFAULT 'en',
    notification_preferences JSONB DEFAULT '{"email": true, "push": true, "sms": false}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created_at ON users(created_at);
```

#### Routes (Static Reference Data)

```sql
CREATE TABLE routes (
    id BIGSERIAL PRIMARY KEY,
    origin_airport VARCHAR(3) NOT NULL,
    destination_airport VARCHAR(3) NOT NULL,
    distance_km INT,
    typical_duration_minutes INT,
    popularity_score FLOAT DEFAULT 0.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(origin_airport, destination_airport)
);

CREATE INDEX idx_routes_origin ON routes(origin_airport);
CREATE INDEX idx_routes_destination ON routes(destination_airport);
CREATE INDEX idx_routes_popularity ON routes(popularity_score DESC);
```

#### Airports

```sql
CREATE TABLE airports (
    code VARCHAR(3) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    airport_type VARCHAR(20) DEFAULT 'international',
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_airports_city ON airports(city);
CREATE INDEX idx_airports_country ON airports(country_code);
```

#### Airlines

```sql
CREATE TABLE airlines (
    code VARCHAR(3) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    logo_url VARCHAR(500),
    alliance VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    baggage_policy_url VARCHAR(500),
    check_in_url VARCHAR(500)
);
```

### Price Alerts

```sql
CREATE TABLE price_alerts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    route_id BIGINT NOT NULL REFERENCES routes(id),
    departure_date DATE NOT NULL,
    return_date DATE,
    target_price_cents BIGINT NOT NULL,
    current_lowest_cents BIGINT,
    cabin_class VARCHAR(20) DEFAULT 'economy',
    passengers_adults INT DEFAULT 1,
    passengers_children INT DEFAULT 0,
    passengers_infants INT DEFAULT 0,
    notification_channels JSONB DEFAULT '["email"]',
    status VARCHAR(20) DEFAULT 'active',
    triggered_at TIMESTAMP WITH TIME ZONE,
    expired_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_checked_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT chk_status CHECK (status IN ('active', 'triggered', 'expired', 'cancelled'))
);

CREATE INDEX idx_alerts_user_id ON price_alerts(user_id);
CREATE INDEX idx_alerts_route_id ON price_alerts(route_id);
CREATE INDEX idx_alerts_status ON price_alerts(status) WHERE status = 'active';
CREATE INDEX idx_alerts_departure ON price_alerts(departure_date);

-- Partition by user_id for scaling
-- ALTER TABLE price_alerts PARTITION BY HASH (user_id);
```

### Bookings

```sql
CREATE TABLE bookings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    booking_reference VARCHAR(20) NOT NULL UNIQUE,
    supplier_booking_id VARCHAR(100),
    supplier_code VARCHAR(20) NOT NULL,

    -- Flight Details (denormalized for query performance)
    origin_airport VARCHAR(3) NOT NULL,
    destination_airport VARCHAR(3) NOT NULL,
    departure_date DATE NOT NULL,
    return_date DATE,
    cabin_class VARCHAR(20) NOT NULL,

    -- Pricing
    base_price_cents BIGINT NOT NULL,
    taxes_cents BIGINT NOT NULL,
    fees_cents BIGINT DEFAULT 0,
    total_price_cents BIGINT NOT NULL,
    currency VARCHAR(3) NOT NULL,

    -- Payment
    payment_method VARCHAR(20),
    payment_reference VARCHAR(100),
    payment_status VARCHAR(20) DEFAULT 'pending',

    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    confirmed_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    cancellation_reason VARCHAR(255),

    -- Metadata
    itinerary_json JSONB NOT NULL,
    idempotency_key VARCHAR(100) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_booking_status CHECK (status IN (
        'pending', 'confirmed', 'ticketed', 'cancelled', 'refunded', 'failed'
    )),
    CONSTRAINT chk_payment_status CHECK (payment_status IN (
        'pending', 'authorized', 'charged', 'refunded', 'failed'
    ))
);

-- Partition by created_at for efficient archival
CREATE INDEX idx_bookings_user_id ON bookings(user_id);
CREATE INDEX idx_bookings_reference ON bookings(booking_reference);
CREATE INDEX idx_bookings_status ON bookings(status);
CREATE INDEX idx_bookings_created_at ON bookings(created_at);
CREATE INDEX idx_bookings_departure ON bookings(departure_date);
```

### Booking Passengers

```sql
CREATE TABLE booking_passengers (
    id BIGSERIAL PRIMARY KEY,
    booking_id BIGINT NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    passenger_type VARCHAR(10) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE,
    gender VARCHAR(10),
    nationality VARCHAR(2),
    passport_number VARCHAR(20),
    passport_expiry DATE,
    ticket_number VARCHAR(20),
    seat_assignments JSONB,
    frequent_flyer_number VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_passenger_type CHECK (passenger_type IN ('adult', 'child', 'infant'))
);

CREATE INDEX idx_passengers_booking ON booking_passengers(booking_id);
```

### Booking Segments

```sql
CREATE TABLE booking_segments (
    id BIGSERIAL PRIMARY KEY,
    booking_id BIGINT NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    segment_order INT NOT NULL,
    flight_number VARCHAR(10) NOT NULL,
    carrier_code VARCHAR(3) NOT NULL,
    origin_airport VARCHAR(3) NOT NULL,
    destination_airport VARCHAR(3) NOT NULL,
    departure_time TIMESTAMP WITH TIME ZONE NOT NULL,
    arrival_time TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_minutes INT NOT NULL,
    aircraft_type VARCHAR(10),
    cabin_class VARCHAR(20) NOT NULL,
    fare_class VARCHAR(5),
    status VARCHAR(20) DEFAULT 'confirmed',

    CONSTRAINT chk_segment_status CHECK (status IN (
        'confirmed', 'checked_in', 'boarded', 'completed', 'cancelled'
    ))
);

CREATE INDEX idx_segments_booking ON booking_segments(booking_id);
CREATE INDEX idx_segments_departure ON booking_segments(departure_time);
```

### Search History

```sql
CREATE TABLE search_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    session_id VARCHAR(100),
    origin_airport VARCHAR(3) NOT NULL,
    destination_airport VARCHAR(3) NOT NULL,
    departure_date DATE NOT NULL,
    return_date DATE,
    passengers_adults INT DEFAULT 1,
    passengers_children INT DEFAULT 0,
    cabin_class VARCHAR(20) DEFAULT 'economy',
    results_count INT,
    lowest_price_cents BIGINT,
    search_latency_ms INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Time-series partitioning for efficient cleanup
-- Partition by month, retain 90 days
CREATE INDEX idx_search_user ON search_history(user_id);
CREATE INDEX idx_search_route ON search_history(origin_airport, destination_airport);
CREATE INDEX idx_search_created ON search_history(created_at);
```

### Suppliers

```sql
CREATE TABLE suppliers (
    code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    supplier_type VARCHAR(20) NOT NULL,
    api_endpoint VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    priority INT DEFAULT 100,
    timeout_ms INT DEFAULT 2000,
    rate_limit_per_minute INT DEFAULT 1000,
    commission_percent DECIMAL(5, 2),
    supported_currencies JSONB DEFAULT '["USD"]',
    credentials_encrypted BYTEA,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_supplier_type CHECK (supplier_type IN (
        'gds', 'direct_airline', 'lcc', 'aggregator'
    ))
);
```

---

## Redis Data Structures

### Search Results Cache

**Key Pattern:** `search:{hash}`

Where `hash = SHA256(origin + dest + date + passengers + cabin_class + filters)`

**Value:** JSON string of search results

```json
{
  "search_id": "srch_abc123",
  "results": [...],
  "cached_at": 1623456789,
  "ttl_seconds": 300
}
```

**TTL Strategy (Dynamic):**
- Departure < 3 days: 120 seconds (2 min)
- Departure 3-7 days: 300 seconds (5 min)
- Departure 7-30 days: 900 seconds (15 min)
- Departure > 30 days: 1800 seconds (30 min)

### Route Prices (Sorted Set)

**Key Pattern:** `route_prices:{route_id}:{departure_date}`

**Type:** Sorted Set (ZSET)

**Score:** Price in cents

**Member:** Flight JSON string

```
ZADD route_prices:JFK-LAX:2024-07-01 29900 '{"flight_id":"flt_001",...}'
ZADD route_prices:JFK-LAX:2024-07-01 32500 '{"flight_id":"flt_002",...}'
```

**Operations:**
- `ZRANGEBYSCORE` - Get flights within price range
- `ZRANGE ... LIMIT 0 10` - Get top 10 cheapest

### User Sessions

**Key Pattern:** `session:{session_id}`

**Type:** Hash

```
HSET session:sess_abc123 user_id 12345
HSET session:sess_abc123 email "user@example.com"
HSET session:sess_abc123 created_at 1623456789
HSET session:sess_abc123 last_activity 1623457000
EXPIRE session:sess_abc123 86400
```

### Rate Limiting

**Key Pattern:** `rate_limit:{identifier}`

**Type:** String with TTL

```
SET rate_limit:ip:192.168.1.1 1 EX 60 NX
INCR rate_limit:ip:192.168.1.1
```

### Price History (Time Series)

Using Redis TimeSeries module:

**Key Pattern:** `price_ts:{route_id}`

```
TS.CREATE price_ts:JFK-LAX RETENTION 7776000000  # 90 days in ms
TS.ADD price_ts:JFK-LAX * 29900
TS.RANGE price_ts:JFK-LAX - + AGGREGATION min 86400000  # Daily min
```

### Supplier Circuit Breaker State

**Key Pattern:** `circuit:{supplier_code}`

**Type:** Hash

```
HSET circuit:amadeus state closed
HSET circuit:amadeus failures 0
HSET circuit:amadeus last_failure 0
HSET circuit:amadeus last_success 1623456789
```

### Flight Availability Cache

**Key Pattern:** `avail:{flight_id}`

**Type:** String

```
SET avail:flt_ua123_20240615 '{"seats":7,"fare_class":"Y","updated":1623456789}' EX 120
```

---

## ClickHouse Schema

### Price History (Analytics)

```sql
CREATE TABLE price_history (
    route_id String,
    origin String,
    destination String,
    departure_date Date,
    supplier_code String,
    flight_number String,
    price_cents UInt64,
    taxes_cents UInt64,
    currency String,
    cabin_class String,
    seats_available UInt8,
    recorded_at DateTime64(3),

    -- Aggregation helpers
    date Date DEFAULT toDate(recorded_at)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (route_id, departure_date, recorded_at)
TTL date + INTERVAL 90 DAY;
```

### Search Events

```sql
CREATE TABLE search_events (
    event_id String,
    user_id Nullable(UInt64),
    session_id String,
    origin String,
    destination String,
    departure_date Date,
    return_date Nullable(Date),
    passengers_adults UInt8,
    passengers_children UInt8,
    cabin_class String,
    results_count UInt32,
    lowest_price_cents Nullable(UInt64),
    highest_price_cents Nullable(UInt64),
    suppliers_queried Array(String),
    cache_hit UInt8,
    latency_ms UInt32,
    client_type String,
    client_version String,
    country_code String,
    timestamp DateTime64(3),

    date Date DEFAULT toDate(timestamp)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (origin, destination, date, timestamp)
TTL date + INTERVAL 365 DAY;
```

### Booking Events

```sql
CREATE TABLE booking_events (
    event_type String,
    booking_id String,
    user_id UInt64,
    origin String,
    destination String,
    departure_date Date,
    return_date Nullable(Date),
    supplier_code String,
    total_price_cents UInt64,
    currency String,
    passengers_count UInt8,
    cabin_class String,
    days_to_departure UInt16,
    search_to_book_minutes UInt32,
    timestamp DateTime64(3),

    date Date DEFAULT toDate(timestamp)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, supplier_code, timestamp)
TTL date + INTERVAL 730 DAY;  -- 2 years
```

### Supplier Performance

```sql
CREATE TABLE supplier_performance (
    supplier_code String,
    request_type String,
    success UInt8,
    latency_ms UInt32,
    error_code Nullable(String),
    timestamp DateTime64(3),

    date Date DEFAULT toDate(timestamp)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (supplier_code, date, timestamp)
TTL date + INTERVAL 30 DAY;

-- Materialized view for aggregations
CREATE MATERIALIZED VIEW supplier_performance_daily
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (supplier_code, date)
AS SELECT
    supplier_code,
    toDate(timestamp) as date,
    count() as total_requests,
    sum(success) as successful_requests,
    avg(latency_ms) as avg_latency_ms,
    quantile(0.95)(latency_ms) as p95_latency_ms,
    quantile(0.99)(latency_ms) as p99_latency_ms
FROM supplier_performance
GROUP BY supplier_code, date;
```

---

## Kafka Topics & Schemas

### Topic: search-events

**Partitions:** 64
**Retention:** 7 days
**Key:** `{origin}-{destination}`

```json
{
  "event_type": "search_completed",
  "event_id": "evt_abc123",
  "timestamp": "2024-06-10T14:30:00.000Z",
  "search_id": "srch_xyz789",
  "user_id": 12345,
  "session_id": "sess_abc",
  "origin": "JFK",
  "destination": "LAX",
  "departure_date": "2024-07-01",
  "return_date": null,
  "passengers": {
    "adults": 1,
    "children": 0,
    "infants": 0
  },
  "cabin_class": "economy",
  "results_count": 145,
  "lowest_price_cents": 29900,
  "latency_ms": 1250,
  "cache_hit": false,
  "suppliers_queried": ["amadeus", "sabre", "direct_ua"]
}
```

### Topic: price-updates

**Partitions:** 128
**Retention:** 24 hours
**Key:** `{route_id}`

```json
{
  "event_type": "price_changed",
  "event_id": "evt_def456",
  "timestamp": "2024-06-10T14:30:00.000Z",
  "route_id": "JFK-LAX",
  "departure_date": "2024-07-01",
  "flight_id": "flt_ua123",
  "supplier_code": "amadeus",
  "previous_price_cents": 32900,
  "new_price_cents": 29900,
  "change_percent": -9.12,
  "seats_remaining": 7
}
```

### Topic: booking-events

**Partitions:** 32
**Retention:** 30 days
**Key:** `{booking_id}`

```json
{
  "event_type": "booking_confirmed",
  "event_id": "evt_ghi789",
  "timestamp": "2024-06-10T14:35:00.000Z",
  "booking_id": "bkg_abc123",
  "booking_reference": "ABC123",
  "user_id": 12345,
  "origin": "JFK",
  "destination": "LAX",
  "departure_date": "2024-07-01",
  "supplier_code": "amadeus",
  "total_price_cents": 34400,
  "currency": "USD",
  "passengers_count": 1
}
```

### Topic: alert-triggers

**Partitions:** 16
**Retention:** 7 days
**Key:** `{alert_id}`

```json
{
  "event_type": "alert_triggered",
  "event_id": "evt_jkl012",
  "timestamp": "2024-06-10T15:00:00.000Z",
  "alert_id": "alt_xyz789",
  "user_id": 12345,
  "route_id": "JFK-LAX",
  "departure_date": "2024-07-01",
  "target_price_cents": 25000,
  "current_price_cents": 24500,
  "notification_channels": ["email", "push"]
}
```

---

## ElasticSearch Indexes

### airports Index

```json
{
  "mappings": {
    "properties": {
      "code": { "type": "keyword" },
      "name": { "type": "text", "analyzer": "standard" },
      "name_suggest": {
        "type": "completion",
        "contexts": [
          { "name": "country", "type": "category" }
        ]
      },
      "city": { "type": "text", "analyzer": "standard" },
      "city_keyword": { "type": "keyword" },
      "country": { "type": "text" },
      "country_code": { "type": "keyword" },
      "location": { "type": "geo_point" },
      "popularity": { "type": "integer" },
      "is_active": { "type": "boolean" }
    }
  },
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 2
  }
}
```

### routes Index

```json
{
  "mappings": {
    "properties": {
      "route_id": { "type": "keyword" },
      "origin": { "type": "keyword" },
      "destination": { "type": "keyword" },
      "origin_city": { "type": "text" },
      "destination_city": { "type": "text" },
      "popularity_score": { "type": "float" },
      "avg_price_cents": { "type": "integer" },
      "typical_duration_minutes": { "type": "integer" }
    }
  }
}
```

---

## Data Retention Policies

| Data Store | Table/Topic | Retention | Archive |
|------------|-------------|-----------|---------|
| PostgreSQL | users | Forever | - |
| PostgreSQL | bookings | 7 years | S3 cold storage |
| PostgreSQL | search_history | 90 days | ClickHouse |
| PostgreSQL | price_alerts | 1 year | Delete |
| Redis | search cache | 2-30 min | - |
| Redis | sessions | 24 hours | - |
| ClickHouse | price_history | 90 days | S3 Parquet |
| ClickHouse | search_events | 1 year | S3 Parquet |
| ClickHouse | booking_events | 2 years | S3 Parquet |
| Kafka | search-events | 7 days | - |
| Kafka | price-updates | 24 hours | - |
| Kafka | booking-events | 30 days | - |
