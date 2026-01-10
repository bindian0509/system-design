//! URL Repository implementations

use async_trait::async_trait;
use chrono::Utc;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
#[allow(unused_imports)]
use tracing::instrument;

#[cfg(feature = "aws")]
use crate::config::AwsConfig;
use crate::domain::Url;
use crate::error::{AppError, AppResult};

/// URL Repository trait
#[async_trait]
pub trait UrlRepository: Send + Sync {
    /// Save a URL
    async fn save(&self, url: &Url) -> AppResult<()>;

    /// Find URL by short code
    async fn find_by_code(&self, code: &str) -> AppResult<Option<Url>>;

    /// Check if code exists
    async fn exists(&self, code: &str) -> AppResult<bool>;

    /// Find URLs by user ID
    async fn find_by_user(&self, user_id: &str, page: u32, limit: u32) -> AppResult<(Vec<Url>, u64)>;

    /// Soft delete a URL
    async fn soft_delete(&self, code: &str) -> AppResult<()>;

    /// Hard delete a URL (for GDPR)
    async fn hard_delete(&self, code: &str) -> AppResult<()>;

    /// Increment click count
    async fn increment_click_count(&self, code: &str) -> AppResult<()>;

    /// Update a URL
    async fn update(&self, url: &Url) -> AppResult<()>;
}

// DynamoDB URL Repository (only available with "aws" feature)
#[cfg(feature = "aws")]
pub struct DynamoDbUrlRepository {
    client: aws_sdk_dynamodb::Client,
    table_name: String,
}

#[cfg(feature = "aws")]
impl DynamoDbUrlRepository {
    /// Create a new DynamoDB repository
    pub async fn new(config: &AwsConfig, table_prefix: &str) -> AppResult<Self> {
        let aws_config = if config.local_mode {
            aws_config::defaults(aws_config::BehaviorVersion::latest())
                .endpoint_url(config.endpoint_url.as_deref().unwrap_or("http://localhost:8000"))
                .region(aws_config::Region::new(config.region.clone()))
                .load()
                .await
        } else {
            aws_config::defaults(aws_config::BehaviorVersion::latest())
                .region(aws_config::Region::new(config.region.clone()))
                .load()
                .await
        };

        let client = aws_sdk_dynamodb::Client::new(&aws_config);
        let table_name = format!("{}-urls", table_prefix);

        Ok(Self { client, table_name })
    }

    /// Convert Url to DynamoDB attributes
    fn url_to_item(&self, url: &Url) -> HashMap<String, aws_sdk_dynamodb::types::AttributeValue> {
        use aws_sdk_dynamodb::types::AttributeValue;

        let mut item = HashMap::new();

        item.insert("pk".to_string(), AttributeValue::S(format!("URL#{}", url.short_code)));
        item.insert("sk".to_string(), AttributeValue::S("v0".to_string()));
        item.insert("id".to_string(), AttributeValue::S(url.id.to_string()));
        item.insert("short_code".to_string(), AttributeValue::S(url.short_code.clone()));
        item.insert("original_url".to_string(), AttributeValue::S(url.original_url.clone()));
        item.insert("created_at".to_string(), AttributeValue::N(url.created_at.timestamp_millis().to_string()));
        item.insert("updated_at".to_string(), AttributeValue::N(url.updated_at.timestamp_millis().to_string()));
        item.insert("click_count".to_string(), AttributeValue::N(url.click_count.to_string()));
        item.insert("is_active".to_string(), AttributeValue::Bool(url.is_active));
        item.insert("is_custom_alias".to_string(), AttributeValue::Bool(url.is_custom_alias));
        item.insert("tier".to_string(), AttributeValue::S(serde_json::to_string(&url.tier).unwrap_or_default()));

        if let Some(ref user_id) = url.user_id {
            item.insert("user_id".to_string(), AttributeValue::S(user_id.clone()));
        }

        if let Some(expires_at) = url.expires_at {
            item.insert("expires_at".to_string(), AttributeValue::N(expires_at.timestamp().to_string()));
        }

        if let Some(ref title) = url.title {
            item.insert("title".to_string(), AttributeValue::S(title.clone()));
        }

        if let Some(ref desc) = url.description {
            item.insert("description".to_string(), AttributeValue::S(desc.clone()));
        }

        if !url.tags.is_empty() {
            item.insert("tags".to_string(), AttributeValue::Ss(url.tags.clone()));
        }

        item
    }

    /// Convert DynamoDB item to Url
    fn item_to_url(&self, item: &HashMap<String, aws_sdk_dynamodb::types::AttributeValue>) -> AppResult<Url> {
        use chrono::TimeZone;

        let id = item.get("id")
            .and_then(|v| v.as_s().ok())
            .and_then(|s| uuid::Uuid::parse_str(s).ok())
            .ok_or_else(|| AppError::Database("Missing id".to_string()))?;

        let short_code = item.get("short_code")
            .and_then(|v| v.as_s().ok())
            .cloned()
            .ok_or_else(|| AppError::Database("Missing short_code".to_string()))?;

        let original_url = item.get("original_url")
            .and_then(|v| v.as_s().ok())
            .cloned()
            .ok_or_else(|| AppError::Database("Missing original_url".to_string()))?;

        let created_at_ms = item.get("created_at")
            .and_then(|v| v.as_n().ok())
            .and_then(|n| n.parse::<i64>().ok())
            .ok_or_else(|| AppError::Database("Missing created_at".to_string()))?;

        let updated_at_ms = item.get("updated_at")
            .and_then(|v| v.as_n().ok())
            .and_then(|n| n.parse::<i64>().ok())
            .ok_or_else(|| AppError::Database("Missing updated_at".to_string()))?;

        Ok(Url {
            id,
            short_code,
            original_url,
            user_id: item.get("user_id").and_then(|v| v.as_s().ok()).cloned(),
            created_at: Utc.timestamp_millis_opt(created_at_ms).single()
                .ok_or_else(|| AppError::Database("Invalid created_at".to_string()))?,
            updated_at: Utc.timestamp_millis_opt(updated_at_ms).single()
                .ok_or_else(|| AppError::Database("Invalid updated_at".to_string()))?,
            expires_at: item.get("expires_at")
                .and_then(|v| v.as_n().ok())
                .and_then(|n| n.parse::<i64>().ok())
                .and_then(|ts| Utc.timestamp_opt(ts, 0).single()),
            last_accessed_at: None,
            click_count: item.get("click_count")
                .and_then(|v| v.as_n().ok())
                .and_then(|n| n.parse().ok())
                .unwrap_or(0),
            is_active: item.get("is_active")
                .and_then(|v| v.as_bool().ok())
                .copied()
                .unwrap_or(true),
            is_custom_alias: item.get("is_custom_alias")
                .and_then(|v| v.as_bool().ok())
                .copied()
                .unwrap_or(false),
            tier: item.get("tier")
                .and_then(|v| v.as_s().ok())
                .and_then(|s| serde_json::from_str(s).ok())
                .unwrap_or_default(),
            title: item.get("title").and_then(|v| v.as_s().ok()).cloned(),
            description: item.get("description").and_then(|v| v.as_s().ok()).cloned(),
            tags: item.get("tags")
                .and_then(|v| v.as_ss().ok())
                .cloned()
                .unwrap_or_default(),
            metadata: serde_json::Value::Null,
        })
    }
}

#[cfg(feature = "aws")]
#[async_trait]
impl UrlRepository for DynamoDbUrlRepository {
    #[instrument(skip(self, url))]
    async fn save(&self, url: &Url) -> AppResult<()> {
        let item = self.url_to_item(url);

        self.client.put_item()
            .table_name(&self.table_name)
            .set_item(Some(item))
            .send()
            .await
            .map_err(|e| AppError::Database(e.to_string()))?;

        Ok(())
    }

    #[instrument(skip(self))]
    async fn find_by_code(&self, code: &str) -> AppResult<Option<Url>> {
        use aws_sdk_dynamodb::types::AttributeValue;

        let result = self.client.get_item()
            .table_name(&self.table_name)
            .key("pk", AttributeValue::S(format!("URL#{}", code)))
            .key("sk", AttributeValue::S("v0".to_string()))
            .send()
            .await
            .map_err(|e| AppError::Database(e.to_string()))?;

        match result.item {
            Some(item) => Ok(Some(self.item_to_url(&item)?)),
            None => Ok(None),
        }
    }

    #[instrument(skip(self))]
    async fn exists(&self, code: &str) -> AppResult<bool> {
        Ok(self.find_by_code(code).await?.is_some())
    }

    #[instrument(skip(self))]
    async fn find_by_user(&self, user_id: &str, _page: u32, limit: u32) -> AppResult<(Vec<Url>, u64)> {
        use aws_sdk_dynamodb::types::AttributeValue;

        let result = self.client.query()
            .table_name(&self.table_name)
            .index_name("user-urls-index")
            .key_condition_expression("user_id = :uid")
            .expression_attribute_values(":uid", AttributeValue::S(user_id.to_string()))
            .scan_index_forward(false) // Newest first
            .limit(limit as i32)
            .send()
            .await
            .map_err(|e| AppError::Database(e.to_string()))?;

        let urls: Vec<Url> = result.items()
            .iter()
            .filter_map(|item| self.item_to_url(item).ok())
            .collect();

        let total = result.count() as u64;

        Ok((urls, total))
    }

    #[instrument(skip(self))]
    async fn soft_delete(&self, code: &str) -> AppResult<()> {
        use aws_sdk_dynamodb::types::AttributeValue;

        self.client.update_item()
            .table_name(&self.table_name)
            .key("pk", AttributeValue::S(format!("URL#{}", code)))
            .key("sk", AttributeValue::S("v0".to_string()))
            .update_expression("SET is_active = :inactive, updated_at = :now")
            .expression_attribute_values(":inactive", AttributeValue::Bool(false))
            .expression_attribute_values(":now", AttributeValue::N(Utc::now().timestamp_millis().to_string()))
            .send()
            .await
            .map_err(|e| AppError::Database(e.to_string()))?;

        Ok(())
    }

    #[instrument(skip(self))]
    async fn hard_delete(&self, code: &str) -> AppResult<()> {
        use aws_sdk_dynamodb::types::AttributeValue;

        self.client.delete_item()
            .table_name(&self.table_name)
            .key("pk", AttributeValue::S(format!("URL#{}", code)))
            .key("sk", AttributeValue::S("v0".to_string()))
            .send()
            .await
            .map_err(|e| AppError::Database(e.to_string()))?;

        Ok(())
    }

    #[instrument(skip(self))]
    async fn increment_click_count(&self, code: &str) -> AppResult<()> {
        use aws_sdk_dynamodb::types::AttributeValue;

        self.client.update_item()
            .table_name(&self.table_name)
            .key("pk", AttributeValue::S(format!("URL#{}", code)))
            .key("sk", AttributeValue::S("v0".to_string()))
            .update_expression("SET click_count = click_count + :inc, updated_at = :now")
            .expression_attribute_values(":inc", AttributeValue::N("1".to_string()))
            .expression_attribute_values(":now", AttributeValue::N(Utc::now().timestamp_millis().to_string()))
            .send()
            .await
            .map_err(|e| AppError::Database(e.to_string()))?;

        Ok(())
    }

    #[instrument(skip(self, url))]
    async fn update(&self, url: &Url) -> AppResult<()> {
        self.save(url).await
    }
}

/// SQLite URL Repository (for local/development)
pub struct SqliteUrlRepository {
    pool: sqlx::SqlitePool,
}

impl SqliteUrlRepository {
    /// Create a new SQLite repository
    pub async fn new(database_url: &str) -> AppResult<Self> {
        let pool = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(5)
            .connect(database_url)
            .await
            .map_err(|e| AppError::Database(e.to_string()))?;

        // Run migrations
        sqlx::migrate!("./migrations")
            .run(&pool)
            .await
            .map_err(|e| AppError::Database(e.to_string()))?;

        Ok(Self { pool })
    }
}

#[async_trait]
impl UrlRepository for SqliteUrlRepository {
    async fn save(&self, url: &Url) -> AppResult<()> {
        let tier = serde_json::to_string(&url.tier)?;
        let tags = serde_json::to_string(&url.tags)?;
        let metadata = serde_json::to_string(&url.metadata)?;

        sqlx::query(r#"
            INSERT INTO urls (id, short_code, original_url, user_id, created_at, updated_at,
                            expires_at, click_count, is_active, is_custom_alias, tier,
                            title, description, tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(short_code) DO UPDATE SET
                original_url = excluded.original_url,
                updated_at = excluded.updated_at,
                expires_at = excluded.expires_at,
                click_count = excluded.click_count,
                is_active = excluded.is_active,
                title = excluded.title,
                description = excluded.description,
                tags = excluded.tags,
                metadata = excluded.metadata
        "#)
        .bind(url.id.to_string())
        .bind(&url.short_code)
        .bind(&url.original_url)
        .bind(&url.user_id)
        .bind(url.created_at)
        .bind(url.updated_at)
        .bind(url.expires_at)
        .bind(url.click_count as i64)
        .bind(url.is_active)
        .bind(url.is_custom_alias)
        .bind(&tier)
        .bind(&url.title)
        .bind(&url.description)
        .bind(&tags)
        .bind(&metadata)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    async fn find_by_code(&self, code: &str) -> AppResult<Option<Url>> {
        let row = sqlx::query_as::<_, UrlRow>(
            "SELECT * FROM urls WHERE short_code = ?"
        )
        .bind(code)
        .fetch_optional(&self.pool)
        .await?;

        match row {
            Some(r) => Ok(Some(r.into_url()?)),
            None => Ok(None),
        }
    }

    async fn exists(&self, code: &str) -> AppResult<bool> {
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM urls WHERE short_code = ?"
        )
        .bind(code)
        .fetch_one(&self.pool)
        .await?;

        Ok(count.0 > 0)
    }

    async fn find_by_user(&self, user_id: &str, page: u32, limit: u32) -> AppResult<(Vec<Url>, u64)> {
        let offset = (page - 1) * limit;

        let rows = sqlx::query_as::<_, UrlRow>(
            "SELECT * FROM urls WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        .bind(user_id)
        .bind(limit as i64)
        .bind(offset as i64)
        .fetch_all(&self.pool)
        .await?;

        let total: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM urls WHERE user_id = ?"
        )
        .bind(user_id)
        .fetch_one(&self.pool)
        .await?;

        let urls: Result<Vec<Url>, _> = rows.into_iter().map(|r| r.into_url()).collect();

        Ok((urls?, total.0 as u64))
    }

    async fn soft_delete(&self, code: &str) -> AppResult<()> {
        sqlx::query("UPDATE urls SET is_active = 0, updated_at = ? WHERE short_code = ?")
            .bind(Utc::now())
            .bind(code)
            .execute(&self.pool)
            .await?;

        Ok(())
    }

    async fn hard_delete(&self, code: &str) -> AppResult<()> {
        sqlx::query("DELETE FROM urls WHERE short_code = ?")
            .bind(code)
            .execute(&self.pool)
            .await?;

        Ok(())
    }

    async fn increment_click_count(&self, code: &str) -> AppResult<()> {
        sqlx::query("UPDATE urls SET click_count = click_count + 1, updated_at = ? WHERE short_code = ?")
            .bind(Utc::now())
            .bind(code)
            .execute(&self.pool)
            .await?;

        Ok(())
    }

    async fn update(&self, url: &Url) -> AppResult<()> {
        self.save(url).await
    }
}

/// SQLite row representation
#[derive(sqlx::FromRow)]
struct UrlRow {
    id: String,
    short_code: String,
    original_url: String,
    user_id: Option<String>,
    created_at: chrono::DateTime<Utc>,
    updated_at: chrono::DateTime<Utc>,
    expires_at: Option<chrono::DateTime<Utc>>,
    click_count: i64,
    is_active: bool,
    is_custom_alias: bool,
    tier: String,
    title: Option<String>,
    description: Option<String>,
    tags: String,
    metadata: String,
}

impl UrlRow {
    fn into_url(self) -> AppResult<Url> {
        Ok(Url {
            id: uuid::Uuid::parse_str(&self.id).map_err(|e| AppError::Database(e.to_string()))?,
            short_code: self.short_code,
            original_url: self.original_url,
            user_id: self.user_id,
            created_at: self.created_at,
            updated_at: self.updated_at,
            expires_at: self.expires_at,
            last_accessed_at: None,
            click_count: self.click_count as u64,
            is_active: self.is_active,
            is_custom_alias: self.is_custom_alias,
            tier: serde_json::from_str(&self.tier).unwrap_or_default(),
            title: self.title,
            description: self.description,
            tags: serde_json::from_str(&self.tags).unwrap_or_default(),
            metadata: serde_json::from_str(&self.metadata).unwrap_or_default(),
        })
    }
}

/// Mock URL Repository for testing
#[cfg(test)]
pub struct MockUrlRepository {
    urls: Arc<RwLock<HashMap<String, Url>>>,
}

#[cfg(test)]
impl MockUrlRepository {
    pub fn new() -> Self {
        Self {
            urls: Arc::new(RwLock::new(HashMap::new())),
        }
    }
}

#[cfg(test)]
#[async_trait]
impl UrlRepository for MockUrlRepository {
    async fn save(&self, url: &Url) -> AppResult<()> {
        self.urls.write().await.insert(url.short_code.clone(), url.clone());
        Ok(())
    }

    async fn find_by_code(&self, code: &str) -> AppResult<Option<Url>> {
        Ok(self.urls.read().await.get(code).cloned())
    }

    async fn exists(&self, code: &str) -> AppResult<bool> {
        Ok(self.urls.read().await.contains_key(code))
    }

    async fn find_by_user(&self, user_id: &str, _page: u32, _limit: u32) -> AppResult<(Vec<Url>, u64)> {
        let urls: Vec<Url> = self.urls.read().await
            .values()
            .filter(|u| u.user_id.as_deref() == Some(user_id))
            .cloned()
            .collect();
        let total = urls.len() as u64;
        Ok((urls, total))
    }

    async fn soft_delete(&self, code: &str) -> AppResult<()> {
        if let Some(url) = self.urls.write().await.get_mut(code) {
            url.is_active = false;
        }
        Ok(())
    }

    async fn hard_delete(&self, code: &str) -> AppResult<()> {
        self.urls.write().await.remove(code);
        Ok(())
    }

    async fn increment_click_count(&self, code: &str) -> AppResult<()> {
        if let Some(url) = self.urls.write().await.get_mut(code) {
            url.click_count += 1;
        }
        Ok(())
    }

    async fn update(&self, url: &Url) -> AppResult<()> {
        self.save(url).await
    }
}
