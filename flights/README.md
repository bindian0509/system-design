# Cheapest Flights & Dynamic Pricing System

A production-grade flight search and dynamic pricing system similar to Google Flights, Skyscanner, and Kayak.

## Scale Parameters

| Metric | Target |
|--------|--------|
| Daily Searches | 100M+ |
| Average RPS | ~1,200 |
| Peak RPS | 5,000 |
| Search Latency (P95) | < 2 seconds |
| Availability | 99.9% |
| Supplier Integrations | 500+ |

## Features

- **Real-time Flight Search**: Aggregate results from 500+ suppliers with sub-2-second latency
- **Dynamic Pricing**: ML-driven price optimization based on demand, seasonality, and booking patterns
- **Price Prediction**: Forecast price movements to help users decide when to book
- **Price Alerts**: Notify users when prices drop below their target
- **Progressive Results**: Stream results as they arrive using Server-Sent Events
- **Multi-city Search**: Support complex itineraries with multiple stops

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│                    (Web App, Mobile App, Partner APIs)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                     │
│                 (Rate Limiting, Auth, Request Routing)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
           ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
           │    Search    │  │   Booking    │  │    Alerts    │
           │    Service   │  │   Service    │  │   Service    │
           └──────────────┘  └──────────────┘  └──────────────┘
                    │                 │                 │
                    ▼                 ▼                 ▼
           ┌──────────────────────────────────────────────────┐
           │              Supplier Gateway Service             │
           │       (Unified interface to 500+ suppliers)       │
           └──────────────────────────────────────────────────┘
                                      │
        ┌────────────────┬────────────┼────────────┬────────────────┐
        ▼                ▼            ▼            ▼                ▼
   ┌─────────┐    ┌─────────┐   ┌─────────┐   ┌─────────┐    ┌─────────┐
   │ Amadeus │    │ Sabre   │   │Travelport│  │ Direct  │    │ LCC     │
   │   GDS   │    │   GDS   │   │   GDS    │  │Airlines │    │ APIs    │
   └─────────┘    └─────────┘   └─────────┘   └─────────┘    └─────────┘
```

## Core Services

| Service | Responsibility |
|---------|----------------|
| **Search Service** | Orchestrates flight searches across suppliers |
| **Booking Service** | Handles reservations and payment processing |
| **Alerts Service** | Manages price alerts and notifications |
| **Supplier Gateway** | Unified adapter layer for external APIs |
| **Pricing Engine** | Dynamic pricing and markup calculations |
| **Prediction Service** | ML-based price trend predictions |

## Data Stores

| Store | Purpose |
|-------|---------|
| **PostgreSQL** | Users, bookings, alerts, routes |
| **Redis Cluster** | Search results, pricing cache, sessions |
| **ClickHouse** | Historical prices, search analytics |
| **ElasticSearch** | Airport/city autocomplete |
| **Kafka** | Event streaming for price updates |

## Documentation

- [System Overview](./architecture/system-overview.md) - Detailed component design
- [Data Flow](./architecture/data-flow.md) - Request/response flows
- [API Contracts](./api/api-contracts.md) - REST API specifications
- [Data Models](./data/data-models.md) - Database schemas
- [Caching Strategy](./data/caching-strategy.md) - Multi-layer caching design
- [Search Orchestrator](./services/search-orchestrator.md) - Search service design
- [Supplier Gateway](./services/supplier-gateway.md) - External integrations
- [Pricing Engine](./services/pricing-engine.md) - Dynamic pricing logic
- [Prediction Service](./services/prediction-service.md) - ML price prediction
- [Capacity Planning](./operations/capacity-planning.md) - Infrastructure sizing

## Key Design Decisions

1. **Progressive Results via SSE**: Return first results within 500ms while continuing to aggregate
2. **Dynamic TTL Caching**: Cache duration based on departure proximity (2-30 min)
3. **Circuit Breaker per Supplier**: Isolate slow/failing suppliers to protect system health
4. **Bounded Dynamic Pricing**: ML adjustments limited to -10% to +15% for fairness
5. **Optimistic Booking**: Real-time verification at payment time, not search time
