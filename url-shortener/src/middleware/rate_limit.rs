//! Rate limiting middleware

use axum::{
    body::Body,
    http::{Request, StatusCode},
    response::{IntoResponse, Response},
};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::warn;

/// Token bucket rate limiter
pub struct RateLimiter {
    buckets: Arc<RwLock<HashMap<String, TokenBucket>>>,
    default_rate: u32,
    default_burst: u32,
}

struct TokenBucket {
    tokens: f64,
    last_update: Instant,
    rate: f64,      // tokens per second
    capacity: f64,  // max tokens
}

impl RateLimiter {
    pub fn new(default_rate: u32, default_burst: u32) -> Self {
        let limiter = Self {
            buckets: Arc::new(RwLock::new(HashMap::new())),
            default_rate,
            default_burst,
        };

        // Start cleanup task
        let buckets = limiter.buckets.clone();
        tokio::spawn(async move {
            loop {
                tokio::time::sleep(Duration::from_secs(60)).await;
                cleanup_old_buckets(&buckets).await;
            }
        });

        limiter
    }

    pub async fn check(&self, key: &str, rate: Option<u32>, burst: Option<u32>) -> bool {
        let rate = rate.unwrap_or(self.default_rate) as f64;
        let capacity = burst.unwrap_or(self.default_burst) as f64;

        let mut buckets = self.buckets.write().await;
        let now = Instant::now();

        let bucket = buckets.entry(key.to_string()).or_insert_with(|| TokenBucket {
            tokens: capacity,
            last_update: now,
            rate,
            capacity,
        });

        // Refill tokens based on elapsed time
        let elapsed = now.duration_since(bucket.last_update).as_secs_f64();
        bucket.tokens = (bucket.tokens + elapsed * bucket.rate).min(bucket.capacity);
        bucket.last_update = now;

        // Try to consume a token
        if bucket.tokens >= 1.0 {
            bucket.tokens -= 1.0;
            true
        } else {
            false
        }
    }
}

async fn cleanup_old_buckets(buckets: &Arc<RwLock<HashMap<String, TokenBucket>>>) {
    let mut buckets = buckets.write().await;
    let now = Instant::now();
    let stale_threshold = Duration::from_secs(300); // 5 minutes

    buckets.retain(|_, bucket| {
        now.duration_since(bucket.last_update) < stale_threshold
    });
}

/// Global rate limiter instance
static RATE_LIMITER: once_cell::sync::Lazy<RateLimiter> =
    once_cell::sync::Lazy::new(|| RateLimiter::new(100, 10));

/// Rate limiting middleware
pub async fn rate_limit(
    request: Request<Body>,
    next: axum::middleware::Next,
) -> Response {
    // Extract client identifier
    let client_id = extract_client_id(&request);

    // Check rate limit
    if !RATE_LIMITER.check(&client_id, None, None).await {
        warn!(client_id = %client_id, "Rate limit exceeded");
        return (
            StatusCode::TOO_MANY_REQUESTS,
            [
                ("Retry-After", "60"),
                ("X-RateLimit-Limit", "100"),
                ("X-RateLimit-Remaining", "0"),
            ],
            "Rate limit exceeded. Please try again later.",
        ).into_response();
    }

    next.run(request).await
}

/// Extract client identifier from request
fn extract_client_id(request: &Request<Body>) -> String {
    // Try to get API key prefix first
    if let Some(auth) = request.headers().get("authorization") {
        if let Ok(auth_str) = auth.to_str() {
            if let Some(key) = auth_str.strip_prefix("ApiKey ") {
                if key.len() >= 16 {
                    return format!("key:{}", &key[..16]);
                }
            }
        }
    }

    // Fall back to IP address
    if let Some(forwarded) = request.headers().get("x-forwarded-for") {
        if let Ok(forwarded_str) = forwarded.to_str() {
            if let Some(ip) = forwarded_str.split(',').next() {
                return format!("ip:{}", ip.trim());
            }
        }
    }

    // Use connection info if available
    if let Some(real_ip) = request.headers().get("x-real-ip") {
        if let Ok(ip) = real_ip.to_str() {
            return format!("ip:{}", ip);
        }
    }

    // Default fallback
    "unknown".to_string()
}
