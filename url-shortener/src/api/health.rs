//! Health check endpoints

use std::sync::Arc;

use axum::{
    extract::State,
    http::StatusCode,
    Json,
};
use chrono::{DateTime, Utc};
use serde::Serialize;

use crate::infrastructure::AppState;

/// Liveness probe response
#[derive(Debug, Serialize)]
pub struct LivenessResponse {
    pub status: &'static str,
    pub timestamp: DateTime<Utc>,
}

/// Readiness probe response
#[derive(Debug, Serialize)]
pub struct ReadinessResponse {
    pub status: String,
    pub version: String,
    pub timestamp: DateTime<Utc>,
    pub checks: Vec<HealthCheck>,
}

#[derive(Debug, Serialize)]
pub struct HealthCheck {
    pub name: String,
    pub status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latency_ms: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

/// Metrics response (Prometheus format placeholder)
#[derive(Debug, Serialize)]
pub struct MetricsResponse {
    pub uptime_seconds: u64,
    pub requests_total: u64,
    pub cache_hit_rate: f64,
}

/// Liveness probe - is the service alive?
pub async fn liveness() -> Json<LivenessResponse> {
    Json(LivenessResponse {
        status: "ok",
        timestamp: Utc::now(),
    })
}

/// Readiness probe - is the service ready to accept traffic?
pub async fn readiness(
    State(state): State<Arc<AppState>>,
) -> (StatusCode, Json<ReadinessResponse>) {
    let mut checks = Vec::new();
    let mut all_healthy = true;

    // Check cache
    let cache_check = check_cache(&state).await;
    if cache_check.status != "healthy" {
        all_healthy = false;
    }
    checks.push(cache_check);

    // Check repository
    let db_check = check_repository(&state).await;
    if db_check.status != "healthy" {
        all_healthy = false;
    }
    checks.push(db_check);

    let status = if all_healthy { "healthy" } else { "degraded" };
    let http_status = if all_healthy {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    };

    (http_status, Json(ReadinessResponse {
        status: status.to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        timestamp: Utc::now(),
        checks,
    }))
}

/// Check cache health
async fn check_cache(state: &AppState) -> HealthCheck {
    let start = std::time::Instant::now();

    // Try a simple cache operation
    match state.cache.exists("health_check").await {
        Ok(_) => HealthCheck {
            name: "cache".to_string(),
            status: "healthy".to_string(),
            latency_ms: Some(start.elapsed().as_millis() as u64),
            message: None,
        },
        Err(e) => HealthCheck {
            name: "cache".to_string(),
            status: "unhealthy".to_string(),
            latency_ms: Some(start.elapsed().as_millis() as u64),
            message: Some(e.to_string()),
        },
    }
}

/// Check repository health
async fn check_repository(state: &AppState) -> HealthCheck {
    let start = std::time::Instant::now();

    // Try a simple repository operation
    match state.repository.exists("_health_check_").await {
        Ok(_) => HealthCheck {
            name: "database".to_string(),
            status: "healthy".to_string(),
            latency_ms: Some(start.elapsed().as_millis() as u64),
            message: None,
        },
        Err(e) => HealthCheck {
            name: "database".to_string(),
            status: "unhealthy".to_string(),
            latency_ms: Some(start.elapsed().as_millis() as u64),
            message: Some(e.to_string()),
        },
    }
}

/// Metrics endpoint (Prometheus format)
pub async fn metrics() -> String {
    // In production, this would integrate with OpenTelemetry/Prometheus
    // For now, return placeholder metrics

    let uptime = 0; // Would track actual uptime

    format!(
        r#"# HELP url_shortener_uptime_seconds Time since service start
# TYPE url_shortener_uptime_seconds counter
url_shortener_uptime_seconds {}

# HELP url_shortener_requests_total Total number of requests
# TYPE url_shortener_requests_total counter
url_shortener_requests_total 0

# HELP url_shortener_cache_hit_rate Cache hit rate
# TYPE url_shortener_cache_hit_rate gauge
url_shortener_cache_hit_rate 0.0
"#,
        uptime
    )
}
