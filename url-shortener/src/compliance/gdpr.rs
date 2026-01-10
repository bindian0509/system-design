//! GDPR compliance implementation

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tracing::instrument;
use uuid::Uuid;

use crate::error::AppResult;
use crate::infrastructure::{UrlRepository, CacheService};

/// GDPR Service for handling data subject rights
pub struct GdprService {
    repository: Arc<dyn UrlRepository>,
    cache: Arc<dyn CacheService>,
}

impl GdprService {
    pub fn new(
        repository: Arc<dyn UrlRepository>,
        cache: Arc<dyn CacheService>,
    ) -> Self {
        Self { repository, cache }
    }

    /// Article 15: Right of Access
    /// Returns all personal data associated with a user
    #[instrument(skip(self))]
    pub async fn get_user_data(&self, user_id: &str) -> AppResult<UserDataExport> {
        let (urls, _) = self.repository.find_by_user(user_id, 1, 1000).await?;

        Ok(UserDataExport {
            user_id: user_id.to_string(),
            exported_at: Utc::now(),
            urls: urls.into_iter().map(|u| UrlExport {
                short_code: u.short_code,
                original_url: u.original_url,
                created_at: u.created_at,
                click_count: u.click_count,
                is_active: u.is_active,
            }).collect(),
            // In production, include:
            // - Profile data
            // - API keys (metadata only)
            // - Analytics data
            // - Audit logs
        })
    }

    /// Article 17: Right to Erasure ("Right to be Forgotten")
    #[instrument(skip(self))]
    pub async fn erasure_request(
        &self,
        user_id: &str,
        request_id: &str,
    ) -> AppResult<ErasureConfirmation> {
        let started_at = Utc::now();

        // 1. Get all user URLs
        let (urls, _) = self.repository.find_by_user(user_id, 1, 10000).await?;
        let url_count = urls.len();

        // 2. Delete all URLs (hard delete for GDPR)
        for url in &urls {
            // Invalidate cache
            self.cache.delete_url(&url.short_code).await?;

            // Hard delete from database
            self.repository.hard_delete(&url.short_code).await?;
        }

        // 3. In production, also delete:
        // - Analytics data
        // - API keys
        // - User profile
        // - Session data

        tracing::info!(
            user_id = %user_id,
            request_id = %request_id,
            urls_deleted = url_count,
            "GDPR erasure completed"
        );

        Ok(ErasureConfirmation {
            request_id: request_id.to_string(),
            user_id: user_id.to_string(),
            started_at,
            completed_at: Utc::now(),
            urls_deleted: url_count,
            data_categories: vec![
                "urls".to_string(),
                "cache".to_string(),
            ],
        })
    }

    /// Article 20: Right to Data Portability
    #[instrument(skip(self))]
    pub async fn export_data(
        &self,
        user_id: &str,
        format: ExportFormat,
    ) -> AppResult<Vec<u8>> {
        let data = self.get_user_data(user_id).await?;

        match format {
            ExportFormat::Json => {
                Ok(serde_json::to_vec_pretty(&data)?)
            }
            ExportFormat::Csv => {
                let mut wtr = csv::Writer::from_writer(vec![]);
                wtr.write_record(&["short_code", "original_url", "created_at", "click_count", "is_active"])
                    .map_err(|e| crate::error::AppError::Internal(e.to_string()))?;

                for url in &data.urls {
                    wtr.write_record(&[
                        &url.short_code,
                        &url.original_url,
                        &url.created_at.to_rfc3339(),
                        &url.click_count.to_string(),
                        &url.is_active.to_string(),
                    ]).map_err(|e| crate::error::AppError::Internal(e.to_string()))?;
                }

                wtr.into_inner().map_err(|e| crate::error::AppError::Internal(e.to_string()))
            }
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserDataExport {
    pub user_id: String,
    pub exported_at: DateTime<Utc>,
    pub urls: Vec<UrlExport>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UrlExport {
    pub short_code: String,
    pub original_url: String,
    pub created_at: DateTime<Utc>,
    pub click_count: u64,
    pub is_active: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct ErasureConfirmation {
    pub request_id: String,
    pub user_id: String,
    pub started_at: DateTime<Utc>,
    pub completed_at: DateTime<Utc>,
    pub urls_deleted: usize,
    pub data_categories: Vec<String>,
}

#[derive(Debug, Clone, Copy)]
pub enum ExportFormat {
    Json,
    Csv,
}
