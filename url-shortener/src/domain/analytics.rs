//! Analytics service for click tracking and reporting

use chrono::{DateTime, Utc};
use sha2::{Sha256, Digest};
use std::sync::Arc;
use tracing::instrument;
use uuid::Uuid;

use crate::domain::{AnalyticsSummary, ClickEvent, CountryStats, DeviceBreakdown, ReferrerStats};
use crate::error::AppResult;
use crate::infrastructure::AnalyticsRepository;

/// Analytics service for tracking and reporting
pub struct AnalyticsService {
    repository: Arc<dyn AnalyticsRepository>,
    daily_salt: String,
}

impl AnalyticsService {
    /// Create a new analytics service
    pub fn new(repository: Arc<dyn AnalyticsRepository>, daily_salt: String) -> Self {
        Self {
            repository,
            daily_salt,
        }
    }

    /// Record a click event
    #[instrument(skip(self))]
    pub async fn record_click(&self, event: RawClickEvent) -> AppResult<()> {
        // Sanitize and transform the event
        let sanitized = self.sanitize_event(event);

        // Store the event
        self.repository.record_click(sanitized).await
    }

    /// Get analytics summary for a URL
    #[instrument(skip(self))]
    pub async fn get_summary(&self, short_code: &str) -> AppResult<AnalyticsSummary> {
        self.repository.get_summary(short_code).await
    }

    /// Get real-time click count (last 5 minutes)
    #[instrument(skip(self))]
    pub async fn get_realtime_clicks(&self, short_code: &str) -> AppResult<u64> {
        self.repository.get_realtime_clicks(short_code).await
    }

    /// Get geographic breakdown
    #[instrument(skip(self))]
    pub async fn get_geo_breakdown(
        &self,
        short_code: &str,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> AppResult<Vec<CountryStats>> {
        self.repository.get_geo_breakdown(short_code, start, end).await
    }

    /// Get referrer breakdown
    #[instrument(skip(self))]
    pub async fn get_referrer_breakdown(
        &self,
        short_code: &str,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> AppResult<Vec<ReferrerStats>> {
        self.repository.get_referrer_breakdown(short_code, start, end).await
    }

    /// Get device breakdown
    #[instrument(skip(self))]
    pub async fn get_device_breakdown(
        &self,
        short_code: &str,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> AppResult<DeviceBreakdown> {
        self.repository.get_device_breakdown(short_code, start, end).await
    }

    // Private helper methods

    /// Sanitize a raw click event for privacy
    fn sanitize_event(&self, raw: RawClickEvent) -> ClickEvent {
        ClickEvent {
            event_id: Uuid::new_v4(),
            short_code: raw.short_code,
            timestamp: raw.timestamp,

            // Hash IP with daily salt for privacy
            ip_hash: self.hash_ip(&raw.ip_address),

            // Keep country/region, remove city for privacy
            country_code: raw.country_code,
            region: raw.region,
            city: None, // Don't store city-level data

            // Extract domain from referrer
            referrer_domain: raw.referrer.and_then(|r| self.extract_domain(&r)),

            // Parse user agent
            device_type: raw.user_agent.as_ref().map(|ua| self.detect_device_type(ua)),
            browser: raw.user_agent.as_ref().map(|ua| self.detect_browser(ua)),
            os: raw.user_agent.as_ref().map(|ua| self.detect_os(ua)),

            is_bot: raw.user_agent.as_ref().map(|ua| self.is_bot(ua)).unwrap_or(false),
        }
    }

    /// Hash IP address with daily salt
    fn hash_ip(&self, ip: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(ip.as_bytes());
        hasher.update(self.daily_salt.as_bytes());
        hex::encode(hasher.finalize())
    }

    /// Extract domain from URL
    fn extract_domain(&self, url: &str) -> Option<String> {
        url::Url::parse(url)
            .ok()
            .and_then(|u| u.host_str().map(|h| h.to_string()))
    }

    /// Detect device type from user agent
    fn detect_device_type(&self, user_agent: &str) -> String {
        let ua_lower = user_agent.to_lowercase();

        if ua_lower.contains("mobile") || ua_lower.contains("android") && !ua_lower.contains("tablet") {
            "mobile".to_string()
        } else if ua_lower.contains("tablet") || ua_lower.contains("ipad") {
            "tablet".to_string()
        } else if ua_lower.contains("bot") || ua_lower.contains("crawler") || ua_lower.contains("spider") {
            "bot".to_string()
        } else {
            "desktop".to_string()
        }
    }

    /// Detect browser from user agent
    fn detect_browser(&self, user_agent: &str) -> String {
        let ua_lower = user_agent.to_lowercase();

        if ua_lower.contains("firefox") {
            "Firefox".to_string()
        } else if ua_lower.contains("edg") {
            "Edge".to_string()
        } else if ua_lower.contains("chrome") {
            "Chrome".to_string()
        } else if ua_lower.contains("safari") {
            "Safari".to_string()
        } else if ua_lower.contains("opera") {
            "Opera".to_string()
        } else {
            "Other".to_string()
        }
    }

    /// Detect OS from user agent
    fn detect_os(&self, user_agent: &str) -> String {
        let ua_lower = user_agent.to_lowercase();

        if ua_lower.contains("windows") {
            "Windows".to_string()
        } else if ua_lower.contains("mac os") || ua_lower.contains("macos") {
            "macOS".to_string()
        } else if ua_lower.contains("linux") {
            "Linux".to_string()
        } else if ua_lower.contains("android") {
            "Android".to_string()
        } else if ua_lower.contains("ios") || ua_lower.contains("iphone") || ua_lower.contains("ipad") {
            "iOS".to_string()
        } else {
            "Other".to_string()
        }
    }

    /// Check if user agent is a bot
    fn is_bot(&self, user_agent: &str) -> bool {
        let ua_lower = user_agent.to_lowercase();

        let bot_patterns = [
            "bot", "crawler", "spider", "scraper", "curl", "wget",
            "python", "java", "go-http", "axios", "fetch",
            "googlebot", "bingbot", "slurp", "duckduckbot", "baiduspider",
            "yandexbot", "facebookexternalhit", "twitterbot", "linkedinbot",
        ];

        bot_patterns.iter().any(|pattern| ua_lower.contains(pattern))
    }
}

/// Raw click event before sanitization
#[derive(Debug, Clone)]
pub struct RawClickEvent {
    pub short_code: String,
    pub timestamp: DateTime<Utc>,
    pub ip_address: String,
    pub country_code: Option<String>,
    pub region: Option<String>,
    pub city: Option<String>,
    pub referrer: Option<String>,
    pub user_agent: Option<String>,
}

impl RawClickEvent {
    /// Create a new raw click event
    pub fn new(short_code: String, ip_address: String) -> Self {
        Self {
            short_code,
            timestamp: Utc::now(),
            ip_address,
            country_code: None,
            region: None,
            city: None,
            referrer: None,
            user_agent: None,
        }
    }

    /// Set geo location
    pub fn with_geo(mut self, country: Option<String>, region: Option<String>, city: Option<String>) -> Self {
        self.country_code = country;
        self.region = region;
        self.city = city;
        self
    }

    /// Set referrer
    pub fn with_referrer(mut self, referrer: Option<String>) -> Self {
        self.referrer = referrer;
        self
    }

    /// Set user agent
    pub fn with_user_agent(mut self, user_agent: Option<String>) -> Self {
        self.user_agent = user_agent;
        self
    }
}
