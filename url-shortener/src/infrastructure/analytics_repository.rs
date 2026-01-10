//! Analytics repository implementations

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

use crate::domain::{AnalyticsSummary, ClickEvent, CountryStats, DeviceBreakdown, ReferrerStats};
use crate::error::AppResult;

/// Analytics repository trait
#[async_trait]
pub trait AnalyticsRepository: Send + Sync {
    /// Record a click event
    async fn record_click(&self, event: ClickEvent) -> AppResult<()>;

    /// Get analytics summary for a URL
    async fn get_summary(&self, short_code: &str) -> AppResult<AnalyticsSummary>;

    /// Get real-time click count (last 5 minutes)
    async fn get_realtime_clicks(&self, short_code: &str) -> AppResult<u64>;

    /// Get geographic breakdown
    async fn get_geo_breakdown(
        &self,
        short_code: &str,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> AppResult<Vec<CountryStats>>;

    /// Get referrer breakdown
    async fn get_referrer_breakdown(
        &self,
        short_code: &str,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> AppResult<Vec<ReferrerStats>>;

    /// Get device breakdown
    async fn get_device_breakdown(
        &self,
        short_code: &str,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> AppResult<DeviceBreakdown>;
}

/// In-memory analytics repository (for development/testing)
pub struct InMemoryAnalyticsRepository {
    events: Arc<RwLock<Vec<ClickEvent>>>,
}

impl InMemoryAnalyticsRepository {
    pub fn new() -> Self {
        Self {
            events: Arc::new(RwLock::new(Vec::new())),
        }
    }
}

impl Default for InMemoryAnalyticsRepository {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl AnalyticsRepository for InMemoryAnalyticsRepository {
    async fn record_click(&self, event: ClickEvent) -> AppResult<()> {
        self.events.write().await.push(event);
        Ok(())
    }

    async fn get_summary(&self, short_code: &str) -> AppResult<AnalyticsSummary> {
        let events = self.events.read().await;
        let code_events: Vec<&ClickEvent> = events
            .iter()
            .filter(|e| e.short_code == short_code)
            .collect();

        let total_clicks = code_events.len() as u64;
        let unique_visitors = code_events
            .iter()
            .map(|e| &e.ip_hash)
            .collect::<std::collections::HashSet<_>>()
            .len() as u64;

        // Calculate time-based metrics
        let now = Utc::now();
        let today_start = now.date_naive().and_hms_opt(0, 0, 0).unwrap();
        let week_start = now - chrono::Duration::days(7);
        let month_start = now - chrono::Duration::days(30);

        let clicks_today = code_events
            .iter()
            .filter(|e| e.timestamp.naive_utc() >= today_start)
            .count() as u64;

        let clicks_this_week = code_events
            .iter()
            .filter(|e| e.timestamp >= week_start)
            .count() as u64;

        let clicks_this_month = code_events
            .iter()
            .filter(|e| e.timestamp >= month_start)
            .count() as u64;

        // Calculate country stats
        let mut country_counts: HashMap<String, u64> = HashMap::new();
        for event in &code_events {
            if let Some(country) = &event.country_code {
                *country_counts.entry(country.clone()).or_insert(0) += 1;
            }
        }

        let mut top_countries: Vec<CountryStats> = country_counts
            .into_iter()
            .map(|(code, clicks)| CountryStats {
                country_code: code.clone(),
                country_name: code, // In production, use a country code lookup
                clicks,
                percentage: if total_clicks > 0 {
                    (clicks as f64 / total_clicks as f64) * 100.0
                } else {
                    0.0
                },
            })
            .collect();
        top_countries.sort_by(|a, b| b.clicks.cmp(&a.clicks));
        top_countries.truncate(10);

        // Calculate referrer stats
        let mut referrer_counts: HashMap<String, u64> = HashMap::new();
        for event in &code_events {
            let referrer = event.referrer_domain.clone().unwrap_or_else(|| "direct".to_string());
            *referrer_counts.entry(referrer).or_insert(0) += 1;
        }

        let mut top_referrers: Vec<ReferrerStats> = referrer_counts
            .into_iter()
            .map(|(referrer, clicks)| ReferrerStats {
                referrer,
                clicks,
                percentage: if total_clicks > 0 {
                    (clicks as f64 / total_clicks as f64) * 100.0
                } else {
                    0.0
                },
            })
            .collect();
        top_referrers.sort_by(|a, b| b.clicks.cmp(&a.clicks));
        top_referrers.truncate(10);

        // Calculate device breakdown
        let mut device_counts: HashMap<String, u64> = HashMap::new();
        for event in &code_events {
            let device = event.device_type.clone().unwrap_or_else(|| "other".to_string());
            *device_counts.entry(device).or_insert(0) += 1;
        }

        let device_breakdown = DeviceBreakdown {
            desktop: *device_counts.get("desktop").unwrap_or(&0),
            mobile: *device_counts.get("mobile").unwrap_or(&0),
            tablet: *device_counts.get("tablet").unwrap_or(&0),
            other: *device_counts.get("other").unwrap_or(&0) + *device_counts.get("bot").unwrap_or(&0),
        };

        Ok(AnalyticsSummary {
            short_code: short_code.to_string(),
            total_clicks,
            unique_visitors,
            clicks_today,
            clicks_this_week,
            clicks_this_month,
            top_countries,
            top_referrers,
            device_breakdown,
        })
    }

    async fn get_realtime_clicks(&self, short_code: &str) -> AppResult<u64> {
        let events = self.events.read().await;
        let five_minutes_ago = Utc::now() - chrono::Duration::minutes(5);

        let count = events
            .iter()
            .filter(|e| e.short_code == short_code && e.timestamp >= five_minutes_ago)
            .count() as u64;

        Ok(count)
    }

    async fn get_geo_breakdown(
        &self,
        short_code: &str,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> AppResult<Vec<CountryStats>> {
        let events = self.events.read().await;

        let filtered: Vec<&ClickEvent> = events
            .iter()
            .filter(|e| {
                e.short_code == short_code && e.timestamp >= start && e.timestamp <= end
            })
            .collect();

        let total = filtered.len() as u64;
        let mut country_counts: HashMap<String, u64> = HashMap::new();

        for event in &filtered {
            if let Some(country) = &event.country_code {
                *country_counts.entry(country.clone()).or_insert(0) += 1;
            }
        }

        let mut stats: Vec<CountryStats> = country_counts
            .into_iter()
            .map(|(code, clicks)| CountryStats {
                country_code: code.clone(),
                country_name: code,
                clicks,
                percentage: if total > 0 {
                    (clicks as f64 / total as f64) * 100.0
                } else {
                    0.0
                },
            })
            .collect();

        stats.sort_by(|a, b| b.clicks.cmp(&a.clicks));
        Ok(stats)
    }

    async fn get_referrer_breakdown(
        &self,
        short_code: &str,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> AppResult<Vec<ReferrerStats>> {
        let events = self.events.read().await;

        let filtered: Vec<&ClickEvent> = events
            .iter()
            .filter(|e| {
                e.short_code == short_code && e.timestamp >= start && e.timestamp <= end
            })
            .collect();

        let total = filtered.len() as u64;
        let mut referrer_counts: HashMap<String, u64> = HashMap::new();

        for event in &filtered {
            let referrer = event.referrer_domain.clone().unwrap_or_else(|| "direct".to_string());
            *referrer_counts.entry(referrer).or_insert(0) += 1;
        }

        let mut stats: Vec<ReferrerStats> = referrer_counts
            .into_iter()
            .map(|(referrer, clicks)| ReferrerStats {
                referrer,
                clicks,
                percentage: if total > 0 {
                    (clicks as f64 / total as f64) * 100.0
                } else {
                    0.0
                },
            })
            .collect();

        stats.sort_by(|a, b| b.clicks.cmp(&a.clicks));
        Ok(stats)
    }

    async fn get_device_breakdown(
        &self,
        short_code: &str,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> AppResult<DeviceBreakdown> {
        let events = self.events.read().await;

        let filtered: Vec<&ClickEvent> = events
            .iter()
            .filter(|e| {
                e.short_code == short_code && e.timestamp >= start && e.timestamp <= end
            })
            .collect();

        let mut device_counts: HashMap<String, u64> = HashMap::new();

        for event in &filtered {
            let device = event.device_type.clone().unwrap_or_else(|| "other".to_string());
            *device_counts.entry(device).or_insert(0) += 1;
        }

        Ok(DeviceBreakdown {
            desktop: *device_counts.get("desktop").unwrap_or(&0),
            mobile: *device_counts.get("mobile").unwrap_or(&0),
            tablet: *device_counts.get("tablet").unwrap_or(&0),
            other: *device_counts.get("other").unwrap_or(&0) + *device_counts.get("bot").unwrap_or(&0),
        })
    }
}
