//! Authentication middleware

use std::sync::Arc;

use axum::{
    extract::{FromRequestParts, State},
    http::{header, request::Parts, StatusCode},
    response::{IntoResponse, Response},
};
use tracing::instrument;

use crate::domain::UserTier;
use crate::error::AppError;
use crate::infrastructure::AppState;

/// Authenticated user information extracted from request
#[derive(Debug, Clone)]
pub struct AuthenticatedUser {
    pub user_id: String,
    pub tier: UserTier,
    pub scopes: Vec<String>,
}

/// Extract authenticated user from request
#[axum::async_trait]
impl FromRequestParts<Arc<AppState>> for AuthenticatedUser {
    type Rejection = Response;

    async fn from_request_parts(
        parts: &mut Parts,
        state: &Arc<AppState>,
    ) -> Result<Self, Self::Rejection> {
        // Get Authorization header
        let auth_header = parts
            .headers
            .get(header::AUTHORIZATION)
            .and_then(|v| v.to_str().ok());

        match auth_header {
            Some(header) => {
                // Parse Bearer token or API key
                if let Some(token) = header.strip_prefix("Bearer ") {
                    validate_bearer_token(token, state).await
                } else if let Some(key) = header.strip_prefix("ApiKey ") {
                    validate_api_key(key, state).await
                } else {
                    Err(AppError::Unauthorized("Invalid authorization header format".to_string())
                        .into_response())
                }
            }
            None => {
                Err(AppError::Unauthorized("Authorization header required".to_string())
                    .into_response())
            }
        }
    }
}

/// Optional authenticated user wrapper (to avoid orphan rule)
#[derive(Debug, Clone)]
pub struct OptionalUser(pub Option<AuthenticatedUser>);

#[axum::async_trait]
impl<S: Send + Sync> FromRequestParts<S> for OptionalUser
where
    Arc<AppState>: FromRequestParts<S>,
{
    type Rejection = std::convert::Infallible;

    async fn from_request_parts(
        parts: &mut Parts,
        _state: &S,
    ) -> Result<Self, Self::Rejection> {
        // Try to get Authorization header
        let auth_header = parts
            .headers
            .get(header::AUTHORIZATION)
            .and_then(|v| v.to_str().ok());

        match auth_header {
            Some(header) => {
                // Parse Bearer token or API key
                if let Some(token) = header.strip_prefix("Bearer ") {
                    let parts: Vec<&str> = token.split(':').collect();
                    if parts.len() >= 2 {
                        let tier = match parts[1] {
                            "premium" => UserTier::Premium,
                            "enterprise" => UserTier::Enterprise,
                            _ => UserTier::Free,
                        };
                        return Ok(OptionalUser(Some(AuthenticatedUser {
                            user_id: parts[0].to_string(),
                            tier,
                            scopes: vec!["read".to_string(), "write".to_string()],
                        })));
                    }
                } else if let Some(key) = header.strip_prefix("ApiKey ") {
                    if key.starts_with("urlsh_sk_") {
                        return Ok(OptionalUser(Some(AuthenticatedUser {
                            user_id: "api_user".to_string(),
                            tier: UserTier::Premium,
                            scopes: vec!["read".to_string(), "write".to_string()],
                        })));
                    }
                }
            }
            None => {}
        }

        Ok(OptionalUser(None))
    }
}

/// Validate a Bearer token (JWT)
async fn validate_bearer_token(
    token: &str,
    state: &Arc<AppState>,
) -> Result<AuthenticatedUser, Response> {
    // In production, this would:
    // 1. Verify JWT signature with RS256
    // 2. Check token expiration
    // 3. Extract user claims

    // For development, accept a simple format: user_id:tier
    let parts: Vec<&str> = token.split(':').collect();

    if parts.len() >= 2 {
        let tier = match parts[1] {
            "premium" => UserTier::Premium,
            "enterprise" => UserTier::Enterprise,
            _ => UserTier::Free,
        };

        Ok(AuthenticatedUser {
            user_id: parts[0].to_string(),
            tier,
            scopes: vec!["read".to_string(), "write".to_string()],
        })
    } else {
        Err(AppError::Unauthorized("Invalid token format".to_string()).into_response())
    }
}

/// Validate an API key
async fn validate_api_key(
    key: &str,
    state: &Arc<AppState>,
) -> Result<AuthenticatedUser, Response> {
    // Validate key format
    if !key.starts_with("urlsh_sk_") {
        return Err(AppError::Unauthorized("Invalid API key format".to_string()).into_response());
    }

    // In production, this would:
    // 1. Extract key prefix
    // 2. Look up key by prefix in database
    // 3. Verify key hash with Argon2
    // 4. Check key expiration and active status
    // 5. Return associated user info

    // For development, accept any properly formatted key
    Ok(AuthenticatedUser {
        user_id: "api_user".to_string(),
        tier: UserTier::Premium,
        scopes: vec!["read".to_string(), "write".to_string()],
    })
}

/// Authentication middleware for routes
pub async fn authenticate(
    State(state): State<Arc<AppState>>,
    request: axum::http::Request<axum::body::Body>,
    next: axum::middleware::Next,
) -> Response {
    // The actual authentication is handled by the FromRequestParts implementation
    // This middleware is just a pass-through that can add logging

    let method = request.method().clone();
    let uri = request.uri().clone();

    tracing::debug!(method = %method, uri = %uri, "Processing authenticated request");

    next.run(request).await
}
