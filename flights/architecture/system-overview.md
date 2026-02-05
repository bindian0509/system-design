# System Overview

## High-Level Architecture

The flight search system is designed as a distributed microservices architecture optimized for high throughput, low latency, and fault tolerance.

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   CLIENT LAYER                                       │
│              ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│              │   Web App    │  │  Mobile App  │  │ Partner APIs │                   │
│              └──────────────┘  └──────────────┘  └──────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   CDN / EDGE                                         │
│                    (Static Assets, Airport Data, Route Metadata)                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                  API GATEWAY                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │Rate Limiter │  │    Auth     │  │   Router    │  │Load Balancer│                 │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                 ┌───────────────────────┼───────────────────────┐
                 ▼                       ▼                       ▼
        ┌────────────────┐      ┌────────────────┐      ┌────────────────┐
        │ Search Service │      │Booking Service │      │ Alerts Service │
        │   (Stateless)  │      │   (Stateless)  │      │   (Stateless)  │
        └────────────────┘      └────────────────┘      └────────────────┘
                 │                       │                       │
                 │                       │                       │
        ┌────────┴────────┐              │                       │
        ▼                 ▼              │                       │
┌──────────────┐  ┌──────────────┐       │                       │
│Pricing Engine│  │Prediction Svc│       │                       │
└──────────────┘  └──────────────┘       │                       │
        │                 │              │                       │
        └─────────────────┼──────────────┼───────────────────────┘
                          ▼
           ┌──────────────────────────────────────┐
           │        Supplier Gateway Service       │
           │  ┌────────────────────────────────┐  │
           │  │     Adapter Layer (500+)       │  │
           │  │  ┌──────┐ ┌──────┐ ┌──────┐   │  │
           │  │  │Amadeus│ │Sabre │ │Direct│   │  │
           │  │  └──────┘ └──────┘ └──────┘   │  │
           │  └────────────────────────────────┘  │
           │  ┌────────────────────────────────┐  │
           │  │   Circuit Breaker / Bulkhead   │  │
           │  └────────────────────────────────┘  │
           └──────────────────────────────────────┘
```

## Component Details

### 1. API Gateway

The API Gateway serves as the single entry point for all client requests.

**Responsibilities:**
- **Rate Limiting**: Token bucket algorithm with 100 requests/minute per user, 1000/minute for partners
- **Authentication**: JWT validation with 15-minute access tokens, 7-day refresh tokens
- **Request Routing**: Path-based routing to appropriate microservices
- **Load Balancing**: Weighted round-robin across service instances
- **Request Validation**: Schema validation, sanitization, and parameter normalization

**Technology**: Kong Gateway or AWS API Gateway

**Configuration:**
```yaml
rate_limits:
  anonymous: 20/minute
  authenticated: 100/minute
  partner: 1000/minute

timeouts:
  connect: 1s
  read: 5s
  write: 5s
```

### 2. Search Service

The core service responsible for orchestrating flight searches across all suppliers.

**Responsibilities:**
- Parse and validate search requests
- Check cache for existing results
- Fan out requests to Supplier Gateway
- Aggregate and deduplicate results
- Apply dynamic pricing
- Sort and filter results
- Stream progressive results via SSE

**Scaling:**
- 50 instances at baseline
- Auto-scale to 200 instances at peak
- 4 vCPU, 8GB RAM per instance

**Key Metrics:**
| Metric | Target |
|--------|--------|
| P50 Latency | 800ms |
| P95 Latency | 2000ms |
| P99 Latency | 3500ms |
| Error Rate | < 0.1% |

### 3. Booking Service

Handles the entire booking lifecycle from availability verification to confirmation.

**Responsibilities:**
- Verify real-time availability and pricing
- Process payments via payment gateway
- Create booking records
- Send confirmation to suppliers
- Handle cancellations and modifications

**Key Features:**
- Idempotency keys prevent duplicate bookings
- Optimistic locking for seat inventory
- Saga pattern for distributed transactions

### 4. Alerts Service

Manages user price alerts and notifications.

**Responsibilities:**
- Store user alert preferences
- Monitor price changes via Kafka events
- Trigger notifications when conditions are met
- Track alert history and effectiveness

**Processing:**
- Batch processing every 15 minutes
- Real-time processing for high-priority alerts
- Notification channels: Email, Push, SMS

### 5. Supplier Gateway Service

Provides a unified interface to 500+ external supplier APIs.

**Architecture:**
```
┌─────────────────────────────────────────────────────────────────┐
│                     Supplier Gateway                             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Request Router                          │  │
│  │   (Route requests to appropriate supplier adapters)        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┼───────────────────────────────┐  │
│  │                    Adapter Layer                           │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │  │
│  │  │ GDS     │  │ Direct  │  │  LCC    │  │ Meta    │      │  │
│  │  │Adapters │  │Airlines │  │ APIs    │  │ Search  │      │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┼───────────────────────────────┐  │
│  │              Resilience Layer                              │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │  │
│  │  │Circuit Breaker│  │  Bulkhead   │  │   Retry     │    │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┼───────────────────────────────┐  │
│  │              Response Normalizer                           │  │
│  │     (Convert supplier-specific formats to unified schema)  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Supplier Categories:**
| Category | Examples | Typical Latency |
|----------|----------|-----------------|
| GDS | Amadeus, Sabre, Travelport | 1-3s |
| Direct Airlines | United, Delta, AA | 500ms-2s |
| LCC | Southwest, Spirit, Frontier | 1-4s |
| Regional | Air India, Emirates | 2-5s |

### 6. Pricing Engine

Calculates final prices by applying dynamic markups to supplier base prices.

**Pricing Formula:**
```
Final Price = Base Price × Booking Window Factor × Demand Factor × Seasonality × Margin
```

**Factors:**
| Factor | Range | Description |
|--------|-------|-------------|
| Booking Window | 0.95 - 1.35 | Based on days until departure |
| Demand | 0.90 - 1.15 | ML model output from search velocity |
| Seasonality | 0.85 - 1.45 | Holiday/peak season adjustments |
| Margin | 1.03 - 1.08 | Based on supplier contract |

### 7. Prediction Service

ML-based service for predicting price trends and providing booking recommendations.

**Model Architecture:**
- Ensemble: XGBoost (70%) + LSTM (30%)
- Features:
  - Historical prices (90-day window)
  - Search velocity
  - Seat availability
  - Days to departure
  - Seasonality indicators
  - Day of week patterns

**Serving:**
- TensorFlow Serving for real-time inference
- < 50ms inference latency
- Daily model retraining

## Data Stores

### PostgreSQL (Primary OLTP)

**Deployment:**
- Primary-replica setup with synchronous replication
- 3 replicas per region for read scaling
- Automatic failover via Patroni

**Partitioning Strategy:**
- Bookings: Range partition by created_at (monthly)
- Price alerts: Hash partition by user_id

### Redis Cluster

**Deployment:**
- 6-node cluster (3 primary, 3 replica)
- 256 hash slots per node
- 64GB RAM per node

**Data Structures:**
| Key Pattern | Type | Purpose |
|-------------|------|---------|
| `search:{hash}` | String/JSON | Cached search results |
| `route_prices:{route}:{date}` | Sorted Set | Price rankings |
| `user_session:{id}` | Hash | Session data |
| `rate_limit:{ip}` | String + TTL | Rate limiting counters |

### ClickHouse

**Use Cases:**
- Historical price analytics
- Search pattern analysis
- A/B test metrics
- Business intelligence

**Tables:**
- `price_history`: Time-series price data
- `search_events`: Search request logs
- `booking_events`: Booking funnel analytics

### Kafka

**Topics:**
| Topic | Partitions | Purpose |
|-------|------------|---------|
| `price-updates` | 128 | Real-time price changes |
| `search-events` | 64 | Search analytics |
| `booking-events` | 32 | Booking notifications |
| `alert-triggers` | 16 | Price alert processing |

## Infrastructure

### Deployment Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                         Region: US-East                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Availability Zone 1                   │    │
│  │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │    │
│  │   │Search x8│ │Booking  │ │Alerts   │ │Supplier │       │    │
│  │   │         │ │   x4    │ │  x2     │ │Gateway  │       │    │
│  │   └─────────┘ └─────────┘ └─────────┘ │   x6    │       │    │
│  │   ┌─────────┐ ┌─────────┐ ┌─────────┐ └─────────┘       │    │
│  │   │Pricing  │ │Predict  │ │ Redis   │                   │    │
│  │   │   x2    │ │   x2    │ │ Node x2 │                   │    │
│  │   └─────────┘ └─────────┘ └─────────┘                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Availability Zone 2                   │    │
│  │               (Mirror configuration)                     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Service Mesh

Using Istio for:
- mTLS between services
- Traffic management
- Observability
- Circuit breaking at mesh level

### Observability Stack

| Component | Tool | Purpose |
|-----------|------|---------|
| Metrics | Prometheus + Grafana | System and business metrics |
| Logging | ELK Stack | Centralized log aggregation |
| Tracing | Jaeger | Distributed tracing |
| Alerting | PagerDuty | On-call notifications |

## Security

### Authentication & Authorization

- OAuth 2.0 + OpenID Connect for user authentication
- API keys with scopes for partner access
- Service-to-service authentication via mTLS

### Data Protection

- TLS 1.3 for all external communication
- AES-256 encryption for PII at rest
- PCI DSS compliance for payment data
- GDPR compliance for EU users

### Rate Limiting

```
Tier 1 (Anonymous):     20 requests/minute
Tier 2 (Free User):     100 requests/minute
Tier 3 (Premium User):  500 requests/minute
Tier 4 (Partner API):   1000 requests/minute
```
