# URL Shortener - Java Spring Boot Implementation

<p align="center">
  <img src="https://img.shields.io/badge/Java-21-orange?style=flat-square&logo=openjdk" alt="Java 21"/>
  <img src="https://img.shields.io/badge/Spring%20Boot-3.2-green?style=flat-square&logo=spring" alt="Spring Boot 3.2"/>
  <img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="MIT License"/>
</p>

A production-grade URL shortener service built with **Java 21** and **Spring Boot 3.2**. Designed to scale from local development to **500 million URLs per month** globally with multi-region active-active deployment.

---

## 📑 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [API Reference](#-api-reference)
- [Configuration](#-configuration)
- [ID Generation & Range Allocation](#-id-generation--range-allocation)
- [Custom Aliases](#-custom-aliases)
- [Caching Strategy](#-caching-strategy)
- [Security](#-security)
- [Rate Limiting](#-rate-limiting)
- [Monitoring & Observability](#-monitoring--observability)
- [Database Design](#-database-design)
- [Scaling Tiers](#-scaling-tiers)
- [Docker Deployment](#-docker-deployment)
- [Testing](#-testing)
- [GDPR Compliance](#-gdpr-compliance)
- [Documentation](#-documentation)
- [Contributing](#-contributing)

---

## ✨ Features

### Core Functionality
- ✅ **URL Shortening** - Create short, memorable links
- ✅ **Custom Aliases** - User-defined vanity URLs
- ✅ **URL Expiration** - Time-based link expiration
- ✅ **Click Tracking** - Real-time analytics
- ✅ **Bulk Operations** - Create multiple URLs at once

### Technical Features
- ✅ **Base62 Encoding** - Compact 7-character codes (3.5 trillion capacity)
- ✅ **Distributed ID Generation** - Range-based allocation for horizontal scaling
- ✅ **Write-Through Caching** - Redis/Memory with 24h TTL
- ✅ **Rate Limiting** - Tier-based request throttling
- ✅ **API Key Authentication** - Secure API access
- ✅ **Prometheus Metrics** - Full observability stack
- ✅ **GDPR Compliance** - Data export and erasure

---

## 🏗️ Architecture

### High-Level Overview

```mermaid
flowchart TB
    subgraph Clients["Client Layer"]
        Browser["🌐 Browser"]
        Mobile["📱 Mobile App"]
        CLI["💻 CLI"]
        API["🔌 API Clients"]
    end

    subgraph LB["Load Balancer / CDN"]
        CloudFront["CloudFront / nginx"]
    end

    subgraph App["Spring Boot Application"]
        subgraph Filters["Filter Chain"]
            Security["Security Filter"]
            RateLimit["Rate Limiter"]
            Request["Request Filter"]
        end

        subgraph Controllers["Controller Layer"]
            UrlCtrl["UrlController"]
            RedirectCtrl["RedirectController"]
            AnalyticsCtrl["AnalyticsController"]
        end

        subgraph Services["Service Layer"]
            UrlSvc["UrlService"]
            IdGen["IdGenerator"]
            CacheSvc["CacheService"]
            AnalyticsSvc["AnalyticsService"]
        end

        subgraph Repos["Repository Layer"]
            UrlRepo["ShortUrlRepository"]
        end
    end

    subgraph Storage["Data Stores"]
        DB[("SQLite / DynamoDB")]
        Cache[("Redis Cache")]
        Metrics[("Prometheus")]
    end

    Clients --> LB
    LB --> Filters
    Filters --> Controllers
    Controllers --> Services
    Services --> Repos
    Repos --> DB
    Services --> Cache
    App --> Metrics
```

### Request Flow - URL Shortening

```mermaid
sequenceDiagram
    participant C as Client
    participant LB as Load Balancer
    participant S as Security Filter
    participant R as Rate Limiter
    participant UC as UrlController
    participant US as UrlService
    participant IG as IdGenerator
    participant DB as Database
    participant Cache as Redis Cache

    C->>LB: POST /api/v1/urls
    LB->>S: Forward request
    S->>S: Validate API Key
    S->>R: Authenticated request
    R->>R: Check rate limit
    R->>UC: Allowed request
    UC->>US: createShortUrl(request)
    US->>IG: generate()
    IG-->>US: "abc123"
    US->>DB: save(shortUrl)
    DB-->>US: saved
    US->>Cache: set(code, url)
    Cache-->>US: ok
    US-->>UC: CreateUrlResponse
    UC-->>C: 201 Created
```

### Request Flow - URL Redirect

```mermaid
sequenceDiagram
    participant C as Client
    participant CDN as CloudFront/CDN
    participant RC as RedirectController
    participant US as UrlService
    participant Cache as Redis Cache
    participant DB as Database
    participant AS as AnalyticsService

    C->>CDN: GET /abc123
    CDN->>CDN: Check cache
    alt Cache Hit
        CDN-->>C: 308 Redirect (cached)
    else Cache Miss
        CDN->>RC: Forward request
        RC->>US: getRedirectUrl("abc123")
        US->>Cache: get("abc123")
        alt Cache Hit
            Cache-->>US: originalUrl
        else Cache Miss
            US->>DB: findByCode("abc123")
            DB-->>US: ShortUrl
            US->>Cache: set("abc123", url)
        end
        US->>AS: recordClick(event)
        US-->>RC: originalUrl
        RC-->>CDN: 308 Redirect
        CDN-->>C: 308 Redirect
    end
```

### Project Structure

```
url-shortener-java/
├── src/
│   ├── main/
│   │   ├── java/com/urlshortener/
│   │   │   ├── UrlShortenerApplication.java    # Application entry point
│   │   │   ├── controller/                     # REST API Layer
│   │   │   ├── domain/                         # Domain Models & DTOs
│   │   │   ├── service/                        # Business Logic
│   │   │   ├── repository/                     # Data Access
│   │   │   ├── security/                       # Security Layer
│   │   │   ├── config/                         # Configuration
│   │   │   └── exception/                      # Error Handling
│   │   └── resources/
│   │       └── application.yml                 # Configuration
│   └── test/java/com/urlshortener/            # Test classes
├── docker/
│   ├── Dockerfile                              # Production build
│   └── Dockerfile.dev                          # Development build
├── config/
│   └── prometheus.yml                          # Prometheus config
├── docs/                                       # Documentation
├── docker-compose.yml                          # Docker orchestration
├── pom.xml                                     # Maven dependencies
└── README.md                                   # This file
```

---

## 🚀 Quick Start

### Prerequisites

- **Java 21** or higher
- **Maven 3.9+** (or use included wrapper)
- **Docker & Docker Compose** (for containerized deployment)

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
cd url-shortener-java

# Start the application
docker-compose up -d

# View logs
docker-compose logs -f url-shortener

# Check health
curl http://localhost:8080/health
```

### Option 2: Maven (Local Development)

```bash
# Using Maven wrapper
./mvnw spring-boot:run

# Or with installed Maven
mvn spring-boot:run
```

### Option 3: Build & Run JAR

```bash
# Build the application
./mvnw clean package -DskipTests

# Run the JAR
java -jar target/url-shortener-1.0.0.jar
```

### Verify Installation

```bash
# Health check
curl http://localhost:8080/health
# Response: {"status":"ok","timestamp":"2024-01-15T10:30:00Z"}

# Create a short URL
curl -X POST http://localhost:8080/api/v1/urls \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_user:free" \
  -d '{"url": "https://github.com/example/repo"}'

# Response:
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "shortCode": "0000001",
#   "shortUrl": "http://localhost:8080/0000001",
#   "originalUrl": "https://github.com/example/repo",
#   "createdAt": "2024-01-15T10:30:00Z",
#   "expiresAt": "2025-01-15T10:30:00Z"
# }

# Test redirect
curl -I http://localhost:8080/0000001
# HTTP/1.1 308 Permanent Redirect
# Location: https://github.com/example/repo
```

---

## 📚 API Reference

### Base URL

```
Local:      http://localhost:8080
Production: https://short.yourdomain.com
```

### Authentication

All API endpoints (except redirects and health checks) require authentication:

```bash
# Bearer Token (Development)
Authorization: Bearer {userId}:{tier}
# Example: Bearer user123:premium

# API Key (Production)
Authorization: ApiKey urlsh_sk_xxxxxxxxxxxxxxxxxx
```

### Endpoints

#### Create Short URL

```http
POST /api/v1/urls
```

**Request Body:**
```json
{
  "url": "https://example.com/very/long/url",
  "customAlias": "my-link",
  "ttlSeconds": 86400,
  "title": "My Link",
  "description": "Description",
  "tags": ["marketing", "2024"]
}
```

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "shortCode": "my-link",
  "shortUrl": "http://localhost:8080/my-link",
  "originalUrl": "https://example.com/very/long/url",
  "createdAt": "2024-01-15T10:30:00Z",
  "expiresAt": "2024-01-16T10:30:00Z"
}
```

#### Get URL Details

```http
GET /api/v1/urls/{code}
```

#### Redirect

```http
GET /{code}
```

**Response: 308 Permanent Redirect**

#### Get Analytics

```http
GET /api/v1/analytics/{code}
```

#### Health Endpoints

```http
GET /health              # Liveness probe
GET /ready               # Readiness probe
GET /actuator/prometheus # Prometheus metrics
```

### Error Responses

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `URL_NOT_FOUND` | 404 | Short URL doesn't exist |
| `URL_EXPIRED` | 410 | URL has expired |
| `URL_DISABLED` | 403 | URL has been disabled |
| `INVALID_URL` | 400 | Invalid URL format |
| `ALIAS_TAKEN` | 409 | Custom alias already exists |
| `RATE_LIMITED` | 429 | Rate limit exceeded |

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SPRING_PROFILES_ACTIVE` | `local` | Active profile |
| `DATABASE_URL` | `jdbc:sqlite:./data/urls.db` | Database connection |
| `CACHE_TYPE` | `memory` | Cache type: `memory` or `redis` |
| `REDIS_HOST` | `localhost` | Redis server host |
| `BASE_URL` | `http://localhost:8080` | Public URL |
| `AWS_REGION` | `us-east-1` | AWS region |

---

## 🔢 ID Generation & Range Allocation

### Global ID Space Division

```mermaid
pie showData
    title Global ID Space (3.52 Trillion)
    "US-EAST-1 (Americas)" : 1173871535403
    "EU-WEST-1 (Europe)" : 1173871535403
    "AP-SOUTH-1 (India/Asia)" : 1173871535402
```

### Distributed Counter Architecture

```mermaid
flowchart TB
    subgraph Global["Global ID Space: 62^7 = 3.52 Trillion"]
        subgraph US["🇺🇸 US-EAST-1"]
            US_Range["Range: 0 - 1.17T<br/>Codes: 0000000 - 0LY7VK2"]
        end
        subgraph EU["🇪🇺 EU-WEST-1"]
            EU_Range["Range: 1.17T - 2.34T<br/>Codes: 0LY7VK3 - 0zXdWV5"]
        end
        subgraph IN["🇮🇳 AP-SOUTH-1"]
            IN_Range["Range: 2.34T - 3.52T<br/>Codes: 0zXdWV6 - ZZZZZZZ"]
        end
    end

    subgraph DDB["DynamoDB Counter Table"]
        Counter["Atomic Counter<br/>per Region"]
    end

    subgraph Pods["Application Pods"]
        Pod1["Pod 1<br/>Local Range: 0-1M"]
        Pod2["Pod 2<br/>Local Range: 1M-2M"]
        Pod3["Pod 3<br/>Local Range: 2M-3M"]
    end

    US_Range --> Counter
    EU_Range --> Counter
    IN_Range --> Counter
    Counter --> Pod1
    Counter --> Pod2
    Counter --> Pod3
```

### ID Generation Flow

```mermaid
sequenceDiagram
    participant App as Application Pod
    participant Counter as AtomicLong (Local)
    participant DDB as DynamoDB Counter
    participant Encoder as Base62 Encoder

    Note over App: Startup
    App->>DDB: allocateRange(batchSize=1M)
    DDB->>DDB: Atomic increment
    DDB-->>App: Range [0, 999999]
    App->>Counter: initialize(0)

    Note over App: Generate ID
    loop For each URL
        App->>Counter: getAndIncrement()
        Counter-->>App: 456789
        App->>Encoder: encode(456789)
        Encoder-->>App: "00007Dj"
    end

    Note over App: 90% Depleted
    App->>DDB: prefetchRange(1M)
    DDB-->>App: Range [1000000, 1999999]
```

### Capacity Planning

| Region | Range Size | At 167M/month | Years |
|--------|------------|---------------|-------|
| US-EAST-1 | 1.17 trillion | 584+ years | ∞ |
| EU-WEST-1 | 1.17 trillion | 584+ years | ∞ |
| AP-SOUTH-1 | 1.17 trillion | 584+ years | ∞ |

---

## 🏷️ Custom Aliases

Custom aliases (user-defined slugs) exist in a **separate logical namespace** from auto-generated codes.

### How Custom Aliases Work

```mermaid
flowchart TB
    subgraph Input["User Request"]
        Req["POST /api/v1/urls<br/>{customAlias: 'my-brand'}"]
    end

    subgraph Validation["Validation Pipeline"]
        V1["Format Check<br/>4-50 chars, alphanumeric + hyphens"]
        V2["Reserved Pattern Check<br/>Not 7-char Base62"]
        V3["Global Uniqueness<br/>DynamoDB Global Tables"]
    end

    subgraph Storage["Storage"]
        DB[("DynamoDB<br/>is_custom_alias: true")]
    end

    Req --> V1 --> V2 --> V3 --> DB
```

### Custom vs Auto-Generated

| Aspect | Auto-Generated | Custom Alias |
|--------|----------------|--------------|
| **Format** | 7 chars, Base62 | 4-50 chars, alphanumeric + hyphens |
| **Source** | Regional counter | User input |
| **Uniqueness** | Range-based | Global DB check |
| **Flag** | `is_custom_alias: false` | `is_custom_alias: true` |

### Cross-Region Custom Alias

```mermaid
sequenceDiagram
    participant User as 👤 Mumbai User
    participant IN as 🇮🇳 AP-SOUTH-1
    participant DDB as DynamoDB Global
    participant US as 🇺🇸 US Replica
    participant EU as 🇪🇺 EU Replica

    User->>IN: Create "my-brand"
    IN->>DDB: Check global uniqueness
    par Replicas checked
        DDB->>US: Exists?
        DDB->>EU: Exists?
    end
    US-->>DDB: No
    EU-->>DDB: No
    DDB-->>IN: Unique ✓
    IN->>DDB: Save (is_custom_alias: true)
    Note over DDB: Replicated globally
    IN-->>User: Created ✓
```

> 📖 **Full Documentation**: [docs/CUSTOM_ALIAS_HANDLING.md](docs/CUSTOM_ALIAS_HANDLING.md)

---

## 💾 Caching Strategy

### Write-Through Cache Pattern

```mermaid
flowchart LR
    subgraph Write["Write Path"]
        W1[Create URL] --> W2[Save to DB]
        W2 --> W3[Write to Cache]
        W3 --> W4[Return Response]
    end

    subgraph Read["Read Path"]
        R1[Get URL] --> R2{Cache Hit?}
        R2 -->|Yes| R3[Return from Cache]
        R2 -->|No| R4[Read from DB]
        R4 --> R5[Populate Cache]
        R5 --> R3
    end
```

### Cache Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| TTL | 24 hours | Cache entry lifetime |
| Type | Memory/Redis | Backend storage |
| Pattern | Write-through | Consistent reads |

---

## 🔒 Security

### Authentication Flow

```mermaid
flowchart TD
    A[Incoming Request] --> B{Has Auth Header?}
    B -->|No| C[401 Unauthorized]
    B -->|Yes| D{Auth Type?}
    D -->|Bearer| E[Parse userId:tier]
    D -->|ApiKey| F[Validate API Key]
    E --> G{Valid?}
    F --> G
    G -->|No| C
    G -->|Yes| H[Set SecurityContext]
    H --> I[Rate Limit Check]
    I --> J{Within Limit?}
    J -->|No| K[429 Too Many Requests]
    J -->|Yes| L[Process Request]
```

### API Key Format

```
Format: urlsh_sk_{random_base62_32_chars}
Example: urlsh_sk_7Kj9mN2pQ4rS6tU8vW0xY1zA3bC5dE
```

---

## ⏱️ Rate Limiting

### Tier-Based Limits

```mermaid
graph LR
    subgraph Free["Free Tier"]
        F1["60 req/min"]
        F2["10 char alias"]
    end
    subgraph Premium["Premium Tier"]
        P1["300 req/min"]
        P2["20 char alias"]
    end
    subgraph Enterprise["Enterprise Tier"]
        E1["1000 req/min"]
        E2["50 char alias"]
    end
```

| Tier | Requests/Minute | Custom Alias Length |
|------|-----------------|---------------------|
| **Free** | 60 | 10 characters |
| **Premium** | 300 | 20 characters |
| **Enterprise** | 1000 | 50 characters |

---

## 📊 Monitoring & Observability

### Metrics Flow

```mermaid
flowchart LR
    App[Spring Boot App] -->|/actuator/prometheus| Prom[Prometheus]
    Prom --> Grafana[Grafana]
    Grafana --> Dashboard[Dashboards]
    Grafana --> Alerts[Alerts]
```

### Key Metrics

```prometheus
# HTTP Request metrics
http_server_requests_seconds_count{method="POST",uri="/api/v1/urls"}
http_server_requests_seconds_sum{method="POST",uri="/api/v1/urls"}

# Custom business metrics
url_shortener_urls_created_total
url_shortener_redirects_total
url_shortener_cache_hit_ratio
```

### Grafana Setup

```bash
# Start monitoring stack
docker-compose --profile monitoring up -d

# Access Grafana
open http://localhost:3000
# Username: admin, Password: admin
```

---

## 🗄️ Database Design

### Entity Relationship

```mermaid
erDiagram
    SHORT_URL {
        uuid id PK
        string short_code UK
        string original_url
        string user_id FK
        timestamp created_at
        timestamp expires_at
        bigint click_count
        boolean is_active
        string tier
    }

    CLICK_EVENT {
        uuid event_id PK
        string short_code FK
        timestamp timestamp
        string ip_hash
        string country_code
        string device_type
        string browser
    }

    USER {
        string user_id PK
        string tier
        timestamp created_at
    }

    SHORT_URL ||--o{ CLICK_EVENT : "has"
    USER ||--o{ SHORT_URL : "owns"
```

### Cleanup Policies

| Data Type | Soft Delete | Hard Delete | Archive |
|-----------|-------------|-------------|---------|
| Active URLs | - | - | - |
| Expired URLs | 30 days | 90 days | - |
| Analytics | - | 2 years | S3 Glacier |

---

## 📈 Scaling Tiers

### Evolution Path

```mermaid
flowchart LR
    subgraph T0["Local"]
        L1["1K URLs/month"]
        L2["SQLite + Memory"]
    end
    subgraph T1["Tier 1"]
        T1_1["100K URLs/month"]
        T1_2["PostgreSQL + Memory"]
    end
    subgraph T2["Tier 2"]
        T2_1["10M URLs/month"]
        T2_2["PostgreSQL + Redis"]
    end
    subgraph T3["Tier 3"]
        T3_1["100M URLs/month"]
        T3_2["DynamoDB + Redis Cluster"]
    end
    subgraph T4["Tier 4"]
        T4_1["500M URLs/month"]
        T4_2["DynamoDB Global + ElastiCache"]
    end

    T0 --> T1 --> T2 --> T3 --> T4
```

### Tier 4: Global Architecture

```mermaid
flowchart TB
    Users["👥 Global Users"]

    subgraph DNS["DNS Layer"]
        R53["Route 53<br/>(Latency-based)"]
    end

    subgraph US["🇺🇸 US-EAST-1"]
        US_CF["CloudFront"]
        US_EKS["EKS Cluster"]
        US_Cache["ElastiCache"]
    end

    subgraph EU["🇪🇺 EU-WEST-1"]
        EU_CF["CloudFront"]
        EU_EKS["EKS Cluster"]
        EU_Cache["ElastiCache"]
    end

    subgraph IN["🇮🇳 AP-SOUTH-1"]
        IN_CF["CloudFront"]
        IN_EKS["EKS Cluster"]
        IN_Cache["ElastiCache"]
    end

    subgraph DDB["DynamoDB Global Tables"]
        DDB_US[("US Replica")]
        DDB_EU[("EU Replica")]
        DDB_IN[("IN Replica")]
    end

    Users --> R53
    R53 --> US_CF & EU_CF & IN_CF
    US_CF --> US_EKS --> US_Cache --> DDB_US
    EU_CF --> EU_EKS --> EU_Cache --> DDB_EU
    IN_CF --> IN_EKS --> IN_Cache --> DDB_IN
    DDB_US <--> DDB_EU <--> DDB_IN
```

---

## 🐳 Docker Deployment

### Development

```bash
# Start application only
docker-compose up -d

# Start with Redis cache
docker-compose --profile redis up -d

# Start with monitoring
docker-compose --profile monitoring up -d

# View logs
docker-compose logs -f url-shortener
```

### Production Build

```bash
# Build production image
docker build -f docker/Dockerfile -t url-shortener:latest .

# Run with production settings
docker run -d \
  --name url-shortener \
  -p 8080:8080 \
  -e SPRING_PROFILES_ACTIVE=production \
  url-shortener:latest
```

---

## 🧪 Testing

```bash
# All tests
./mvnw test

# With coverage report
./mvnw test jacoco:report

# Integration tests
./mvnw verify -P integration-test
```

---

## 🔐 GDPR Compliance

### Data Subject Rights

```mermaid
flowchart LR
    User["Data Subject"]

    subgraph Rights["GDPR Rights"]
        Access["Right to Access"]
        Erasure["Right to Erasure"]
        Port["Data Portability"]
    end

    subgraph API["Compliance API"]
        Export["GET /gdpr/export"]
        Delete["DELETE /gdpr/erasure"]
    end

    User --> Rights
    Access --> Export
    Erasure --> Delete
    Port --> Export
```

| Right | Endpoint | Description |
|-------|----------|-------------|
| Access | `GET /api/v1/compliance/gdpr/export` | Export all user data |
| Erasure | `DELETE /api/v1/compliance/gdpr/erasure` | Delete all user data |
| Portability | `GET /api/v1/compliance/gdpr/export?format=csv` | Export in portable format |

---

## 📖 Documentation

Detailed documentation is available in the `docs/` directory:

| Document | Description |
|----------|-------------|
| [GLOBAL_RANGE_ALLOCATION.md](docs/GLOBAL_RANGE_ALLOCATION.md) | How distributed ID generation works across regions |
| [CUSTOM_ALIAS_HANDLING.md](docs/CUSTOM_ALIAS_HANDLING.md) | Custom alias validation and collision prevention |
| [SCALING_GLOBAL_VALIDATION.md](docs/SCALING_GLOBAL_VALIDATION.md) | Scaling strategies for global uniqueness checks |

### Architecture Decisions

```mermaid
mindmap
  root((URL Shortener<br/>Architecture))
    ID Generation
      Base62 Encoding
      Regional Ranges
      Atomic Counters
      Prefetch Strategy
    Custom Aliases
      Format Validation
      Global Uniqueness
      Collision Prevention
    Storage
      DynamoDB Global Tables
      Write-through Cache
      TTL-based Cleanup
    Security
      API Key Auth
      Rate Limiting
      GDPR Compliance
    Observability
      Prometheus Metrics
      Distributed Tracing
      Alerting
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with ❤️ using Java and Spring Boot
</p>
