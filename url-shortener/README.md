# URL Shortener - Production-Grade System Design

A comprehensive URL shortener service built with Rust, designed to scale from local development to serving **500 million new URLs per month** globally.

## Overview

This project demonstrates a complete system design implementation including:

- **5 Scaling Tiers**: From local SQLite to global DynamoDB with edge computing
- **Full Rust Implementation**: Using Axum for maximum performance
- **AWS Infrastructure**: CloudFront, EKS, DynamoDB Global Tables, ElastiCache
- **Compliance**: GDPR, CCPA, SOC 2, and HIPAA ready
- **Observability**: OpenTelemetry, CloudWatch, X-Ray integration

## Architecture

```mermaid
flowchart TB
    subgraph Edge["CloudFront (200+ PoPs) + Lambda@Edge + WAF"]
        CF["Edge Layer"]
    end

    CF --> US["US-East-1<br/>EKS + Redis"]
    CF --> EU["EU-West-1<br/>EKS + Redis"]
    CF --> AP["AP-South-1<br/>EKS + Redis"]

    US --> Data["DynamoDB Global Tables<br/>+ Kinesis + Timestream"]
    EU --> Data
    AP --> Data
```

## Quick Start

### Local Development (Tier 1)

```bash
# Clone the repository
git clone https://github.com/your-org/url-shortener.git
cd url-shortener

# Run with Docker Compose
docker-compose up -d

# Or run directly with Cargo
cargo run

# The service will be available at http://localhost:8080
```

### Create a Short URL

```bash
# Create a short URL
curl -X POST http://localhost:8080/api/v1/urls \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/very/long/path"}'

# Response:
# {
#   "id": "uuid",
#   "short_code": "abc123X",
#   "short_url": "http://localhost:8080/abc123X",
#   "original_url": "https://example.com/very/long/path",
#   "created_at": "2024-01-15T10:30:00Z"
# }

# Use the short URL
curl -L http://localhost:8080/abc123X
# Redirects to https://example.com/very/long/path
```

## Project Structure

```
url-shortener/
├── docs/                       # Comprehensive documentation
│   ├── 01-overview.md          # System overview
│   ├── 02-requirements.md      # Requirements per tier
│   ├── 03-architecture.md      # Architecture details
│   ├── 04-database-design.md   # Schema and cleanup policies
│   ├── 05-security-compliance.md # GDPR/CCPA/SOC2/HIPAA
│   ├── 06-telemetry.md         # Observability
│   └── 07-deployment.md        # AWS deployment
├── src/                        # Rust application
│   ├── main.rs                 # Entry point
│   ├── api/                    # HTTP handlers
│   ├── domain/                 # Business logic
│   ├── infrastructure/         # External services
│   ├── telemetry/              # Observability
│   ├── compliance/             # GDPR, audit
│   └── middleware/             # Auth, rate limiting
├── terraform/                  # AWS infrastructure
│   ├── modules/                # Reusable modules
│   └── environments/           # Environment configs
├── k8s/                        # Kubernetes manifests
├── docker/                     # Docker configurations
└── migrations/                 # Database migrations
```

## Scaling Tiers

```mermaid
flowchart LR
    T1["Tier 1: LOCAL<br/>1K URLs/mo<br/>SQLite"]
    T2["Tier 2: STARTUP<br/>100K URLs/mo<br/>PostgreSQL + Redis"]
    T3["Tier 3: GROWTH<br/>10M URLs/mo<br/>Multi-instance"]
    T4["Tier 4: SCALE<br/>100M URLs/mo<br/>Multi-region"]
    T5["Tier 5: GLOBAL<br/>500M URLs/mo<br/>Edge computing"]

    T1 --> T2 --> T3 --> T4 --> T5
```

| Tier | Scale | URLs/Month | Architecture |
|------|-------|------------|--------------|
| 1 | Local | 1K | Single binary + SQLite |
| 2 | Startup | 100K | PostgreSQL + Redis |
| 3 | Growth | 10M | Multi-instance + Replicas |
| 4 | Scale | 100M | Multi-region + DynamoDB |
| 5 | Global | 500M | Edge computing + Sharded |

## API Endpoints

```mermaid
flowchart LR
    subgraph URLs["URL Management"]
        POST["POST /api/v1/urls"]
        GET_ALL["GET /api/v1/urls"]
        GET_ONE["GET /api/v1/urls/:code"]
        DELETE["DELETE /api/v1/urls/:code"]
        BULK["POST /api/v1/urls/bulk"]
    end

    subgraph Analytics["Analytics"]
        SUMMARY["GET /api/v1/analytics/:code"]
        REALTIME["GET /api/v1/analytics/:code/realtime"]
        GEO["GET /api/v1/analytics/:code/geo"]
    end

    subgraph Compliance["Compliance"]
        EXPORT["GET /api/v1/compliance/gdpr/export"]
        ERASURE["DELETE /api/v1/compliance/gdpr/erasure"]
    end

    subgraph Health["Health"]
        LIVE["/health"]
        READY["/ready"]
        METRICS["/metrics"]
    end
```

## Configuration

Environment variables:

```bash
# Server
PORT=8080
ENVIRONMENT=development

# Database
DATABASE_TYPE=sqlite  # or: dynamodb
DATABASE_URL=sqlite:./data/urls.db?mode=rwc

# Cache
CACHE_TYPE=memory  # or: redis
REDIS_URL=redis://localhost:6379

# AWS (for DynamoDB mode)
AWS_REGION=us-east-1
AWS_LOCAL_MODE=true  # Use LocalStack

# Telemetry
RUST_LOG=info
OTLP_ENDPOINT=http://localhost:4317

# URL Configuration
BASE_URL=http://localhost:8080
```

## ID Generation

```mermaid
flowchart TB
    subgraph Generation["ID Generation Strategy"]
        Counter["Distributed Counter<br/>(DynamoDB)"]
        Batch["Allocate 1M IDs<br/>per instance"]
        Local["Local atomic counter"]
        Encode["Base62 encode<br/>7 characters"]
    end

    Counter --> Batch --> Local --> Encode

    subgraph Capacity["Capacity"]
        Total["62^7 = 3.5 trillion codes"]
        Years["At 500M/month = 580 years"]
    end
```

## Deployment

### Kubernetes (EKS)

```bash
# Apply base configuration
kubectl apply -k k8s/base/

# Or use environment-specific overlay
kubectl apply -k k8s/overlays/production/
```

### Terraform

```bash
cd terraform/environments/production

terraform init
terraform plan
terraform apply
```

## Security Features

```mermaid
flowchart LR
    subgraph Auth["Authentication"]
        APIKeys["API Keys<br/>(Argon2 hashed)"]
        JWT["JWT Tokens"]
    end

    subgraph Protection["Protection"]
        RateLimit["Rate Limiting"]
        Shield["AWS Shield"]
        WAF["AWS WAF"]
    end

    subgraph Encryption["Encryption"]
        TLS["TLS 1.3 in transit"]
        AES["AES-256 at rest"]
    end

    subgraph Audit["Audit"]
        Logs["Immutable logs"]
        Retention["7-year retention"]
    end
```

## Compliance

| Framework | Status | Features |
|-----------|--------|----------|
| GDPR | Ready | Data export, erasure (72h SLA), consent tracking |
| CCPA | Ready | Do-not-sell, disclosure, opt-out |
| SOC 2 | Ready | Access controls, audit logs, encryption |
| HIPAA | Ready | Enterprise tier with BAA |

## Performance Targets

```mermaid
xychart-beta
    title "Latency by Tier (p99)"
    x-axis ["Tier 1", "Tier 2", "Tier 3", "Tier 4", "Tier 5"]
    y-axis "Latency (ms)" 0 --> 100
    bar [50, 100, 50, 30, 20]
```

| Metric | Target (Tier 5) |
|--------|-----------------|
| Redirect Latency (p99) | < 20ms |
| Availability | 99.99% |
| Cache Hit Rate | > 98% |
| Throughput | 50K+ RPS |

## Documentation

See the `/docs` directory for comprehensive documentation:

1. [System Overview](docs/01-overview.md)
2. [Requirements](docs/02-requirements.md)
3. [Architecture](docs/03-architecture.md)
4. [Database Design](docs/04-database-design.md)
5. [Security & Compliance](docs/05-security-compliance.md)
6. [Telemetry](docs/06-telemetry.md)
7. [Deployment](docs/07-deployment.md)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `cargo test`
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

This project was designed as a comprehensive system design example, demonstrating best practices for building scalable, secure, and compliant web services.
