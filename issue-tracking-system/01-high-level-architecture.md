# High-Level Architecture

[← Back to README](./README.md)

## System Architecture Diagram

```mermaid
flowchart TB
    subgraph Clients ["Clients"]
        Web[Web App]
        Mobile[Mobile App]
        API[Public API]
    end

    subgraph Gateway ["API Gateway Layer"]
        LB[Load Balancer]
        Auth[Auth Service]
        RateLimit[Rate Limiter]
        TenantRouter[Tenant Router]
    end

    subgraph CoreServices ["Core Services"]
        ProjectSvc[Project Service]
        IssueSvc[Issue Service]
        CommentSvc[Comment Service]
        WorkflowSvc[Workflow Service]
        AssignmentSvc[Assignment Service]
    end

    subgraph AsyncPipeline ["Async Pipeline"]
        Kafka[Kafka Cluster]
        SearchIndexer[Search Indexer]
        AuditWriter[Audit Writer]
        NotificationSvc[Notification Service]
    end

    subgraph SearchLayer ["Search Layer"]
        ES[Elasticsearch Cluster]
        SearchCache[Search Cache]
    end

    subgraph Storage ["Storage Layer"]
        PrimaryDB[(PostgreSQL Clusters)]
        CacheLayer[(Redis Cluster)]
        ObjectStore[(S3/GCS)]
    end

    subgraph Observability ["Monitoring"]
        Metrics[Prometheus]
        Logs[ELK Stack]
        Traces[Jaeger]
        Alerts[PagerDuty]
    end

    Clients --> LB --> Auth --> RateLimit --> TenantRouter
    TenantRouter --> CoreServices
    CoreServices --> Kafka
    CoreServices --> PrimaryDB
    CoreServices --> CacheLayer
    Kafka --> SearchIndexer --> ES
    Kafka --> AuditWriter --> ObjectStore
    Kafka --> NotificationSvc
    CoreServices --> Observability
```

## Component Overview

| Layer | Components | Purpose |
|-------|------------|---------|
| **Clients** | Web, Mobile, Public API | User interfaces and integrations |
| **API Gateway** | Load Balancer, Auth, Rate Limiter, Tenant Router | Request routing, authentication, throttling |
| **Core Services** | Project, Issue, Comment, Workflow, Assignment | Business logic and data operations |
| **Async Pipeline** | Kafka, Indexer, Audit Writer, Notifications | Event processing and async operations |
| **Search Layer** | Elasticsearch, Search Cache | Full-text search and caching |
| **Storage** | PostgreSQL, Redis, S3/GCS | Persistent storage and caching |
| **Observability** | Prometheus, ELK, Jaeger, PagerDuty | Monitoring, logging, tracing, alerting |

## Request Flow

### Write Request (Create Issue)

```mermaid
sequenceDiagram
    participant C as Client
    participant LB as Load Balancer
    participant GW as API Gateway
    participant IS as Issue Service
    participant DB as PostgreSQL
    participant Cache as Redis
    participant Kafka as Kafka

    C->>LB: POST /api/v1/issues
    LB->>GW: Forward request
    GW->>GW: Authenticate (JWT validation)
    GW->>GW: Rate limit check
    GW->>GW: Extract tenant context
    GW->>IS: CreateIssue(tenant_id, payload)

    IS->>DB: BEGIN TRANSACTION
    IS->>DB: INSERT issue
    IS->>DB: INSERT audit_log
    IS->>DB: UPDATE project.issue_counter
    IS->>DB: COMMIT

    IS->>Cache: INVALIDATE issue_list:tenant_id:project_id
    IS->>Kafka: Publish IssueCreated event
    IS-->>GW: 201 Created
    GW-->>C: Response with issue data
```

### Read Request (Get Issue)

```mermaid
sequenceDiagram
    participant C as Client
    participant GW as API Gateway
    participant IS as Issue Service
    participant Cache as Redis
    participant DB as PostgreSQL

    C->>GW: GET /api/v1/issues/{id}
    GW->>GW: Auth + Rate Limit + Tenant Context
    GW->>IS: GetIssue(tenant_id, issue_id)

    IS->>Cache: GET issue:{tenant_id}:{issue_id}

    alt Cache Hit
        Cache-->>IS: Cached issue data
        Note over IS: Response in < 50ms
    else Cache Miss
        IS->>DB: SELECT with RLS
        DB-->>IS: Issue row
        IS->>Cache: SET with 5min TTL
        Note over IS: Response in < 150ms
    end

    IS-->>GW: Issue data
    GW-->>C: 200 OK
```

## API Gateway Responsibilities

### 1. Load Balancing

- Round-robin distribution across service instances
- Health check-based routing
- Connection draining for graceful shutdowns

### 2. Authentication

```mermaid
flowchart LR
    Request --> JWTValidator
    JWTValidator --> |Valid| ExtractClaims
    JWTValidator --> |Invalid| Reject401
    ExtractClaims --> |Has tenant_id| Continue
    ExtractClaims --> |Missing tenant_id| Reject403
```

Supported auth methods:
- **Bearer Token (JWT)**: Primary method for API access
- **API Key**: For service-to-service and integrations
- **OAuth2**: For third-party app authorization

### 3. Rate Limiting

| Tier | Requests/min | Burst | Scope |
|------|--------------|-------|-------|
| Free | 100 | 20 | Per user |
| Standard | 1,000 | 100 | Per user |
| Enterprise | 10,000 | 1,000 | Per tenant |

Rate limiting implemented via Redis with sliding window algorithm:

```lua
-- Redis Lua script for sliding window rate limiting
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)

if count < limit then
    redis.call('ZADD', key, now, now .. ':' .. math.random())
    redis.call('EXPIRE', key, window / 1000)
    return 1
else
    return 0
end
```

### 4. Tenant Routing

See [Multi-Tenancy Strategy](./02-multi-tenancy-strategy.md) for detailed tenant routing logic.

## Infrastructure Diagram

```mermaid
flowchart TB
    subgraph EdgeLayer ["Edge Layer"]
        CDN[CDN / CloudFront]
        WAF[WAF]
    end

    subgraph K8sCluster ["Kubernetes Cluster"]
        subgraph Ingress ["Ingress"]
            LB[Load Balancer]
            Kong[Kong API Gateway]
        end

        subgraph Services ["Services"]
            ProjectSvc[Project Service]
            IssueSvc[Issue Service]
            CommentSvc[Comment Service]
            WorkflowSvc[Workflow Service]
            SearchSvc[Search Service]
        end

        subgraph Workers ["Background Workers"]
            SearchIndexer[Search Indexer]
            NotificationWorker[Notification Worker]
            AuditWorker[Audit Worker]
        end
    end

    subgraph DataLayer ["Data Layer"]
        PostgreSQL[(PostgreSQL Cluster)]
        Redis[(Redis Cluster)]
        Elasticsearch[(Elasticsearch)]
        Kafka[(Kafka Cluster)]
        S3[(S3 / Object Storage)]
    end

    subgraph Observability ["Observability"]
        Prometheus[Prometheus]
        Grafana[Grafana]
        Jaeger[Jaeger]
        ELK[ELK Stack]
    end

    CDN --> WAF --> LB --> Kong
    Kong --> Services
    Services --> DataLayer
    Workers --> DataLayer
    Services --> Kafka --> Workers
    Services --> Observability
    Workers --> Observability
```

## Service Communication

### Synchronous (gRPC/REST)

Used for:
- User-facing API requests
- Queries requiring immediate response
- Cross-service data lookups

```mermaid
flowchart LR
    IssueService --> |gRPC| ProjectService
    IssueService --> |gRPC| WorkflowService
    CommentService --> |gRPC| IssueService
    AssignmentService --> |gRPC| IssueService
```

### Asynchronous (Kafka Events)

Used for:
- Search index updates
- Audit logging
- Notifications
- Webhooks
- Analytics

```mermaid
flowchart TB
    IssueService --> |IssueCreated| Kafka
    IssueService --> |IssueUpdated| Kafka
    CommentService --> |CommentAdded| Kafka
    WorkflowService --> |TransitionExecuted| Kafka

    Kafka --> SearchIndexer
    Kafka --> NotificationService
    Kafka --> AuditService
    Kafka --> WebhookDispatcher
    Kafka --> AnalyticsSink
```

## Next

[Multi-Tenancy Strategy →](./02-multi-tenancy-strategy.md)
