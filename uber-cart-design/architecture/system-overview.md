# Uber Cart System - High-Level Architecture

## Overview

The Uber Cart Management System is a unified platform that manages shopping carts and order lifecycle across Uber's full ecosystem: Uber Eats, Uber Grocery, Uber Rides, and Package Delivery. This document outlines the high-level architecture, service boundaries, and communication patterns.

## System Context

```mermaid
flowchart TB
    subgraph users [Users]
        PrimaryUser[Primary User]
        SubUser[Sub-User/Teen]
    end

    subgraph uber [Uber Cart System]
        CartSystem[Cart Management System]
    end

    subgraph external [External Systems]
        Merchants[Merchants/Restaurants]
        Drivers[Driver Network]
        Partners[3rd Party Partners]
        PaymentGateway[Payment Providers]
    end

    PrimaryUser -->|CRUD Operations| CartSystem
    SubUser -->|Read-Only Access| CartSystem
    CartSystem <-->|Menu/Inventory| Merchants
    CartSystem <-->|Fulfillment| Drivers
    CartSystem <-->|Partner Orders| Partners
    CartSystem <-->|Transactions| PaymentGateway
```

## Core Architectural Principles

### 1. Domain-Driven Design
- Clear bounded contexts for Cart, Order, User, and Fulfillment domains
- Each domain owns its data and exposes well-defined APIs
- Domain events for cross-service communication

### 2. Microservices Architecture
- Independently deployable services
- Service-specific databases (Database per Service pattern)
- API Gateway for unified client access

### 3. Event-Driven Communication
- Asynchronous processing for non-critical paths
- Event sourcing for order state changes
- Eventual consistency where appropriate

### 4. Offline-First Design
- Client-side state management with local persistence
- Conflict resolution strategies for cart merges
- Background synchronization queues

## Service Architecture

```mermaid
flowchart TB
    subgraph clientLayer [Client Layer]
        MobileApp[Mobile Apps<br/>iOS/Android]
        WebApp[Web Application]
    end

    subgraph gatewayLayer [Gateway Layer]
        APIGateway[API Gateway]
        AuthService[Auth Service]
        RateLimiter[Rate Limiter]
    end

    subgraph coreServices [Core Domain Services]
        CartService[Cart Service]
        OrderService[Order Service]
        UserService[User Service]
        CatalogService[Catalog Service]
    end

    subgraph fulfillmentServices [Fulfillment Services]
        FulfillmentOrchestrator[Fulfillment Orchestrator]
        DeliveryService[Delivery Service]
        RideService[Ride Service]
        PickupService[Pickup Service]
    end

    subgraph integrationServices [Integration Layer]
        PartnerGateway[Partner Gateway]
        MerchantService[Merchant Service]
        NotificationService[Notification Service]
    end

    subgraph dataLayer [Data Layer]
        CartDB[(Cart Store)]
        OrderDB[(Order Store)]
        UserDB[(User Store)]
        CacheCluster[(Redis Cluster)]
        SearchIndex[(Elasticsearch)]
    end

    subgraph messagingLayer [Messaging Layer]
        EventBus[Event Bus<br/>Kafka]
        TaskQueue[Task Queue<br/>SQS/RabbitMQ]
    end

    MobileApp --> APIGateway
    WebApp --> APIGateway
    APIGateway --> AuthService
    APIGateway --> RateLimiter
    APIGateway --> CartService
    APIGateway --> OrderService
    APIGateway --> UserService

    CartService --> CartDB
    CartService --> CacheCluster
    OrderService --> OrderDB
    OrderService --> EventBus
    UserService --> UserDB

    OrderService --> FulfillmentOrchestrator
    FulfillmentOrchestrator --> DeliveryService
    FulfillmentOrchestrator --> RideService
    FulfillmentOrchestrator --> PickupService

    FulfillmentOrchestrator --> PartnerGateway
    OrderService --> NotificationService

    CartService --> CatalogService
    CatalogService --> MerchantService
    CatalogService --> SearchIndex

    NotificationService --> TaskQueue
```

## Service Boundaries

### Cart Service
**Responsibility**: Manages active shopping carts, cart items, and cart lifecycle

| Capability | Description |
|------------|-------------|
| Cart CRUD | Create, read, update, delete carts |
| Item Management | Add, update, remove items from cart |
| Multi-Merchant | Support items from multiple merchants in one cart |
| Price Calculation | Real-time pricing with promotions |
| Cart Validation | Validate items, quantities, availability |
| Cart Expiration | TTL-based cart cleanup |

**Data Owned**: Cart, CartItem, CartMetadata

---

### Order Service
**Responsibility**: Manages order lifecycle from checkout to completion

| Capability | Description |
|------------|-------------|
| Order Creation | Convert cart to order(s) |
| Status Management | Track and update order status |
| Order Modifications | Handle cancel, modify requests |
| Order History | Query historical orders |
| Sub-User Access | Manage order visibility for sub-users |

**Data Owned**: Order, OrderItem, OrderStatusHistory

---

### User Service
**Responsibility**: User identity, relationships, and preferences

| Capability | Description |
|------------|-------------|
| User Management | User profiles and authentication |
| Sub-User Management | Parent-child relationships (teens) |
| Permissions | Role-based access control |
| Preferences | Delivery addresses, payment methods |

**Data Owned**: User, SubUser, UserPreferences, UserAddress

---

### Fulfillment Orchestrator
**Responsibility**: Coordinates order fulfillment across different fulfillment types

| Capability | Description |
|------------|-------------|
| Fulfillment Routing | Route to appropriate fulfillment service |
| Status Aggregation | Aggregate status from multiple services |
| SLA Management | Track fulfillment SLAs |
| Retry Handling | Handle fulfillment failures |

**Data Owned**: Fulfillment, FulfillmentStatus

---

### Partner Gateway
**Responsibility**: Integration with third-party partners

| Capability | Description |
|------------|-------------|
| Partner Adapters | Normalize partner APIs |
| Capability Registry | Track partner capabilities |
| Operation Filtering | Restrict operations per partner |
| Webhook Management | Handle partner callbacks |

**Data Owned**: PartnerConfig, PartnerOrder, PartnerCapability

## Communication Patterns

### Synchronous Communication (REST/gRPC)

```mermaid
sequenceDiagram
    participant Client
    participant Gateway as API Gateway
    participant Cart as Cart Service
    participant Catalog as Catalog Service
    participant Cache as Redis Cache

    Client->>Gateway: POST /cart/items
    Gateway->>Gateway: Authenticate & Rate Limit
    Gateway->>Cart: addItem(cartId, item)
    Cart->>Cache: Get cached item details
    alt Cache Miss
        Cart->>Catalog: getItemDetails(itemId)
        Catalog-->>Cart: ItemDetails
        Cart->>Cache: Cache item details
    end
    Cart->>Cart: Validate & Calculate Price
    Cart-->>Gateway: CartItem
    Gateway-->>Client: 201 Created
```

**When to Use Synchronous:**
- User-facing read operations (get cart, get order)
- Operations requiring immediate confirmation (add to cart)
- Real-time validations (price checks, availability)

### Asynchronous Communication (Events)

```mermaid
sequenceDiagram
    participant Order as Order Service
    participant EventBus as Kafka
    participant Fulfillment as Fulfillment Service
    participant Notification as Notification Service
    participant Analytics as Analytics Service

    Order->>EventBus: Publish OrderCreated

    par Fulfillment Processing
        EventBus->>Fulfillment: OrderCreated
        Fulfillment->>Fulfillment: Initiate Fulfillment
    and Notification
        EventBus->>Notification: OrderCreated
        Notification->>Notification: Send Confirmation
    and Analytics
        EventBus->>Analytics: OrderCreated
        Analytics->>Analytics: Record Metrics
    end
```

**When to Use Asynchronous:**
- Order status updates
- Notification dispatch
- Analytics and reporting
- Cross-service data sync

### Event Types

| Event | Publisher | Subscribers | Purpose |
|-------|-----------|-------------|---------|
| `CartUpdated` | Cart Service | Analytics | Track cart changes |
| `OrderCreated` | Order Service | Fulfillment, Notification, Analytics | Initiate order processing |
| `OrderStatusChanged` | Order Service | Notification, Client (WebSocket) | Status updates |
| `FulfillmentUpdated` | Fulfillment Service | Order Service, Notification | Fulfillment progress |
| `PaymentProcessed` | Payment Service | Order Service | Payment confirmation |

## Data Flow Patterns

### Cart to Order Conversion

```mermaid
stateDiagram-v2
    [*] --> CartEmpty: Create Cart
    CartEmpty --> CartActive: Add Item
    CartActive --> CartActive: Add/Update/Remove Items
    CartActive --> CartValidating: Checkout Initiated
    CartValidating --> CartActive: Validation Failed
    CartValidating --> CartLocked: Validation Passed
    CartLocked --> OrderCreated: Payment Confirmed
    CartLocked --> CartActive: Payment Failed
    OrderCreated --> [*]: Cart Archived
```

### Order State Machine

```mermaid
stateDiagram-v2
    [*] --> Pending: Order Created
    Pending --> Confirmed: Payment Confirmed
    Pending --> Cancelled: Payment Failed / User Cancel
    Confirmed --> Preparing: Merchant Accepted
    Confirmed --> Cancelled: Merchant Rejected
    Preparing --> ReadyForPickup: Preparation Complete
    ReadyForPickup --> InTransit: Driver Picked Up
    ReadyForPickup --> PickedUp: Customer Picked Up
    InTransit --> Delivered: Delivery Complete
    PickedUp --> [*]
    Delivered --> [*]
    Cancelled --> [*]

    Confirmed --> ModificationRequested: User Request
    ModificationRequested --> Confirmed: Modification Applied
    ModificationRequested --> Confirmed: Modification Rejected
```

## Scalability Considerations

### Horizontal Scaling
- All services are stateless and horizontally scalable
- Cart Service scales based on active users
- Order Service scales based on order volume
- Fulfillment services scale based on geographic demand

### Caching Strategy
| Data Type | Cache TTL | Invalidation Strategy |
|-----------|-----------|----------------------|
| Cart Data | 30 min | Write-through |
| Menu Items | 5 min | Event-based |
| User Preferences | 1 hour | Write-through |
| Order Status | No cache | Real-time updates |

### Database Sharding
- Cart DB: Shard by user_id
- Order DB: Shard by region + time-based partitioning
- User DB: Shard by user_id

## Failure Handling

### Circuit Breaker Pattern
```
┌─────────────────────────────────────────────────────────┐
│                    Circuit Breaker                       │
├─────────────────────────────────────────────────────────┤
│  State: CLOSED → OPEN → HALF_OPEN → CLOSED              │
│                                                          │
│  Thresholds:                                             │
│  - Failure Rate: 50% over 10 requests                    │
│  - Open Duration: 30 seconds                             │
│  - Half-Open Requests: 3                                 │
└─────────────────────────────────────────────────────────┘
```

### Retry Strategy
| Operation | Max Retries | Backoff | Circuit Breaker |
|-----------|-------------|---------|-----------------|
| Cart Read | 3 | Exponential | Yes |
| Cart Write | 2 | Linear | Yes |
| Order Create | 0 | N/A | No (Idempotent) |
| Fulfillment Update | 5 | Exponential | Yes |

### Fallback Strategies
- **Cart Service Down**: Serve from local cache, queue writes
- **Catalog Service Down**: Serve stale menu data with warning
- **Fulfillment Service Down**: Queue orders, notify user of delay
- **Payment Service Down**: Hold order, retry with exponential backoff

## Security Architecture

### Authentication & Authorization
```mermaid
flowchart LR
    Client -->|JWT Token| Gateway[API Gateway]
    Gateway -->|Validate| AuthService[Auth Service]
    AuthService -->|User Context| Gateway
    Gateway -->|User Context| Service[Backend Service]
    Service -->|Check Permissions| RBAC[RBAC Engine]
```

### Data Protection
- **In Transit**: TLS 1.3 for all communications
- **At Rest**: AES-256 encryption for sensitive data
- **PII Handling**: Data masking, audit logging
- **Token Management**: Short-lived JWTs, refresh token rotation

## Monitoring & Observability

### Key Metrics
| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Cart Add Latency (p99) | < 100ms | > 200ms |
| Order Create Latency (p99) | < 500ms | > 1s |
| Cart Service Availability | 99.99% | < 99.9% |
| Order Service Availability | 99.99% | < 99.9% |
| Cart Conversion Rate | Baseline | -10% |

### Distributed Tracing
- Trace ID propagation across all services
- Span collection for critical paths
- Integration with Jaeger/Zipkin

### Logging Strategy
- Structured JSON logging
- Correlation IDs for request tracking
- Log levels: DEBUG (dev), INFO (prod), ERROR (alerts)

