//! Infrastructure layer - External services and repositories

pub mod state;
pub mod url_repository;
pub mod cache;
pub mod analytics_repository;

pub use state::AppState;
pub use url_repository::{UrlRepository, DynamoDbUrlRepository, SqliteUrlRepository};
pub use cache::{CacheService, RedisCacheService, MemoryCacheService};
pub use analytics_repository::AnalyticsRepository;

// Mock implementations for testing
#[cfg(test)]
pub use url_repository::MockUrlRepository;
#[cfg(test)]
pub use cache::MockCacheService;
