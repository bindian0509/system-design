//! Error types and handling

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde::Serialize;
use thiserror::Error;

/// Application error types
#[derive(Debug, Error)]
pub enum AppError {
    #[error("URL not found: {0}")]
    UrlNotFound(String),

    #[error("URL has expired: {0}")]
    UrlExpired(String),

    #[error("URL is disabled: {0}")]
    UrlDisabled(String),

    #[error("Invalid URL: {0}")]
    InvalidUrl(String),

    #[error("Custom alias already taken: {0}")]
    AliasTaken(String),

    #[error("Rate limit exceeded")]
    RateLimited,

    #[error("Unauthorized: {0}")]
    Unauthorized(String),

    #[error("Forbidden: {0}")]
    Forbidden(String),

    #[error("Validation error: {0}")]
    Validation(String),

    #[error("Database error: {0}")]
    Database(String),

    #[error("Cache error: {0}")]
    Cache(String),

    #[error("Internal error: {0}")]
    Internal(String),

    #[error("Configuration error: {0}")]
    Config(String),
}

/// Error response body
#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: ErrorDetails,
}

#[derive(Debug, Serialize)]
pub struct ErrorDetails {
    pub code: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub request_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub documentation_url: Option<String>,
}

impl AppError {
    /// Get the error code
    pub fn code(&self) -> &'static str {
        match self {
            AppError::UrlNotFound(_) => "URL_NOT_FOUND",
            AppError::UrlExpired(_) => "URL_EXPIRED",
            AppError::UrlDisabled(_) => "URL_DISABLED",
            AppError::InvalidUrl(_) => "INVALID_URL",
            AppError::AliasTaken(_) => "ALIAS_TAKEN",
            AppError::RateLimited => "RATE_LIMITED",
            AppError::Unauthorized(_) => "UNAUTHORIZED",
            AppError::Forbidden(_) => "FORBIDDEN",
            AppError::Validation(_) => "VALIDATION_ERROR",
            AppError::Database(_) => "DATABASE_ERROR",
            AppError::Cache(_) => "CACHE_ERROR",
            AppError::Internal(_) => "INTERNAL_ERROR",
            AppError::Config(_) => "CONFIG_ERROR",
        }
    }

    /// Get the HTTP status code
    pub fn status_code(&self) -> StatusCode {
        match self {
            AppError::UrlNotFound(_) => StatusCode::NOT_FOUND,
            AppError::UrlExpired(_) => StatusCode::GONE,
            AppError::UrlDisabled(_) => StatusCode::FORBIDDEN,
            AppError::InvalidUrl(_) => StatusCode::BAD_REQUEST,
            AppError::AliasTaken(_) => StatusCode::CONFLICT,
            AppError::RateLimited => StatusCode::TOO_MANY_REQUESTS,
            AppError::Unauthorized(_) => StatusCode::UNAUTHORIZED,
            AppError::Forbidden(_) => StatusCode::FORBIDDEN,
            AppError::Validation(_) => StatusCode::BAD_REQUEST,
            AppError::Database(_) => StatusCode::INTERNAL_SERVER_ERROR,
            AppError::Cache(_) => StatusCode::INTERNAL_SERVER_ERROR,
            AppError::Internal(_) => StatusCode::INTERNAL_SERVER_ERROR,
            AppError::Config(_) => StatusCode::INTERNAL_SERVER_ERROR,
        }
    }

    /// Get documentation URL for the error
    pub fn documentation_url(&self) -> String {
        format!("https://docs.shortener.io/errors/{}", self.code())
    }
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let status = self.status_code();
        let code = self.code().to_string();
        let message = self.to_string();
        let documentation_url = self.documentation_url();

        // Log the error
        match &self {
            AppError::Internal(_) | AppError::Database(_) | AppError::Cache(_) => {
                tracing::error!(error = %self, code = %code, "Internal error occurred");
            }
            _ => {
                tracing::warn!(error = %self, code = %code, "Client error occurred");
            }
        }

        let body = ErrorResponse {
            error: ErrorDetails {
                code,
                message,
                details: None,
                request_id: None, // Will be populated by middleware
                documentation_url: Some(documentation_url),
            },
        };

        (status, Json(body)).into_response()
    }
}

// Implement From for common error types
impl From<sqlx::Error> for AppError {
    fn from(err: sqlx::Error) -> Self {
        AppError::Database(err.to_string())
    }
}

impl From<redis::RedisError> for AppError {
    fn from(err: redis::RedisError) -> Self {
        AppError::Cache(err.to_string())
    }
}

impl From<aws_sdk_dynamodb::Error> for AppError {
    fn from(err: aws_sdk_dynamodb::Error) -> Self {
        AppError::Database(err.to_string())
    }
}

impl From<serde_json::Error> for AppError {
    fn from(err: serde_json::Error) -> Self {
        AppError::Validation(err.to_string())
    }
}

impl From<validator::ValidationErrors> for AppError {
    fn from(err: validator::ValidationErrors) -> Self {
        AppError::Validation(err.to_string())
    }
}

impl From<url::ParseError> for AppError {
    fn from(err: url::ParseError) -> Self {
        AppError::InvalidUrl(err.to_string())
    }
}

impl From<anyhow::Error> for AppError {
    fn from(err: anyhow::Error) -> Self {
        AppError::Internal(err.to_string())
    }
}

/// Result type alias for our application
pub type AppResult<T> = Result<T, AppError>;
