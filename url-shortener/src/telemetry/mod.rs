//! Telemetry and observability

use tracing_subscriber::{
    fmt,
    layer::SubscriberExt,
    util::SubscriberInitExt,
    EnvFilter,
};

use crate::config::TelemetryConfig;
use crate::error::AppResult;

/// Initialize telemetry (logging, metrics, tracing)
pub fn init_telemetry(config: &TelemetryConfig) -> AppResult<()> {
    // Create an environment filter
    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(&config.log_level));

    // Check if we should use JSON format (production) or pretty format (development)
    let is_production = std::env::var("ENVIRONMENT")
        .map(|e| e == "production")
        .unwrap_or(false);

    if is_production {
        // JSON format for production
        let subscriber = tracing_subscriber::registry()
            .with(env_filter)
            .with(
                fmt::layer()
                    .json()
                    .with_target(true)
                    .with_file(true)
                    .with_line_number(true)
            );

        subscriber.try_init()
            .map_err(|e| crate::error::AppError::Config(e.to_string()))?;
    } else {
        // Pretty format for development
        let subscriber = tracing_subscriber::registry()
            .with(env_filter)
            .with(
                fmt::layer()
                    .pretty()
                    .with_target(true)
            );

        subscriber.try_init()
            .map_err(|e| crate::error::AppError::Config(e.to_string()))?;
    }

    tracing::info!(
        service_name = %config.service_name,
        log_level = %config.log_level,
        "Telemetry initialized"
    );

    Ok(())
}

/// Custom metrics for the URL shortener
pub mod metrics {
    use std::sync::atomic::{AtomicU64, Ordering};

    /// Application metrics
    pub struct AppMetrics {
        pub urls_created: AtomicU64,
        pub urls_deleted: AtomicU64,
        pub redirects_served: AtomicU64,
        pub cache_hits: AtomicU64,
        pub cache_misses: AtomicU64,
        pub errors: AtomicU64,
    }

    impl AppMetrics {
        pub const fn new() -> Self {
            Self {
                urls_created: AtomicU64::new(0),
                urls_deleted: AtomicU64::new(0),
                redirects_served: AtomicU64::new(0),
                cache_hits: AtomicU64::new(0),
                cache_misses: AtomicU64::new(0),
                errors: AtomicU64::new(0),
            }
        }

        pub fn inc_urls_created(&self) {
            self.urls_created.fetch_add(1, Ordering::Relaxed);
        }

        pub fn inc_redirects(&self) {
            self.redirects_served.fetch_add(1, Ordering::Relaxed);
        }

        pub fn inc_cache_hit(&self) {
            self.cache_hits.fetch_add(1, Ordering::Relaxed);
        }

        pub fn inc_cache_miss(&self) {
            self.cache_misses.fetch_add(1, Ordering::Relaxed);
        }

        pub fn cache_hit_rate(&self) -> f64 {
            let hits = self.cache_hits.load(Ordering::Relaxed) as f64;
            let misses = self.cache_misses.load(Ordering::Relaxed) as f64;
            let total = hits + misses;

            if total > 0.0 {
                hits / total
            } else {
                0.0
            }
        }
    }

    /// Global metrics instance
    pub static METRICS: AppMetrics = AppMetrics::new();
}
