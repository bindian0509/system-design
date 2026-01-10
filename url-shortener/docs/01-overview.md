# URL Shortener System Design - Overview

## Introduction

This document describes the system design for a production-grade URL shortener service that scales from a local development environment to serving **500 million new URLs per month** across the globe. The system is built with Rust for maximum performance and deployed on AWS infrastructure.

## What is a URL Shortener?

A URL shortener is a service that converts long URLs into short, memorable links that redirect to the original destination. For example:

```
Original:  https://example.com/very/long/path/with/many/parameters?utm_source=email&campaign=summer2026
Shortened: https://short.io/abc123X
```

## Core Use Cases

1. **Social Media Sharing**: Character-limited platforms benefit from shorter URLs
2. **Marketing Campaigns**: Track click-through rates with unique short links
3. **Print Media**: QR codes and printed materials need concise URLs
4. **Analytics**: Understand user behavior through click tracking
5. **A/B Testing**: Route traffic to different destinations dynamically

---

## Scaling Tiers

The system is designed to evolve through five distinct scaling tiers, each building upon the previous one:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            SCALING PROGRESSION                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Tier 1          Tier 2          Tier 3          Tier 4          Tier 5         │
│  LOCAL           STARTUP         GROWTH          SCALE           GLOBAL         │
│  ─────           ───────         ──────          ─────           ──────         │
│  1K URLs/mo      100K URLs/mo    10M URLs/mo     100M URLs/mo    500M URLs/mo   │
│  10 RPS          100 RPS         1K RPS          10K RPS         50K+ RPS       │
│                                                                                  │
│  SQLite          PostgreSQL      Multi-Instance  Multi-Region    Edge           │
│  Single Binary   + Redis         + Replicas      + Global DB     Computing      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Tier 1: Local Development (1K URLs/month)

**Target**: Individual developers, prototyping, local testing

| Aspect | Details |
|--------|---------|
| Scale | ~1,000 URLs/month, ~10 reads/second |
| Infrastructure | Single binary, SQLite database |
| Deployment | Local machine or single VPS |
| Cost | $0 - $5/month |

**Architecture**:
```
┌──────────────────────────────────────┐
│         Single Rust Binary           │
│  ┌──────────┐    ┌────────────────┐  │
│  │  Axum    │────│    SQLite      │  │
│  │  Server  │    │   (File DB)    │  │
│  └──────────┘    └────────────────┘  │
└──────────────────────────────────────┘
```

### Tier 2: Startup (100K URLs/month)

**Target**: Early-stage startups, small teams, MVPs

| Aspect | Details |
|--------|---------|
| Scale | ~100,000 URLs/month, ~100 reads/second |
| Infrastructure | Single server, PostgreSQL, Redis cache |
| Deployment | Single EC2 instance or equivalent |
| Cost | $50 - $200/month |

**Architecture**:
```
┌────────────────────────────────────────────────────────────┐
│                      Single Server                          │
│  ┌──────────┐    ┌──────────┐    ┌────────────────────┐    │
│  │  Axum    │────│  Redis   │    │    PostgreSQL      │    │
│  │  Server  │    │  Cache   │────│    (Primary)       │    │
│  └──────────┘    └──────────┘    └────────────────────┘    │
└────────────────────────────────────────────────────────────┘
```

### Tier 3: Growth (10M URLs/month)

**Target**: Growing companies, moderate traffic, first scale challenges

| Aspect | Details |
|--------|---------|
| Scale | ~10 million URLs/month, ~1,000 reads/second |
| Infrastructure | Load balancer, multiple instances, read replicas |
| Deployment | Kubernetes cluster (EKS) |
| Cost | $1,000 - $5,000/month |

**Architecture**:
```
                    ┌─────────────┐
                    │    ALB      │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │  Instance  │  │  Instance  │  │  Instance  │
    │     1      │  │     2      │  │     3      │
    └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
          │               │               │
          └───────────────┼───────────────┘
                          ▼
    ┌──────────────────────────────────────────────┐
    │              Redis Cluster                    │
    └──────────────────────┬───────────────────────┘
                           ▼
    ┌────────────────┐          ┌────────────────┐
    │   PostgreSQL   │◀────────▶│  Read Replica  │
    │    Primary     │          │                │
    └────────────────┘          └────────────────┘
```

### Tier 4: Scale (100M URLs/month)

**Target**: Large companies, multi-region requirements, compliance needs

| Aspect | Details |
|--------|---------|
| Scale | ~100 million URLs/month, ~10,000 reads/second |
| Infrastructure | Multi-region, DynamoDB Global Tables, CloudFront |
| Deployment | Multi-region EKS clusters |
| Cost | $10,000 - $50,000/month |

**Architecture**:
```
                         ┌──────────────┐
                         │  CloudFront  │
                         │     CDN      │
                         └──────┬───────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│   US-East-1   │       │   EU-West-1   │       │   AP-South-1  │
│  EKS Cluster  │       │  EKS Cluster  │       │  EKS Cluster  │
│  + Redis      │       │  + Redis      │       │  + Redis      │
└───────┬───────┘       └───────┬───────┘       └───────┬───────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
                    ┌───────────────────────┐
                    │  DynamoDB Global      │
                    │  Tables (Multi-Region)│
                    └───────────────────────┘
```

### Tier 5: Global (500M URLs/month)

**Target**: Internet-scale companies, global presence, real-time requirements

| Aspect | Details |
|--------|---------|
| Scale | ~500 million URLs/month, ~50,000+ reads/second |
| Infrastructure | Edge computing, sharded architecture, real-time analytics |
| Deployment | Global edge presence (50+ locations) |
| Cost | $100,000+/month |

**Architecture**:
```
                    ┌────────────────────────────────────────┐
                    │         CloudFront (200+ PoPs)         │
                    │         + Lambda@Edge                  │
                    │         + AWS WAF + Shield             │
                    └───────────────────┬────────────────────┘
                                        │
    ┌───────────────────────────────────┼───────────────────────────────────┐
    │                                   │                                   │
    ▼                                   ▼                                   ▼
┌─────────────────┐           ┌─────────────────┐           ┌─────────────────┐
│    US-East-1    │           │    EU-West-1    │           │    AP-South-1   │
│  ┌───────────┐  │           │  ┌───────────┐  │           │  ┌───────────┐  │
│  │    ALB    │  │           │  │    ALB    │  │           │  │    ALB    │  │
│  └─────┬─────┘  │           │  └─────┬─────┘  │           │  └─────┬─────┘  │
│        ▼        │           │        ▼        │           │        ▼        │
│  ┌───────────┐  │           │  ┌───────────┐  │           │  ┌───────────┐  │
│  │    EKS    │  │           │  │    EKS    │  │           │  │    EKS    │  │
│  │  Cluster  │  │           │  │  Cluster  │  │           │  │  Cluster  │  │
│  └─────┬─────┘  │           │  └─────┬─────┘  │           │  └─────┬─────┘  │
│        ▼        │           │        ▼        │           │        ▼        │
│  ┌───────────┐  │           │  ┌───────────┐  │           │  ┌───────────┐  │
│  │ElastiCache│  │           │  │ElastiCache│  │           │  │ElastiCache│  │
│  │  Redis    │  │           │  │  Redis    │  │           │  │  Redis    │  │
│  └───────────┘  │           │  └───────────┘  │           │  └───────────┘  │
└────────┬────────┘           └────────┬────────┘           └────────┬────────┘
         │                             │                             │
         └─────────────────────────────┼─────────────────────────────┘
                                       ▼
              ┌────────────────────────────────────────────────────┐
              │              DynamoDB Global Tables                 │
              │         (Active-Active Multi-Region)                │
              └────────────────────────┬───────────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
┌─────────────────┐         ┌─────────────────────┐        ┌─────────────────┐
│ Kinesis Streams │────────▶│  Lambda Processors  │───────▶│   Timestream    │
│ (Click Events)  │         │  (Real-time ETL)    │        │  (Analytics)    │
└─────────────────┘         └─────────────────────┘        └─────────────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │    S3 Audit Logs    │
                            │   + Glacier Archive │
                            └─────────────────────┘
```

---

## Traffic Calculations

### Tier 5 Capacity Planning (500M URLs/month)

```
URLs Created:
  - 500M new URLs/month
  - ~16.7M URLs/day
  - ~694K URLs/hour
  - ~193 URLs/second (write)

Redirect Traffic (assuming 100:1 read-to-write ratio):
  - 50B redirects/month
  - ~1.67B redirects/day
  - ~69.4M redirects/hour
  - ~19,300 redirects/second (read)

Peak Traffic (3x average):
  - ~580 URLs/second (write peak)
  - ~58,000 redirects/second (read peak)
```

### Storage Calculations

```
Per URL Record:
  - short_code: 7 bytes
  - original_url: ~200 bytes (average)
  - metadata: ~100 bytes
  - Total: ~310 bytes per URL

Monthly Storage:
  - 500M URLs × 310 bytes = 155 GB/month
  - Annual: 1.86 TB/year

Analytics Events (per click):
  - Event size: ~200 bytes
  - 50B clicks × 200 bytes = 10 TB/month (before rollup)
  - After daily rollup: ~100 GB/month
```

---

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Rust | Maximum performance, memory safety, zero-cost abstractions |
| Web Framework | Axum | Async, type-safe, excellent performance |
| Database (Local) | SQLite | Zero configuration, embedded |
| Database (Production) | DynamoDB | Global replication, auto-scaling, single-digit ms latency |
| Cache | Redis (ElastiCache) | Sub-ms latency, clustering support |
| CDN | CloudFront | Global edge network, Lambda@Edge support |
| Container Orchestration | EKS (Kubernetes) | Industry standard, auto-scaling |
| Infrastructure | Terraform | Reproducible, version-controlled infrastructure |
| Observability | OpenTelemetry | Vendor-neutral, comprehensive telemetry |
| Metrics | CloudWatch + Grafana | AWS-native + visualization |
| Tracing | AWS X-Ray | Distributed tracing across services |

---

## Key Design Decisions

### 1. Short Code Generation

Using **Base62 encoding** with 7 characters:
- Character set: `0-9`, `a-z`, `A-Z` (62 characters)
- 7 characters = 62^7 = **3.5 trillion** unique combinations
- At 500M URLs/month, this lasts ~580 years

```
Example:
  Counter: 1234567890
  Base62:  1LY7VK
```

### 2. ID Generation Strategy

**Approach**: Distributed counter with range allocation
- Each instance gets a range of IDs (e.g., 1M IDs at a time)
- No coordination needed for most writes
- DynamoDB atomic counter for range allocation

### 3. Caching Strategy

**Write-through cache** with 24-hour TTL:
- Write to both cache and database on create
- Read from cache first, fallback to database
- Popular URLs stay hot in cache
- Cache hit rate target: >95%

### 4. Collision Handling

**Check-and-retry** with exponential backoff:
- For custom aliases: immediate collision check
- For generated codes: statistically near-zero collision probability
- Retry up to 3 times with randomized suffix

---

## Document Index

| Document | Description |
|----------|-------------|
| [02-requirements.md](./02-requirements.md) | Functional and non-functional requirements per tier |
| [03-architecture.md](./03-architecture.md) | Detailed architecture and component design |
| [04-database-design.md](./04-database-design.md) | Schema, cleanup, and purge policies |
| [05-security-compliance.md](./05-security-compliance.md) | GDPR, CCPA, SOC2, HIPAA compliance |
| [06-telemetry.md](./06-telemetry.md) | Observability and monitoring strategy |
| [07-deployment.md](./07-deployment.md) | AWS infrastructure and deployment |

---

## Quick Start

```bash
# Local development (Tier 1)
cargo run

# Docker development
docker-compose up -d

# Kubernetes deployment (Tier 3+)
kubectl apply -k k8s/overlays/production/
```

---

## Repository Structure

```
url-shortener/
├── docs/                    # Documentation
├── src/                     # Rust application source
│   ├── main.rs              # Entry point
│   ├── api/                 # HTTP handlers
│   ├── domain/              # Business logic
│   ├── infrastructure/      # External services
│   ├── telemetry/           # Observability
│   └── compliance/          # Compliance modules
├── migrations/              # Database migrations
├── terraform/               # Infrastructure as Code
├── docker/                  # Container configurations
├── k8s/                     # Kubernetes manifests
├── Cargo.toml               # Rust dependencies
└── README.md                # Project README
```
