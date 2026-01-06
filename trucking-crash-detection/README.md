# Trucking Crash Detection & Prediction System

## Overview

A real-time IoT-based system for automated crash detection and prediction for commercial trucking fleets. The system processes telematics sensor data from ~1M vehicles to provide instant crash alerts, predictive warnings, and streamlined claims processing.

## System Architecture (High-Level)

```mermaid
flowchart LR
    subgraph Sources["🚚 Data Sources"]
        V[1M Vehicles]
        P[100+ Providers]
    end

    subgraph Ingestion["📥 Ingestion"]
        GW[API Gateway]
        NORM[Normalizer]
    end

    subgraph Stream["⚡ Processing"]
        K[(Kafka<br/>10M/s)]
        F[Flink]
        ML[ML Models]
    end

    subgraph Alert["🚨 Alerts"]
        AR[Router]
        N[Notify]
    end

    subgraph Output["📱 Output"]
        D[Dashboard]
        M[Mobile]
        C[Claims]
    end

    V --> P --> GW --> NORM --> K --> F <--> ML
    F --> AR --> N --> D & M & C

    style Sources fill:#e1f5fe
    style Ingestion fill:#fff3e0
    style Stream fill:#e8f5e9
    style Alert fill:#fce4ec
    style Output fill:#e3f2fd
```

## End-to-End Data Flow

```mermaid
sequenceDiagram
    participant V as 🚚 Vehicle
    participant P as 📡 Provider
    participant I as 📥 Ingestion
    participant K as 📨 Kafka
    participant F as ⚡ Flink
    participant M as 🧠 ML
    participant A as 🚨 Alert
    participant U as 👤 User

    V->>P: Sensor data (10-50/sec)
    P->>I: Push/Pull (~50ms)
    I->>K: Produce (~10ms)
    K->>F: Consume
    F->>M: Inference request
    M->>F: Crash detected (0.92)
    F->>A: Crash event
    A->>U: SMS + Push (<30s)

    Note over V,U: Total: ~500ms detection, <30s notification
```

## Business Context

### Problem Statement
- Manual crash detection leads to delayed response times
- Slow claims processing increases costs
- No predictive capabilities for accident prevention
- Multiple telematics providers with no uniform standards

### Goals
1. **Immediate Detection**: Real-time crash detection < 5 seconds from event
2. **Customer Notification**: Alert stakeholders within 30 seconds
3. **Predictive Warnings**: Surface high-risk patterns before incidents
4. **Fast Settlement**: Pre-populated claims to reduce processing time by 60%

## Scale Parameters

| Metric | Value |
|--------|-------|
| Total Policies | 10,000 |
| Total Vehicles | ~1,000,000 |
| Vehicles per Policy | 10-500 (avg: 100) |
| Coverage Area | Continental USA |
| Telematics Providers | 100+ |
| Data Points per Vehicle/Second | 10-50 |

## Documentation Structure

1. [System Architecture](./system-architecture.md) - High-level design and components
2. [Data Ingestion Layer](./data-ingestion.md) - Provider integration strategies
3. [Stream Processing](./stream-processing.md) - Real-time data processing pipeline
4. [ML Pipeline](./ml-pipeline.md) - Crash detection and prediction models
5. [Alert & Notification](./alerts-notifications.md) - Alert routing and delivery
6. [Observability](./observability.md) - Monitoring, logging, alerting, SLAs
7. [Architecture Diagrams](./diagrams/architecture-diagrams.md) - Visual representations

## Quick Links

- [API Contracts](./api-contracts.md)
- [Data Models](./data-models.md)
- [Deployment Strategy](./deployment.md)

