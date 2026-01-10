//! Domain models

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use validator::Validate;

/// URL entity - core domain model
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Url {
    /// Unique identifier
    pub id: Uuid,

    /// Short code (e.g., "abc123X")
    pub short_code: String,

    /// Original/destination URL
    pub original_url: String,

    /// Owner user ID (optional for anonymous URLs)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_id: Option<String>,

    /// Creation timestamp
    pub created_at: DateTime<Utc>,

    /// Last update timestamp
    pub updated_at: DateTime<Utc>,

    /// Expiration timestamp (optional)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expires_at: Option<DateTime<Utc>>,

    /// Last access timestamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_accessed_at: Option<DateTime<Utc>>,

    /// Total click count
    pub click_count: u64,

    /// Whether the URL is active
    pub is_active: bool,

    /// Whether this is a custom alias
    pub is_custom_alias: bool,

    /// User tier (free, premium, enterprise)
    pub tier: UserTier,

    /// Optional title
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,

    /// Optional description
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,

    /// Tags for organization
    #[serde(default)]
    pub tags: Vec<String>,

    /// Additional metadata
    #[serde(default)]
    pub metadata: serde_json::Value,
}

impl Url {
    /// Create a new URL
    pub fn new(
        short_code: String,
        original_url: String,
        user_id: Option<String>,
        tier: UserTier,
        is_custom_alias: bool,
    ) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            short_code,
            original_url,
            user_id,
            created_at: now,
            updated_at: now,
            expires_at: None,
            last_accessed_at: None,
            click_count: 0,
            is_active: true,
            is_custom_alias,
            tier,
            title: None,
            description: None,
            tags: vec![],
            metadata: serde_json::Value::Null,
        }
    }

    /// Check if the URL is expired
    pub fn is_expired(&self) -> bool {
        if let Some(expires_at) = self.expires_at {
            expires_at < Utc::now()
        } else {
            false
        }
    }

    /// Check if the URL can be accessed
    pub fn can_redirect(&self) -> bool {
        self.is_active && !self.is_expired()
    }

    /// Record a click
    pub fn record_click(&mut self) {
        self.click_count += 1;
        self.last_accessed_at = Some(Utc::now());
    }
}

/// User tier levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum UserTier {
    Free,
    Premium,
    Enterprise,
}

impl Default for UserTier {
    fn default() -> Self {
        UserTier::Free
    }
}

impl UserTier {
    /// Get the default TTL for this tier in seconds
    pub fn default_ttl(&self) -> Option<i64> {
        match self {
            UserTier::Free => Some(365 * 24 * 60 * 60), // 1 year
            UserTier::Premium => None, // No expiration
            UserTier::Enterprise => None, // No expiration
        }
    }

    /// Get the maximum custom alias length
    pub fn max_alias_length(&self) -> usize {
        match self {
            UserTier::Free => 10,
            UserTier::Premium => 20,
            UserTier::Enterprise => 50,
        }
    }
}

/// Request to create a new URL
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct CreateUrlRequest {
    /// The destination URL
    #[validate(url, length(max = 4096))]
    pub url: String,

    /// Optional custom alias
    #[validate(length(min = 4, max = 50))]
    pub custom_alias: Option<String>,

    /// Optional TTL in seconds
    #[validate(range(min = 60, max = 31536000))]
    pub ttl_seconds: Option<i64>,

    /// Optional title
    #[validate(length(max = 500))]
    pub title: Option<String>,

    /// Optional description
    #[validate(length(max = 2000))]
    pub description: Option<String>,

    /// Optional tags
    #[validate(length(max = 10))]
    pub tags: Option<Vec<String>>,
}

/// Response for URL creation
#[derive(Debug, Clone, Serialize)]
pub struct CreateUrlResponse {
    pub id: Uuid,
    pub short_code: String,
    pub short_url: String,
    pub original_url: String,
    pub created_at: DateTime<Utc>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expires_at: Option<DateTime<Utc>>,
}

/// Response for URL details
#[derive(Debug, Clone, Serialize)]
pub struct UrlResponse {
    pub id: Uuid,
    pub short_code: String,
    pub short_url: String,
    pub original_url: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expires_at: Option<DateTime<Utc>>,
    pub click_count: u64,
    pub is_active: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    pub tags: Vec<String>,
}

impl UrlResponse {
    pub fn from_url(url: &Url, base_url: &str) -> Self {
        Self {
            id: url.id,
            short_code: url.short_code.clone(),
            short_url: format!("{}/{}", base_url, url.short_code),
            original_url: url.original_url.clone(),
            created_at: url.created_at,
            updated_at: url.updated_at,
            expires_at: url.expires_at,
            click_count: url.click_count,
            is_active: url.is_active,
            title: url.title.clone(),
            description: url.description.clone(),
            tags: url.tags.clone(),
        }
    }
}

/// Bulk URL creation request
#[derive(Debug, Clone, Deserialize, Validate)]
pub struct BulkCreateRequest {
    #[validate(length(min = 1, max = 100))]
    pub urls: Vec<CreateUrlRequest>,
}

/// Bulk URL creation response
#[derive(Debug, Clone, Serialize)]
pub struct BulkCreateResponse {
    pub created: Vec<CreateUrlResponse>,
    pub errors: Vec<BulkCreateError>,
}

#[derive(Debug, Clone, Serialize)]
pub struct BulkCreateError {
    pub index: usize,
    pub url: String,
    pub error: String,
}

/// Click event for analytics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClickEvent {
    pub event_id: Uuid,
    pub short_code: String,
    pub timestamp: DateTime<Utc>,

    // Privacy-preserving fields
    pub ip_hash: String,
    pub country_code: Option<String>,
    pub region: Option<String>,
    pub city: Option<String>,

    // Request metadata
    pub referrer_domain: Option<String>,
    pub device_type: Option<String>,
    pub browser: Option<String>,
    pub os: Option<String>,

    pub is_bot: bool,
}

/// Analytics summary
#[derive(Debug, Clone, Serialize)]
pub struct AnalyticsSummary {
    pub short_code: String,
    pub total_clicks: u64,
    pub unique_visitors: u64,
    pub clicks_today: u64,
    pub clicks_this_week: u64,
    pub clicks_this_month: u64,
    pub top_countries: Vec<CountryStats>,
    pub top_referrers: Vec<ReferrerStats>,
    pub device_breakdown: DeviceBreakdown,
}

#[derive(Debug, Clone, Serialize)]
pub struct CountryStats {
    pub country_code: String,
    pub country_name: String,
    pub clicks: u64,
    pub percentage: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ReferrerStats {
    pub referrer: String,
    pub clicks: u64,
    pub percentage: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct DeviceBreakdown {
    pub desktop: u64,
    pub mobile: u64,
    pub tablet: u64,
    pub other: u64,
}

/// User entity
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    pub id: Uuid,
    pub email: String,
    pub tier: UserTier,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub is_active: bool,
    pub metadata: serde_json::Value,
}

/// API Key entity
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKey {
    pub id: Uuid,
    pub user_id: Uuid,
    pub prefix: String,
    pub hash: String,
    pub name: Option<String>,
    pub scopes: Vec<String>,
    pub created_at: DateTime<Utc>,
    pub expires_at: Option<DateTime<Utc>>,
    pub last_used_at: Option<DateTime<Utc>>,
    pub is_active: bool,
}

/// Pagination parameters
#[derive(Debug, Clone, Deserialize)]
pub struct PaginationParams {
    #[serde(default = "default_page")]
    pub page: u32,

    #[serde(default = "default_limit")]
    pub limit: u32,
}

fn default_page() -> u32 {
    1
}

fn default_limit() -> u32 {
    20
}

/// Paginated response
#[derive(Debug, Clone, Serialize)]
pub struct PaginatedResponse<T> {
    pub data: Vec<T>,
    pub pagination: PaginationInfo,
}

#[derive(Debug, Clone, Serialize)]
pub struct PaginationInfo {
    pub page: u32,
    pub limit: u32,
    pub total_items: u64,
    pub total_pages: u32,
    pub has_next: bool,
    pub has_prev: bool,
}
