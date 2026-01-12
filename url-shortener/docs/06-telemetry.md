# Telemetry, Observability, and Alerting

This document covers the observability strategy including metrics, logging, tracing, dashboards, and alerting for the URL shortener system.

---

## Observability Strategy

```mermaid
flowchart TB
    subgraph Pillars["THREE PILLARS OF OBSERVABILITY"]
        subgraph Metrics["METRICS"]
            M1["What is happening?"]
            M2["Counters, Gauges, Histograms"]
        end

        subgraph Logs["LOGS"]
            L1["What happened?"]
            L2["Events, Errors, Audit"]
        end

        subgraph Traces["TRACES"]
            T1["How does it flow?"]
            T2["Spans, Context, Latency"]
        end
    end

    Metrics --> CorrelationID["Correlation ID<br/>(Request Tracing)"]
    Logs --> CorrelationID
    Traces --> CorrelationID
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

### Telemetry Pipeline

```mermaid
flowchart LR
    subgraph App["Application"]
        Metrics["Metrics"]
        Logs["Logs"]
        Traces["Traces"]
    end

    subgraph OTEL["OpenTelemetry"]
        SDK["Rust SDK"]
        OTLP["OTLP Exporter"]
    end

    subgraph AWS["AWS Services"]
        CW["CloudWatch"]
        XRay["X-Ray"]
        Logs_CW["CloudWatch Logs"]
    end

    subgraph Viz["Visualization"]
        Grafana["Grafana"]
    end

    App --> SDK --> OTLP
    OTLP --> CW
    OTLP --> XRay
    OTLP --> Logs_CW
    CW --> Grafana
```

### Custom Metrics

```mermaid
flowchart TB
    subgraph Counters["Counters"]
        urls_created["urls.created<br/>Total URLs created"]
        urls_deleted["urls.deleted<br/>Total URLs deleted"]
        redirects_served["redirects.served<br/>Total redirects"]
        cache_hits["cache.hits<br/>Cache hits"]
        cache_misses["cache.misses<br/>Cache misses"]
    end

    subgraph Histograms["Histograms"]
        redirect_latency["redirect.latency<br/>Redirect latency (ms)"]
        create_latency["create.latency<br/>URL creation latency (ms)"]
        db_latency["db.query.latency<br/>Database query latency (ms)"]
        cache_latency["cache.operation.latency<br/>Cache operation latency (ms)"]
    end

    subgraph Gauges["Gauges"]
        active_connections["connections.active<br/>Active connections"]
        cache_size["cache.size<br/>Items in cache"]
    end
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

```mermaid
flowchart LR
    subgraph Sources["Log Sources"]
        EKS["EKS Pod (stdout)"]
    end

    subgraph Collection["Collection"]
        FluentBit["FluentBit (DaemonSet)"]
    end

    subgraph Storage["Storage"]
        CWLogs["CloudWatch Logs"]
        OpenSearch["OpenSearch (Optional)"]
    end

    subgraph Analysis["Analysis"]
        Insights["CloudWatch Logs Insights<br/>• Query and analyze<br/>• Create dashboards<br/>• Metric filters"]
    end

    subgraph Archive["Long-term Archive"]
        S3["S3<br/>• 90 days hot<br/>• 1 year Glacier IR<br/>• 7 years Deep Archive"]
    end

    EKS --> FluentBit --> CWLogs
    CWLogs --> OpenSearch
    CWLogs --> Insights
    CWLogs --> S3
```

---

## Metrics and Dashboards

### Key Metrics (RED Method)

```mermaid
flowchart TB
    subgraph Rate["RATE (Requests/second)"]
        R1["redirects.rate"]
        R2["creates.rate"]
        R3["api.requests.rate"]
    end

    subgraph Errors["ERRORS (Error rate)"]
        E1["errors.rate"]
        E2["errors.ratio (%)"]
        E3["errors.by_type (4xx, 5xx)"]
        E4["errors.by_endpoint"]
    end

    subgraph Duration["DURATION (Latency percentiles)"]
        D1["latency.p50 (median)"]
        D2["latency.p90"]
        D3["latency.p99"]
        D4["latency.p999"]
    end
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

---

## Alerting Strategy

### Alert Severity Levels

```mermaid
flowchart LR
    subgraph Critical["Critical (P1)"]
        C1["Service down"]
        C2["Data breach"]
        C3["Error rate > 5%"]
    end

    subgraph High["High (P2)"]
        H1["Latency > 500ms p99"]
        H2["Error rate > 1%"]
        H3["DynamoDB throttling"]
    end

    subgraph Warning["Warning (P3)"]
        W1["Latency > 100ms p99"]
        W2["Error rate > 0.1%"]
        W3["Cache hit rate < 90%"]
    end

    subgraph Info["Info (P4)"]
        I1["Unusual traffic spike"]
        I2["No URLs created 1 hour"]
    end

    Critical -->|"15 min response"| PagerDuty["PagerDuty"]
    High -->|"1 hour response"| PagerDuty
    Warning -->|"4 hour response"| Slack["Slack"]
    Info -->|"Next business day"| Slack
```

### Alert Definitions

```mermaid
flowchart TB
    subgraph LatencyAlerts["Latency Alerts"]
        HighLatency["high-p99-latency<br/>P99 > 100ms, 5 min<br/>Severity: Warning"]
        CriticalLatency["critical-p99-latency<br/>P99 > 500ms, 1 min<br/>Severity: Critical"]
    end

    subgraph ErrorAlerts["Error Rate Alerts"]
        ElevatedError["elevated-error-rate<br/>Error > 0.1%, 5 min<br/>Severity: Warning"]
        CriticalError["critical-error-rate<br/>Error > 1%, 1 min<br/>Severity: Critical"]
    end

    subgraph AvailabilityAlerts["Availability Alerts"]
        Unavailable["service-unavailable<br/>Health check fail, 1 min<br/>Severity: Critical"]
    end

    subgraph InfraAlerts["Infrastructure Alerts"]
        HighCPU["high-cpu-utilization<br/>CPU > 80%, 5 min<br/>Severity: Warning"]
        DDBThrottle["dynamodb-throttling<br/>Throttled > 10, 1 min<br/>Severity: High"]
        LowCache["low-cache-hit-rate<br/>Hit rate < 90%, 5 min<br/>Severity: Warning"]
    end
```

### Escalation Policy

```mermaid
flowchart TB
    Incident["Incident Triggered"]

    L1["Level 1: Primary On-Call<br/>0 minutes"]
    L2["Level 2: Secondary On-Call<br/>15 minutes"]
    L3["Level 3: Engineering Manager<br/>30 minutes"]
    L4["Level 4: VP Engineering<br/>45 minutes"]

    Incident --> L1
    L1 -->|"No response"| L2
    L2 -->|"No response"| L3
    L3 -->|"No response"| L4
```

---

## Health Checks

### Health Check Endpoints

```mermaid
flowchart LR
    subgraph Endpoints["Health Endpoints"]
        Liveness["/health<br/>Liveness probe<br/>Returns: OK"]
        Readiness["/ready<br/>Readiness probe<br/>Returns: JSON status"]
        Metrics["/metrics<br/>Prometheus metrics"]
    end

    subgraph ReadinessChecks["Readiness Checks"]
        DDB["DynamoDB connectivity"]
        Redis["Redis connectivity"]
    end

    Readiness --> DDB
    Readiness --> Redis
```

### Readiness Response

```json
{
  "status": "healthy",
  "version": "1.2.3",
  "checks": [
    {
      "name": "dynamodb",
      "status": "healthy",
      "latency_ms": 5
    },
    {
      "name": "redis",
      "status": "healthy",
      "latency_ms": 1
    }
  ]
}
```

---

## SLIs, SLOs, and SLAs

### Service Level Indicators (SLIs)

```mermaid
flowchart LR
    subgraph SLIs["Service Level Indicators"]
        Availability["Availability<br/>(2xx + 3xx) / Total"]
        Latency["Latency<br/>p99 request duration"]
        ErrorRate["Error Rate<br/>(4xx + 5xx) / Total"]
        Throughput["Throughput<br/>Requests/second"]
    end
```

### Service Level Objectives (SLOs)

| Metric | SLO | Error Budget (monthly) |
|--------|-----|------------------------|
| Availability | 99.95% | 22 minutes |
| Redirect Latency (p99) | < 50ms | N/A |
| API Latency (p99) | < 200ms | N/A |
| Error Rate | < 0.1% | N/A |

### Error Budget Consumption

```mermaid
xychart-beta
    title "Error Budget Consumption (30-day window)"
    x-axis ["Week 1", "Week 2", "Week 3", "Week 4"]
    y-axis "Budget Consumed (%)" 0 --> 100
    bar [15, 35, 55, 72]
    line [25, 50, 75, 100]
```

### Error Budget Alerts

| Threshold | Window | Severity | Action |
|-----------|--------|----------|--------|
| 50% consumed | 7 days | Warning | Review velocity |
| 75% consumed | 7 days | High | Slow deployments |
| 90% consumed | 7 days | Critical | Freeze deployments |
