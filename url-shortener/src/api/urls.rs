//! URL management API handlers

use std::sync::Arc;

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use tracing::instrument;

use crate::domain::{
    BulkCreateRequest, BulkCreateResponse, CreateUrlRequest, CreateUrlResponse,
    PaginatedResponse, PaginationParams, UrlResponse, UserTier,
};
use crate::error::{AppError, AppResult};
use crate::infrastructure::AppState;
use crate::middleware::auth::AuthenticatedUser;

/// Create a new short URL
#[instrument(skip(state))]
pub async fn create_url(
    State(state): State<Arc<AppState>>,
    user: Option<AuthenticatedUser>,
    Json(request): Json<CreateUrlRequest>,
) -> AppResult<(StatusCode, Json<CreateUrlResponse>)> {
    let (user_id, tier) = match user {
        Some(u) => (Some(u.user_id), u.tier),
        None => (None, UserTier::Free),
    };

    let response = state.url_service.create_url(request, user_id, tier).await?;

    Ok((StatusCode::CREATED, Json(response)))
}

/// List URLs for the authenticated user
#[instrument(skip(state))]
pub async fn list_urls(
    State(state): State<Arc<AppState>>,
    user: AuthenticatedUser,
    Query(pagination): Query<PaginationParams>,
) -> AppResult<Json<PaginatedResponse<UrlResponse>>> {
    let response = state.url_service.list_urls(&user.user_id, pagination).await?;

    Ok(Json(response))
}

/// Get URL details
#[instrument(skip(state))]
pub async fn get_url(
    State(state): State<Arc<AppState>>,
    user: Option<AuthenticatedUser>,
    Path(code): Path<String>,
) -> AppResult<Json<UrlResponse>> {
    let user_id = user.as_ref().map(|u| u.user_id.as_str());
    let response = state.url_service.get_url(&code, user_id).await?;

    Ok(Json(response))
}

/// Delete a URL
#[instrument(skip(state))]
pub async fn delete_url(
    State(state): State<Arc<AppState>>,
    user: AuthenticatedUser,
    Path(code): Path<String>,
) -> AppResult<StatusCode> {
    state.url_service.delete_url(&code, &user.user_id).await?;

    Ok(StatusCode::NO_CONTENT)
}

/// Bulk create URLs
#[instrument(skip(state))]
pub async fn bulk_create(
    State(state): State<Arc<AppState>>,
    user: AuthenticatedUser,
    Json(request): Json<BulkCreateRequest>,
) -> AppResult<(StatusCode, Json<BulkCreateResponse>)> {
    // Bulk create requires at least premium tier
    if user.tier == UserTier::Free {
        return Err(AppError::Forbidden("Bulk creation requires Premium tier or higher".to_string()));
    }

    let response = state.url_service.bulk_create(request, Some(user.user_id), user.tier).await?;

    Ok((StatusCode::CREATED, Json(response)))
}
