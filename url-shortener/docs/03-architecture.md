# System Architecture

This document describes the detailed architecture of the URL shortener system, including component design, data flows, and key architectural decisions.

---

## High-Level Architecture

```mermaid
flowchart TB
    subgraph Clients["CLIENT LAYER"]
        Browser["Browser Users"]
        Mobile["Mobile Apps"]
        CLI["CLI Tools"]
        API["API Clients"]
        Partner["Partner Integrations"]
    end
    
    subgraph Edge["EDGE LAYER"]
        CF["CloudFront CDN (200+ PoPs)"]
        Lambda["Lambda@Edge"]
        WAF["AWS WAF"]
        Shield["AWS Shield"]
    end
    
    subgraph Gateway["API GATEWAY LAYER"]
        ALB["Application Load Balancer<br/>• SSL/TLS Termination<br/>• Health Checks<br/>• Request Routing"]
    end
    
    subgraph App["APPLICATION LAYER - EKS Cluster"]
        Pod1["Pod 1 (Axum)"]
        Pod2["Pod 2 (Axum)"]
        Pod3["Pod 3 (Axum)"]
        PodN["Pod N (Axum)"]
    end
    
    subgraph Cache["CACHE LAYER"]
        Redis["ElastiCache Redis Cluster<br/>• URL mappings<br/>• Rate limits<br/>• Session cache"]
    end
    
    subgraph Data["DATA LAYER"]
        DDB["DynamoDB Global Tables<br/>• URLs<br/>• Users<br/>• Analytics<br/>• Audit logs"]
    end
    
    subgraph Analytics["ANALYTICS LAYER"]
        Kinesis["Kinesis Streams<br/>(Click Events)"]
        LambdaProc["Lambda Processors"]
        Timestream["Timestream<br/>(Analytics)"]
    end
    
    Clients --> Edge
    Edge --> Gateway
    Gateway --> App
    App --> Cache
    App --> Data
    App --> Analytics
    Kinesis --> LambdaProc --> Timestream
```

---

## Component Architecture

### 1. Edge Layer (CloudFront + Lambda@Edge)

The edge layer handles the majority of redirect traffic with ultra-low latency.

```mermaid
sequenceDiagram
    participant User
    participant CloudFront
    participant Lambda@Edge
    participant EdgeCache
    participant Origin
    
    User->>CloudFront: GET /abc123X
    CloudFront->>Lambda@Edge: Viewer Request
    Lambda@Edge->>EdgeCache: Check Edge Cache
    
    alt Cache Hit
        EdgeCache-->>Lambda@Edge: URL Found
        Lambda@Edge-->>CloudFront: Return Redirect
        CloudFront-->>User: 301 Redirect
    else Cache Miss
        Lambda@Edge->>CloudFront: Forward to Origin
        CloudFront->>Origin: Request
        Origin-->>CloudFront: Response
        CloudFront-->>User: 301 Redirect
    end
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

```mermaid
flowchart TB
    subgraph AxumApp["AXUM APPLICATION"]
        subgraph Router["ROUTER"]
            API["/api/v1/*<br/>(API)"]
            Redirect["/:code<br/>(Redirect)"]
            Health["/health<br/>(Health)"]
        end
        
        subgraph Middleware["MIDDLEWARE STACK"]
            Tracing["Tracing"]
            RateLimit["Rate Limit"]
            Auth["Auth"]
            Metrics["Metrics"]
        end
        
        subgraph Handlers["HANDLERS"]
            URLHandlers["URL Handlers"]
            AnalyticsHandlers["Analytics Handlers"]
            AdminHandlers["Admin Handlers"]
        end
        
        subgraph Domain["DOMAIN LAYER"]
            URLService["URL Service"]
            AnalyticsService["Analytics Service"]
            ComplianceService["Compliance Service"]
        end
        
        subgraph Infra["INFRASTRUCTURE LAYER"]
            DDBClient["DynamoDB Client"]
            RedisClient["Redis Client"]
            S3Client["S3 Client"]
            KinesisClient["Kinesis Client"]
            SESClient["SES Client"]
        end
        
        Router --> Middleware --> Handlers --> Domain --> Infra
    end
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

```mermaid
flowchart LR
    subgraph Patterns["DynamoDB Access Patterns"]
        P1["Get URL by code<br/>PK = URL#abc123X"]
        P2["List user's URLs<br/>GSI2-PK = user_id"]
        P3["Find expiring URLs<br/>GSI1-PK < current_time"]
    end
```

### 4. Analytics Pipeline

```mermaid
flowchart LR
    Click["Click Event"]
    Kinesis["Kinesis Stream"]
    Lambda["Lambda Processor"]
    Timestream["Timestream Database"]
    S3["S3 (Raw Archives)"]
    
    Click --> Kinesis --> Lambda
    Lambda --> Timestream
    Lambda --> S3
```

**Click Event Schema:**

```json
{
  "event_id": "uuid",
  "short_code": "abc123X",
  "timestamp": 1704067200000,
  "ip_hash": "sha256(...)",
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

```mermaid
sequenceDiagram
    participant Client
    participant ALB
    participant Service
    participant Redis
    participant DynamoDB
    
    Client->>ALB: POST /api/v1/urls
    ALB->>Service: Forward
    Service->>Service: Validate URL
    Service->>Service: Generate Code
    Service->>Redis: Check exists
    Redis-->>Service: Not found
    Service->>Redis: Write to cache
    Redis-->>Service: ACK
    Service->>DynamoDB: Write to DB
    DynamoDB-->>Service: ACK
    Service-->>ALB: 201 Created
    ALB-->>Client: Response
```

### URL Redirect Flow (Edge)

```mermaid
sequenceDiagram
    participant Client
    participant CloudFront
    participant Lambda@Edge
    participant Redis as Redis (Global)
    participant Origin as Origin (EKS)
    
    Client->>CloudFront: GET /abc123X
    CloudFront->>Lambda@Edge: Viewer Request
    Lambda@Edge->>Redis: Check Cache
    Redis-->>Lambda@Edge: Cache Hit!
    Lambda@Edge-->>CloudFront: 301 Redirect
    CloudFront-->>Client: 301 Redirect
    
    Note over Lambda@Edge,Origin: Async: Send click event
```

### Cache Miss Flow

```mermaid
sequenceDiagram
    participant Client
    participant CloudFront
    participant ALB
    participant EKS
    participant DynamoDB
    
    Client->>CloudFront: GET /xyz789Z
    CloudFront->>CloudFront: Cache Miss
    CloudFront->>ALB: Forward
    ALB->>EKS: Forward
    EKS->>DynamoDB: Get URL
    DynamoDB-->>EKS: URL Data
    EKS-->>ALB: 301 + Headers
    ALB-->>CloudFront: Cache Response
    CloudFront-->>Client: 301 Redirect
```

---

## Multi-Region Architecture

### Active-Active Deployment

```mermaid
flowchart TB
    R53["Route 53 (DNS)<br/>Latency-based + Health"]
    
    R53 --> US["US-EAST-1 (Primary)"]
    R53 --> EU["EU-WEST-1 (Secondary)"]
    R53 --> AP["AP-SOUTH-1 (Secondary)"]
    
    subgraph US["US-EAST-1"]
        US_ALB["ALB"]
        US_EKS["EKS (3 nodes)"]
        US_Redis["ElastiCache Redis"]
        US_ALB --> US_EKS --> US_Redis
    end
    
    subgraph EU["EU-WEST-1"]
        EU_ALB["ALB"]
        EU_EKS["EKS (3 nodes)"]
        EU_Redis["ElastiCache Redis"]
        EU_ALB --> EU_EKS --> EU_Redis
    end
    
    subgraph AP["AP-SOUTH-1"]
        AP_ALB["ALB"]
        AP_EKS["EKS (3 nodes)"]
        AP_Redis["ElastiCache Redis"]
        AP_ALB --> AP_EKS --> AP_Redis
    end
    
    US_Redis --> DDB["DynamoDB Global Tables"]
    EU_Redis --> DDB
    AP_Redis --> DDB
    
    subgraph DDBDetails["DynamoDB Replication"]
        DDB_US["us-east"]
        DDB_EU["eu-west"]
        DDB_AP["ap-south"]
        DDB_US <--> DDB_EU <--> DDB_AP
    end
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

```mermaid
flowchart TB
    subgraph Layer1["Layer 1: CloudFront Edge Cache"]
        L1["200+ locations<br/>TTL: 86400s (24 hours)<br/>Hit rate target: 60-70%"]
    end
    
    subgraph Layer2["Layer 2: Regional Redis Cluster"]
        L2["Per region<br/>TTL: 86400s (24 hours)<br/>Hit rate target: 30-35%"]
    end
    
    subgraph Layer3["Layer 3: DynamoDB DAX (optional)"]
        L3["TTL: 300s (5 minutes)<br/>Hit rate target: 5-10%"]
    end
    
    subgraph Layer4["Layer 4: DynamoDB"]
        L4["Source of truth<br/>Strongly consistent reads when needed"]
    end
    
    Layer1 --> Layer2 --> Layer3 --> Layer4
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

```mermaid
flowchart TB
    subgraph Perimeter["SECURITY PERIMETER"]
        subgraph Shield["AWS Shield Advanced"]
            DDoS["DDoS Protection - Layer 3/4/7"]
        end
        
        subgraph WAF_Layer["AWS WAF"]
            RateLimit["Rate Limit Rules"]
            SQLi["SQL Injection Detection"]
            XSS["XSS Filter Rules"]
            GeoBlock["Geo Block Rules"]
            BotControl["Bot Control Rules"]
            IPRep["IP Reputation Lists"]
        end
        
        subgraph VPC["VPC Security"]
            Public["Public Subnets<br/>(ALB only)"]
            Private["Private Subnets<br/>(EKS)"]
            DataSubnet["Data Subnets<br/>(Redis, DB)"]
        end
        
        subgraph AppSec["Application Security"]
            mTLS["mTLS between services"]
            Argon2["API keys hashed with Argon2"]
            JWT["JWT with RS256 signatures"]
            RequestSign["Request signing for internal calls"]
        end
        
        subgraph DataSec["Data Security"]
            DDBEncrypt["DynamoDB: Encrypted at rest (AES-256)"]
            RedisEncrypt["Redis: Encrypted at rest + in-transit"]
            S3Encrypt["S3: SSE-KMS encryption"]
            Secrets["Secrets: AWS Secrets Manager"]
        end
    end
```

---

## ID Generation Algorithm

### Base62 Encoding

```mermaid
flowchart LR
    subgraph Algorithm["ID Generation"]
        Counter["1. Get next ID<br/>from distributed counter"]
        Encode["2. Encode to Base62"]
        Pad["3. Pad to 7 characters"]
        Verify["4. Verify uniqueness"]
        Retry["5. Retry with suffix<br/>if collision"]
    end
    
    Counter --> Encode --> Pad --> Verify
    Verify -->|"Collision"| Retry --> Counter
```

- Character set: `0-9`, `a-z`, `A-Z` (62 characters)
- 7 characters = 62^7 = **3,521,614,606,208** unique codes
- At 500M/month = 7,000 years of capacity

### Distributed Counter Implementation

```mermaid
flowchart TB
    subgraph DDBCounter["DynamoDB Counter Table"]
        Counter["PK: COUNTER<br/>current_value: 1,234,567,890,000<br/>last_allocated: 2024-01-15T10:30:00Z"]
    end
    
    subgraph Allocation["Allocation Strategy"]
        Step1["1. Each instance requests 1M IDs batch"]
        Step2["2. Atomic increment in DynamoDB"]
        Step3["3. Instance generates codes from range"]
        Step4["4. Request new batch at 90% depleted"]
    end
    
    subgraph Instance["Instance Memory"]
        Range["start: 1,234,567M<br/>end: 1,235,567M<br/>current: 1,234,890M"]
    end
    
    DDBCounter --> Allocation --> Instance
```

**Benefits:**
- No coordination for most writes
- Atomic operation prevents duplicates
- Predictable, sequential IDs (helps cache locality)

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

```mermaid
stateDiagram-v2
    [*] --> Closed
    Closed --> Open: Failures > 5
    Open --> HalfOpen: 30s timeout
    HalfOpen --> Closed: 3 successes
    HalfOpen --> Open: Any failure
    
    state Closed {
        [*] --> NormalOps
        NormalOps: Normal operation
    }
    
    state Open {
        [*] --> Fallback
        Fallback: Use fallback (DynamoDB)
    }
    
    state HalfOpen {
        [*] --> Testing
        Testing: Test recovery
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

```mermaid
flowchart TB
    Request["Incoming Request"]
    Cache["1. Try cache<br/>(non-blocking)"]
    Analytics["2. Fire-and-forget analytics<br/>(non-blocking)"]
    DB["3. Fallback to database<br/>(non-blocking)"]
    UpdateCache["4. Update cache<br/>(non-blocking)"]
    Response["Return Response"]
    
    Request --> Cache
    Cache -->|"Hit"| Analytics --> Response
    Cache -->|"Miss"| DB --> UpdateCache --> Response
```
