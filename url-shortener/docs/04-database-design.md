# Database Design, Cleanup, and Purge Policies

This document covers the database schema design, data lifecycle management, cleanup strategies, and purge policies for the URL shortener system.

---

## Database Strategy by Tier

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

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy search

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),  -- NULL for SSO users
    tier VARCHAR(20) NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'premium', 'enterprise')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::JSONB
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tier ON users(tier);

-- API Keys table
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL,  -- Argon2 hash of API key
    key_prefix VARCHAR(8) NOT NULL,  -- First 8 chars for identification
    name VARCHAR(100),
    scopes VARCHAR(50)[] DEFAULT ARRAY['read', 'write'],
    rate_limit_override INTEGER,  -- NULL means use tier default
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);

-- URLs table (main table)
CREATE TABLE urls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    short_code VARCHAR(10) UNIQUE NOT NULL,
    original_url VARCHAR(4096) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,  -- NULL means never expires
    last_accessed_at TIMESTAMP WITH TIME ZONE,

    -- Counters (denormalized for performance)
    click_count BIGINT DEFAULT 0,
    unique_visitor_count BIGINT DEFAULT 0,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_custom_alias BOOLEAN DEFAULT FALSE,

    -- Metadata
    title VARCHAR(500),
    description TEXT,
    tags VARCHAR(50)[] DEFAULT ARRAY[]::VARCHAR[],
    metadata JSONB DEFAULT '{}'::JSONB,

    -- Compliance
    gdpr_consent BOOLEAN DEFAULT FALSE,
    data_residency VARCHAR(10),  -- 'us', 'eu', 'ap', etc.

    -- A/B Testing
    is_ab_test BOOLEAN DEFAULT FALSE
);

-- Indexes for URLs
CREATE INDEX idx_urls_short_code ON urls(short_code);
CREATE INDEX idx_urls_user_id ON urls(user_id);
CREATE INDEX idx_urls_created_at ON urls(created_at DESC);
CREATE INDEX idx_urls_expires_at ON urls(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_urls_is_active ON urls(is_active) WHERE is_active = FALSE;
CREATE INDEX idx_urls_tags ON urls USING GIN(tags);

-- A/B Test Variants
CREATE TABLE url_variants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url_id UUID NOT NULL REFERENCES urls(id) ON DELETE CASCADE,
    destination_url VARCHAR(4096) NOT NULL,
    weight INTEGER NOT NULL CHECK (weight >= 0 AND weight <= 100),
    is_control BOOLEAN DEFAULT FALSE,
    click_count BIGINT DEFAULT 0,
    conversion_count BIGINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_url_variants_url_id ON url_variants(url_id);

-- Click Events (for real-time analytics, before aggregation)
CREATE TABLE click_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url_id UUID NOT NULL,  -- No FK for performance
    short_code VARCHAR(10) NOT NULL,

    -- Timestamp
    clicked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Location (derived from IP)
    country_code CHAR(2),
    region VARCHAR(100),
    city VARCHAR(100),

    -- Request metadata
    ip_hash VARCHAR(64),  -- SHA-256 hash for privacy
    referrer VARCHAR(2048),
    user_agent VARCHAR(1024),

    -- Derived fields
    device_type VARCHAR(20),  -- 'desktop', 'mobile', 'tablet'
    browser VARCHAR(50),
    os VARCHAR(50),
    is_bot BOOLEAN DEFAULT FALSE,

    -- A/B Testing
    variant_id UUID
);

-- Partition by month for efficient cleanup
CREATE INDEX idx_click_events_short_code ON click_events(short_code);
CREATE INDEX idx_click_events_clicked_at ON click_events(clicked_at);
CREATE INDEX idx_click_events_url_id ON click_events(url_id);

-- Click Aggregates (hourly rollups)
CREATE TABLE click_aggregates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url_id UUID NOT NULL,
    short_code VARCHAR(10) NOT NULL,
    hour TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Counts
    total_clicks BIGINT DEFAULT 0,
    unique_visitors BIGINT DEFAULT 0,
    bot_clicks BIGINT DEFAULT 0,

    -- Breakdowns (JSONB for flexibility)
    country_breakdown JSONB DEFAULT '{}'::JSONB,
    device_breakdown JSONB DEFAULT '{}'::JSONB,
    browser_breakdown JSONB DEFAULT '{}'::JSONB,
    referrer_breakdown JSONB DEFAULT '{}'::JSONB,

    UNIQUE(url_id, hour)
);

CREATE INDEX idx_click_aggregates_short_code ON click_aggregates(short_code);
CREATE INDEX idx_click_aggregates_hour ON click_aggregates(hour);

-- Audit Log table
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Actor
    user_id UUID,
    api_key_id UUID,
    ip_address INET,

    -- Action
    action VARCHAR(50) NOT NULL,  -- 'create_url', 'delete_url', 'update_user', etc.
    resource_type VARCHAR(50) NOT NULL,  -- 'url', 'user', 'api_key'
    resource_id UUID,

    -- Details
    request_id VARCHAR(64),
    changes JSONB,  -- Before/after snapshot
    metadata JSONB,

    -- Compliance
    is_gdpr_relevant BOOLEAN DEFAULT FALSE,
    retention_until TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);

-- Custom Domains
CREATE TABLE custom_domains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    domain VARCHAR(255) UNIQUE NOT NULL,

    -- Verification
    verification_token VARCHAR(64) NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP WITH TIME ZONE,

    -- SSL
    ssl_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'active', 'failed'
    ssl_expires_at TIMESTAMP WITH TIME ZONE,

    -- Settings
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_custom_domains_user_id ON custom_domains(user_id);
CREATE INDEX idx_custom_domains_domain ON custom_domains(domain);
```

### Database Functions and Triggers

```sql
-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_urls_updated_at
    BEFORE UPDATE ON urls
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Increment click count atomically
CREATE OR REPLACE FUNCTION increment_click_count(p_short_code VARCHAR)
RETURNS VOID AS $$
BEGIN
    UPDATE urls
    SET click_count = click_count + 1,
        last_accessed_at = NOW()
    WHERE short_code = p_short_code;
END;
$$ LANGUAGE plpgsql;

-- Aggregate clicks (called by scheduled job)
CREATE OR REPLACE FUNCTION aggregate_hourly_clicks(p_hour TIMESTAMP WITH TIME ZONE)
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    INSERT INTO click_aggregates (
        url_id, short_code, hour,
        total_clicks, unique_visitors, bot_clicks,
        country_breakdown, device_breakdown, browser_breakdown, referrer_breakdown
    )
    SELECT
        url_id,
        short_code,
        date_trunc('hour', clicked_at) as hour,
        COUNT(*) as total_clicks,
        COUNT(DISTINCT ip_hash) as unique_visitors,
        COUNT(*) FILTER (WHERE is_bot = TRUE) as bot_clicks,
        jsonb_object_agg(
            COALESCE(country_code, 'unknown'),
            country_count
        ) as country_breakdown,
        jsonb_object_agg(
            COALESCE(device_type, 'unknown'),
            device_count
        ) as device_breakdown,
        jsonb_object_agg(
            COALESCE(browser, 'unknown'),
            browser_count
        ) as browser_breakdown,
        jsonb_object_agg(
            COALESCE(referrer_domain, 'direct'),
            referrer_count
        ) as referrer_breakdown
    FROM (
        SELECT
            url_id, short_code, clicked_at, ip_hash, is_bot,
            country_code, device_type, browser,
            CASE
                WHEN referrer IS NULL THEN 'direct'
                ELSE split_part(referrer, '/', 3)
            END as referrer_domain,
            COUNT(*) as country_count,
            COUNT(*) as device_count,
            COUNT(*) as browser_count,
            COUNT(*) as referrer_count
        FROM click_events
        WHERE clicked_at >= p_hour
          AND clicked_at < p_hour + INTERVAL '1 hour'
        GROUP BY url_id, short_code, clicked_at, ip_hash, is_bot,
                 country_code, device_type, browser, referrer
    ) sub
    GROUP BY url_id, short_code, date_trunc('hour', clicked_at)
    ON CONFLICT (url_id, hour) DO UPDATE
    SET total_clicks = click_aggregates.total_clicks + EXCLUDED.total_clicks,
        unique_visitors = GREATEST(click_aggregates.unique_visitors, EXCLUDED.unique_visitors),
        bot_clicks = click_aggregates.bot_clicks + EXCLUDED.bot_clicks;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;
```

---

## Tier 4-5: DynamoDB Schema

### Table Definitions

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           URLS TABLE                                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Table Name: url-shortener-urls                                                  │
│  Billing Mode: PAY_PER_REQUEST (on-demand)                                       │
│  Global Tables: Enabled (us-east-1, eu-west-1, ap-south-1)                      │
│                                                                                  │
│  Primary Key:                                                                    │
│    PK (Partition Key): pk (String)    Format: "URL#<short_code>"                │
│    SK (Sort Key):      sk (String)    Format: "v0" (version for future use)     │
│                                                                                  │
│  Attributes:                                                                     │
│  ┌────────────────────┬──────────┬─────────────────────────────────────────┐    │
│  │ Attribute          │ Type     │ Description                              │    │
│  ├────────────────────┼──────────┼─────────────────────────────────────────┤    │
│  │ pk                 │ String   │ "URL#abc123X"                           │    │
│  │ sk                 │ String   │ "v0"                                    │    │
│  │ short_code         │ String   │ "abc123X"                               │    │
│  │ original_url       │ String   │ Full destination URL                    │    │
│  │ user_id            │ String   │ Owner's user ID (UUID)                  │    │
│  │ created_at         │ Number   │ Unix timestamp (milliseconds)           │    │
│  │ updated_at         │ Number   │ Unix timestamp (milliseconds)           │    │
│  │ expires_at         │ Number   │ TTL attribute (Unix seconds)            │    │
│  │ click_count        │ Number   │ Atomic counter                          │    │
│  │ tier               │ String   │ "free" | "premium" | "enterprise"       │    │
│  │ is_active          │ Boolean  │ Soft delete flag                        │    │
│  │ is_custom_alias    │ Boolean  │ True if user chose the code             │    │
│  │ metadata           │ Map      │ Tags, title, description, etc.          │    │
│  │ gdpr_consent       │ Boolean  │ GDPR consent flag                       │    │
│  │ data_residency     │ String   │ Region code for data residency          │    │
│  └────────────────────┴──────────┴─────────────────────────────────────────┘    │
│                                                                                  │
│  Global Secondary Indexes:                                                       │
│                                                                                  │
│  GSI1: user-urls-index                                                          │
│    PK: user_id (String)                                                         │
│    SK: created_at (Number)                                                      │
│    Projection: ALL                                                              │
│    Use case: List all URLs for a user                                           │
│                                                                                  │
│  GSI2: expires-at-index                                                         │
│    PK: expires_at_date (String)  Format: "2024-01-15"                          │
│    SK: expires_at (Number)                                                      │
│    Projection: KEYS_ONLY                                                        │
│    Use case: Find URLs expiring on a specific date                              │
│                                                                                  │
│  TTL Configuration:                                                              │
│    Attribute: expires_at                                                         │
│    Format: Unix timestamp in seconds                                             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                           USERS TABLE                                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Table Name: url-shortener-users                                                 │
│                                                                                  │
│  Primary Key:                                                                    │
│    PK: pk (String)    Format: "USER#<user_id>"                                  │
│    SK: sk (String)    Format: "PROFILE"                                         │
│                                                                                  │
│  Additional Item Types (same table, different SK):                               │
│    - API Keys:  PK="USER#<id>", SK="APIKEY#<key_prefix>"                        │
│    - Sessions:  PK="USER#<id>", SK="SESSION#<session_id>"                       │
│                                                                                  │
│  GSI: email-index                                                                │
│    PK: email (String)                                                           │
│    Projection: ALL                                                              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                        ANALYTICS TABLE (Timestream)                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Database: url-shortener-analytics                                               │
│  Table: click_events                                                             │
│                                                                                  │
│  Dimensions:                                                                     │
│    - short_code (VARCHAR)                                                        │
│    - country_code (VARCHAR)                                                      │
│    - device_type (VARCHAR)                                                       │
│    - browser (VARCHAR)                                                           │
│    - os (VARCHAR)                                                                │
│    - referrer_domain (VARCHAR)                                                   │
│    - is_bot (VARCHAR)                                                            │
│                                                                                  │
│  Measures:                                                                       │
│    - click_count (BIGINT)                                                        │
│    - unique_visitors (BIGINT)                                                    │
│                                                                                  │
│  Retention:                                                                      │
│    - Memory store: 24 hours                                                      │
│    - Magnetic store: 2 years                                                     │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AUDIT LOGS TABLE (S3 + Athena)                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  S3 Bucket: url-shortener-audit-logs                                             │
│  Path: s3://url-shortener-audit-logs/year=YYYY/month=MM/day=DD/                 │
│  Format: Parquet (compressed)                                                    │
│                                                                                  │
│  Schema:                                                                         │
│    - event_id (STRING)                                                           │
│    - timestamp (TIMESTAMP)                                                       │
│    - user_id (STRING)                                                            │
│    - action (STRING)                                                             │
│    - resource_type (STRING)                                                      │
│    - resource_id (STRING)                                                        │
│    - ip_address (STRING)                                                         │
│    - request_id (STRING)                                                         │
│    - changes (STRING - JSON)                                                     │
│    - metadata (STRING - JSON)                                                    │
│                                                                                  │
│  Lifecycle:                                                                      │
│    - 0-90 days: S3 Standard                                                      │
│    - 90-365 days: S3 Glacier Instant Retrieval                                  │
│    - 1-7 years: S3 Glacier Deep Archive                                         │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
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

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        DATA LIFECYCLE MANAGEMENT                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐   │
│  │   ACTIVE DATA     │──────│   ARCHIVED DATA   │──────│   DELETED DATA    │   │
│  └───────────────────┘      └───────────────────┘      └───────────────────┘   │
│                                                                                  │
│  URLs:                                                                           │
│  • Free tier: Auto-expire after 1 year                                          │
│  • Premium: User-defined expiration                                              │
│  • Enterprise: Permanent (unless deleted)                                        │
│                                                                                  │
│  Analytics (Raw Events):                                                         │
│  • Real-time: 24 hours in Timestream memory                                     │
│  • Short-term: 7 days in Timestream magnetic                                    │
│  • Aggregated: 2 years in Timestream                                            │
│                                                                                  │
│  Audit Logs:                                                                     │
│  • Hot: 90 days (S3 Standard)                                                   │
│  • Warm: 1 year (S3 Glacier Instant)                                            │
│  • Cold: 7 years (S3 Glacier Deep Archive)                                      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1. URL Expiration Policies

```yaml
# URL Lifecycle Configuration
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

  # URL states
  states:
    active:
      description: "URL is live and redirecting"

    expired:
      description: "TTL reached, URL returns 410 Gone"
      retention: 30d                 # Keep metadata for 30 days

    soft_deleted:
      description: "User deleted, can be restored"
      retention: 30d

    hard_deleted:
      description: "Permanently removed from all systems"
```

### 2. DynamoDB TTL Configuration

```python
# Terraform configuration for DynamoDB TTL
resource "aws_dynamodb_table" "urls" {
  name         = "url-shortener-urls"
  billing_mode = "PAY_PER_REQUEST"

  # ... key schema ...

  ttl {
    enabled        = true
    attribute_name = "expires_at"  # Unix timestamp in seconds
  }

  # Global table configuration
  replica {
    region_name = "eu-west-1"
  }

  replica {
    region_name = "ap-south-1"
  }
}
```

### 3. Analytics Data Cleanup

```sql
-- PostgreSQL: Cleanup raw click events (Tier 2-3)
-- Run daily via pg_cron

-- Delete raw events older than 7 days (already aggregated)
DELETE FROM click_events
WHERE clicked_at < NOW() - INTERVAL '7 days';

-- Archive old aggregates to S3 (before deleting)
-- Using pg_dump or AWS DMS for this

-- Delete aggregates older than 2 years
DELETE FROM click_aggregates
WHERE hour < NOW() - INTERVAL '2 years';

-- VACUUM to reclaim space
VACUUM ANALYZE click_events;
VACUUM ANALYZE click_aggregates;
```

```python
# Lambda function for Timestream data management

import boto3
from datetime import datetime, timedelta

def lambda_handler(event, context):
    """
    Manages Timestream data retention and S3 archival
    Triggered daily by EventBridge
    """
    timestream_write = boto3.client('timestream-write')
    timestream_query = boto3.client('timestream-query')
    s3 = boto3.client('s3')

    # Timestream handles retention automatically via table policies
    # This function handles archival to S3 for long-term compliance storage

    # Query data for archival (data about to leave Timestream)
    archive_cutoff = datetime.now() - timedelta(days=700)  # 30 days before 2-year retention

    query = f"""
    SELECT short_code, time, country_code, device_type,
           SUM(click_count) as total_clicks
    FROM "url-shortener-analytics"."click_events"
    WHERE time < ago(700d) AND time >= ago(730d)
    GROUP BY short_code, time, country_code, device_type
    """

    # Execute query and write to S3 as Parquet
    # ... archival logic ...

    return {"archived_records": record_count}
```

### 4. Audit Log Retention

```yaml
# S3 Lifecycle Policy for Audit Logs
apiVersion: s3/v1
kind: LifecycleConfiguration
spec:
  rules:
    - id: audit-log-lifecycle
      status: Enabled
      prefix: ""
      transitions:
        - days: 90
          storageClass: GLACIER_IR          # Glacier Instant Retrieval
        - days: 365
          storageClass: DEEP_ARCHIVE        # Glacier Deep Archive
      expiration:
        days: 2555                          # 7 years (SOC2/HIPAA requirement)

    - id: gdpr-relevant-extended
      status: Enabled
      prefix: "gdpr/"
      expiration:
        days: 3650                          # 10 years for GDPR audit trails
```

### 5. Scheduled Cleanup Jobs

```rust
// Rust implementation of cleanup jobs

use aws_sdk_dynamodb::Client as DynamoClient;
use aws_sdk_s3::Client as S3Client;
use chrono::{Duration, Utc};

/// Cleanup job configuration
pub struct CleanupConfig {
    /// Delete URLs inactive for this duration
    pub inactive_threshold: Duration,
    /// Soft-deleted URLs retention period
    pub soft_delete_retention: Duration,
    /// Batch size for DynamoDB operations
    pub batch_size: usize,
}

impl Default for CleanupConfig {
    fn default() -> Self {
        Self {
            inactive_threshold: Duration::days(180),
            soft_delete_retention: Duration::days(30),
            batch_size: 25, // DynamoDB batch limit
        }
    }
}

/// Cleanup expired URLs
pub async fn cleanup_expired_urls(
    dynamo: &DynamoClient,
    config: &CleanupConfig,
) -> Result<CleanupResult, Error> {
    let mut deleted_count = 0;
    let mut archived_count = 0;

    // DynamoDB TTL handles automatic deletion for expires_at
    // This job handles inactive URL cleanup for free tier

    let inactive_cutoff = Utc::now() - config.inactive_threshold;

    // Query for inactive free-tier URLs
    let inactive_urls = query_inactive_urls(dynamo, inactive_cutoff, "free").await?;

    for batch in inactive_urls.chunks(config.batch_size) {
        // Archive to S3 before deletion
        archive_urls_to_s3(batch).await?;
        archived_count += batch.len();

        // Batch delete from DynamoDB
        batch_delete_urls(dynamo, batch).await?;
        deleted_count += batch.len();
    }

    Ok(CleanupResult {
        deleted_count,
        archived_count,
        timestamp: Utc::now(),
    })
}

/// Purge soft-deleted URLs after retention period
pub async fn purge_soft_deleted_urls(
    dynamo: &DynamoClient,
    config: &CleanupConfig,
) -> Result<PurgeResult, Error> {
    let retention_cutoff = Utc::now() - config.soft_delete_retention;

    // Query for soft-deleted URLs past retention
    let urls_to_purge = query_soft_deleted_urls(dynamo, retention_cutoff).await?;

    let mut purged_count = 0;

    for batch in urls_to_purge.chunks(config.batch_size) {
        // Create audit log entry for compliance
        create_purge_audit_log(batch).await?;

        // Permanently delete from all regions
        batch_purge_urls(dynamo, batch).await?;
        purged_count += batch.len();
    }

    Ok(PurgeResult {
        purged_count,
        timestamp: Utc::now(),
    })
}

/// GDPR erasure - complete removal within 72 hours
pub async fn gdpr_erasure(
    dynamo: &DynamoClient,
    user_id: &str,
    request_id: &str,
) -> Result<ErasureResult, Error> {
    // 1. Get all user data
    let user_urls = get_user_urls(dynamo, user_id).await?;
    let user_analytics = get_user_analytics(user_id).await?;

    // 2. Create erasure audit log (retained separately for compliance)
    create_erasure_audit_log(request_id, user_id, &user_urls).await?;

    // 3. Delete all URLs
    for batch in user_urls.chunks(25) {
        batch_purge_urls(dynamo, batch).await?;
    }

    // 4. Delete analytics data
    delete_user_analytics(user_id).await?;

    // 5. Delete user profile
    delete_user(dynamo, user_id).await?;

    // 6. Invalidate caches globally
    invalidate_user_cache_globally(user_id).await?;

    Ok(ErasureResult {
        urls_deleted: user_urls.len(),
        request_id: request_id.to_string(),
        completed_at: Utc::now(),
    })
}
```

### 6. Cleanup Job Schedule

```yaml
# EventBridge Rules for scheduled cleanup jobs

cleanup_schedules:

  # Hourly: Aggregate raw click events
  - name: aggregate-clicks
    schedule: "rate(1 hour)"
    target: lambda:aggregate-clicks
    enabled: true

  # Daily: Cleanup expired and inactive URLs
  - name: cleanup-expired-urls
    schedule: "cron(0 2 * * ? *)"  # 2 AM UTC daily
    target: lambda:cleanup-expired-urls
    enabled: true

  # Daily: Purge soft-deleted URLs past retention
  - name: purge-soft-deleted
    schedule: "cron(0 3 * * ? *)"  # 3 AM UTC daily
    target: lambda:purge-soft-deleted
    enabled: true

  # Weekly: Archive old analytics to S3
  - name: archive-analytics
    schedule: "cron(0 4 ? * SUN *)"  # 4 AM UTC every Sunday
    target: lambda:archive-analytics
    enabled: true

  # Monthly: Cleanup orphaned data
  - name: cleanup-orphans
    schedule: "cron(0 5 1 * ? *)"  # 5 AM UTC on 1st of month
    target: lambda:cleanup-orphans
    enabled: true

  # Continuous: GDPR erasure requests (SQS triggered)
  - name: process-gdpr-erasure
    source: sqs:gdpr-erasure-requests
    target: lambda:gdpr-erasure
    batch_size: 1
    max_concurrency: 10
```

---

## Data Recovery Procedures

### Point-in-Time Recovery (PITR)

```bash
# DynamoDB PITR - restore to any point in the last 35 days
aws dynamodb restore-table-to-point-in-time \
    --source-table-name url-shortener-urls \
    --target-table-name url-shortener-urls-restored \
    --restore-date-time "2024-01-15T10:30:00Z"

# PostgreSQL PITR (RDS)
aws rds restore-db-instance-to-point-in-time \
    --source-db-instance-identifier url-shortener-primary \
    --target-db-instance-identifier url-shortener-restored \
    --restore-time "2024-01-15T10:30:00Z"
```

### Soft Delete Recovery

```rust
/// Restore a soft-deleted URL
pub async fn restore_url(
    dynamo: &DynamoClient,
    short_code: &str,
    user_id: &str,
) -> Result<Url, Error> {
    // Verify ownership
    let url = get_url(dynamo, short_code).await?;

    if url.user_id != user_id {
        return Err(Error::Forbidden);
    }

    if !url.is_soft_deleted() {
        return Err(Error::AlreadyActive);
    }

    if url.soft_deleted_at + Duration::days(30) < Utc::now() {
        return Err(Error::PermanentlyDeleted);
    }

    // Restore the URL
    let restored = update_url(dynamo, short_code, |url| {
        url.is_active = true;
        url.deleted_at = None;
        url.updated_at = Utc::now();
    }).await?;

    // Update cache
    cache_url(&restored).await?;

    // Audit log
    audit_log("url_restored", short_code, user_id).await?;

    Ok(restored)
}
```

---

## Monitoring and Alerting for Data Operations

```yaml
# CloudWatch Alarms for data operations

alarms:
  - name: high-deletion-rate
    metric: DeletedUrls
    threshold: 10000
    period: 1h
    action: alert-oncall
    description: "Unusually high URL deletion rate"

  - name: ttl-deletion-spike
    metric: DynamoDBTTLDeletions
    threshold: 100000
    period: 1h
    action: alert-oncall
    description: "Spike in TTL-based deletions"

  - name: gdpr-erasure-backlog
    metric: GDPRErasureQueueDepth
    threshold: 100
    period: 15m
    action: alert-oncall
    description: "GDPR erasure requests backing up"

  - name: cleanup-job-failure
    metric: CleanupJobErrors
    threshold: 1
    period: 1d
    action: alert-oncall
    description: "Scheduled cleanup job failed"
```
