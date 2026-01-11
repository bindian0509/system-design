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
- [Caching Strategy](#-caching-strategy)
- [Security](#-security)
- [Rate Limiting](#-rate-limiting)
- [Monitoring & Observability](#-monitoring--observability)
- [Database Design](#-database-design)
- [Scaling Tiers](#-scaling-tiers)
- [Docker Deployment](#-docker-deployment)
- [Testing](#-testing)
- [GDPR Compliance](#-gdpr-compliance)
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

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
│   Browser │ Mobile App │ CLI │ API Clients │ Partner Integrations   │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      LOAD BALANCER / CDN                             │
│              CloudFront (Production) / nginx (Development)          │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SPRING BOOT APPLICATION                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │  Security   │  │    Rate     │  │   Request   │                  │
│  │   Filter    │──│   Limiter   │──│    Filter   │                  │
│  └─────────────┘  └─────────────┘  └─────────────┘                  │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                      CONTROLLER LAYER                        │    │
│  │  UrlController │ RedirectController │ AnalyticsController    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                       SERVICE LAYER                          │    │
│  │  UrlService │ IdGenerator │ CacheService │ AnalyticsService  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                     REPOSITORY LAYER                         │    │
│  │              ShortUrlRepository (JPA/DynamoDB)               │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼                   ▼                   ▼
       ┌───────────┐       ┌───────────┐       ┌───────────┐
       │  SQLite/  │       │   Redis   │       │ Prometheus│
       │ DynamoDB  │       │   Cache   │       │  Metrics  │
       └───────────┘       └───────────┘       └───────────┘
```

### Project Structure

```
url-shortener-java/
├── src/
│   ├── main/
│   │   ├── java/com/urlshortener/
│   │   │   ├── UrlShortenerApplication.java    # Application entry point
│   │   │   │
│   │   │   ├── controller/                     # REST API Layer
│   │   │   │   ├── UrlController.java          # URL CRUD operations
│   │   │   │   ├── RedirectController.java     # Redirect handling
│   │   │   │   ├── AnalyticsController.java    # Analytics endpoints
│   │   │   │   └── HealthController.java       # Health probes
│   │   │   │
│   │   │   ├── domain/                         # Domain Models
│   │   │   │   ├── ShortUrl.java               # Core URL entity
│   │   │   │   ├── ClickEvent.java             # Analytics event
│   │   │   │   ├── UserTier.java               # User tier enum
│   │   │   │   └── dto/                        # Data Transfer Objects
│   │   │   │       ├── CreateUrlRequest.java
│   │   │   │       ├── CreateUrlResponse.java
│   │   │   │       ├── UrlResponse.java
│   │   │   │       └── AnalyticsSummary.java
│   │   │   │
│   │   │   ├── service/                        # Business Logic
│   │   │   │   ├── UrlService.java             # URL operations
│   │   │   │   ├── IdGenerator.java            # Base62 ID generation
│   │   │   │   ├── CacheService.java           # Caching abstraction
│   │   │   │   └── AnalyticsService.java       # Click analytics
│   │   │   │
│   │   │   ├── repository/                     # Data Access
│   │   │   │   └── ShortUrlRepository.java     # JPA repository
│   │   │   │
│   │   │   ├── security/                       # Security Layer
│   │   │   │   ├── SecurityConfig.java         # Spring Security config
│   │   │   │   ├── ApiKeyAuthFilter.java       # Authentication filter
│   │   │   │   ├── RateLimitFilter.java        # Rate limiting
│   │   │   │   └── AuthenticatedUser.java      # User principal
│   │   │   │
│   │   │   └── exception/                      # Error Handling
│   │   │       ├── GlobalExceptionHandler.java # Exception handler
│   │   │       ├── UrlShortenerException.java  # Base exception
│   │   │       ├── UrlNotFoundException.java
│   │   │       ├── UrlExpiredException.java
│   │   │       ├── UrlDisabledException.java
│   │   │       ├── InvalidUrlException.java
│   │   │       ├── AliasAlreadyExistsException.java
│   │   │       └── RateLimitExceededException.java
│   │   │
│   │   └── resources/
│   │       └── application.yml                 # Configuration
│   │
│   └── test/java/com/urlshortener/            # Test classes
│
├── docker/
│   ├── Dockerfile                              # Production build
│   └── Dockerfile.dev                          # Development build
│
├── config/
│   └── prometheus.yml                          # Prometheus config
│
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
  "customAlias": "my-link",        // Optional: 4-50 chars
  "ttlSeconds": 86400,             // Optional: 60 - 31,536,000
  "title": "My Link",              // Optional: max 500 chars
  "description": "Description",    // Optional: max 2000 chars
  "tags": ["marketing", "2024"]    // Optional: max 10 tags
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

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "shortCode": "my-link",
  "shortUrl": "http://localhost:8080/my-link",
  "originalUrl": "https://example.com/very/long/url",
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T10:30:00Z",
  "expiresAt": "2024-01-16T10:30:00Z",
  "clickCount": 42,
  "isActive": true,
  "title": "My Link",
  "description": "Description",
  "tags": ["marketing", "2024"]
}
```

#### List User's URLs

```http
GET /api/v1/urls?page=0&size=20
```

**Response (200 OK):**
```json
{
  "content": [...],
  "page": 0,
  "size": 20,
  "totalElements": 150,
  "totalPages": 8,
  "hasNext": true,
  "hasPrevious": false
}
```

#### Delete URL

```http
DELETE /api/v1/urls/{code}
```

**Response: 204 No Content**

#### Redirect

```http
GET /{code}
```

**Response: 308 Permanent Redirect**
```
Location: https://example.com/very/long/url
Cache-Control: public, max-age=86400
```

#### Get Analytics

```http
GET /api/v1/analytics/{code}
```

**Response (200 OK):**
```json
{
  "shortCode": "my-link",
  "totalClicks": 1250,
  "uniqueVisitors": 890,
  "clicksToday": 45,
  "clicksThisWeek": 312,
  "clicksThisMonth": 1100,
  "topCountries": [
    {"countryCode": "US", "countryName": "United States", "clicks": 450, "percentage": 36.0},
    {"countryCode": "GB", "countryName": "United Kingdom", "clicks": 200, "percentage": 16.0}
  ],
  "topReferrers": [
    {"referrer": "twitter.com", "clicks": 380, "percentage": 30.4},
    {"referrer": "direct", "clicks": 290, "percentage": 23.2}
  ],
  "deviceBreakdown": {
    "desktop": 625,
    "mobile": 500,
    "tablet": 100,
    "other": 25
  }
}
```

#### Health Endpoints

```http
GET /health              # Liveness probe
GET /ready               # Readiness probe
GET /actuator/prometheus # Prometheus metrics
```

### Error Responses

```json
{
  "code": "URL_NOT_FOUND",
  "message": "URL not found: abc123",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `URL_NOT_FOUND` | 404 | Short URL doesn't exist |
| `URL_EXPIRED` | 410 | URL has expired |
| `URL_DISABLED` | 403 | URL has been disabled |
| `INVALID_URL` | 400 | Invalid URL format |
| `ALIAS_TAKEN` | 409 | Custom alias already exists |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `VALIDATION_ERROR` | 400 | Request validation failed |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SPRING_PROFILES_ACTIVE` | `local` | Active profile: `local`, `development`, `production` |
| `DATABASE_URL` | `jdbc:sqlite:./data/urls.db` | Database connection string |
| `CACHE_TYPE` | `memory` | Cache type: `memory` or `redis` |
| `REDIS_HOST` | `localhost` | Redis server host |
| `REDIS_PORT` | `6379` | Redis server port |
| `BASE_URL` | `http://localhost:8080` | Public URL for generated short links |
| `LOG_LEVEL` | `DEBUG` | Logging level for application |
| `AWS_ENABLED` | `false` | Enable AWS services (DynamoDB, etc.) |
| `AWS_REGION` | `us-east-1` | AWS region |

### Application Profiles

#### Local Profile (Default)
```yaml
# SQLite database, in-memory cache
spring.profiles.active: local
```

#### Development Profile
```yaml
# SQLite database, Redis cache, LocalStack AWS
spring.profiles.active: development
```

#### Production Profile
```yaml
# DynamoDB, Redis cluster, full AWS
spring.profiles.active: production
```

### Configuration File

```yaml
# application.yml
url-shortener:
  base-url: ${BASE_URL:http://localhost:8080}
  code-length: 7

  id-generator:
    range-size: 1000000        # IDs per batch
    prefetch-threshold: 0.9    # Prefetch at 90%

  cache:
    type: ${CACHE_TYPE:memory}
    ttl-seconds: 86400         # 24 hours

  rate-limit:
    enabled: true
    requests-per-minute: 60

  url:
    default-ttl-days: 365
    max-url-length: 4096
```

---

## 🔢 ID Generation & Range Allocation

### Overview

The ID generator uses **Base62 encoding** with **distributed range allocation** to ensure:
- **Zero coordination** for most writes
- **Guaranteed uniqueness** across all instances
- **High throughput** (millions of IDs/second)
- **Predictable, sequential** codes (cache-friendly)

### How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DISTRIBUTED COUNTER ALLOCATION                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  DynamoDB Counter Table (Single Source of Truth):                   │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  PK: COUNTER                                                │     │
│  │  current_value: 5,000,000,000                              │     │
│  │  last_allocated: 2024-01-15T10:30:00Z                      │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
│  Instance 1             Instance 2             Instance 3           │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      │
│  │ Range:       │      │ Range:       │      │ Range:       │      │
│  │ 1B - 1.001B  │      │ 1.001B-1.002B│      │ 1.002B-1.003B│      │
│  │ Counter:     │      │ Counter:     │      │ Counter:     │      │
│  │ 1,000,234,567│      │ 1,001,500,000│      │ 1,002,100,000│      │
│  └──────────────┘      └──────────────┘      └──────────────┘      │
│       │                      │                      │               │
│       ▼                      ▼                      ▼               │
│   Atomic                 Atomic                 Atomic              │
│   Increment              Increment              Increment           │
│       │                      │                      │               │
│       ▼                      ▼                      ▼               │
│   Base62                 Base62                 Base62              │
│   Encode                 Encode                 Encode              │
│       │                      │                      │               │
│       ▼                      ▼                      ▼               │
│   "0LY7VK3"              "0LY9AB2"              "0LYCD45"           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Capacity Calculation

```
Base62 Character Set: 0-9, a-z, A-Z (62 characters)

Code Length: 7 characters
Capacity: 62^7 = 3,521,614,606,208 unique codes

At 500M URLs/month:
  Years of capacity = 3.5 trillion / (500M × 12) ≈ 584 years

At 500M URLs/day:
  Years of capacity = 3.5 trillion / (500M × 365) ≈ 19 years
```

### Code Example

```java
@Component
public class IdGenerator {

    private static final String CHARSET =
        "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";

    private final AtomicLong counter = new AtomicLong(0);
    private volatile long rangeStart = 0;
    private volatile long rangeEnd = Long.MAX_VALUE;

    public String generate() {
        long value = counter.getAndIncrement();

        if (value >= rangeEnd) {
            refreshRange();  // Get new range from DynamoDB
        }

        return encode(value);
    }

    public String encode(long num) {
        StringBuilder sb = new StringBuilder();
        while (num > 0) {
            sb.insert(0, CHARSET.charAt((int)(num % 62)));
            num /= 62;
        }
        return pad(sb.toString(), 7);
    }
}
```

---

## 💾 Caching Strategy

### Write-Through Cache

```
┌─────────────────────────────────────────────────────────────────────┐
│                      WRITE-THROUGH CACHING                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  CREATE URL Request                                                  │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────┐                                                    │
│  │ URL Service │                                                    │
│  └──────┬──────┘                                                    │
│         │                                                            │
│         ├──────────────────┬──────────────────┐                     │
│         │                  │                  │                      │
│         ▼                  ▼                  ▼                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │  Database   │    │    Cache    │    │  Response   │             │
│  │   (Write)   │    │   (Write)   │    │  (Return)   │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
│                                                                      │
│  REDIRECT Request                                                    │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────┐                                                    │
│  │    Cache    │──── Hit ────▶ Return URL                           │
│  │   (Read)    │                                                    │
│  └──────┬──────┘                                                    │
│         │                                                            │
│       Miss                                                           │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────┐                                                    │
│  │  Database   │──── Found ───▶ Cache + Return                      │
│  │   (Read)    │                                                    │
│  └─────────────┘                                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
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

```
Request
   │
   ▼
┌─────────────────────────────────────────┐
│          ApiKeyAuthFilter               │
├─────────────────────────────────────────┤
│ 1. Extract Authorization header         │
│ 2. Detect auth type (Bearer/ApiKey)     │
│ 3. Validate credentials                 │
│ 4. Set SecurityContext                  │
└─────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────┐
│          RateLimitFilter                │
├─────────────────────────────────────────┤
│ 1. Get identifier (user/IP)             │
│ 2. Check rate limit                     │
│ 3. Add rate limit headers               │
│ 4. Reject if exceeded                   │
└─────────────────────────────────────────┘
   │
   ▼
Controller
```

### API Key Format

```
Format: urlsh_sk_{random_base62_32_chars}
Example: urlsh_sk_7Kj9mN2pQ4rS6tU8vW0xY1zA3bC5dE

Prefix: urlsh_sk_  (identifies as URL Shortener secret key)
Random: 32 Base62 characters (192 bits of entropy)
```

### Security Headers

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

---

## ⏱️ Rate Limiting

### Tier-Based Limits

| Tier | Requests/Minute | Burst Size | Custom Alias Length |
|------|-----------------|------------|---------------------|
| **Free** | 60 | 100 | 10 characters |
| **Premium** | 300 | 500 | 20 characters |
| **Enterprise** | 1000 | 2000 | 50 characters |

### Response Headers

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1705312260
```

### Rate Limit Exceeded Response

```json
{
  "error": "Rate limit exceeded",
  "code": "RATE_LIMITED",
  "retryAfter": 60
}
```

---

## 📊 Monitoring & Observability

### Metrics Endpoints

| Endpoint | Description |
|----------|-------------|
| `/actuator/prometheus` | Prometheus metrics |
| `/actuator/health` | Health information |
| `/actuator/info` | Application info |
| `/actuator/metrics` | All metrics |

### Key Metrics

```prometheus
# HTTP Request metrics
http_server_requests_seconds_count{method="POST",uri="/api/v1/urls",status="201"}
http_server_requests_seconds_sum{method="POST",uri="/api/v1/urls",status="201"}

# JVM metrics
jvm_memory_used_bytes{area="heap"}
jvm_threads_live_threads

# Custom business metrics
url_shortener_urls_created_total
url_shortener_redirects_total
url_shortener_cache_hit_ratio
```

### Grafana Dashboard Setup

1. Start monitoring stack:
   ```bash
   docker-compose --profile monitoring up -d
   ```

2. Access Grafana: http://localhost:3000
   - Username: `admin`
   - Password: `admin`

3. Add Prometheus data source:
   - URL: `http://url-shortener-prometheus:9090`

4. Create dashboard with panels:
   - Request rate
   - Response times (p50, p95, p99)
   - Error rate
   - Cache hit ratio
   - JVM memory

---

## 🗄️ Database Design

### ShortUrl Entity

```sql
CREATE TABLE urls (
    id              UUID PRIMARY KEY,
    short_code      VARCHAR(50) NOT NULL UNIQUE,
    original_url    VARCHAR(4096) NOT NULL,
    user_id         VARCHAR(255),
    created_at      TIMESTAMP NOT NULL,
    updated_at      TIMESTAMP NOT NULL,
    expires_at      TIMESTAMP,
    last_accessed_at TIMESTAMP,
    click_count     BIGINT DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    is_custom_alias BOOLEAN DEFAULT FALSE,
    tier            VARCHAR(20) NOT NULL,
    title           VARCHAR(500),
    description     VARCHAR(2000),
    metadata        TEXT
);

CREATE INDEX idx_short_code ON urls(short_code);
CREATE INDEX idx_user_id ON urls(user_id);
CREATE INDEX idx_created_at ON urls(created_at);
```

### Cleanup Policies

| Data Type | Soft Delete | Hard Delete | Archive |
|-----------|-------------|-------------|---------|
| Active URLs | - | - | - |
| Expired URLs | 30 days | 90 days | - |
| Deleted URLs | Immediate | 30 days | - |
| Analytics | - | 2 years | S3 Glacier |

---

## 📈 Scaling Tiers

### Tier Overview

| Tier | URLs/Month | Architecture | Database | Cache |
|------|------------|--------------|----------|-------|
| **Local** | 1K | Single instance | SQLite | Memory |
| **Tier 1** | 100K | Single instance | PostgreSQL | Memory |
| **Tier 2** | 10M | Multi-instance | PostgreSQL | Redis |
| **Tier 3** | 100M | Kubernetes | DynamoDB | Redis Cluster |
| **Tier 4** | 500M | Multi-region | DynamoDB Global | ElastiCache Global |

### Tier 4: Global Architecture

```
                    ┌─────────────────┐
                    │   Route 53      │
                    │ (Latency-based) │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  US-EAST-1    │   │  EU-WEST-1    │   │  AP-SOUTH-1   │
│  CloudFront   │   │  CloudFront   │   │  CloudFront   │
│       +       │   │       +       │   │       +       │
│  Lambda@Edge  │   │  Lambda@Edge  │   │  Lambda@Edge  │
│       +       │   │       +       │   │       +       │
│     EKS       │   │     EKS       │   │     EKS       │
│       +       │   │       +       │   │       +       │
│ ElastiCache   │   │ ElastiCache   │   │ ElastiCache   │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                ┌───────────┴───────────┐
                │  DynamoDB Global      │
                │  Tables (Active-Active)│
                └───────────────────────┘
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

# Start everything
docker-compose --profile redis --profile monitoring up -d

# View logs
docker-compose logs -f url-shortener

# Stop all
docker-compose down
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
  -e DATABASE_URL=jdbc:postgresql://db:5432/urls \
  -e REDIS_HOST=redis \
  -e BASE_URL=https://short.example.com \
  url-shortener:latest
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: url-shortener
spec:
  replicas: 3
  selector:
    matchLabels:
      app: url-shortener
  template:
    metadata:
      labels:
        app: url-shortener
    spec:
      containers:
      - name: url-shortener
        image: url-shortener:latest
        ports:
        - containerPort: 8080
        env:
        - name: SPRING_PROFILES_ACTIVE
          value: "production"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

---

## 🧪 Testing

### Run Tests

```bash
# All tests
./mvnw test

# With coverage report
./mvnw test jacoco:report
# Report: target/site/jacoco/index.html

# Integration tests
./mvnw verify -P integration-test

# Specific test class
./mvnw test -Dtest=IdGeneratorTest
```

### Test Categories

| Type | Location | Description |
|------|----------|-------------|
| Unit | `src/test/java` | Service and utility tests |
| Integration | `src/test/java` | Repository and API tests |
| E2E | `src/test/java` | Full flow tests |

---

## 🔐 GDPR Compliance

### Data Subject Rights

| Right | Endpoint | Description |
|-------|----------|-------------|
| Access | `GET /api/v1/compliance/gdpr/export` | Export all user data |
| Erasure | `DELETE /api/v1/compliance/gdpr/erasure` | Delete all user data |
| Portability | `GET /api/v1/compliance/gdpr/export?format=csv` | Export in portable format |

### Data Retention

- Active URLs: Until deleted or expired
- Deleted URLs: Hard deleted after 30 days
- Analytics: Anonymized after 2 years
- Audit Logs: Retained for 7 years

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
