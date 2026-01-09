# API Communication Styles

This section covers the fundamental patterns for how services communicate in distributed systems. The choice of communication style significantly impacts performance, developer experience, and system architecture.

## Overview

```mermaid
flowchart LR
    Client[Client] --> Decision{What do you need?}

    Decision -->|Simple CRUD, Caching| REST
    Decision -->|Flexible queries, Mobile| GraphQL
    Decision -->|High performance, Streaming| gRPC
    Decision -->|Real-time bidirectional| WebSockets

    REST --> Server1[REST Server]
    GraphQL --> Server2[GraphQL Server]
    gRPC --> Server3[gRPC Server]
    WebSockets --> Server4[WebSocket Server]
```

## Patterns in This Category

| Pattern | Document | Best For |
|---------|----------|----------|
| REST API | [rest-api.md](./rest-api.md) | Public APIs, CRUD operations, web applications |
| GraphQL | [graphql.md](./graphql.md) | Complex data requirements, mobile apps, flexible queries |
| gRPC | [grpc.md](./grpc.md) | Internal microservices, high-performance, streaming |
| WebSockets | [websockets.md](./websockets.md) | Real-time bidirectional communication |

## Comparison Matrix

| Aspect | REST | GraphQL | gRPC | WebSockets |
|--------|------|---------|------|------------|
| **Protocol** | HTTP/1.1, HTTP/2 | HTTP | HTTP/2 | TCP (upgraded from HTTP) |
| **Data Format** | JSON, XML | JSON | Protocol Buffers | Any (typically JSON) |
| **Type Safety** | Optional (OpenAPI) | Built-in schema | Built-in (protobuf) | None by default |
| **Caching** | Excellent (HTTP native) | Complex | Limited | Not applicable |
| **Real-time** | Polling/SSE | Subscriptions | Streaming | Native |
| **Browser Support** | Excellent | Excellent | Limited (grpc-web) | Excellent |
| **Learning Curve** | Low | Medium | Medium-High | Low |
| **Tooling** | Mature | Growing | Mature | Mature |

## Performance Characteristics

```mermaid
quadrantChart
    title Performance vs Flexibility Trade-offs
    x-axis Low Flexibility --> High Flexibility
    y-axis Low Performance --> High Performance
    quadrant-1 High perf, High flex
    quadrant-2 High perf, Low flex
    quadrant-3 Low perf, Low flex
    quadrant-4 Low perf, High flex
    gRPC: [0.3, 0.9]
    WebSockets: [0.5, 0.8]
    REST: [0.4, 0.5]
    GraphQL: [0.85, 0.6]
```

## Decision Guide

### Choose REST when:
- Building public-facing APIs
- CRUD operations dominate your use cases
- HTTP caching is important
- You need maximum interoperability
- Team is new to API development

### Choose GraphQL when:
- Clients have diverse data requirements
- Over-fetching/under-fetching is a problem
- Building for mobile with bandwidth constraints
- Rapid frontend iteration is needed
- You have a complex, interconnected data model

### Choose gRPC when:
- Building internal microservices
- Performance is critical
- You need bidirectional streaming
- Strong typing and code generation is valuable
- Polyglot environment (multiple languages)

### Choose WebSockets when:
- Real-time updates are essential
- Bidirectional communication is needed
- Low latency is critical
- Building chat, gaming, or collaborative apps
- Server needs to push data to clients

## Hybrid Approaches

Many production systems combine multiple styles:

```mermaid
flowchart TB
    subgraph External[External Clients]
        Web[Web App]
        Mobile[Mobile App]
    end

    subgraph Gateway[API Gateway]
        REST_GW[REST Endpoints]
        GraphQL_GW[GraphQL Endpoint]
        WS_GW[WebSocket Handler]
    end

    subgraph Internal[Internal Services]
        Service1[User Service]
        Service2[Order Service]
        Service3[Notification Service]
    end

    Web --> REST_GW
    Web --> WS_GW
    Mobile --> GraphQL_GW
    Mobile --> WS_GW

    REST_GW -->|gRPC| Service1
    REST_GW -->|gRPC| Service2
    GraphQL_GW -->|gRPC| Service1
    GraphQL_GW -->|gRPC| Service2
    WS_GW -->|gRPC| Service3
```

**Common Combinations:**
- **REST + WebSockets**: REST for CRUD, WebSockets for real-time updates
- **GraphQL + gRPC**: GraphQL for external, gRPC for internal
- **REST + gRPC**: REST for public API, gRPC between microservices

## Related Patterns

- [API Gateway](../02-api-gateway-patterns/api-gateway.md) - Unified entry point for all API styles
- [Backend for Frontend](../02-api-gateway-patterns/backend-for-frontend.md) - Optimize APIs per client type
- [Circuit Breaker](../03-resilience-patterns/circuit-breaker.md) - Handle communication failures
