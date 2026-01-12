# Database Design, Cleanup, and Purge Policies

This document covers the database schema design, data lifecycle management, cleanup strategies, and purge policies for the URL shortener system.

---

## Database Strategy by Tier

```mermaid
flowchart LR
    subgraph Tier1["Tier 1: Local"]
        T1_DB["SQLite"]
        T1_Cache["In-memory HashMap"]
    end
    
    subgraph Tier2["Tier 2: Startup"]
        T2_DB["PostgreSQL"]
        T2_Cache["Redis (single)"]
    end
    
    subgraph Tier3["Tier 3: Growth"]
        T3_DB["PostgreSQL + Replicas"]
        T3_Cache["Redis Cluster"]
    end
    
    subgraph Tier4_5["Tier 4-5: Scale/Global"]
        T4_DB["DynamoDB Global Tables"]
        T4_Cache["ElastiCache + Edge"]
    end
    
    Tier1 --> Tier2 --> Tier3 --> Tier4_5
```

| Tier | Primary Database | Cache | Rationale |
|------|-----------------|-------|-----------|
| 1 - Local | SQLite | In-memory HashMap | Zero configuration, embedded |
| 2 - Startup | PostgreSQL | Redis (single) | Battle-tested, familiar tooling |
| 3 - Growth | PostgreSQL + Replicas | Redis Cluster | Horizontal read scaling |
| 4 - Scale | DynamoDB Global Tables | ElastiCache | Multi-region, auto-scaling |
| 5 - Global | DynamoDB Global Tables | ElastiCache + Edge | Edge caching for ultra-low latency |

---

## Tier 1-3: PostgreSQL Schema

### Core Tables

```mermaid
erDiagram
    users ||--o{ api_keys : "has"
    users ||--o{ urls : "creates"
    urls ||--o{ url_variants : "has"
    urls ||--o{ click_events : "generates"
    click_events ||--o{ click_aggregates : "aggregates to"
    users ||--o{ custom_domains : "owns"
    
    users {
        uuid id PK
        varchar email UK
        varchar password_hash
        varchar tier
        timestamp created_at
        timestamp updated_at
        boolean is_active
        jsonb metadata
    }
    
    api_keys {
        uuid id PK
        uuid user_id FK
        varchar key_hash
        varchar key_prefix
        varchar name
        array scopes
        timestamp expires_at
        boolean is_active
    }
    
    urls {
        uuid id PK
        varchar short_code UK
        varchar original_url
        uuid user_id FK
        timestamp created_at
        timestamp expires_at
        bigint click_count
        boolean is_active
        boolean is_custom_alias
        jsonb metadata
    }
    
    click_events {
        uuid id PK
        uuid url_id
        varchar short_code
        timestamp clicked_at
        varchar country_code
        varchar device_type
        varchar browser
        boolean is_bot
    }
    
    click_aggregates {
        varchar short_code PK
        timestamp hour PK
        bigint total_clicks
        bigint unique_visitors
        jsonb country_breakdown
        jsonb device_breakdown
    }
```

### Database Functions and Triggers

```mermaid
flowchart TB
    subgraph Triggers["Database Triggers"]
        UpdateTrigger["update_updated_at_column()<br/>Auto-update timestamps"]
        ClickTrigger["increment_click_count()<br/>Atomic counter increment"]
    end
    
    subgraph Functions["Aggregation Functions"]
        Aggregate["aggregate_hourly_clicks()<br/>Scheduled hourly job"]
    end
    
    Triggers --> Functions
```

---

## Tier 4-5: DynamoDB Schema

### Table Definitions

```mermaid
flowchart TB
    subgraph URLsTable["URLS TABLE"]
        URLs_PK["PK: URL#short_code<br/>SK: v0"]
        URLs_GSI1["GSI1: user-urls-index<br/>PK: user_id, SK: created_at"]
        URLs_GSI2["GSI2: expires-at-index<br/>PK: expires_at_date, SK: expires_at"]
        URLs_TTL["TTL: expires_at"]
    end
    
    subgraph UsersTable["USERS TABLE"]
        Users_PK["PK: USER#user_id<br/>SK: PROFILE"]
        Users_Items["Additional SK patterns:<br/>• APIKEY#prefix<br/>• SESSION#session_id"]
        Users_GSI["GSI: email-index"]
    end
    
    subgraph AnalyticsTable["ANALYTICS (Timestream)"]
        Analytics_Dims["Dimensions:<br/>short_code, country, device, browser"]
        Analytics_Measures["Measures:<br/>click_count, unique_visitors"]
        Analytics_Retention["Retention:<br/>• Memory: 24 hours<br/>• Magnetic: 2 years"]
    end
    
    subgraph AuditTable["AUDIT LOGS (S3 + Athena)"]
        Audit_Path["Path: s3://bucket/year=YYYY/month=MM/day=DD/"]
        Audit_Format["Format: Parquet (compressed)"]
        Audit_Lifecycle["Lifecycle:<br/>• 0-90d: S3 Standard<br/>• 90-365d: Glacier IR<br/>• 1-7y: Deep Archive"]
    end
```

### DynamoDB Access Patterns

| Access Pattern | Key Condition | Index | Frequency |
|---------------|---------------|-------|-----------|
| Get URL by code | `pk = "URL#abc123X"` | Table | Very High |
| List user's URLs | `user_id = "xxx"` | GSI1 | Medium |
| Get user by email | `email = "user@example.com"` | GSI (users) | Medium |
| Find expiring URLs | `expires_at_date = "2024-01-15"` | GSI2 | Low (batch job) |
| Get API keys for user | `pk = "USER#xxx" AND begins_with(sk, "APIKEY#")` | Table | Medium |

---

## Cleanup and Purge Policies

### Policy Overview

```mermaid
flowchart LR
    subgraph Lifecycle["DATA LIFECYCLE MANAGEMENT"]
        Active["ACTIVE DATA"]
        Archived["ARCHIVED DATA"]
        Deleted["DELETED DATA"]
        
        Active -->|"TTL/Inactive"| Archived
        Archived -->|"Retention period"| Deleted
    end
    
    subgraph URLs["URLs Lifecycle"]
        Free["Free tier: 1 year auto-expire"]
        Premium["Premium: User-defined"]
        Enterprise["Enterprise: Permanent"]
    end
    
    subgraph Analytics["Analytics Lifecycle"]
        Realtime["Real-time: 24h in memory"]
        ShortTerm["Short-term: 7d magnetic"]
        Aggregated["Aggregated: 2 years"]
    end
    
    subgraph Audit["Audit Logs Lifecycle"]
        Hot["Hot: 90d (S3 Standard)"]
        Warm["Warm: 1y (Glacier Instant)"]
        Cold["Cold: 7y (Deep Archive)"]
    end
```

### 1. URL Expiration Policies

```yaml
url_lifecycle:
  tiers:
    free:
      default_ttl: 365d              # 1 year default
      max_ttl: 365d                  # Cannot exceed 1 year
      inactive_cleanup: 180d         # Delete if no clicks for 6 months

    premium:
      default_ttl: null              # No default expiration
      max_ttl: null                  # Unlimited
      inactive_cleanup: 730d         # 2 years inactive threshold

    enterprise:
      default_ttl: null              # No default expiration
      max_ttl: null                  # Unlimited
      inactive_cleanup: null         # Never auto-delete
```

### 2. URL States

```mermaid
stateDiagram-v2
    [*] --> Active: Create URL
    Active --> Expired: TTL reached
    Active --> SoftDeleted: User deletes
    Expired --> HardDeleted: 30 days retention
    SoftDeleted --> Active: Restore (within 30d)
    SoftDeleted --> HardDeleted: 30 days retention
    HardDeleted --> [*]: Permanent removal
```

### 3. Scheduled Cleanup Jobs

```mermaid
flowchart TB
    subgraph Hourly["Hourly Jobs"]
        AggClicks["aggregate-clicks<br/>Aggregate raw click events"]
    end
    
    subgraph Daily["Daily Jobs (2-3 AM UTC)"]
        CleanExpired["cleanup-expired-urls<br/>Remove expired URLs"]
        PurgeSoftDel["purge-soft-deleted<br/>Purge past retention"]
    end
    
    subgraph Weekly["Weekly Jobs (Sunday 4 AM)"]
        ArchiveAnalytics["archive-analytics<br/>Archive old analytics to S3"]
    end
    
    subgraph Monthly["Monthly Jobs (1st of month)"]
        CleanOrphans["cleanup-orphans<br/>Remove orphaned data"]
    end
    
    subgraph Continuous["Continuous"]
        GDPR["process-gdpr-erasure<br/>SQS triggered, max 10 concurrent"]
    end
```

---

## GDPR Erasure Process

```mermaid
flowchart TB
    Request["GDPR Erasure Request"]
    Validate["1. Validate request"]
    CheckHold["2. Check legal holds"]
    
    Request --> Validate --> CheckHold
    
    CheckHold -->|"Hold exists"| Error["Return Error:<br/>LegalHoldActive"]
    CheckHold -->|"No hold"| CreateAudit["3. Create audit record"]
    
    CreateAudit --> DeleteData["4. Delete all user data"]
    
    subgraph Parallel["Parallel Deletion"]
        DelURLs["Delete URLs"]
        DelAnalytics["Delete Analytics"]
        DelAPIKeys["Delete API Keys"]
        DelProfile["Delete Profile"]
    end
    
    DeleteData --> Parallel
    Parallel --> InvalidateCache["5. Invalidate caches globally"]
    InvalidateCache --> Confirm["6. Return confirmation"]
```

---

## Data Recovery Procedures

### Point-in-Time Recovery (PITR)

```mermaid
flowchart LR
    subgraph DynamoDB["DynamoDB PITR"]
        DDB_PITR["35 days retention<br/>Restore to any point"]
    end
    
    subgraph PostgreSQL["PostgreSQL PITR (RDS)"]
        PG_PITR["Restore to any point<br/>within retention window"]
    end
    
    subgraph SoftDelete["Soft Delete Recovery"]
        SoftDel["Within 30 days<br/>User can restore via API"]
    end
```

### Soft Delete Recovery Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant DB
    participant Cache
    participant Audit
    
    User->>API: Restore URL request
    API->>DB: Verify ownership
    DB-->>API: URL found (soft-deleted)
    API->>API: Check retention period
    
    alt Within 30 days
        API->>DB: Set is_active = true
        DB-->>API: Success
        API->>Cache: Update cache
        API->>Audit: Log restoration
        API-->>User: URL restored
    else Past 30 days
        API-->>User: Error: Permanently deleted
    end
```

---

## Monitoring and Alerting for Data Operations

```mermaid
flowchart TB
    subgraph Alarms["CloudWatch Alarms"]
        HighDeletion["high-deletion-rate<br/>Threshold: 10K/hour"]
        TTLSpike["ttl-deletion-spike<br/>Threshold: 100K/hour"]
        GDPRBacklog["gdpr-erasure-backlog<br/>Threshold: 100 pending"]
        JobFailure["cleanup-job-failure<br/>Any failure in 24h"]
    end
    
    subgraph Actions["Alert Actions"]
        OnCall["Alert on-call engineer"]
        Investigate["Trigger investigation"]
    end
    
    Alarms --> Actions
```
