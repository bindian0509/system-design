//! Analytics API handlers

use std::sync::Arc;

use axum::{
    extract::{Path, Query, State},
    Json,
};
use chrono::{DateTime, Duration, Utc};
use serde::Deserialize;
use tracing::instrument;

use crate::domain::{AnalyticsSummary, CountryStats, DeviceBreakdown, ReferrerStats};
use crate::error::AppResult;
use crate::infrastructure::AppState;
use crate::middleware::auth::AuthenticatedUser;

/// Date range query parameters
#[derive(Debug, Deserialize)]
pub struct DateRangeQuery {
    #[serde(default = "default_start")]
    pub start: DateTime<Utc>,

    #[serde(default = "default_end")]
    pub end: DateTime<Utc>,
}

fn default_start() -> DateTime<Utc> {
    Utc::now() - Duration::days(30)
}

fn default_end() -> DateTime<Utc> {
    Utc::now()
}

/// Get analytics summary for a URL
#[instrument(skip(state))]
pub async fn get_analytics(
    State(state): State<Arc<AppState>>,
    _user: AuthenticatedUser,
    Path(code): Path<String>,
) -> AppResult<Json<AnalyticsSummary>> {
    let summary = state.analytics_service.get_summary(&code).await?;
    Ok(Json(summary))
}

/// Get real-time click count (last 5 minutes)
#[instrument(skip(state))]
pub async fn get_realtime(
    State(state): State<Arc<AppState>>,
    _user: AuthenticatedUser,
    Path(code): Path<String>,
) -> AppResult<Json<RealtimeResponse>> {
    let clicks = state.analytics_service.get_realtime_clicks(&code).await?;
    Ok(Json(RealtimeResponse {
        short_code: code,
        clicks_last_5_minutes: clicks,
        timestamp: Utc::now(),
    }))
}

#[derive(serde::Serialize)]
pub struct RealtimeResponse {
    pub short_code: String,
    pub clicks_last_5_minutes: u64,
    pub timestamp: DateTime<Utc>,
}

/// Get geographic breakdown
#[instrument(skip(state))]
pub async fn get_geo_breakdown(
    State(state): State<Arc<AppState>>,
    _user: AuthenticatedUser,
    Path(code): Path<String>,
    Query(range): Query<DateRangeQuery>,
) -> AppResult<Json<Vec<CountryStats>>> {
    let breakdown = state.analytics_service
        .get_geo_breakdown(&code, range.start, range.end)
        .await?;
    Ok(Json(breakdown))
}

/// Get referrer breakdown
#[instrument(skip(state))]
pub async fn get_referrer_breakdown(
    State(state): State<Arc<AppState>>,
    _user: AuthenticatedUser,
    Path(code): Path<String>,
    Query(range): Query<DateRangeQuery>,
) -> AppResult<Json<Vec<ReferrerStats>>> {
    let breakdown = state.analytics_service
        .get_referrer_breakdown(&code, range.start, range.end)
        .await?;
    Ok(Json(breakdown))
}

/// Get device breakdown
#[instrument(skip(state))]
pub async fn get_device_breakdown(
    State(state): State<Arc<AppState>>,
    _user: AuthenticatedUser,
    Path(code): Path<String>,
    Query(range): Query<DateRangeQuery>,
) -> AppResult<Json<DeviceBreakdown>> {
    let breakdown = state.analytics_service
        .get_device_breakdown(&code, range.start, range.end)
        .await?;
    Ok(Json(breakdown))
}
