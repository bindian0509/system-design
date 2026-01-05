# Uber Cart Management System - Design Overview

## Executive Summary

A comprehensive Cart Management System for Uber's full ecosystem (Eats, Grocery, Rides, Package Delivery) supporting multi-merchant carts, multiple fulfillment types, family accounts with sub-user access, third-party partner integrations, and offline-first behavior.

---

## System Context Diagram

```mermaid
flowchart TB
    subgraph users [Users]
        PrimaryUser[👤 Primary User]
        SubUser[👤 Sub-User/Teen]
    end

    subgraph uber [Uber Cart System]
        direction TB
        CartSystem[🛒 Cart Management System]
    end

    subgraph external [External Systems]
        Merchants[🏪 Merchants]
        Drivers[🚗 Driver Network]
        Partners[🤝 3rd Party Partners]
        Payments[💳 Payment Gateway]
        Rides[🚕 Uber Rides]
    end

    PrimaryUser -->|Full CRUD| CartSystem
    SubUser -->|Limited Access| CartSystem
    CartSystem <-->|Menu & Inventory| Merchants
    CartSystem <-->|Delivery/Pickup| Drivers
    CartSystem <-->|Partner Orders| Partners
    CartSystem <-->|Transactions| Payments
    CartSystem <-->|Pickup with Ride| Rides
```

---

## End-to-End Architecture

```mermaid
flowchart TB
    subgraph clientLayer [Client Layer]
        MobileApp[📱 Mobile Apps<br/>iOS / Android]
        WebApp[🌐 Web App]
    end

    subgraph gatewayLayer [Gateway Layer]
        CDN[☁️ CDN]
        LB[⚖️ Load Balancer]
        APIGateway[🚪 API Gateway]
        AuthService[🔐 Auth Service]
    end

    subgraph coreServices [Core Domain Services]
        CartService[🛒 Cart Service]
        OrderService[📦 Order Service]
        UserService[👤 User Service]
        CatalogService[📋 Catalog Service]
    end

    subgraph fulfillment [Fulfillment Domain]
        FulfillmentOrch[🎯 Fulfillment Orchestrator]
        DeliveryService[🚴 Delivery Service]
        PickupService[🏃 Pickup Service]
        RideService[🚕 Ride Service]
    end

    subgraph integration [Integration Layer]
        PartnerGateway[🔌 Partner Gateway]
        NotificationService[🔔 Notification Service]
        WebhookHandler[📨 Webhook Handler]
    end

    subgraph dataLayer [Data Layer]
        CartDB[(🗄️ Cart DB)]
        OrderDB[(🗄️ Order DB)]
        UserDB[(🗄️ User DB)]
        Redis[(⚡ Redis Cache)]
        Kafka[📬 Kafka]
        ES[(🔍 Elasticsearch)]
    end

    MobileApp --> CDN
    WebApp --> CDN
    CDN --> LB
    LB --> APIGateway
    APIGateway --> AuthService

    APIGateway --> CartService
    APIGateway --> OrderService
    APIGateway --> UserService

    CartService --> CartDB
    CartService --> Redis
    OrderService --> OrderDB
    OrderService --> ES
    UserService --> UserDB

    CartService --> Kafka
    OrderService --> Kafka
    Kafka --> FulfillmentOrch
    Kafka --> NotificationService

    FulfillmentOrch --> DeliveryService
    FulfillmentOrch --> PickupService
    FulfillmentOrch --> RideService
    FulfillmentOrch --> PartnerGateway

    PartnerGateway --> WebhookHandler
```

---

## Core User Flows

### 1. Cart to Order Flow

```mermaid
sequenceDiagram
    participant User
    participant App as Mobile App
    participant Cart as Cart Service
    participant Order as Order Service
    participant Fulfillment as Fulfillment Orchestrator
    participant Notification as Notification Service

    User->>App: Add items to cart
    App->>Cart: POST /carts/{id}/items
    Cart-->>App: Item added

    User->>App: Checkout
    App->>Cart: POST /carts/{id}/validate
    Cart-->>App: Validation result

    App->>Cart: POST /carts/{id}/checkout
    Cart->>Order: Create order
    Order->>Fulfillment: Initiate fulfillment
    Order-->>Cart: Order created
    Cart-->>App: Order confirmation

    Fulfillment->>Notification: Send confirmation
    Notification-->>User: Push notification
```

### 2. Order Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Pending: Order Placed
    Pending --> Confirmed: Payment OK
    Pending --> Cancelled: Payment Failed

    Confirmed --> Preparing: Merchant Accepts
    Confirmed --> Cancelled: Merchant Rejects

    Preparing --> Ready: Preparation Done

    Ready --> DriverAssigned: Delivery
    Ready --> PickedUp: Customer Pickup
    Ready --> RideBooked: Pickup with Ride

    DriverAssigned --> InTransit: Driver Has Order
    InTransit --> Delivered: At Destination

    RideBooked --> RideArrived: At Merchant
    RideArrived --> PickedUp: Customer Gets Order

    Delivered --> [*]
    PickedUp --> [*]
    Cancelled --> [*]
```

---

## Fulfillment Types

```mermaid
flowchart LR
    subgraph types [Fulfillment Types]
        Delivery[🚴 DELIVERY<br/>Driver delivers to you]
        Pickup[🏃 PICKUP<br/>You pick up]
        RidePickup[🚕 PICKUP_WITH_RIDE<br/>Ride booked for you]
    end

    subgraph delivery [Delivery Flow]
        D1[Driver Assigned] --> D2[At Merchant]
        D2 --> D3[In Transit]
        D3 --> D4[Delivered]
    end

    subgraph pickup [Pickup Flow]
        P1[Order Ready] --> P2[User Notified]
        P2 --> P3[User Picks Up]
    end

    subgraph ridePickup [Pickup with Ride Flow]
        R1[Order + Ride Booked] --> R2[Ride to Merchant]
        R2 --> R3[Pick Up Order]
        R3 --> R4[Optional: Ride Home]
    end

    Delivery -.-> delivery
    Pickup -.-> pickup
    RidePickup -.-> ridePickup
```

---

## Data Model Overview

```mermaid
erDiagram
    USER ||--o{ SUB_USER : manages
    USER ||--o{ CART : owns
    USER ||--o{ ORDER : places

    SUB_USER }o--o{ ORDER : can_view

    CART ||--o{ CART_ITEM : contains
    CART_ITEM }o--|| MERCHANT : from

    ORDER ||--o{ ORDER_ITEM : contains
    ORDER ||--|| FULFILLMENT : has
    ORDER }o--o| PARTNER : from

    FULFILLMENT ||--o| DELIVERY_DETAILS : type
    FULFILLMENT ||--o| PICKUP_DETAILS : type
    FULFILLMENT ||--o| RIDE_PICKUP_DETAILS : type

    USER {
        uuid id PK
        string email
        string phone
        enum status
    }

    SUB_USER {
        uuid id PK
        uuid parent_user_id FK
        enum permission_level
        json restrictions
    }

    CART {
        uuid id PK
        uuid user_id FK
        enum status
        enum fulfillment_type
        int version
    }

    ORDER {
        uuid id PK
        string order_number
        enum status
        enum fulfillment_type
        decimal total
    }

    FULFILLMENT {
        uuid id PK
        uuid order_id FK
        enum type
        enum status
        timestamp eta
    }
```

---

## Sub-User Access Model

```mermaid
flowchart TB
    subgraph permissions [Permission Levels]
        ViewOnly[👁️ VIEW_ONLY<br/>See parent orders only]
        Limited[🔒 LIMITED<br/>Order with restrictions]
        Supervised[👨‍👧 SUPERVISED<br/>Requires approval]
        Full[✅ FULL<br/>All capabilities]
    end

    subgraph restrictions [Restriction Types]
        Spending[💰 Spending Limits<br/>Daily/Weekly/Monthly]
        Merchants[🏪 Merchant Restrictions<br/>Allowlist/Blocklist]
        Time[⏰ Time Restrictions<br/>Ordering hours]
        Fulfillment[📦 Fulfillment<br/>Pickup only, etc.]
    end

    subgraph flow [Approval Flow]
        Request[Sub-user requests order]
        Pending[Order pending approval]
        Notify[Parent notified]
        Decision{Parent decision}
        Approved[Order placed]
        Rejected[Order rejected]
    end

    Limited --> restrictions
    Supervised --> flow
    Request --> Pending --> Notify --> Decision
    Decision -->|Approve| Approved
    Decision -->|Reject| Rejected
```

---

## Partner Integration Architecture

```mermaid
flowchart TB
    subgraph uber [Uber Platform]
        OrderService[Order Service]
        PartnerGateway[Partner Gateway]
        CapabilityRegistry[Capability Registry]
    end

    subgraph adapters [Partner Adapters]
        GroceryAdapter[🥬 Grocery Adapter]
        PharmacyAdapter[💊 Pharmacy Adapter]
        RetailAdapter[🛍️ Retail Adapter]
    end

    subgraph partners [External Partners]
        Grocery[Grocery API]
        Pharmacy[Pharmacy API]
        Retail[Retail API]
    end

    subgraph capabilities [Capabilities per Partner]
        Cap1[✅ CREATE_ORDER]
        Cap2[⚠️ MODIFY_ORDER<br/>15 min window]
        Cap3[⚠️ CANCEL_ORDER<br/>Before preparing]
        Cap4[✅ SUBSTITUTIONS]
        Cap5[❌ REAL_TIME_TRACKING]
    end

    OrderService --> PartnerGateway
    PartnerGateway --> CapabilityRegistry
    PartnerGateway --> adapters

    GroceryAdapter --> Grocery
    PharmacyAdapter --> Pharmacy
    RetailAdapter --> Retail

    CapabilityRegistry -.-> capabilities
```

---

## Offline Architecture

```mermaid
flowchart TB
    subgraph client [Client]
        UI[UI Layer]
        StateManager[State Manager]
        LocalDB[(SQLite/Realm)]
        SyncQueue[(Sync Queue)]
        NetworkMonitor[Network Monitor]
    end

    subgraph sync [Sync Engine]
        SyncManager[Sync Manager]
        ConflictResolver[Conflict Resolver]
    end

    subgraph server [Server]
        API[Backend API]
    end

    UI --> StateManager
    StateManager --> LocalDB
    StateManager --> SyncQueue

    NetworkMonitor --> SyncManager
    SyncQueue --> SyncManager
    SyncManager --> API
    API --> SyncManager
    SyncManager --> ConflictResolver
    ConflictResolver --> LocalDB

    subgraph strategies [Conflict Resolution]
        S1[Price Changed → Remote Wins]
        S2[Quantity Conflict → Merge Deltas]
        S3[Item Deleted → Prompt User]
    end
```

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| **Mobile** | React Native / Swift / Kotlin |
| **Web** | React + Redux Toolkit |
| **API Gateway** | Kong / AWS API Gateway |
| **Backend Services** | Go / Java (Spring Boot) |
| **Databases** | PostgreSQL (sharded) |
| **Cache** | Redis Cluster |
| **Message Queue** | Apache Kafka |
| **Search** | Elasticsearch |
| **Local Storage** | SQLite / Realm |
| **Container Orchestration** | Kubernetes |

---

## Key API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/carts/current` | GET | Get user's active cart |
| `/carts/{id}/items` | POST | Add item to cart |
| `/carts/{id}/checkout` | POST | Checkout cart → create order |
| `/orders` | GET | List user's orders |
| `/orders/{id}` | GET | Get order details |
| `/orders/{id}/cancel` | POST | Cancel order |
| `/orders/family/{subUserId}` | GET | Get sub-user's orders |
| `/approvals/pending` | GET | Get pending approvals (parent) |
| `/webhooks/partners/{id}` | POST | Receive partner webhooks |

---

## Scalability Considerations

```
┌─────────────────────────────────────────────────────────────────┐
│                      SCALING STRATEGY                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Cart Service                Order Service                       │
│  ┌─────────────┐            ┌─────────────┐                     │
│  │ Stateless   │            │ Stateless   │                     │
│  │ Horizontal  │            │ Horizontal  │                     │
│  │ Scale by    │            │ Scale by    │                     │
│  │ active users│            │ order volume│                     │
│  └─────────────┘            └─────────────┘                     │
│                                                                  │
│  Database Sharding                                               │
│  ┌─────────────────────────────────────────────┐                │
│  │ Cart DB: Shard by user_id                   │                │
│  │ Order DB: Shard by region + time partition  │                │
│  └─────────────────────────────────────────────┘                │
│                                                                  │
│  Caching                                                         │
│  ┌─────────────────────────────────────────────┐                │
│  │ Cart: Write-through, 30 min TTL             │                │
│  │ Menu: 5 min TTL, event invalidation         │                │
│  │ User: 1 hour TTL                            │                │
│  └─────────────────────────────────────────────┘                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Documentation Index

| Document | Path | Description |
|----------|------|-------------|
| **System Overview** | [architecture/system-overview.md](architecture/system-overview.md) | High-level architecture, service boundaries |
| **Client Architecture** | [architecture/client-architecture.md](architecture/client-architecture.md) | Mobile/web design, state management |
| **Server Architecture** | [architecture/server-architecture.md](architecture/server-architecture.md) | Backend services, databases, events |
| **Data Models** | [data-models/data-model-design.md](data-models/data-model-design.md) | Entity schemas, relationships |
| **API Contracts** | [api-design/api-contracts.md](api-design/api-contracts.md) | REST/GraphQL APIs, SDK |
| **Sub-User Access** | [features/sub-user-access.md](features/sub-user-access.md) | Family accounts, permissions |
| **Partner Integration** | [features/third-party-integration.md](features/third-party-integration.md) | 3rd party adapters |
| **Offline Behavior** | [features/offline-behavior.md](features/offline-behavior.md) | Sync, conflict resolution |

---

## Key Design Decisions

1. **Multi-Merchant Cart**: Single cart with items grouped by merchant, each group becomes a separate order at checkout

2. **Polymorphic Fulfillment**: Base `Fulfillment` entity with type-specific data (Delivery, Pickup, Pickup with Ride)

3. **Event-Driven Architecture**: Kafka for order events enabling loose coupling between services

4. **Capability-Based Partner Integration**: Partners declare capabilities; operations are validated against these at runtime

5. **Offline-First with Optimistic UI**: All cart operations work locally first, sync in background with automatic conflict resolution

6. **Hierarchical Permissions for Sub-Users**: Four permission levels (VIEW_ONLY → LIMITED → SUPERVISED → FULL) with configurable restrictions

