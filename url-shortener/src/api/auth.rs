//! Authentication API handlers

use std::sync::Arc;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use tracing::instrument;
use uuid::Uuid;

use crate::error::{AppError, AppResult};
use crate::infrastructure::AppState;
use crate::middleware::auth::AuthenticatedUser;

/// Create API key request
#[derive(Debug, Deserialize)]
pub struct CreateApiKeyRequest {
    pub name: Option<String>,
    #[serde(default)]
    pub scopes: Vec<String>,
    pub expires_in_days: Option<u32>,
}

/// Create API key response
#[derive(Debug, Serialize)]
pub struct CreateApiKeyResponse {
    pub id: Uuid,
    pub key: String, // Full key - only shown once!
    pub prefix: String,
    pub name: Option<String>,
    pub scopes: Vec<String>,
    pub created_at: DateTime<Utc>,
    pub expires_at: Option<DateTime<Utc>>,
}

/// API key list item
#[derive(Debug, Serialize)]
pub struct ApiKeyListItem {
    pub id: Uuid,
    pub prefix: String,
    pub name: Option<String>,
    pub scopes: Vec<String>,
    pub created_at: DateTime<Utc>,
    pub expires_at: Option<DateTime<Utc>>,
    pub last_used_at: Option<DateTime<Utc>>,
    pub is_active: bool,
}

/// Create a new API key
#[instrument(skip(state))]
pub async fn create_api_key(
    State(state): State<Arc<AppState>>,
    user: AuthenticatedUser,
    Json(request): Json<CreateApiKeyRequest>,
) -> AppResult<(StatusCode, Json<CreateApiKeyResponse>)> {
    // Generate API key
    let id = Uuid::new_v4();
    let now = Utc::now();

    // Generate the actual key using random u128 values
    let random1: u128 = rand::random();
    let random2: u64 = rand::random();
    let encoded = format!("{}{}", base62::encode(random1), base62::encode(random2 as u128));
    let full_key = format!("urlsh_sk_{}", &encoded[..32]);
    let prefix = full_key[..16].to_string();

    // Calculate expiration
    let expires_at = request.expires_in_days
        .map(|days| now + chrono::Duration::days(days as i64));

    // Default scopes if none provided
    let scopes = if request.scopes.is_empty() {
        vec!["read".to_string(), "write".to_string()]
    } else {
        request.scopes
    };

    // In a real implementation, we would:
    // 1. Hash the full_key with Argon2
    // 2. Store the hash, prefix, and metadata in the database
    // For now, we'll just return the response

    tracing::info!(
        user_id = %user.user_id,
        key_prefix = %prefix,
        "API key created"
    );

    Ok((StatusCode::CREATED, Json(CreateApiKeyResponse {
        id,
        key: full_key, // Only shown once!
        prefix,
        name: request.name,
        scopes,
        created_at: now,
        expires_at,
    })))
}

/// List API keys for the authenticated user
#[instrument(skip(state))]
pub async fn list_api_keys(
    State(state): State<Arc<AppState>>,
    user: AuthenticatedUser,
) -> AppResult<Json<Vec<ApiKeyListItem>>> {
    // In a real implementation, we would fetch from the database
    // For now, return an empty list

    tracing::debug!(user_id = %user.user_id, "Listing API keys");

    Ok(Json(vec![]))
}

/// Revoke an API key
#[instrument(skip(state))]
pub async fn revoke_api_key(
    State(state): State<Arc<AppState>>,
    user: AuthenticatedUser,
    Path(key_id): Path<Uuid>,
) -> AppResult<StatusCode> {
    // In a real implementation, we would:
    // 1. Verify the key belongs to the user
    // 2. Mark it as inactive in the database

    tracing::info!(
        user_id = %user.user_id,
        key_id = %key_id,
        "API key revoked"
    );

    Ok(StatusCode::NO_CONTENT)
}
