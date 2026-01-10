//! URL Shortener Service
//!
//! A production-grade URL shortener built with Rust and Axum.
//! Scales from local development to 500M URLs per month globally.

use std::net::SocketAddr;
use std::sync::Arc;

use axum::{
    routing::{get, post, delete},
    Router,
};
use tokio::signal;
use tower::ServiceBuilder;
use tower_http::{
    compression::CompressionLayer,
    cors::CorsLayer,
    request_id::{SetRequestIdLayer, PropagateRequestIdLayer, MakeRequestUuid},
    trace::TraceLayer,
};
use tracing::info;

mod api;
mod config;
mod domain;
mod error;
mod infrastructure;
mod middleware;
mod telemetry;
mod compliance;

use crate::config::AppConfig;
use crate::infrastructure::AppState;
use crate::telemetry::init_telemetry;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Load environment variables from .env file
    dotenvy::dotenv().ok();

    // Load configuration
    let config = AppConfig::load()?;

    // Initialize telemetry (logging, metrics, tracing)
    init_telemetry(&config.telemetry)?;

    info!(
        version = env!("CARGO_PKG_VERSION"),
        environment = %config.environment,
        "Starting URL Shortener service"
    );

    // Initialize application state
    let state = AppState::new(&config).await?;
    let state = Arc::new(state);

    // Build the router
    let app = build_router(state);

    // Create the server
    let addr = SocketAddr::from(([0, 0, 0, 0], config.server.port));
    let listener = tokio::net::TcpListener::bind(addr).await?;

    info!(address = %addr, "Server listening");

    // Run with graceful shutdown, including connect info for client IP
    axum::serve(listener, app.into_make_service_with_connect_info::<std::net::SocketAddr>())
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    info!("Server shutdown complete");

    Ok(())
}

/// Build the application router with all routes and middleware
fn build_router(state: Arc<AppState>) -> Router {
    // API v1 routes
    let api_v1 = Router::new()
        // URL management
        .route("/urls", post(api::urls::create_url))
        .route("/urls", get(api::urls::list_urls))
        .route("/urls/:code", get(api::urls::get_url))
        .route("/urls/:code", delete(api::urls::delete_url))
        .route("/urls/bulk", post(api::urls::bulk_create))

        // Analytics
        .route("/analytics/:code", get(api::analytics::get_analytics))
        .route("/analytics/:code/realtime", get(api::analytics::get_realtime))
        .route("/analytics/:code/geo", get(api::analytics::get_geo_breakdown))

        // Auth
        .route("/auth/keys", post(api::auth::create_api_key))
        .route("/auth/keys", get(api::auth::list_api_keys))
        .route("/auth/keys/:id", delete(api::auth::revoke_api_key))

        // Compliance
        .route("/compliance/gdpr/export", get(api::compliance::gdpr_export))
        .route("/compliance/gdpr/erasure", delete(api::compliance::gdpr_erasure))

        // Apply authentication middleware to API routes
        .layer(axum::middleware::from_fn_with_state(
            state.clone(),
            middleware::auth::authenticate,
        ));

    // Public routes (no auth required)
    let public = Router::new()
        // Redirect endpoint
        .route("/:code", get(api::redirect::handle_redirect))

        // Health checks
        .route("/health", get(api::health::liveness))
        .route("/ready", get(api::health::readiness))
        .route("/metrics", get(api::health::metrics));

    // Combine all routes
    Router::new()
        .nest("/api/v1", api_v1)
        .merge(public)
        .with_state(state)
        .layer(
            ServiceBuilder::new()
                // Add request ID to all requests
                .layer(SetRequestIdLayer::x_request_id(MakeRequestUuid))
                .layer(PropagateRequestIdLayer::x_request_id())
                // Add tracing
                .layer(TraceLayer::new_for_http())
                // Add CORS
                .layer(CorsLayer::permissive())
                // Add compression
                .layer(CompressionLayer::new())
                // Rate limiting middleware
                .layer(axum::middleware::from_fn(middleware::rate_limit::rate_limit)),
        )
}

/// Graceful shutdown signal handler
async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("Failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("Failed to install SIGTERM handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }

    info!("Received shutdown signal, starting graceful shutdown");
}
