//! Application configuration

use serde::Deserialize;
use std::env;

/// Main application configuration
#[derive(Debug, Clone, Deserialize)]
pub struct AppConfig {
    /// Environment: development, staging, production
    #[serde(default = "default_environment")]
    pub environment: String,

    /// Server configuration
    #[serde(default)]
    pub server: ServerConfig,

    /// Database configuration
    #[serde(default)]
    pub database: DatabaseConfig,

    /// Redis/cache configuration
    #[serde(default)]
    pub cache: CacheConfig,

    /// AWS configuration
    #[serde(default)]
    pub aws: AwsConfig,

    /// Telemetry configuration
    #[serde(default)]
    pub telemetry: TelemetryConfig,

    /// URL configuration
    #[serde(default)]
    pub url: UrlConfig,

    /// Rate limiting configuration
    #[serde(default)]
    pub rate_limit: RateLimitConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ServerConfig {
    #[serde(default = "default_port")]
    pub port: u16,

    #[serde(default = "default_host")]
    pub host: String,

    /// Request timeout in seconds
    #[serde(default = "default_timeout")]
    pub timeout_seconds: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct DatabaseConfig {
    /// Database type: sqlite, postgres, dynamodb
    #[serde(default = "default_db_type")]
    pub db_type: String,

    /// Database URL for SQL databases
    #[serde(default)]
    pub url: Option<String>,

    /// DynamoDB table name prefix
    #[serde(default = "default_table_prefix")]
    pub table_prefix: String,

    /// Maximum connections in pool
    #[serde(default = "default_max_connections")]
    pub max_connections: u32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CacheConfig {
    /// Cache type: memory, redis
    #[serde(default = "default_cache_type")]
    pub cache_type: String,

    /// Redis URL
    #[serde(default)]
    pub redis_url: Option<String>,

    /// Default TTL in seconds
    #[serde(default = "default_cache_ttl")]
    pub ttl_seconds: u64,

    /// Maximum pool size
    #[serde(default = "default_pool_size")]
    pub pool_size: usize,
}

#[derive(Debug, Clone, Deserialize)]
pub struct AwsConfig {
    /// AWS region
    #[serde(default = "default_aws_region")]
    pub region: String,

    /// Enable local development mode (LocalStack)
    #[serde(default)]
    pub local_mode: bool,

    /// LocalStack endpoint
    #[serde(default)]
    pub endpoint_url: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct TelemetryConfig {
    /// Service name for telemetry
    #[serde(default = "default_service_name")]
    pub service_name: String,

    /// OTLP endpoint for traces
    #[serde(default)]
    pub otlp_endpoint: Option<String>,

    /// Trace sampling rate (0.0 to 1.0)
    #[serde(default = "default_sample_rate")]
    pub sample_rate: f64,

    /// Log level
    #[serde(default = "default_log_level")]
    pub log_level: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct UrlConfig {
    /// Base URL for short links
    #[serde(default = "default_base_url")]
    pub base_url: String,

    /// Short code length
    #[serde(default = "default_code_length")]
    pub code_length: usize,

    /// Maximum URL length
    #[serde(default = "default_max_url_length")]
    pub max_url_length: usize,

    /// Default TTL for URLs in seconds (0 = no expiration)
    #[serde(default)]
    pub default_ttl_seconds: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RateLimitConfig {
    /// Requests per second for unauthenticated users
    #[serde(default = "default_anon_rps")]
    pub anonymous_rps: u32,

    /// Requests per second for free tier
    #[serde(default = "default_free_rps")]
    pub free_rps: u32,

    /// Requests per second for premium tier
    #[serde(default = "default_premium_rps")]
    pub premium_rps: u32,

    /// Requests per second for enterprise tier
    #[serde(default = "default_enterprise_rps")]
    pub enterprise_rps: u32,
}

// Default value functions
fn default_environment() -> String {
    env::var("ENVIRONMENT").unwrap_or_else(|_| "development".to_string())
}

fn default_port() -> u16 {
    env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8080)
}

fn default_host() -> String {
    "0.0.0.0".to_string()
}

fn default_timeout() -> u64 {
    30
}

fn default_db_type() -> String {
    env::var("DATABASE_TYPE").unwrap_or_else(|_| "sqlite".to_string())
}

fn default_table_prefix() -> String {
    "url-shortener".to_string()
}

fn default_max_connections() -> u32 {
    10
}

fn default_cache_type() -> String {
    env::var("CACHE_TYPE").unwrap_or_else(|_| "memory".to_string())
}

fn default_cache_ttl() -> u64 {
    86400 // 24 hours
}

fn default_pool_size() -> usize {
    10
}

fn default_aws_region() -> String {
    env::var("AWS_REGION").unwrap_or_else(|_| "us-east-1".to_string())
}

fn default_service_name() -> String {
    "url-shortener".to_string()
}

fn default_sample_rate() -> f64 {
    1.0
}

fn default_log_level() -> String {
    env::var("LOG_LEVEL").unwrap_or_else(|_| "info".to_string())
}

fn default_base_url() -> String {
    env::var("BASE_URL").unwrap_or_else(|_| "http://localhost:8080".to_string())
}

fn default_code_length() -> usize {
    7
}

fn default_max_url_length() -> usize {
    4096
}

fn default_anon_rps() -> u32 {
    10
}

fn default_free_rps() -> u32 {
    100
}

fn default_premium_rps() -> u32 {
    1000
}

fn default_enterprise_rps() -> u32 {
    10000
}

// Default implementations
impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            port: default_port(),
            host: default_host(),
            timeout_seconds: default_timeout(),
        }
    }
}

impl Default for DatabaseConfig {
    fn default() -> Self {
        Self {
            db_type: default_db_type(),
            url: env::var("DATABASE_URL").ok(),
            table_prefix: default_table_prefix(),
            max_connections: default_max_connections(),
        }
    }
}

impl Default for CacheConfig {
    fn default() -> Self {
        Self {
            cache_type: default_cache_type(),
            redis_url: env::var("REDIS_URL").ok(),
            ttl_seconds: default_cache_ttl(),
            pool_size: default_pool_size(),
        }
    }
}

impl Default for AwsConfig {
    fn default() -> Self {
        Self {
            region: default_aws_region(),
            local_mode: env::var("AWS_LOCAL_MODE").is_ok(),
            endpoint_url: env::var("AWS_ENDPOINT_URL").ok(),
        }
    }
}

impl Default for TelemetryConfig {
    fn default() -> Self {
        Self {
            service_name: default_service_name(),
            otlp_endpoint: env::var("OTLP_ENDPOINT").ok(),
            sample_rate: default_sample_rate(),
            log_level: default_log_level(),
        }
    }
}

impl Default for UrlConfig {
    fn default() -> Self {
        Self {
            base_url: default_base_url(),
            code_length: default_code_length(),
            max_url_length: default_max_url_length(),
            default_ttl_seconds: 0,
        }
    }
}

impl Default for RateLimitConfig {
    fn default() -> Self {
        Self {
            anonymous_rps: default_anon_rps(),
            free_rps: default_free_rps(),
            premium_rps: default_premium_rps(),
            enterprise_rps: default_enterprise_rps(),
        }
    }
}

impl AppConfig {
    /// Load configuration from environment and config files
    pub fn load() -> anyhow::Result<Self> {
        let config = config::Config::builder()
            // Start with default values
            .set_default("environment", default_environment())?
            // Add config file if it exists
            .add_source(config::File::with_name("config/default").required(false))
            // Add environment-specific config
            .add_source(
                config::File::with_name(&format!(
                    "config/{}",
                    env::var("ENVIRONMENT").unwrap_or_else(|_| "development".to_string())
                ))
                .required(false),
            )
            // Add environment variables with prefix
            .add_source(config::Environment::with_prefix("APP").separator("__"))
            .build()?;

        let app_config: AppConfig = config.try_deserialize().unwrap_or_default();

        Ok(app_config)
    }

    /// Check if running in production
    pub fn is_production(&self) -> bool {
        self.environment == "production"
    }

    /// Check if running in development
    pub fn is_development(&self) -> bool {
        self.environment == "development"
    }
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            environment: default_environment(),
            server: ServerConfig::default(),
            database: DatabaseConfig::default(),
            cache: CacheConfig::default(),
            aws: AwsConfig::default(),
            telemetry: TelemetryConfig::default(),
            url: UrlConfig::default(),
            rate_limit: RateLimitConfig::default(),
        }
    }
}
