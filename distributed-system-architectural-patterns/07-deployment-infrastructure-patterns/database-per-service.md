# Database Per Service Pattern

## Overview

**Database Per Service** is a microservices pattern where each service owns and manages its private database. Other services cannot access it directly; they must use the service's API. This ensures loose coupling, independent deployability, and allows each service to choose the best database for its needs.

```mermaid
flowchart TB
    subgraph Shared[Anti-Pattern: Shared Database]
        S1[Service A] --> SharedDB[(Shared DB)]
        S2[Service B] --> SharedDB
        S3[Service C] --> SharedDB
    end

    subgraph Separate[Database Per Service]
        A[Order Service] --> DBA[(Orders DB<br/>PostgreSQL)]
        B[Product Service] --> DBB[(Products DB<br/>MongoDB)]
        C[Analytics Service] --> DBC[(Analytics DB<br/>ClickHouse)]
    end
```

---

## Why Use It

### Problems It Solves

1. **Tight coupling**: Shared database creates dependencies
2. **Schema changes**: One change affects all services
3. **Technology lock-in**: All services use same database
4. **Scaling limitations**: Can't scale databases independently
5. **Team autonomy**: Database changes require coordination

### Key Benefits

- **Loose coupling** - Services are independent
- **Technology freedom** - Choose best database per service
- **Independent scaling** - Scale databases as needed
- **Team autonomy** - Own your data, own your schema
- **Fault isolation** - Database failure is contained

---

## When to Use

| Use Case | Why It Works Well |
|----------|------------------|
| Microservices architecture | Core principle of microservices |
| Polyglot persistence | Different data needs per service |
| Team autonomy | Independent development |
| Different scaling needs | Scale hot services independently |
| Compliance requirements | Data isolation for security |

---

## When NOT to Use

| Scenario | Alternative |
|----------|-------------|
| Monolith | Shared database is fine |
| Strong consistency required | Shared database or distributed transactions |
| Small team | Added complexity not justified |
| Tight integration needed | Consider service boundaries |

---

## How It Works

### Architecture

```mermaid
flowchart TB
    subgraph OrderContext[Order Bounded Context]
        OrderAPI[Order API]
        OrderService[Order Service]
        OrderDB[(Orders DB)]
    end

    subgraph ProductContext[Product Bounded Context]
        ProductAPI[Product API]
        ProductService[Product Service]
        ProductDB[(Products DB)]
    end

    subgraph UserContext[User Bounded Context]
        UserAPI[User API]
        UserService[User Service]
        UserDB[(Users DB)]
    end

    OrderService --> OrderDB
    ProductService --> ProductDB
    UserService --> UserDB

    OrderService -->|API Call| ProductAPI
    OrderService -->|API Call| UserAPI
```

### Data Access Rules

```mermaid
flowchart LR
    subgraph Allowed[Allowed Access]
        ServiceA[Service A] -->|API| ServiceB[Service B]
        ServiceB --> DBB[(DB B)]
    end

    subgraph Forbidden[Forbidden Access]
        ServiceX[Service X] -.->|Direct DB Access| DBY[(DB Y)]
    end
```

---

## Pros and Cons

### Pros

| Advantage | Description |
|-----------|-------------|
| **Loose coupling** | No direct database dependencies |
| **Technology freedom** | Use best database for the job |
| **Independent scaling** | Scale databases per service needs |
| **Team autonomy** | Full ownership of data |
| **Fault isolation** | Database failure contained |

### Cons

| Disadvantage | Mitigation |
|--------------|------------|
| **Data duplication** | Accept some duplication, sync via events |
| **Distributed transactions** | Saga pattern |
| **Join complexity** | API composition, denormalization |
| **Consistency** | Eventual consistency, events |
| **Operational overhead** | DevOps automation |

---

## Data Sharing Strategies

### 1. API Composition

Query multiple services and compose result.

```python
class OrderDetailService:
    def __init__(self, order_client, product_client, user_client):
        self.order_client = order_client
        self.product_client = product_client
        self.user_client = user_client

    async def get_order_details(self, order_id: str) -> dict:
        # Get order from Order Service
        order = await self.order_client.get_order(order_id)

        # Get user from User Service
        user = await self.user_client.get_user(order['user_id'])

        # Get products from Product Service
        products = await asyncio.gather(*[
            self.product_client.get_product(item['product_id'])
            for item in order['items']
        ])

        return {
            'order': order,
            'user': {'id': user['id'], 'name': user['name']},
            'products': products
        }
```

### 2. Data Replication via Events

Subscribe to events and maintain local copy.

```python
class ProductCatalogProjection:
    """Order service maintains read-only product data."""

    def __init__(self, db, event_bus):
        self.db = db
        event_bus.subscribe('product.created', self.on_product_created)
        event_bus.subscribe('product.updated', self.on_product_updated)

    async def on_product_created(self, event):
        await self.db.execute("""
            INSERT INTO product_catalog (id, name, price, image_url)
            VALUES (?, ?, ?, ?)
        """, event.product_id, event.name, event.price, event.image_url)

    async def on_product_updated(self, event):
        await self.db.execute("""
            UPDATE product_catalog
            SET name = ?, price = ?, image_url = ?
            WHERE id = ?
        """, event.name, event.price, event.image_url, event.product_id)
```

### 3. Shared Kernel (Limited Sharing)

Share small, stable subset of data.

```mermaid
flowchart TB
    subgraph SharedKernel[Shared Kernel - Read Only]
        Countries[(Countries)]
        Currencies[(Currencies)]
    end

    subgraph Services
        Order[Order Service]
        Payment[Payment Service]
        Shipping[Shipping Service]
    end

    Order -->|Read| SharedKernel
    Payment -->|Read| SharedKernel
    Shipping -->|Read| SharedKernel
```

---

## Implementation Example

### Service with Private Database

```python
# Order Service with its own database
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class OrderService:
    def __init__(self):
        # Private database - only this service can access
        self.engine = create_engine(
            'postgresql://orders_user:secret@orders-db:5432/orders'
        )
        self.Session = sessionmaker(bind=self.engine)

    def create_order(self, user_id: str, items: list) -> Order:
        session = self.Session()
        try:
            order = Order(user_id=user_id, items=items)
            session.add(order)
            session.commit()

            # Publish event for other services
            self.event_bus.publish('order.created', {
                'order_id': order.id,
                'user_id': user_id,
                'items': items
            })

            return order
        finally:
            session.close()

# Product Service with different database technology
class ProductService:
    def __init__(self):
        # Uses MongoDB - best fit for product catalog
        self.db = MongoClient('mongodb://products-db:27017')['products']

    def get_product(self, product_id: str) -> dict:
        return self.db.products.find_one({'_id': product_id})

    def search_products(self, query: str) -> list:
        return list(self.db.products.find({
            '$text': {'$search': query}
        }))

# Analytics Service with columnar database
class AnalyticsService:
    def __init__(self):
        # Uses ClickHouse - optimized for analytics
        self.client = clickhouse_connect.get_client(
            host='analytics-db', port=8123
        )

    def get_sales_by_day(self, start_date, end_date):
        return self.client.query("""
            SELECT
                toDate(created_at) as date,
                sum(total) as revenue,
                count(*) as orders
            FROM orders
            WHERE created_at BETWEEN %(start)s AND %(end)s
            GROUP BY date
            ORDER BY date
        """, parameters={'start': start_date, 'end': end_date})
```

### Database Technology Choices

```yaml
# docker-compose.yml
services:
  orders-db:
    image: postgres:15
    environment:
      POSTGRES_DB: orders
    # Strong consistency, ACID transactions

  products-db:
    image: mongo:6
    # Flexible schema, rich queries

  users-db:
    image: postgres:15
    environment:
      POSTGRES_DB: users
    # Relational data, strong consistency

  sessions-db:
    image: redis:7
    # Fast key-value, TTL support

  analytics-db:
    image: clickhouse/clickhouse-server
    # Columnar storage, fast aggregations

  search-db:
    image: elasticsearch:8
    # Full-text search, faceting
```

---

## Handling Cross-Service Queries

### Problem: "Get order with customer and product details"

```mermaid
flowchart LR
    Query[Query: Order Details] --> Aggregator[API Aggregator]
    Aggregator --> OrderSvc[Order Service]
    Aggregator --> UserSvc[User Service]
    Aggregator --> ProductSvc[Product Service]
```

### Solution: BFF or Aggregator

```python
# Backend for Frontend aggregating data
class OrderDetailsBFF:
    async def get_order_details(self, order_id: str):
        # Parallel fetch from multiple services
        order, user, products = await asyncio.gather(
            self.order_client.get(order_id),
            self.get_user_for_order(order_id),
            self.get_products_for_order(order_id)
        )

        return {
            **order,
            'customer': user,
            'product_details': products
        }
```

---

## Real-World Examples

| Company | Implementation |
|---------|----------------|
| **Netflix** | Each microservice owns its data |
| **Amazon** | Hundreds of databases, one per service |
| **Uber** | Polyglot persistence per domain |
| **Spotify** | Domain-driven database ownership |

---

## Related Patterns

- [Saga](../04-data-patterns/saga-pattern.md) - Distributed transactions
- [CQRS](../04-data-patterns/cqrs.md) - Read/write separation
- [Event Sourcing](../04-data-patterns/event-sourcing.md) - Event-based sync
- [Outbox](../04-data-patterns/outbox-pattern.md) - Reliable event publishing
- [Strangler Fig](./strangler-fig-pattern.md) - Migration strategy

---

## Further Reading

- [Database per Service - microservices.io](https://microservices.io/patterns/data/database-per-service.html)
- [Building Microservices - Sam Newman](https://samnewman.io/books/building-microservices-2nd/)
- [Polyglot Persistence](https://martinfowler.com/bliki/PolyglotPersistence.html)
