//! Infrastructure layer - External services and repositories

pub mod state;
pub mod url_repository;
pub mod cache;
pub mod analytics_repository;

pub use state::AppState;
pub use url_repository::{UrlRepository, SqliteUrlRepository};
pub use cache::{CacheService, MemoryCacheService};
pub use analytics_repository::AnalyticsRepository;

// AWS/DynamoDB support (optional)
#[cfg(feature = "aws")]
pub use url_repository::DynamoDbUrlRepository;

// Redis support (optional)
#[cfg(feature = "redis")]
pub use cache::RedisCacheService;

// Mock implementations for testing
#[cfg(test)]
pub use url_repository::MockUrlRepository;
#[cfg(test)]
pub use cache::MockCacheService;
