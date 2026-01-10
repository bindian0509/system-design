//! Cache service implementations

use async_trait::async_trait;
use deadpool_redis::{Config, Pool, Runtime};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::instrument;

use crate::error::{AppError, AppResult};

/// Cache service trait
#[async_trait]
pub trait CacheService: Send + Sync {
    /// Get a URL from cache
    async fn get_url(&self, code: &str) -> AppResult<Option<String>>;

    /// Set a URL in cache with TTL
    async fn set_url(&self, code: &str, url: &str, ttl_seconds: u64) -> AppResult<()>;

    /// Delete a URL from cache
    async fn delete_url(&self, code: &str) -> AppResult<()>;

    /// Check if a key exists
    async fn exists(&self, key: &str) -> AppResult<bool>;

    /// Increment a counter (for rate limiting)
    async fn incr(&self, key: &str, ttl_seconds: u64) -> AppResult<u64>;

    /// Get a counter value
    async fn get_counter(&self, key: &str) -> AppResult<u64>;
}

/// Redis cache service
pub struct RedisCacheService {
    pool: Pool,
    prefix: String,
}

impl RedisCacheService {
    /// Create a new Redis cache service
    pub async fn new(redis_url: &str, pool_size: usize) -> AppResult<Self> {
        let cfg = Config::from_url(redis_url);
        let pool = cfg.builder()
            .map_err(|e| AppError::Cache(e.to_string()))?
            .max_size(pool_size)
            .runtime(Runtime::Tokio1)
            .build()
            .map_err(|e| AppError::Cache(e.to_string()))?;

        Ok(Self {
            pool,
            prefix: "urlsh:".to_string(),
        })
    }

    /// Get a connection from the pool
    async fn get_conn(&self) -> AppResult<deadpool_redis::Connection> {
        self.pool.get()
            .await
            .map_err(|e| AppError::Cache(e.to_string()))
    }

    /// Build a cache key
    fn key(&self, suffix: &str) -> String {
        format!("{}{}", self.prefix, suffix)
    }
}

#[async_trait]
impl CacheService for RedisCacheService {
    #[instrument(skip(self))]
    async fn get_url(&self, code: &str) -> AppResult<Option<String>> {
        let mut conn = self.get_conn().await?;
        let key = self.key(&format!("url:{}", code));

        let result: Option<String> = redis::cmd("GET")
            .arg(&key)
            .query_async(&mut conn)
            .await
            .map_err(|e| AppError::Cache(e.to_string()))?;

        Ok(result)
    }

    #[instrument(skip(self))]
    async fn set_url(&self, code: &str, url: &str, ttl_seconds: u64) -> AppResult<()> {
        let mut conn = self.get_conn().await?;
        let key = self.key(&format!("url:{}", code));

        redis::cmd("SETEX")
            .arg(&key)
            .arg(ttl_seconds)
            .arg(url)
            .query_async::<_, ()>(&mut conn)
            .await
            .map_err(|e| AppError::Cache(e.to_string()))?;

        Ok(())
    }

    #[instrument(skip(self))]
    async fn delete_url(&self, code: &str) -> AppResult<()> {
        let mut conn = self.get_conn().await?;
        let key = self.key(&format!("url:{}", code));

        redis::cmd("DEL")
            .arg(&key)
            .query_async::<_, ()>(&mut conn)
            .await
            .map_err(|e| AppError::Cache(e.to_string()))?;

        Ok(())
    }

    #[instrument(skip(self))]
    async fn exists(&self, key: &str) -> AppResult<bool> {
        let mut conn = self.get_conn().await?;
        let full_key = self.key(key);

        let exists: bool = redis::cmd("EXISTS")
            .arg(&full_key)
            .query_async(&mut conn)
            .await
            .map_err(|e| AppError::Cache(e.to_string()))?;

        Ok(exists)
    }

    #[instrument(skip(self))]
    async fn incr(&self, key: &str, ttl_seconds: u64) -> AppResult<u64> {
        let mut conn = self.get_conn().await?;
        let full_key = self.key(key);

        // Use MULTI/EXEC for atomic increment + expire
        let (count,): (u64,) = redis::pipe()
            .atomic()
            .incr(&full_key, 1u64)
            .expire(&full_key, ttl_seconds as i64)
            .ignore()
            .query_async(&mut conn)
            .await
            .map_err(|e| AppError::Cache(e.to_string()))?;

        Ok(count)
    }

    #[instrument(skip(self))]
    async fn get_counter(&self, key: &str) -> AppResult<u64> {
        let mut conn = self.get_conn().await?;
        let full_key = self.key(key);

        let count: Option<u64> = redis::cmd("GET")
            .arg(&full_key)
            .query_async(&mut conn)
            .await
            .map_err(|e| AppError::Cache(e.to_string()))?;

        Ok(count.unwrap_or(0))
    }
}

/// In-memory cache service (for local development)
pub struct MemoryCacheService {
    cache: Arc<RwLock<HashMap<String, CacheEntry>>>,
}

struct CacheEntry {
    value: String,
    expires_at: Option<std::time::Instant>,
}

impl MemoryCacheService {
    /// Create a new in-memory cache service
    pub fn new() -> Self {
        let cache = Arc::new(RwLock::new(HashMap::new()));

        // Start cleanup task
        let cache_clone = cache.clone();
        tokio::spawn(async move {
            loop {
                tokio::time::sleep(Duration::from_secs(60)).await;
                Self::cleanup(&cache_clone).await;
            }
        });

        Self { cache }
    }

    /// Clean up expired entries
    async fn cleanup(cache: &Arc<RwLock<HashMap<String, CacheEntry>>>) {
        let now = std::time::Instant::now();
        let mut cache = cache.write().await;
        cache.retain(|_, entry| {
            entry.expires_at.map_or(true, |exp| exp > now)
        });
    }
}

impl Default for MemoryCacheService {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl CacheService for MemoryCacheService {
    async fn get_url(&self, code: &str) -> AppResult<Option<String>> {
        let key = format!("url:{}", code);
        let cache = self.cache.read().await;

        if let Some(entry) = cache.get(&key) {
            // Check expiration
            if let Some(expires_at) = entry.expires_at {
                if expires_at <= std::time::Instant::now() {
                    return Ok(None);
                }
            }
            return Ok(Some(entry.value.clone()));
        }

        Ok(None)
    }

    async fn set_url(&self, code: &str, url: &str, ttl_seconds: u64) -> AppResult<()> {
        let key = format!("url:{}", code);
        let expires_at = if ttl_seconds > 0 {
            Some(std::time::Instant::now() + Duration::from_secs(ttl_seconds))
        } else {
            None
        };

        let entry = CacheEntry {
            value: url.to_string(),
            expires_at,
        };

        self.cache.write().await.insert(key, entry);
        Ok(())
    }

    async fn delete_url(&self, code: &str) -> AppResult<()> {
        let key = format!("url:{}", code);
        self.cache.write().await.remove(&key);
        Ok(())
    }

    async fn exists(&self, key: &str) -> AppResult<bool> {
        let cache = self.cache.read().await;

        if let Some(entry) = cache.get(key) {
            if let Some(expires_at) = entry.expires_at {
                return Ok(expires_at > std::time::Instant::now());
            }
            return Ok(true);
        }

        Ok(false)
    }

    async fn incr(&self, key: &str, ttl_seconds: u64) -> AppResult<u64> {
        let mut cache = self.cache.write().await;

        let entry = cache.entry(key.to_string()).or_insert_with(|| CacheEntry {
            value: "0".to_string(),
            expires_at: Some(std::time::Instant::now() + Duration::from_secs(ttl_seconds)),
        });

        let count: u64 = entry.value.parse().unwrap_or(0) + 1;
        entry.value = count.to_string();

        Ok(count)
    }

    async fn get_counter(&self, key: &str) -> AppResult<u64> {
        let cache = self.cache.read().await;

        if let Some(entry) = cache.get(key) {
            return Ok(entry.value.parse().unwrap_or(0));
        }

        Ok(0)
    }
}

/// Mock cache service for testing
#[cfg(test)]
pub struct MockCacheService {
    cache: Arc<RwLock<HashMap<String, String>>>,
}

#[cfg(test)]
impl MockCacheService {
    pub fn new() -> Self {
        Self {
            cache: Arc::new(RwLock::new(HashMap::new())),
        }
    }
}

#[cfg(test)]
#[async_trait]
impl CacheService for MockCacheService {
    async fn get_url(&self, code: &str) -> AppResult<Option<String>> {
        Ok(self.cache.read().await.get(&format!("url:{}", code)).cloned())
    }

    async fn set_url(&self, code: &str, url: &str, _ttl_seconds: u64) -> AppResult<()> {
        self.cache.write().await.insert(format!("url:{}", code), url.to_string());
        Ok(())
    }

    async fn delete_url(&self, code: &str) -> AppResult<()> {
        self.cache.write().await.remove(&format!("url:{}", code));
        Ok(())
    }

    async fn exists(&self, key: &str) -> AppResult<bool> {
        Ok(self.cache.read().await.contains_key(key))
    }

    async fn incr(&self, key: &str, _ttl_seconds: u64) -> AppResult<u64> {
        let mut cache = self.cache.write().await;
        let count: u64 = cache.get(key).and_then(|v| v.parse().ok()).unwrap_or(0) + 1;
        cache.insert(key.to_string(), count.to_string());
        Ok(count)
    }

    async fn get_counter(&self, key: &str) -> AppResult<u64> {
        Ok(self.cache.read().await.get(key).and_then(|v| v.parse().ok()).unwrap_or(0))
    }
}
