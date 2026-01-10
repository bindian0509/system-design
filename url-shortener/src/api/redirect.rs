//! Redirect handler

use std::sync::Arc;

use axum::{
    extract::{ConnectInfo, Path, State},
    http::{header, HeaderMap, StatusCode},
    response::{IntoResponse, Redirect, Response},
};
use std::net::SocketAddr;
use tracing::{info, instrument};

use crate::domain::analytics::RawClickEvent;
use crate::error::AppError;
use crate::infrastructure::AppState;

/// Handle redirect from short URL to original URL
#[instrument(skip(state, headers))]
pub async fn handle_redirect(
    State(state): State<Arc<AppState>>,
    Path(code): Path<String>,
    headers: HeaderMap,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
) -> Response {
    // Get the redirect URL
    let url = match state.url_service.get_redirect_url(&code).await {
        Ok(url) => url,
        Err(AppError::UrlNotFound(_)) => {
            return (StatusCode::NOT_FOUND, "Short URL not found").into_response();
        }
        Err(AppError::UrlExpired(_)) => {
            return (StatusCode::GONE, "This short URL has expired").into_response();
        }
        Err(AppError::UrlDisabled(_)) => {
            return (StatusCode::FORBIDDEN, "This short URL has been disabled").into_response();
        }
        Err(e) => {
            tracing::error!(error = %e, "Failed to get redirect URL");
            return (StatusCode::INTERNAL_SERVER_ERROR, "Internal error").into_response();
        }
    };

    // Extract request metadata for analytics (fire and forget)
    let ip = addr.ip().to_string();
    let referrer = headers
        .get(header::REFERER)
        .and_then(|v| v.to_str().ok())
        .map(String::from);
    let user_agent = headers
        .get(header::USER_AGENT)
        .and_then(|v| v.to_str().ok())
        .map(String::from);

    // Record analytics asynchronously
    let analytics_service = state.analytics_service.clone();
    let code_clone = code.clone();
    tokio::spawn(async move {
        let event = RawClickEvent::new(code_clone, ip)
            .with_referrer(referrer)
            .with_user_agent(user_agent);

        if let Err(e) = analytics_service.record_click(event).await {
            tracing::warn!(error = %e, "Failed to record click event");
        }
    });

    // Increment click count asynchronously
    let url_service = state.url_service.clone();
    let code_clone = code.clone();
    tokio::spawn(async move {
        if let Err(e) = url_service.record_click(&code_clone).await {
            tracing::warn!(error = %e, "Failed to increment click count");
        }
    });

    info!(short_code = %code, destination = %url, "Redirecting");

    // Use 301 for permanent redirect (helps with SEO and caching)
    Redirect::permanent(&url).into_response()
}
