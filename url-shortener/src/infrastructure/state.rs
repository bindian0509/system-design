//! Application state

use std::sync::Arc;

use crate::config::AppConfig;
use crate::domain::UrlService;
use crate::domain::analytics::AnalyticsService;
use crate::error::AppResult;
use crate::infrastructure::{
    CacheService, MemoryCacheService, SqliteUrlRepository,
    UrlRepository, AnalyticsRepository,
};

#[cfg(feature = "redis")]
use crate::infrastructure::RedisCacheService;

#[cfg(feature = "aws")]
use crate::infrastructure::DynamoDbUrlRepository;

/// Application state shared across handlers
#[derive(Clone)]
pub struct AppState {
    /// URL service for business logic
    pub url_service: Arc<UrlService>,

    /// Analytics service
    pub analytics_service: Arc<AnalyticsService>,

    /// Configuration
    pub config: Arc<AppConfig>,

    /// Cache service
    pub cache: Arc<dyn CacheService>,

    /// URL repository
    pub repository: Arc<dyn UrlRepository>,
}

impl AppState {
    /// Create a new application state
    pub async fn new(config: &AppConfig) -> AppResult<Self> {
        // Initialize cache
        let cache: Arc<dyn CacheService> = Self::create_cache(config).await?;

        // Initialize repository
        let repository: Arc<dyn UrlRepository> = Self::create_repository(config).await?;

        // Initialize analytics repository (simplified for now)
        let analytics_repository: Arc<dyn AnalyticsRepository> =
            Arc::new(crate::infrastructure::analytics_repository::InMemoryAnalyticsRepository::new());

        // Create URL service
        let url_service = Arc::new(UrlService::new(
            repository.clone(),
            cache.clone(),
            config.url.clone(),
        ));

        // Create analytics service
        let daily_salt = std::env::var("ANALYTICS_SALT")
            .unwrap_or_else(|_| chrono::Utc::now().format("%Y-%m-%d").to_string());
        let analytics_service = Arc::new(AnalyticsService::new(analytics_repository, daily_salt));

        Ok(Self {
            url_service,
            analytics_service,
            config: Arc::new(config.clone()),
            cache,
            repository,
        })
    }

    async fn create_cache(config: &AppConfig) -> AppResult<Arc<dyn CacheService>> {
        #[cfg(feature = "redis")]
        if config.cache.cache_type == "redis" {
            if let Some(ref redis_url) = config.cache.redis_url {
                return Ok(Arc::new(RedisCacheService::new(redis_url, config.cache.pool_size).await?));
            }
        }

        // Default to in-memory cache
        Ok(Arc::new(MemoryCacheService::new()))
    }

    async fn create_repository(config: &AppConfig) -> AppResult<Arc<dyn UrlRepository>> {
        #[cfg(feature = "aws")]
        if config.database.db_type == "dynamodb" {
            return Ok(Arc::new(DynamoDbUrlRepository::new(&config.aws, &config.database.table_prefix).await?));
        }

        // Default to SQLite
        let db_url = config.database.url.as_deref()
            .unwrap_or("sqlite:./data/urls.db?mode=rwc");
        Ok(Arc::new(SqliteUrlRepository::new(db_url).await?))
    }
}
