# Telemetry, Observability, and Alerting

This document covers the observability strategy including metrics, logging, tracing, dashboards, and alerting for the URL shortener system.

---

## Observability Strategy

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      THREE PILLARS OF OBSERVABILITY                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│     METRICS                    LOGS                      TRACES                  │
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐              │
│  │             │          │             │          │             │              │
│  │  What is    │          │  What       │          │  How does   │              │
│  │  happening? │          │  happened?  │          │  it flow?   │              │
│  │             │          │             │          │             │              │
│  │  Counters   │          │  Events     │          │  Spans      │              │
│  │  Gauges     │          │  Errors     │          │  Context    │              │
│  │  Histograms │          │  Audit      │          │  Latency    │              │
│  │             │          │             │          │             │              │
│  └──────┬──────┘          └──────┬──────┘          └──────┬──────┘              │
│         │                        │                        │                      │
│         └────────────────────────┼────────────────────────┘                      │
│                                  │                                               │
│                                  ▼                                               │
│                    ┌─────────────────────────────┐                              │
│                    │    Correlation ID           │                              │
│                    │    (Request Tracing)        │                              │
│                    └─────────────────────────────┘                              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Instrumentation | OpenTelemetry (Rust SDK) | Vendor-neutral telemetry collection |
| Metrics Backend | CloudWatch + Prometheus | Metrics storage and querying |
| Logs Backend | CloudWatch Logs + OpenSearch | Log aggregation and search |
| Traces Backend | AWS X-Ray | Distributed tracing |
| Visualization | Grafana | Dashboards and visualization |
| Alerting | CloudWatch Alarms + PagerDuty | Alert management and escalation |
| APM | AWS X-Ray + Custom Dashboards | Application performance monitoring |

---

## OpenTelemetry Integration

### Rust Implementation

```rust
use opentelemetry::{
    global,
    sdk::{
        export::trace::SpanExporter,
        propagation::TraceContextPropagator,
        trace::{self, Sampler, TracerProvider},
        Resource,
    },
    trace::{Span, SpanKind, Tracer, TracerProvider as _},
    KeyValue,
};
use opentelemetry_otlp::WithExportConfig;
use tracing_opentelemetry::OpenTelemetryLayer;
use tracing_subscriber::{layer::SubscriberExt, Registry};

/// Initialize OpenTelemetry with AWS X-Ray integration
pub fn init_telemetry(config: &TelemetryConfig) -> Result<(), Error> {
    // Set global propagator for distributed tracing
    global::set_text_map_propagator(TraceContextPropagator::new());

    // Resource attributes
    let resource = Resource::new(vec![
        KeyValue::new("service.name", config.service_name.clone()),
        KeyValue::new("service.version", env!("CARGO_PKG_VERSION")),
        KeyValue::new("deployment.environment", config.environment.clone()),
        KeyValue::new("cloud.provider", "aws"),
        KeyValue::new("cloud.region", config.region.clone()),
    ]);

    // Configure OTLP exporter (to AWS X-Ray via ADOT collector)
    let otlp_exporter = opentelemetry_otlp::new_exporter()
        .tonic()
        .with_endpoint(&config.otlp_endpoint)
        .with_timeout(Duration::from_secs(3));

    // Configure tracer
    let tracer_provider = opentelemetry_otlp::new_pipeline()
        .tracing()
        .with_exporter(otlp_exporter)
        .with_trace_config(
            trace::config()
                .with_sampler(Sampler::TraceIdRatioBased(config.sample_rate))
                .with_resource(resource.clone()),
        )
        .install_batch(opentelemetry::runtime::Tokio)?;

    let tracer = tracer_provider.tracer("url-shortener");

    // Configure metrics
    let meter_provider = init_metrics(&config, resource)?;

    // Set up tracing subscriber with OpenTelemetry
    let telemetry_layer = OpenTelemetryLayer::new(tracer);

    let subscriber = Registry::default()
        .with(telemetry_layer)
        .with(tracing_subscriber::fmt::layer()
            .json()
            .with_target(true)
            .with_span_events(tracing_subscriber::fmt::format::FmtSpan::CLOSE));

    tracing::subscriber::set_global_default(subscriber)?;

    Ok(())
}

/// Initialize metrics pipeline
fn init_metrics(config: &TelemetryConfig, resource: Resource) -> Result<MeterProvider, Error> {
    let metrics_exporter = opentelemetry_otlp::new_exporter()
        .tonic()
        .with_endpoint(&config.otlp_endpoint);

    let meter_provider = opentelemetry_otlp::new_pipeline()
        .metrics(opentelemetry::runtime::Tokio)
        .with_exporter(metrics_exporter)
        .with_resource(resource)
        .with_period(Duration::from_secs(30))
        .build()?;

    global::set_meter_provider(meter_provider.clone());

    Ok(meter_provider)
}
```

### Custom Metrics

```rust
use opentelemetry::{
    global,
    metrics::{Counter, Histogram, Meter, UpDownCounter},
    KeyValue,
};

/// Custom metrics for URL shortener
pub struct AppMetrics {
    // Counters
    pub urls_created: Counter<u64>,
    pub urls_deleted: Counter<u64>,
    pub redirects_served: Counter<u64>,
    pub cache_hits: Counter<u64>,
    pub cache_misses: Counter<u64>,

    // Histograms
    pub redirect_latency: Histogram<f64>,
    pub create_latency: Histogram<f64>,
    pub db_query_latency: Histogram<f64>,
    pub cache_operation_latency: Histogram<f64>,

    // Gauges
    pub active_connections: UpDownCounter<i64>,
    pub cache_size: UpDownCounter<i64>,
}

impl AppMetrics {
    pub fn new() -> Self {
        let meter = global::meter("url-shortener");

        Self {
            // Counters
            urls_created: meter
                .u64_counter("urls.created")
                .with_description("Total number of URLs created")
                .init(),

            urls_deleted: meter
                .u64_counter("urls.deleted")
                .with_description("Total number of URLs deleted")
                .init(),

            redirects_served: meter
                .u64_counter("redirects.served")
                .with_description("Total number of redirects served")
                .init(),

            cache_hits: meter
                .u64_counter("cache.hits")
                .with_description("Number of cache hits")
                .init(),

            cache_misses: meter
                .u64_counter("cache.misses")
                .with_description("Number of cache misses")
                .init(),

            // Histograms
            redirect_latency: meter
                .f64_histogram("redirect.latency")
                .with_description("Redirect request latency in milliseconds")
                .with_unit("ms")
                .init(),

            create_latency: meter
                .f64_histogram("create.latency")
                .with_description("URL creation latency in milliseconds")
                .with_unit("ms")
                .init(),

            db_query_latency: meter
                .f64_histogram("db.query.latency")
                .with_description("Database query latency in milliseconds")
                .with_unit("ms")
                .init(),

            cache_operation_latency: meter
                .f64_histogram("cache.operation.latency")
                .with_description("Cache operation latency in milliseconds")
                .with_unit("ms")
                .init(),

            // Gauges
            active_connections: meter
                .i64_up_down_counter("connections.active")
                .with_description("Number of active connections")
                .init(),

            cache_size: meter
                .i64_up_down_counter("cache.size")
                .with_description("Number of items in cache")
                .init(),
        }
    }

    /// Record a successful redirect
    pub fn record_redirect(&self, latency_ms: f64, cache_hit: bool, country: &str) {
        let attrs = [
            KeyValue::new("cache_hit", cache_hit),
            KeyValue::new("country", country.to_string()),
        ];

        self.redirects_served.add(1, &attrs);
        self.redirect_latency.record(latency_ms, &attrs);

        if cache_hit {
            self.cache_hits.add(1, &attrs);
        } else {
            self.cache_misses.add(1, &attrs);
        }
    }

    /// Record a URL creation
    pub fn record_create(&self, latency_ms: f64, tier: &str, is_custom: bool) {
        let attrs = [
            KeyValue::new("tier", tier.to_string()),
            KeyValue::new("is_custom_alias", is_custom),
        ];

        self.urls_created.add(1, &attrs);
        self.create_latency.record(latency_ms, &attrs);
    }
}
```

### Tracing Middleware

```rust
use axum::{
    extract::Request,
    middleware::Next,
    response::Response,
};
use tracing::{instrument, Span};
use uuid::Uuid;

/// Request tracing middleware
pub async fn tracing_middleware(request: Request, next: Next) -> Response {
    // Generate or extract correlation ID
    let correlation_id = request
        .headers()
        .get("x-correlation-id")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string())
        .unwrap_or_else(|| Uuid::new_v4().to_string());

    // Extract request metadata
    let method = request.method().to_string();
    let uri = request.uri().to_string();
    let user_agent = request
        .headers()
        .get("user-agent")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("unknown");

    // Create span with request context
    let span = tracing::info_span!(
        "http_request",
        correlation_id = %correlation_id,
        http.method = %method,
        http.url = %uri,
        http.user_agent = %user_agent,
        otel.kind = "server",
    );

    let _guard = span.enter();

    // Process request
    let start = std::time::Instant::now();
    let response = next.run(request).await;
    let latency = start.elapsed();

    // Record response metadata
    let status = response.status().as_u16();
    span.record("http.status_code", status);
    span.record("http.latency_ms", latency.as_millis() as i64);

    // Log completion
    if status >= 500 {
        tracing::error!(
            correlation_id = %correlation_id,
            status = status,
            latency_ms = latency.as_millis(),
            "Request failed"
        );
    } else if status >= 400 {
        tracing::warn!(
            correlation_id = %correlation_id,
            status = status,
            latency_ms = latency.as_millis(),
            "Client error"
        );
    } else {
        tracing::info!(
            correlation_id = %correlation_id,
            status = status,
            latency_ms = latency.as_millis(),
            "Request completed"
        );
    }

    response
}

/// Instrument database operations
#[instrument(
    name = "db.query",
    skip(client),
    fields(
        db.system = "dynamodb",
        db.operation = %operation,
        db.table = %table,
    )
)]
pub async fn traced_db_query<T>(
    client: &DynamoClient,
    operation: &str,
    table: &str,
    query_fn: impl Future<Output = Result<T, Error>>,
) -> Result<T, Error> {
    let start = std::time::Instant::now();
    let result = query_fn.await;
    let latency = start.elapsed();

    Span::current().record("db.latency_ms", latency.as_millis() as i64);

    if result.is_err() {
        Span::current().record("error", true);
    }

    result
}
```

---

## Logging Strategy

### Log Levels and Usage

| Level | Usage | Example |
|-------|-------|---------|
| ERROR | Unhandled errors, system failures | Database connection failure |
| WARN | Handled errors, degraded state | Rate limit exceeded, cache miss fallback |
| INFO | Business events, request completion | URL created, redirect served |
| DEBUG | Detailed debugging info | Query parameters, cache operations |
| TRACE | Very detailed tracing | Individual function calls |

### Structured Log Format

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "message": "URL created successfully",
  "target": "url_shortener::api::urls",
  "span": {
    "name": "create_url",
    "correlation_id": "req_abc123xyz"
  },
  "fields": {
    "short_code": "abc123X",
    "user_id": "user_uuid",
    "tier": "premium",
    "is_custom_alias": false,
    "latency_ms": 45
  },
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

### Log Aggregation Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          LOG AGGREGATION PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │   EKS Pod   │    │  FluentBit  │    │  CloudWatch │    │ OpenSearch  │       │
│  │   (stdout)  │───▶│  (DaemonSet)│───▶│    Logs     │───▶│  (Optional) │       │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘       │
│                                              │                                   │
│                                              ▼                                   │
│                           ┌─────────────────────────────────┐                   │
│                           │  CloudWatch Logs Insights       │                   │
│                           │  • Query and analyze logs       │                   │
│                           │  • Create dashboards            │                   │
│                           │  • Set up metric filters        │                   │
│                           └─────────────────────────────────┘                   │
│                                              │                                   │
│                                              ▼                                   │
│                           ┌─────────────────────────────────┐                   │
│                           │  S3 (Long-term Archive)         │                   │
│                           │  • 90 days hot                  │                   │
│                           │  • 1 year warm (Glacier IR)     │                   │
│                           │  • 7 years cold (Deep Archive)  │                   │
│                           └─────────────────────────────────┘                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### FluentBit Configuration

```yaml
# fluent-bit-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
  namespace: logging
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         5
        Log_Level     info
        Daemon        off
        Parsers_File  parsers.conf

    [INPUT]
        Name              tail
        Tag               kube.*
        Path              /var/log/containers/*url-shortener*.log
        Parser            docker
        DB                /var/log/flb_kube.db
        Mem_Buf_Limit     50MB
        Skip_Long_Lines   On
        Refresh_Interval  10

    [FILTER]
        Name                kubernetes
        Match               kube.*
        Kube_URL            https://kubernetes.default.svc:443
        Kube_CA_File        /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
        Kube_Token_File     /var/run/secrets/kubernetes.io/serviceaccount/token
        Kube_Tag_Prefix     kube.var.log.containers.
        Merge_Log           On
        Merge_Log_Key       log_processed
        K8S-Logging.Parser  On
        K8S-Logging.Exclude Off

    [FILTER]
        Name    modify
        Match   *
        Add     cluster ${CLUSTER_NAME}
        Add     region ${AWS_REGION}

    [OUTPUT]
        Name                cloudwatch_logs
        Match               *
        region              ${AWS_REGION}
        log_group_name      /aws/eks/url-shortener/application
        log_stream_prefix   ${HOSTNAME}-
        auto_create_group   true
        log_retention_days  90

  parsers.conf: |
    [PARSER]
        Name        docker
        Format      json
        Time_Key    time
        Time_Format %Y-%m-%dT%H:%M:%S.%L
        Time_Keep   On
```

---

## Metrics and Dashboards

### Key Metrics (RED Method)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            RED METRICS                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  RATE (Requests per second)                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ • redirects.rate       - Redirects per second                               ││
│  │ • creates.rate         - URL creations per second                           ││
│  │ • api.requests.rate    - Total API requests per second                      ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  ERRORS (Error rate and types)                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ • errors.rate          - Errors per second                                  ││
│  │ • errors.ratio         - Error percentage (errors / total)                  ││
│  │ • errors.by_type       - Breakdown by error code (4xx, 5xx)                ││
│  │ • errors.by_endpoint   - Errors per endpoint                                ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  DURATION (Latency percentiles)                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ • latency.p50          - Median latency                                     ││
│  │ • latency.p90          - 90th percentile                                    ││
│  │ • latency.p99          - 99th percentile                                    ││
│  │ • latency.p999         - 99.9th percentile                                  ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Business Metrics

| Metric | Description | Dashboard |
|--------|-------------|-----------|
| `urls.total` | Total URLs in system | Business Overview |
| `urls.active` | Active (non-expired) URLs | Business Overview |
| `urls.created.daily` | URLs created per day | Growth Dashboard |
| `redirects.daily` | Redirects served per day | Traffic Dashboard |
| `users.active.daily` | Daily active users | User Analytics |
| `users.by_tier` | Users by subscription tier | Revenue Dashboard |
| `cache.hit_rate` | Cache hit percentage | Performance Dashboard |

### Infrastructure Metrics

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| CPU Utilization | CloudWatch | > 80% for 5 min |
| Memory Utilization | CloudWatch | > 85% for 5 min |
| Network I/O | CloudWatch | > 80% capacity |
| DynamoDB Read Capacity | CloudWatch | > 80% consumed |
| DynamoDB Write Capacity | CloudWatch | > 80% consumed |
| Redis Memory | ElastiCache | > 75% used |
| Redis Connections | ElastiCache | > 90% max |

### Grafana Dashboard Configuration

```json
{
  "dashboard": {
    "title": "URL Shortener - Operations",
    "tags": ["url-shortener", "production"],
    "timezone": "UTC",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "gridPos": { "x": 0, "y": 0, "w": 12, "h": 8 },
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{service=\"url-shortener\"}[5m]))",
            "legendFormat": "Total RPS"
          },
          {
            "expr": "sum(rate(http_requests_total{service=\"url-shortener\",handler=\"redirect\"}[5m]))",
            "legendFormat": "Redirects RPS"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "gridPos": { "x": 12, "y": 0, "w": 12, "h": 8 },
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{service=\"url-shortener\",status=~\"5..\"}[5m])) / sum(rate(http_requests_total{service=\"url-shortener\"}[5m])) * 100",
            "legendFormat": "Error %"
          }
        ],
        "alert": {
          "conditions": [
            {
              "evaluator": { "type": "gt", "params": [1] },
              "operator": { "type": "and" },
              "query": { "params": ["A", "5m", "now"] },
              "reducer": { "type": "avg" }
            }
          ],
          "name": "High Error Rate",
          "notifications": [{ "uid": "pagerduty" }]
        }
      },
      {
        "title": "Latency Percentiles",
        "type": "graph",
        "gridPos": { "x": 0, "y": 8, "w": 12, "h": 8 },
        "targets": [
          {
            "expr": "histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{service=\"url-shortener\"}[5m])) by (le))",
            "legendFormat": "p50"
          },
          {
            "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{service=\"url-shortener\"}[5m])) by (le))",
            "legendFormat": "p95"
          },
          {
            "expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service=\"url-shortener\"}[5m])) by (le))",
            "legendFormat": "p99"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "type": "gauge",
        "gridPos": { "x": 12, "y": 8, "w": 6, "h": 8 },
        "targets": [
          {
            "expr": "sum(rate(cache_hits_total{service=\"url-shortener\"}[5m])) / (sum(rate(cache_hits_total{service=\"url-shortener\"}[5m])) + sum(rate(cache_misses_total{service=\"url-shortener\"}[5m]))) * 100"
          }
        ],
        "options": {
          "thresholds": [
            { "color": "red", "value": 0 },
            { "color": "yellow", "value": 80 },
            { "color": "green", "value": 95 }
          ]
        }
      },
      {
        "title": "URLs Created",
        "type": "stat",
        "gridPos": { "x": 18, "y": 8, "w": 6, "h": 8 },
        "targets": [
          {
            "expr": "sum(increase(urls_created_total{service=\"url-shortener\"}[24h]))"
          }
        ]
      }
    ]
  }
}
```

---

## Alerting Strategy

### Alert Definitions

```yaml
# cloudwatch-alarms.yaml
alarms:
  # Latency Alerts
  - name: high-p99-latency
    description: "P99 latency exceeds 100ms"
    metric: redirect.latency.p99
    threshold: 100
    comparison: GreaterThanThreshold
    period: 300  # 5 minutes
    evaluation_periods: 2
    statistic: Average
    actions:
      - sns:pagerduty-high
    severity: warning

  - name: critical-p99-latency
    description: "P99 latency exceeds 500ms"
    metric: redirect.latency.p99
    threshold: 500
    comparison: GreaterThanThreshold
    period: 60
    evaluation_periods: 3
    statistic: Average
    actions:
      - sns:pagerduty-critical
    severity: critical

  # Error Rate Alerts
  - name: elevated-error-rate
    description: "Error rate exceeds 0.1%"
    metric: errors.ratio
    threshold: 0.1
    comparison: GreaterThanThreshold
    period: 300
    evaluation_periods: 2
    statistic: Average
    actions:
      - sns:pagerduty-high
    severity: warning

  - name: critical-error-rate
    description: "Error rate exceeds 1%"
    metric: errors.ratio
    threshold: 1
    comparison: GreaterThanThreshold
    period: 60
    evaluation_periods: 3
    statistic: Average
    actions:
      - sns:pagerduty-critical
    severity: critical

  # Availability Alerts
  - name: service-unavailable
    description: "Service health check failing"
    metric: health.check.success
    threshold: 1
    comparison: LessThanThreshold
    period: 60
    evaluation_periods: 2
    statistic: Minimum
    actions:
      - sns:pagerduty-critical
    severity: critical

  # Infrastructure Alerts
  - name: high-cpu-utilization
    description: "CPU utilization exceeds 80%"
    metric: CPUUtilization
    namespace: AWS/ECS
    threshold: 80
    comparison: GreaterThanThreshold
    period: 300
    evaluation_periods: 3
    statistic: Average
    actions:
      - sns:pagerduty-high
    severity: warning

  - name: dynamodb-throttling
    description: "DynamoDB requests being throttled"
    metric: ThrottledRequests
    namespace: AWS/DynamoDB
    threshold: 10
    comparison: GreaterThanThreshold
    period: 60
    evaluation_periods: 1
    statistic: Sum
    actions:
      - sns:pagerduty-high
    severity: high

  - name: low-cache-hit-rate
    description: "Cache hit rate below 90%"
    metric: cache.hit_rate
    threshold: 90
    comparison: LessThanThreshold
    period: 300
    evaluation_periods: 3
    statistic: Average
    actions:
      - sns:slack-engineering
    severity: warning

  # Business Alerts
  - name: unusual-traffic-spike
    description: "Traffic 3x normal for this time"
    metric: redirects.rate
    threshold: dynamic  # Based on historical data
    comparison: GreaterThanThreshold
    period: 300
    evaluation_periods: 2
    statistic: Average
    actions:
      - sns:slack-engineering
    severity: info

  - name: zero-urls-created
    description: "No URLs created in last hour"
    metric: urls.created
    threshold: 0
    comparison: LessThanOrEqualToThreshold
    period: 3600
    evaluation_periods: 1
    statistic: Sum
    actions:
      - sns:slack-engineering
    severity: warning
```

### Escalation Policy

```yaml
# pagerduty-escalation.yaml
escalation_policies:
  - name: url-shortener-production
    rules:
      - escalation_delay_in_minutes: 0
        targets:
          - type: schedule
            id: primary-on-call

      - escalation_delay_in_minutes: 15
        targets:
          - type: schedule
            id: secondary-on-call

      - escalation_delay_in_minutes: 30
        targets:
          - type: user
            id: engineering-manager

      - escalation_delay_in_minutes: 45
        targets:
          - type: user
            id: vp-engineering

on_call_schedules:
  - name: primary-on-call
    time_zone: UTC
    rotation:
      type: weekly
      start_time: "09:00"

  - name: secondary-on-call
    time_zone: UTC
    rotation:
      type: weekly
      start_time: "09:00"
      shift_offset: 1  # Offset by 1 person
```

### Alert Response Runbooks

```markdown
## Runbook: High P99 Latency

### Symptoms
- P99 latency > 100ms for > 5 minutes

### Diagnosis Steps
1. Check CloudWatch dashboard for latency trends
2. Verify cache hit rate (should be > 95%)
3. Check DynamoDB consumed capacity
4. Review recent deployments
5. Check for traffic spikes

### Resolution
1. If cache hit rate low:
   - Check Redis cluster health
   - Verify cache is populating correctly
   - Consider cache warm-up

2. If DynamoDB throttling:
   - Enable on-demand capacity mode
   - Check for hot partitions

3. If traffic spike:
   - Scale EKS pods horizontally
   - Verify auto-scaling is working

### Escalation
- If unresolved after 30 minutes, escalate to senior engineer
- If impacting SLA, notify customer success team
```

---

## Health Checks

### Application Health Endpoints

```rust
use axum::{extract::State, Json};
use serde::Serialize;

#[derive(Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
    pub checks: Vec<HealthCheck>,
}

#[derive(Serialize)]
pub struct HealthCheck {
    pub name: String,
    pub status: String,
    pub latency_ms: Option<u64>,
    pub message: Option<String>,
}

/// Liveness probe - is the service alive?
pub async fn liveness() -> &'static str {
    "OK"
}

/// Readiness probe - is the service ready to accept traffic?
pub async fn readiness(State(state): State<AppState>) -> Json<HealthResponse> {
    let mut checks = Vec::new();
    let mut all_healthy = true;

    // Check DynamoDB
    let dynamo_check = check_dynamodb(&state.dynamo).await;
    if dynamo_check.status != "healthy" {
        all_healthy = false;
    }
    checks.push(dynamo_check);

    // Check Redis
    let redis_check = check_redis(&state.redis).await;
    if redis_check.status != "healthy" {
        all_healthy = false;
    }
    checks.push(redis_check);

    Json(HealthResponse {
        status: if all_healthy { "healthy" } else { "degraded" }.to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        checks,
    })
}

async fn check_dynamodb(client: &DynamoClient) -> HealthCheck {
    let start = std::time::Instant::now();

    match client
        .describe_table()
        .table_name("url-shortener-urls")
        .send()
        .await
    {
        Ok(_) => HealthCheck {
            name: "dynamodb".to_string(),
            status: "healthy".to_string(),
            latency_ms: Some(start.elapsed().as_millis() as u64),
            message: None,
        },
        Err(e) => HealthCheck {
            name: "dynamodb".to_string(),
            status: "unhealthy".to_string(),
            latency_ms: Some(start.elapsed().as_millis() as u64),
            message: Some(e.to_string()),
        },
    }
}

async fn check_redis(client: &RedisPool) -> HealthCheck {
    let start = std::time::Instant::now();

    match client.get_async_connection().await {
        Ok(mut conn) => {
            match redis::cmd("PING").query_async::<_, String>(&mut conn).await {
                Ok(_) => HealthCheck {
                    name: "redis".to_string(),
                    status: "healthy".to_string(),
                    latency_ms: Some(start.elapsed().as_millis() as u64),
                    message: None,
                },
                Err(e) => HealthCheck {
                    name: "redis".to_string(),
                    status: "unhealthy".to_string(),
                    latency_ms: Some(start.elapsed().as_millis() as u64),
                    message: Some(e.to_string()),
                },
            }
        }
        Err(e) => HealthCheck {
            name: "redis".to_string(),
            status: "unhealthy".to_string(),
            latency_ms: Some(start.elapsed().as_millis() as u64),
            message: Some(e.to_string()),
        },
    }
}
```

---

## SLIs, SLOs, and SLAs

### Service Level Indicators (SLIs)

| SLI | Definition | Measurement |
|-----|------------|-------------|
| Availability | Successful requests / Total requests | (2xx + 3xx) / Total |
| Latency | Request duration at p99 | Histogram percentile |
| Error Rate | Failed requests / Total requests | (4xx + 5xx) / Total |
| Throughput | Requests handled per second | Counter rate |

### Service Level Objectives (SLOs)

| Metric | SLO | Error Budget (monthly) |
|--------|-----|------------------------|
| Availability | 99.95% | 22 minutes |
| Redirect Latency (p99) | < 50ms | N/A |
| API Latency (p99) | < 200ms | N/A |
| Error Rate | < 0.1% | N/A |

### SLO Monitoring

```yaml
# slo-monitoring.yaml
slos:
  - name: redirect-availability
    description: "Redirect endpoint availability"
    sli:
      type: availability
      good_events: "http_requests_total{handler='redirect',status=~'2..|3..'}"
      total_events: "http_requests_total{handler='redirect'}"
    objective: 99.95
    window: 30d

  - name: redirect-latency
    description: "Redirect latency under 50ms"
    sli:
      type: latency
      threshold: 0.05  # 50ms
      metric: "http_request_duration_seconds{handler='redirect'}"
    objective: 99
    window: 30d

  - name: api-availability
    description: "API endpoint availability"
    sli:
      type: availability
      good_events: "http_requests_total{handler=~'api.*',status=~'2..|3..'}"
      total_events: "http_requests_total{handler=~'api.*'}"
    objective: 99.9
    window: 30d

error_budget_alerts:
  - name: error-budget-50-consumed
    threshold: 50
    window: 7d
    severity: warning

  - name: error-budget-75-consumed
    threshold: 75
    window: 7d
    severity: high

  - name: error-budget-90-consumed
    threshold: 90
    window: 7d
    severity: critical
```
