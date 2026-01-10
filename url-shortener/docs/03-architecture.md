# System Architecture

This document describes the detailed architecture of the URL shortener system, including component design, data flows, and key architectural decisions.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ Browser  │  │ Mobile   │  │   CLI    │  │   API    │  │ Partner  │           │
│  │  Users   │  │   Apps   │  │  Tools   │  │ Clients  │  │ Integr.  │           │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘           │
└───────┼─────────────┼─────────────┼─────────────┼─────────────┼─────────────────┘
        │             │             │             │             │
        └─────────────┴─────────────┴──────┬──────┴─────────────┘
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EDGE LAYER                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                        CloudFront CDN (200+ PoPs)                       │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │     │
│  │  │ Edge Cache  │  │ Lambda@Edge │  │   AWS WAF   │  │AWS Shield   │    │     │
│  │  │  (Hot URLs) │  │ (Redirects) │  │  (Firewall) │  │(DDoS Prot.) │    │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │     │
│  └────────────────────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────┬────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY LAYER                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                    Application Load Balancer (ALB)                      │     │
│  │  • SSL/TLS Termination  • Health Checks  • Request Routing              │     │
│  └────────────────────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────┬────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              APPLICATION LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                     EKS Cluster (Kubernetes)                             │    │
│  │  ┌───────────────────────────────────────────────────────────────┐      │    │
│  │  │                   URL Shortener Service                        │      │    │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │      │    │
│  │  │  │  Pod 1   │  │  Pod 2   │  │  Pod 3   │  │  Pod N   │       │      │    │
│  │  │  │ (Axum)   │  │ (Axum)   │  │ (Axum)   │  │ (Axum)   │       │      │    │
│  │  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │      │    │
│  │  └───────────────────────────────────────────────────────────────┘      │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────┬────────────────────────────────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              │                              │                              │
              ▼                              ▼                              ▼
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│      CACHE LAYER        │  │      DATA LAYER         │  │     ANALYTICS LAYER     │
│  ┌───────────────────┐  │  │  ┌───────────────────┐  │  │  ┌───────────────────┐  │
│  │   ElastiCache     │  │  │  │    DynamoDB       │  │  │  │  Kinesis Streams  │  │
│  │   (Redis Cluster) │  │  │  │  (Global Tables)  │  │  │  │  (Click Events)   │  │
│  │                   │  │  │  │                   │  │  │  │                   │  │
│  │  • URL mappings   │  │  │  │  • URLs           │  │  │  │         │         │  │
│  │  • Rate limits    │  │  │  │  • Users          │  │  │  │         ▼         │  │
│  │  • Session cache  │  │  │  │  • Analytics      │  │  │  │  ┌─────────────┐  │  │
│  └───────────────────┘  │  │  │  • Audit logs     │  │  │  │  │  Lambda     │  │  │
└─────────────────────────┘  │  └───────────────────┘  │  │  │  │ Processors  │  │  │
                             └─────────────────────────┘  │  │  └──────┬──────┘  │  │
                                                          │  │         │         │  │
                                                          │  │         ▼         │  │
                                                          │  │  ┌─────────────┐  │  │
                                                          │  │  │ Timestream  │  │  │
                                                          │  │  │ (Analytics) │  │  │
                                                          │  │  └─────────────┘  │  │
                                                          │  └───────────────────┘  │
                                                          └─────────────────────────┘
```

---

## Component Architecture

### 1. Edge Layer (CloudFront + Lambda@Edge)

The edge layer handles the majority of redirect traffic with ultra-low latency.

```
Request Flow at Edge:

User Request                  Lambda@Edge                    Origin
    │                             │                            │
    │  GET /abc123X               │                            │
    │────────────────────────────▶│                            │
    │                             │                            │
    │                       ┌─────┴─────┐                      │
    │                       │ Check     │                      │
    │                       │ Edge Cache│                      │
    │                       └─────┬─────┘                      │
    │                             │                            │
    │                    Cache Hit│Cache Miss                  │
    │                    ┌────────┴────────┐                   │
    │                    │                 │                   │
    │              ┌─────▼─────┐     ┌─────▼─────┐             │
    │              │ Return    │     │ Forward   │             │
    │              │ Redirect  │     │ to Origin │─────────────▶
    │              └─────┬─────┘     └───────────┘             │
    │                    │                                     │
    │◀───────────────────┘                                     │
    │  301 Redirect                                            │
```

**Lambda@Edge Functions:**

| Function | Trigger | Purpose |
|----------|---------|---------|
| `viewer-request` | Before cache check | Authentication, rate limiting |
| `origin-request` | On cache miss | Modify request to origin |
| `origin-response` | After origin response | Cache headers, error handling |
| `viewer-response` | Before response to user | Analytics headers |

### 2. API Layer (Axum Application)

The core application is built with Rust and the Axum framework.

```
┌────────────────────────────────────────────────────────────────────┐
│                        AXUM APPLICATION                             │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                         ROUTER                                 │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │  │
│  │  │  /api/v1/*  │ │    /:code   │ │  /health    │              │  │
│  │  │  (API)      │ │ (Redirect)  │ │  (Health)   │              │  │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘              │  │
│  └─────────┼───────────────┼───────────────┼─────────────────────┘  │
│            │               │               │                        │
│  ┌─────────▼───────────────▼───────────────▼─────────────────────┐  │
│  │                      MIDDLEWARE STACK                          │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │  │
│  │  │   Tracing  │ │ Rate Limit │ │    Auth    │ │  Metrics   │  │  │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                         HANDLERS                               │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │  │
│  │  │    URL      │ │  Analytics  │ │   Admin     │              │  │
│  │  │  Handlers   │ │  Handlers   │ │  Handlers   │              │  │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘              │  │
│  └─────────┼───────────────┼───────────────┼─────────────────────┘  │
│            │               │               │                        │
│  ┌─────────▼───────────────▼───────────────▼─────────────────────┐  │
│  │                      DOMAIN LAYER                              │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │  │
│  │  │    URL      │ │  Analytics  │ │  Compliance │              │  │
│  │  │   Service   │ │   Service   │ │   Service   │              │  │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘              │  │
│  └─────────┼───────────────┼───────────────┼─────────────────────┘  │
│            │               │               │                        │
│  ┌─────────▼───────────────▼───────────────▼─────────────────────┐  │
│  │                   INFRASTRUCTURE LAYER                         │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │  │
│  │  │DynamoDB │ │  Redis  │ │   S3    │ │ Kinesis │ │   SES   │ │  │
│  │  │ Client  │ │ Client  │ │ Client  │ │ Client  │ │ Client  │ │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │  │
│  └───────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### 3. Data Layer

#### DynamoDB Table Design

**URLs Table (Main)**

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `pk` | String | PK | `URL#<short_code>` |
| `sk` | String | SK | `v0` (version) |
| `original_url` | String | - | Destination URL |
| `created_at` | Number | - | Unix timestamp |
| `expires_at` | Number | GSI1-PK | TTL for expiration |
| `user_id` | String | GSI2-PK | Owner's user ID |
| `tier` | String | - | free/premium/enterprise |
| `click_count` | Number | - | Atomic counter |
| `is_active` | Boolean | - | Soft delete flag |
| `custom_alias` | Boolean | - | Was this a custom code |
| `metadata` | Map | - | Tags, notes, etc. |

**Access Patterns:**

| Pattern | Keys | Use Case |
|---------|------|----------|
| Get URL by code | PK = `URL#abc123X` | Redirect lookup |
| List user's URLs | GSI2-PK = user_id | Dashboard |
| Find expiring URLs | GSI1-PK < current_time | Cleanup |

**Global Secondary Indexes:**

```
GSI1: expires_at-index
  PK: expires_at (sparse - only if set)
  SK: pk
  Projection: short_code, original_url

GSI2: user_id-index
  PK: user_id
  SK: created_at
  Projection: ALL
```

### 4. Analytics Pipeline

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Click      │    │   Kinesis    │    │    Lambda    │    │  Timestream  │
│   Event      │───▶│   Stream     │───▶│  Processor   │───▶│   Database   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                              │
                                              ▼
                                        ┌──────────────┐
                                        │  S3 (Raw)    │
                                        │  Archives    │
                                        └──────────────┘

Click Event Schema:
{
  "event_id": "uuid",
  "short_code": "abc123X",
  "timestamp": 1704067200000,
  "ip_hash": "sha256(...)",      // Privacy-preserving
  "country": "US",
  "region": "California",
  "city": "San Francisco",
  "referrer": "https://twitter.com",
  "user_agent": "Mozilla/5.0...",
  "device_type": "mobile",
  "browser": "Chrome",
  "os": "iOS",
  "is_bot": false
}
```

---

## Data Flow Diagrams

### URL Creation Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │     │   ALB    │     │  Service │     │   Redis  │     │ DynamoDB │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │ POST /api/v1/urls               │                │                │
     │───────────────▶│                │                │                │
     │                │ Forward        │                │                │
     │                │───────────────▶│                │                │
     │                │                │                │                │
     │                │                │ Validate URL   │                │
     │                │                │───────┐        │                │
     │                │                │       │        │                │
     │                │                │◀──────┘        │                │
     │                │                │                │                │
     │                │                │ Generate Code  │                │
     │                │                │───────┐        │                │
     │                │                │       │        │                │
     │                │                │◀──────┘        │                │
     │                │                │                │                │
     │                │                │ Check exists   │                │
     │                │                │───────────────▶│                │
     │                │                │                │                │
     │                │                │ Not found      │                │
     │                │                │◀───────────────│                │
     │                │                │                │                │
     │                │                │ Write to cache │                │
     │                │                │───────────────▶│                │
     │                │                │                │                │
     │                │                │ ACK            │                │
     │                │                │◀───────────────│                │
     │                │                │                │                │
     │                │                │ Write to DB    │                │
     │                │                │────────────────────────────────▶│
     │                │                │                │                │
     │                │                │ ACK            │                │
     │                │                │◀────────────────────────────────│
     │                │                │                │                │
     │                │ 201 Created    │                │                │
     │                │◀───────────────│                │                │
     │ Response       │                │                │                │
     │◀───────────────│                │                │                │
```

### URL Redirect Flow (Edge)

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │     │CloudFront│     │Lambda@   │     │  Redis   │     │  Origin  │
│          │     │          │     │Edge      │     │ (Global) │     │ (EKS)    │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │ GET /abc123X   │                │                │                │
     │───────────────▶│                │                │                │
     │                │                │                │                │
     │                │ Viewer Request │                │                │
     │                │───────────────▶│                │                │
     │                │                │                │                │
     │                │                │ Check Cache    │                │
     │                │                │───────────────▶│                │
     │                │                │                │                │
     │                │                │ Cache Hit!     │                │
     │                │                │◀───────────────│                │
     │                │                │                │                │
     │                │ 301 Redirect   │                │                │
     │                │◀───────────────│                │                │
     │ 301 Redirect   │                │                │                │
     │◀───────────────│                │                │                │
     │                │                │                │                │
     │                │                │ Async: Send    │                │
     │                │                │ click event    │                │
     │                │                │────────────────────────────────▶│
```

### Cache Miss Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │     │CloudFront│     │   ALB    │     │   EKS    │     │ DynamoDB │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │ GET /xyz789Z   │                │                │                │
     │───────────────▶│                │                │                │
     │                │                │                │                │
     │                │ Cache Miss     │                │                │
     │                │───────────────▶│                │                │
     │                │                │                │                │
     │                │                │ Forward        │                │
     │                │                │───────────────▶│                │
     │                │                │                │                │
     │                │                │                │ Get URL        │
     │                │                │                │───────────────▶│
     │                │                │                │                │
     │                │                │                │ URL Data       │
     │                │                │                │◀───────────────│
     │                │                │                │                │
     │                │                │ 301 + Headers  │                │
     │                │                │◀───────────────│                │
     │                │                │                │                │
     │                │ Cache Response │                │                │
     │                │◀───────────────│                │                │
     │ 301 Redirect   │                │                │                │
     │◀───────────────│                │                │                │
```

---

## Multi-Region Architecture

### Active-Active Deployment

```
                          ┌────────────────────────────────┐
                          │        Route 53 (DNS)          │
                          │   Latency-based + Health       │
                          └───────────────┬────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
                    ▼                     ▼                     ▼
        ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
        │    US-EAST-1      │ │    EU-WEST-1      │ │    AP-SOUTH-1     │
        │   (Primary)       │ │   (Secondary)     │ │   (Secondary)     │
        ├───────────────────┤ ├───────────────────┤ ├───────────────────┤
        │                   │ │                   │ │                   │
        │  ┌─────────────┐  │ │  ┌─────────────┐  │ │  ┌─────────────┐  │
        │  │     ALB     │  │ │  │     ALB     │  │ │  │     ALB     │  │
        │  └──────┬──────┘  │ │  └──────┬──────┘  │ │  └──────┬──────┘  │
        │         │         │ │         │         │ │         │         │
        │  ┌──────▼──────┐  │ │  ┌──────▼──────┐  │ │  ┌──────▼──────┐  │
        │  │     EKS     │  │ │  │     EKS     │  │ │  │     EKS     │  │
        │  │  (3 nodes)  │  │ │  │  (3 nodes)  │  │ │  │  (3 nodes)  │  │
        │  └──────┬──────┘  │ │  └──────┬──────┘  │ │  └──────┬──────┘  │
        │         │         │ │         │         │ │         │         │
        │  ┌──────▼──────┐  │ │  ┌──────▼──────┐  │ │  ┌──────▼──────┐  │
        │  │ ElastiCache │  │ │  │ ElastiCache │  │ │  │ ElastiCache │  │
        │  │   Redis     │  │ │  │   Redis     │  │ │  │   Redis     │  │
        │  └─────────────┘  │ │  └─────────────┘  │ │  └─────────────┘  │
        │                   │ │                   │ │                   │
        └─────────┬─────────┘ └─────────┬─────────┘ └─────────┬─────────┘
                  │                     │                     │
                  └──────────────┬──────┴─────────────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │   DynamoDB Global Tables     │
                  │                              │
                  │  ┌────────┐ ┌────────┐ ┌────────┐
                  │  │us-east │◀▶│eu-west │◀▶│ap-south│
                  │  └────────┘ └────────┘ └────────┘
                  │                              │
                  │  • Automatic replication     │
                  │  • ~1 second propagation     │
                  │  • Conflict resolution       │
                  └──────────────────────────────┘
```

### Conflict Resolution Strategy

DynamoDB Global Tables use "last writer wins" conflict resolution. Our application handles conflicts by:

1. **URL Creation**: Short codes are unique; conflicts are impossible for generated codes
2. **Click Counts**: Use atomic counters; conflicts are resolved automatically
3. **Metadata Updates**: Timestamp-based; latest update wins
4. **Deletion**: Propagates across all regions within ~1 second

---

## Caching Strategy

### Cache Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CACHE HIERARCHY                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Layer 1: CloudFront Edge Cache (200+ locations)                    │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  • TTL: 86400s (24 hours) for redirects                        │ │
│  │  • Cache key: URL path only (no query string)                  │ │
│  │  • Hit rate target: 60-70%                                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  Layer 2: Regional Redis Cluster (per region)                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  • TTL: 86400s (24 hours)                                      │ │
│  │  • Data: URL mappings, rate limit counters, session cache      │ │
│  │  • Hit rate target: 30-35% (of edge misses)                    │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  Layer 3: DynamoDB DAX (optional)                                   │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  • TTL: 300s (5 minutes)                                       │ │
│  │  • Hit rate target: 5-10% (of Redis misses)                    │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  Layer 4: DynamoDB (source of truth)                                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  • Strongly consistent reads when needed                       │ │
│  │  • Eventually consistent for redirects (acceptable)            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Cache Invalidation

| Event | Invalidation Strategy |
|-------|----------------------|
| URL Deleted | Immediate invalidation at all layers |
| URL Disabled | Immediate invalidation at all layers |
| URL Updated | Write-through (update cache + DB simultaneously) |
| URL Expired | DynamoDB TTL handles removal; cache naturally expires |

---

## Security Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SECURITY PERIMETER                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    AWS Shield Advanced                        │   │
│  │          (DDoS Protection - Layer 3/4/7)                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                       AWS WAF                                 │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │   │
│  │  │ Rate Limit  │ │ SQL Inject  │ │ XSS Filter  │             │   │
│  │  │   Rules     │ │  Detection  │ │   Rules     │             │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘             │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │   │
│  │  │ Geo Block   │ │ Bot Control │ │ IP Rep.     │             │   │
│  │  │   Rules     │ │   Rules     │ │   Lists     │             │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   VPC Security                                │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │   │
│  │  │ Public      │ │ Private     │ │ Data        │             │   │
│  │  │ Subnets     │ │ Subnets     │ │ Subnets     │             │   │
│  │  │ (ALB only)  │ │ (EKS)       │ │ (Redis, DB) │             │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘             │   │
│  │                                                               │   │
│  │  Security Groups:                                             │   │
│  │  • ALB: 443/tcp from 0.0.0.0/0                               │   │
│  │  • EKS: 8080/tcp from ALB SG only                            │   │
│  │  • Redis: 6379/tcp from EKS SG only                          │   │
│  │  • (DynamoDB via VPC Endpoint - no public access)            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                 Application Security                          │   │
│  │  • mTLS between services                                      │   │
│  │  • API keys hashed with Argon2                               │   │
│  │  • JWT with RS256 signatures                                  │   │
│  │  • Request signing for internal calls                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   Data Security                               │   │
│  │  • DynamoDB: Encrypted at rest (AES-256)                     │   │
│  │  • Redis: Encrypted at rest + in-transit                      │   │
│  │  • S3: SSE-KMS encryption                                     │   │
│  │  • Secrets: AWS Secrets Manager                               │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ID Generation Algorithm

### Base62 Encoding

```rust
// Character set: 0-9, a-z, A-Z (62 characters)
const CHARSET: &[u8] = b"0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
const CODE_LENGTH: usize = 7;

// 62^7 = 3,521,614,606,208 unique codes
// At 500M/month = 7,000 years of capacity

Algorithm:
1. Get next ID from distributed counter
2. Encode to Base62
3. Pad to 7 characters if needed
4. Verify uniqueness (collision check)
5. Retry with random suffix if collision

Example:
  Counter: 1,234,567,890
  Base62:  "1ly7vk" (padded to "01ly7vk")
```

### Distributed Counter Implementation

```
┌────────────────────────────────────────────────────────────────────┐
│                    COUNTER ALLOCATION                               │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  DynamoDB Counter Table:                                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  PK: COUNTER                                                  │  │
│  │  current_value: 1,234,567,890,000                            │  │
│  │  last_allocated: 2024-01-15T10:30:00Z                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Allocation Strategy:                                               │
│  1. Each instance requests a batch of 1,000,000 IDs               │
│  2. Atomic increment in DynamoDB                                   │
│  3. Instance generates codes from its allocated range              │
│  4. Request new batch when 90% depleted                            │
│                                                                     │
│  Benefits:                                                          │
│  • No coordination for most writes                                  │
│  • Atomic operation prevents duplicates                             │
│  • Predictable, sequential IDs (helps cache locality)             │
│                                                                     │
│  Instance Memory:                                                   │
│  ┌────────────────────┐                                            │
│  │ start: 1,234,567M  │                                            │
│  │ end:   1,235,567M  │                                            │
│  │ current: 1,234,890M│                                            │
│  └────────────────────┘                                            │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

---

## Failure Modes and Recovery

### Failure Scenarios

| Failure | Impact | Detection | Recovery |
|---------|--------|-----------|----------|
| Single Pod | None (load balanced) | Health check | Auto-restart |
| AZ Outage | Minimal (multi-AZ) | CloudWatch | Automatic failover |
| Region Outage | Traffic shifts | Route53 health | DNS failover (~60s) |
| Redis Failure | Higher latency | Connection errors | Fallback to DB |
| DynamoDB Throttle | Requests queued | CloudWatch | Auto-scale, retry |
| CloudFront Outage | Global impact | External monitoring | AWS incident |

### Circuit Breaker Pattern

```rust
// Circuit breaker states:
// CLOSED -> Normal operation
// OPEN -> Failing, reject requests immediately
// HALF_OPEN -> Testing if service recovered

struct CircuitBreaker {
    state: State,
    failure_count: u32,
    failure_threshold: u32,    // 5 failures
    success_threshold: u32,    // 3 successes
    timeout: Duration,         // 30 seconds
    last_failure: Instant,
}

// Usage in Redis calls:
match circuit_breaker.call(|| redis.get(key)).await {
    Ok(value) => value,
    Err(CircuitOpen) => {
        // Fallback to DynamoDB
        dynamodb.get(key).await
    }
}
```

---

## Performance Optimizations

### Connection Pooling

```rust
// DynamoDB: SDK handles pooling internally
// Redis: Use connection pool
let redis_pool = Pool::builder()
    .max_size(100)           // 100 connections per instance
    .min_idle(10)            // Keep 10 warm
    .connection_timeout(Duration::from_millis(100))
    .build(redis_manager)?;

// HTTP client for external calls
let http_client = reqwest::Client::builder()
    .pool_max_idle_per_host(50)
    .timeout(Duration::from_secs(5))
    .build()?;
```

### Batch Operations

```rust
// Batch write to DynamoDB (up to 25 items)
dynamodb.batch_write_item()
    .request_items("urls", write_requests)
    .send()
    .await?;

// Pipeline Redis commands
let mut pipe = redis::pipe();
for code in codes {
    pipe.get(code);
}
let results: Vec<Option<String>> = pipe.query_async(&mut conn).await?;
```

### Async Everywhere

```rust
// All I/O is non-blocking
async fn redirect(
    State(state): State<AppState>,
    Path(code): Path<String>,
) -> Response {
    // 1. Try cache (non-blocking)
    if let Some(url) = state.cache.get(&code).await {
        // 2. Fire-and-forget analytics (non-blocking)
        tokio::spawn(record_click(code.clone(), request_context));
        return Redirect::to(&url).into_response();
    }

    // 3. Fallback to database (non-blocking)
    match state.db.get_url(&code).await {
        Some(url) => {
            // 4. Update cache (non-blocking)
            tokio::spawn(state.cache.set(code.clone(), url.clone()));
            Redirect::to(&url).into_response()
        }
        None => StatusCode::NOT_FOUND.into_response()
    }
}
```
