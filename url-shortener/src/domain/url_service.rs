//! URL Service - Core business logic for URL operations

use std::sync::Arc;

use chrono::{Duration, Utc};
use tracing::{info, instrument, warn};
use url::Url as UrlParser;
use uuid::Uuid;
use validator::Validate;

use crate::config::UrlConfig;
use crate::domain::{
    CreateUrlRequest, CreateUrlResponse, Url, UrlResponse, UserTier,
    BulkCreateRequest, BulkCreateResponse, BulkCreateError,
    PaginatedResponse, PaginationInfo, PaginationParams,
};
use crate::error::{AppError, AppResult};
use crate::infrastructure::{UrlRepository, CacheService};

use super::id_generator::IdGenerator;

/// URL Service - handles all URL-related business logic
pub struct UrlService {
    repository: Arc<dyn UrlRepository>,
    cache: Arc<dyn CacheService>,
    id_generator: IdGenerator,
    config: UrlConfig,
}

impl UrlService {
    /// Create a new URL service
    pub fn new(
        repository: Arc<dyn UrlRepository>,
        cache: Arc<dyn CacheService>,
        config: UrlConfig,
    ) -> Self {
        Self {
            repository,
            cache,
            id_generator: IdGenerator::new(config.code_length),
            config,
        }
    }

    /// Create a new shortened URL
    #[instrument(skip(self), fields(url = %request.url))]
    pub async fn create_url(
        &self,
        request: CreateUrlRequest,
        user_id: Option<String>,
        tier: UserTier,
    ) -> AppResult<CreateUrlResponse> {
        // Validate request
        request.validate()?;

        // Validate the URL
        self.validate_url(&request.url)?;

        // Determine the short code
        let (short_code, is_custom) = if let Some(alias) = &request.custom_alias {
            // Validate custom alias
            if !IdGenerator::is_valid_custom_alias(alias, tier.max_alias_length()) {
                return Err(AppError::Validation(format!(
                    "Invalid custom alias. Must be 4-{} alphanumeric characters or hyphens.",
                    tier.max_alias_length()
                )));
            }

            // Check if alias is taken
            if self.repository.exists(alias).await? {
                return Err(AppError::AliasTaken(alias.clone()));
            }

            (alias.clone(), true)
        } else {
            // Generate a new code with collision check
            let code = self.generate_unique_code().await?;
            (code, false)
        };

        // Calculate expiration
        let expires_at = request.ttl_seconds
            .or(tier.default_ttl())
            .map(|ttl| Utc::now() + Duration::seconds(ttl));

        // Create the URL entity
        let mut url = Url::new(
            short_code.clone(),
            request.url.clone(),
            user_id,
            tier,
            is_custom,
        );
        url.expires_at = expires_at;
        url.title = request.title;
        url.description = request.description;
        url.tags = request.tags.unwrap_or_default();

        // Save to repository
        self.repository.save(&url).await?;

        // Cache the URL for fast redirects
        self.cache.set_url(&short_code, &url.original_url, self.config.max_url_length as u64).await?;

        info!(short_code = %short_code, "URL created successfully");

        Ok(CreateUrlResponse {
            id: url.id,
            short_code: short_code.clone(),
            short_url: format!("{}/{}", self.config.base_url, short_code),
            original_url: url.original_url,
            created_at: url.created_at,
            expires_at: url.expires_at,
        })
    }

    /// Create multiple URLs in bulk
    #[instrument(skip(self))]
    pub async fn bulk_create(
        &self,
        request: BulkCreateRequest,
        user_id: Option<String>,
        tier: UserTier,
    ) -> AppResult<BulkCreateResponse> {
        request.validate()?;

        let mut created = Vec::new();
        let mut errors = Vec::new();

        for (index, url_request) in request.urls.into_iter().enumerate() {
            match self.create_url(url_request.clone(), user_id.clone(), tier).await {
                Ok(response) => created.push(response),
                Err(e) => errors.push(BulkCreateError {
                    index,
                    url: url_request.url,
                    error: e.to_string(),
                }),
            }
        }

        Ok(BulkCreateResponse { created, errors })
    }

    /// Get a URL by short code (for redirect)
    #[instrument(skip(self))]
    pub async fn get_redirect_url(&self, code: &str) -> AppResult<String> {
        // Try cache first
        if let Some(url) = self.cache.get_url(code).await? {
            return Ok(url);
        }

        // Fallback to repository
        let url = self.repository
            .find_by_code(code)
            .await?
            .ok_or_else(|| AppError::UrlNotFound(code.to_string()))?;

        // Check if URL can be redirected
        if !url.is_active {
            return Err(AppError::UrlDisabled(code.to_string()));
        }

        if url.is_expired() {
            return Err(AppError::UrlExpired(code.to_string()));
        }

        // Update cache
        self.cache.set_url(code, &url.original_url, 86400).await?;

        Ok(url.original_url)
    }

    /// Get URL details
    #[instrument(skip(self))]
    pub async fn get_url(&self, code: &str, user_id: Option<&str>) -> AppResult<UrlResponse> {
        let url = self.repository
            .find_by_code(code)
            .await?
            .ok_or_else(|| AppError::UrlNotFound(code.to_string()))?;

        // Check ownership if user_id is provided
        if let Some(uid) = user_id {
            if url.user_id.as_deref() != Some(uid) {
                return Err(AppError::Forbidden("You don't have access to this URL".to_string()));
            }
        }

        Ok(UrlResponse::from_url(&url, &self.config.base_url))
    }

    /// List URLs for a user
    #[instrument(skip(self))]
    pub async fn list_urls(
        &self,
        user_id: &str,
        pagination: PaginationParams,
    ) -> AppResult<PaginatedResponse<UrlResponse>> {
        let (urls, total) = self.repository
            .find_by_user(user_id, pagination.page, pagination.limit)
            .await?;

        let total_pages = (total as f64 / pagination.limit as f64).ceil() as u32;

        let data: Vec<UrlResponse> = urls
            .iter()
            .map(|url| UrlResponse::from_url(url, &self.config.base_url))
            .collect();

        Ok(PaginatedResponse {
            data,
            pagination: PaginationInfo {
                page: pagination.page,
                limit: pagination.limit,
                total_items: total,
                total_pages,
                has_next: pagination.page < total_pages,
                has_prev: pagination.page > 1,
            },
        })
    }

    /// Delete a URL (soft delete)
    #[instrument(skip(self))]
    pub async fn delete_url(&self, code: &str, user_id: &str) -> AppResult<()> {
        let url = self.repository
            .find_by_code(code)
            .await?
            .ok_or_else(|| AppError::UrlNotFound(code.to_string()))?;

        // Check ownership
        if url.user_id.as_deref() != Some(user_id) {
            return Err(AppError::Forbidden("You don't have permission to delete this URL".to_string()));
        }

        // Soft delete
        self.repository.soft_delete(code).await?;

        // Remove from cache
        self.cache.delete_url(code).await?;

        info!(short_code = %code, "URL deleted");

        Ok(())
    }

    /// Record a click event
    #[instrument(skip(self))]
    pub async fn record_click(&self, code: &str) -> AppResult<()> {
        self.repository.increment_click_count(code).await?;
        Ok(())
    }

    // Private helper methods

    /// Validate the destination URL
    fn validate_url(&self, url: &str) -> AppResult<()> {
        // Check length
        if url.len() > self.config.max_url_length {
            return Err(AppError::InvalidUrl(format!(
                "URL exceeds maximum length of {} characters",
                self.config.max_url_length
            )));
        }

        // Parse and validate
        let parsed = UrlParser::parse(url)?;

        // Only allow http and https
        if parsed.scheme() != "http" && parsed.scheme() != "https" {
            return Err(AppError::InvalidUrl("Only HTTP and HTTPS URLs are allowed".to_string()));
        }

        // Block localhost and private IPs
        if let Some(host) = parsed.host_str() {
            if self.is_private_host(host) {
                return Err(AppError::InvalidUrl("Private/localhost URLs are not allowed".to_string()));
            }
        }

        Ok(())
    }

    /// Check if a host is private/localhost
    fn is_private_host(&self, host: &str) -> bool {
        let host_lower = host.to_lowercase();

        // Check localhost variations
        if host_lower == "localhost" || host_lower == "127.0.0.1" || host_lower == "::1" {
            return true;
        }

        // Check private IP ranges
        if let Ok(ip) = host.parse::<std::net::IpAddr>() {
            return match ip {
                std::net::IpAddr::V4(ipv4) => {
                    ipv4.is_private() || ipv4.is_loopback() || ipv4.is_link_local()
                }
                std::net::IpAddr::V6(ipv6) => {
                    ipv6.is_loopback()
                }
            };
        }

        false
    }

    /// Generate a unique short code with collision checking
    async fn generate_unique_code(&self) -> AppResult<String> {
        const MAX_RETRIES: usize = 3;

        for attempt in 0..MAX_RETRIES {
            let code = if attempt == 0 {
                self.id_generator.generate()
            } else {
                // Use random generation for retries
                self.id_generator.generate_random()
            };

            // Check if code exists
            if !self.repository.exists(&code).await? {
                return Ok(code);
            }

            warn!(code = %code, attempt = attempt, "Code collision detected, retrying");
        }

        Err(AppError::Internal("Failed to generate unique code after multiple attempts".to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_private_host() {
        let config = UrlConfig::default();
        let service = UrlService::new(
            Arc::new(crate::infrastructure::MockUrlRepository::new()),
            Arc::new(crate::infrastructure::MockCacheService::new()),
            config,
        );

        assert!(service.is_private_host("localhost"));
        assert!(service.is_private_host("127.0.0.1"));
        assert!(service.is_private_host("192.168.1.1"));
        assert!(service.is_private_host("10.0.0.1"));

        assert!(!service.is_private_host("google.com"));
        assert!(!service.is_private_host("8.8.8.8"));
    }
}
