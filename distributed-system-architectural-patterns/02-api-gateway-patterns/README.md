# API Gateway Patterns

This section covers patterns for managing how external clients access your microservices ecosystem. These patterns provide a unified entry point, aggregate responses, and handle cross-cutting concerns like authentication and rate limiting.

## Overview

```mermaid
flowchart TB
    subgraph Clients[External Clients]
        Web[Web App]
        Mobile[Mobile App]
        IoT[IoT Devices]
        ThirdParty[Third Party]
    end

    subgraph Gateway[Gateway Layer]
        AG[API Gateway]
        BFF1[Web BFF]
        BFF2[Mobile BFF]
        Aggregator[Aggregator]
    end

    subgraph Services[Backend Services]
        UserSvc[User Service]
        OrderSvc[Order Service]
        ProductSvc[Product Service]
        PaymentSvc[Payment Service]
    end

    Web --> AG
    Mobile --> AG
    IoT --> AG
    ThirdParty --> AG

    AG --> BFF1
    AG --> BFF2
    AG --> Aggregator

    BFF1 --> Services
    BFF2 --> Services
    Aggregator --> Services
```

## Patterns in This Category

| Pattern | Document | Best For |
|---------|----------|----------|
| API Gateway | [api-gateway.md](./api-gateway.md) | Centralized entry point, cross-cutting concerns |
| Backend for Frontend | [backend-for-frontend.md](./backend-for-frontend.md) | Multi-platform clients with different needs |
| Aggregator Pattern | [aggregator-pattern.md](./aggregator-pattern.md) | Composing responses from multiple services |

## Comparison Matrix

| Aspect | API Gateway | Backend for Frontend | Aggregator |
|--------|-------------|---------------------|------------|
| **Primary Purpose** | Single entry point | Client-specific optimization | Response composition |
| **Number of Endpoints** | One per service | One per client type | One per aggregate |
| **Ownership** | Platform/Infra team | Frontend teams | Backend teams |
| **Complexity** | Medium | High (multiple BFFs) | Medium |
| **Client Coupling** | Loose | Tight (per client) | Loose |
| **Use Case** | Cross-cutting concerns | Mobile/Web optimization | Dashboard APIs |

## Pattern Selection Guide

```mermaid
flowchart TD
    Start[What's your primary need?] --> Q1{Need single entry point?}

    Q1 -->|Yes| Q2{Need client-specific APIs?}
    Q1 -->|No| Aggregator[Use Aggregator]

    Q2 -->|Yes| BFF[Use BFF + Gateway]
    Q2 -->|No| Gateway[Use API Gateway]

    Gateway --> Q3{Need response composition?}
    Q3 -->|Yes| GatewayAgg[Gateway + Aggregator]
    Q3 -->|No| GatewayOnly[Gateway Only]
```

## Decision Framework

### Choose API Gateway when:
- You need a single entry point for all clients
- Cross-cutting concerns (auth, rate limiting, logging) are important
- You want to decouple clients from service topology
- Service discovery and load balancing are needed

### Choose Backend for Frontend when:
- You have multiple client types (web, mobile, IoT)
- Each client has significantly different data/performance needs
- Frontend teams want autonomy over their APIs
- Mobile needs optimized payloads for bandwidth

### Choose Aggregator when:
- Single requests need data from multiple services
- You want to reduce client round trips
- Building dashboard or composite views
- Need to join data at the API layer

## Combined Patterns

Most production systems combine these patterns:

```mermaid
flowchart TB
    subgraph External[External Traffic]
        Web[Web]
        Mobile[Mobile]
        Partner[Partner API]
    end

    subgraph Gateway[API Gateway Layer]
        Kong[Kong / Ambassador]
    end

    subgraph BFFs[BFF Layer]
        WebBFF[Web BFF]
        MobileBFF[Mobile BFF]
    end

    subgraph Aggregators[Aggregator Layer]
        Dashboard[Dashboard Aggregator]
        Checkout[Checkout Aggregator]
    end

    subgraph Backend[Backend Services]
        User[User]
        Product[Product]
        Order[Order]
        Payment[Payment]
    end

    External --> Gateway
    Gateway --> BFFs
    Gateway --> Partner
    BFFs --> Aggregators
    Aggregators --> Backend
    Partner --> Backend
```

**Common Combinations:**

| Pattern Combination | Use Case |
|---------------------|----------|
| Gateway + BFF | Consumer apps with web and mobile |
| Gateway + Aggregator | Complex dashboard applications |
| Gateway + BFF + Aggregator | Enterprise platforms |

## Cross-Cutting Concerns

All gateway patterns typically handle:

| Concern | Description |
|---------|-------------|
| **Authentication** | Validate tokens, API keys |
| **Authorization** | Check permissions, scopes |
| **Rate Limiting** | Protect backend services |
| **Request Logging** | Audit trail, debugging |
| **Request/Response Transform** | Protocol translation |
| **Caching** | Response caching |
| **Circuit Breaking** | Fail-fast on unhealthy services |
| **Load Balancing** | Distribute traffic |

## Related Patterns

- [REST API](../01-api-communication-styles/rest-api.md) - Common protocol behind gateways
- [gRPC](../01-api-communication-styles/grpc.md) - Backend protocol translation
- [Circuit Breaker](../03-resilience-patterns/circuit-breaker.md) - Resilience at gateway
- [Rate Limiting](../03-resilience-patterns/rate-limiting.md) - Traffic control
- [Service Discovery](../06-service-discovery-mesh/service-registry.md) - Finding backend services
