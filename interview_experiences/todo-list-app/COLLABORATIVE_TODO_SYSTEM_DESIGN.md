# Collaborative Todo List App - System Design

## Overview
A real-time collaborative todo list application supporting 500-1000 users with concurrent editing capabilities using CRDT for conflict resolution.

## Functional Requirements

### Core Features
1. **User Management**
   - User registration
   - User login/authentication

2. **List Management**
   - Create todo lists
   - Share lists with other users
   - View shared lists

3. **Collaborative Features**
   - Real-time parallel editing by multiple users
   - Simultaneous viewing of lists
   - Conflict-free concurrent updates using CRDT

4. **Task Management**
   - Advanced task properties: title, description, priority, due dates, assignees, tags, status

### Scale
- **Target Users**: 500-1000 customers
- **Concurrent Users**: ~100-200 active users at peak
- **Lists per User**: ~20-50 lists
- **Tasks per List**: ~50-100 tasks

---

## System Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web Browser]
        MOBILE[Mobile App]
    end

    subgraph "API Gateway Layer"
        LB[Load Balancer]
        APIGW[API Gateway]
    end

    subgraph "Application Layer"
        AUTH[Auth Service]
        TODO[Todo Service]
        WS[WebSocket Server]
        COLLAB[Collaboration Service<br/>CRDT Engine]
    end

    subgraph "Data Layer"
        CACHE[(Redis Cache)]
        DB[(PostgreSQL)]
        SEARCH[(ElasticSearch)]
    end

    subgraph "Supporting Services"
        QUEUE[Message Queue<br/>RabbitMQ/Redis]
        NOTIFY[Notification Service]
    end

    WEB --> LB
    MOBILE --> LB
    LB --> APIGW

    APIGW --> AUTH
    APIGW --> TODO
    APIGW --> WS

    WS --> COLLAB
    TODO --> COLLAB

    AUTH --> DB
    AUTH --> CACHE
    TODO --> DB
    TODO --> CACHE
    TODO --> SEARCH
    COLLAB --> CACHE
    COLLAB --> QUEUE

    QUEUE --> NOTIFY
    NOTIFY --> WEB
    NOTIFY --> MOBILE

    style WS fill:#e1f5ff
    style COLLAB fill:#e1f5ff
    style CACHE fill:#fff4e1
    style DB fill:#fff4e1
```

---

## Database Design

### Schema Design

```mermaid
erDiagram
    USERS ||--o{ LISTS : creates
    USERS ||--o{ LIST_SHARES : "shares with"
    LISTS ||--o{ LIST_SHARES : "shared via"
    LISTS ||--o{ TASKS : contains
    TASKS ||--o{ TASK_OPERATIONS : "has operations"
    USERS ||--o{ TASKS : "assigned to"

    USERS {
        uuid id PK
        string email UK
        string password_hash
        string name
        timestamp created_at
        timestamp last_login
    }

    LISTS {
        uuid id PK
        uuid owner_id FK
        string title
        text description
        timestamp created_at
        timestamp updated_at
        jsonb crdt_state
    }

    LIST_SHARES {
        uuid id PK
        uuid list_id FK
        uuid shared_with_user_id FK
        timestamp shared_at
        uuid shared_by FK
    }

    TASKS {
        uuid id PK
        uuid list_id FK
        string title
        text description
        string priority
        timestamp due_date
        uuid assigned_to FK
        string[] tags
        string status
        int position
        timestamp created_at
        timestamp updated_at
        jsonb crdt_state
        string crdt_clock
    }

    TASK_OPERATIONS {
        uuid id PK
        uuid task_id FK
        uuid user_id FK
        string operation_type
        jsonb operation_data
        string lamport_timestamp
        timestamp created_at
    }
```

### Key Design Decisions

1. **CRDT State Storage**: Each task and list stores its CRDT state as JSONB for conflict-free merging
2. **Operation Log**: `TASK_OPERATIONS` table maintains operation history for CRDT synchronization
3. **Lamport Timestamps**: Used for ordering operations in distributed system

---

## Component Architecture

```mermaid
graph TB
    subgraph "Frontend Components"
        UI[React UI Components]
        STATE[State Management<br/>Redux + Yjs CRDT]
        WSLIB[WebSocket Client]
        APILIB[REST API Client]
    end

    subgraph "Backend Services"
        subgraph "Auth Service"
            AUTHAPI[Auth API]
            JWT[JWT Handler]
        end

        subgraph "Todo Service"
            TODOAPI[Todo REST API]
            LISTMGR[List Manager]
            TASKMGR[Task Manager]
        end

        subgraph "WebSocket Service"
            WSCONN[WS Connection Manager]
            ROOM[Room Manager]
            BROADCAST[Broadcast Handler]
        end

        subgraph "Collaboration Service"
            CRDT[CRDT Engine<br/>Yjs/Automerge]
            SYNC[Sync Manager]
            CONFLICT[Conflict Resolver]
        end
    end

    UI --> STATE
    STATE --> WSLIB
    STATE --> APILIB

    WSLIB --> WSCONN
    APILIB --> AUTHAPI
    APILIB --> TODOAPI

    WSCONN --> ROOM
    ROOM --> BROADCAST
    BROADCAST --> CRDT

    TODOAPI --> LISTMGR
    TODOAPI --> TASKMGR
    LISTMGR --> SYNC
    TASKMGR --> SYNC

    SYNC --> CRDT
    CRDT --> CONFLICT

    style STATE fill:#e1f5ff
    style CRDT fill:#e1f5ff
    style SYNC fill:#e1f5ff
```

---

## Key Flows

### 1. User Registration & Login

```mermaid
sequenceDiagram
    actor User
    participant Web as Web Client
    participant API as API Gateway
    participant Auth as Auth Service
    participant DB as PostgreSQL
    participant Cache as Redis

    User->>Web: Enter credentials
    Web->>API: POST /api/auth/register
    API->>Auth: Validate & Create User
    Auth->>DB: INSERT user record
    DB-->>Auth: User created
    Auth->>Cache: Cache user session
    Auth-->>API: JWT token
    API-->>Web: Return JWT + user data
    Web-->>User: Login successful
```

### 2. Create List & Share

```mermaid
sequenceDiagram
    actor User
    participant Web as Web Client
    participant API as API Gateway
    participant Todo as Todo Service
    participant DB as PostgreSQL
    participant Cache as Redis

    User->>Web: Create new list
    Web->>API: POST /api/lists
    API->>Todo: Create list
    Todo->>DB: INSERT list with CRDT state
    DB-->>Todo: List created
    Todo->>Cache: Cache list metadata
    Todo-->>Web: Return list data

    User->>Web: Share list with user@email.com
    Web->>API: POST /api/lists/{id}/share
    API->>Todo: Create share record
    Todo->>DB: INSERT list_share
    DB-->>Todo: Share created
    Todo->>Cache: Invalidate cache
    Todo-->>Web: Share successful
```

### 3. Real-time Collaborative Editing

```mermaid
sequenceDiagram
    actor User1
    actor User2
    participant WS1 as WebSocket Client 1
    participant WS2 as WebSocket Client 2
    participant Server as WebSocket Server
    participant Collab as Collaboration Service
    participant CRDT as CRDT Engine
    participant Cache as Redis
    participant DB as PostgreSQL

    User1->>WS1: Connect to list
    WS1->>Server: JOIN list:abc123
    Server->>Collab: Add to room
    Collab->>Cache: Get CRDT state
    Cache-->>Collab: Current state
    Collab-->>WS1: Sync current state

    User2->>WS2: Connect to same list
    WS2->>Server: JOIN list:abc123
    Server->>Collab: Add to room
    Collab->>Cache: Get CRDT state
    Cache-->>Collab: Current state
    Collab-->>WS2: Sync current state

    User1->>WS1: Edit task title
    WS1->>Server: OPERATION {type: edit, data: {...}}
    Server->>Collab: Process operation
    Collab->>CRDT: Apply operation
    CRDT-->>Collab: Merged state
    Collab->>Cache: Update CRDT state
    Collab->>Server: Broadcast to room
    Server->>WS2: OPERATION update
    WS2-->>User2: UI updates

    par Concurrent Edit
        User2->>WS2: Edit same task (priority)
        WS2->>Server: OPERATION {type: edit, data: {...}}
        Server->>Collab: Process operation
        Collab->>CRDT: Apply & merge
        CRDT-->>Collab: Conflict-free merge
    end

    Collab->>Server: Broadcast merged state
    Server->>WS1: OPERATION update
    Server->>WS2: OPERATION update
    WS1-->>User1: UI updates (no conflict)
    WS2-->>User2: UI updates (no conflict)

    Note over Collab,DB: Periodic persistence
    Collab->>DB: Save operations log
    Collab->>DB: Update task state
```

### 4. CRDT Conflict Resolution Flow

```mermaid
graph TB
    START[Multiple Users Edit Same Task]

    OP1[User 1: Edit Title<br/>Clock: T1]
    OP2[User 2: Change Priority<br/>Clock: T2]
    OP3[User 3: Add Tag<br/>Clock: T3]

    START --> OP1
    START --> OP2
    START --> OP3

    OP1 --> CRDT[CRDT Engine<br/>Yjs/Automerge]
    OP2 --> CRDT
    OP3 --> CRDT

    CRDT --> MERGE{Merge Operations}

    MERGE --> CHECK1{Conflict?}
    CHECK1 -->|Different Fields| NOCONFLICT[Auto-merge:<br/>Title + Priority + Tag]
    CHECK1 -->|Same Field| RESOLVE[LWW/Operational Transform]

    NOCONFLICT --> FINAL[Final State]
    RESOLVE --> FINAL

    FINAL --> BROADCAST[Broadcast to All Clients]
    FINAL --> PERSIST[(Persist to DB)]

    style CRDT fill:#e1f5ff
    style MERGE fill:#fff4e1
    style FINAL fill:#e1ffe1
```

---

## API Design

### Authentication Endpoints

```
POST   /api/auth/register          - Register new user
POST   /api/auth/login             - Login user
POST   /api/auth/logout            - Logout user
GET    /api/auth/me                - Get current user
POST   /api/auth/refresh           - Refresh JWT token
```

### List Management Endpoints

```
GET    /api/lists                  - Get all lists (owned + shared)
POST   /api/lists                  - Create new list
GET    /api/lists/:id              - Get list details
PUT    /api/lists/:id              - Update list
DELETE /api/lists/:id              - Delete list
POST   /api/lists/:id/share        - Share list with user
DELETE /api/lists/:id/share/:userId - Remove share
GET    /api/lists/:id/collaborators - Get list collaborators
```

### Task Management Endpoints

```
GET    /api/lists/:listId/tasks    - Get all tasks in list
POST   /api/lists/:listId/tasks    - Create new task
GET    /api/tasks/:id              - Get task details
PUT    /api/tasks/:id              - Update task
DELETE /api/tasks/:id              - Delete task
PATCH  /api/tasks/:id/status       - Update task status
```

### WebSocket Events

```
Client -> Server:
  - join:list:{listId}              - Join list room
  - leave:list:{listId}             - Leave list room
  - operation                       - Send CRDT operation
  - cursor:position                 - Share cursor position

Server -> Client:
  - sync:state                      - Full state sync
  - operation                       - CRDT operation from other user
  - user:joined                     - User joined list
  - user:left                       - User left list
  - cursor:update                   - Other user's cursor position
```

---

## Technology Stack Recommendations

### Frontend
- **Framework**: React 18+ with TypeScript
- **State Management**: Redux Toolkit + Yjs for CRDT
- **WebSocket**: Socket.io-client
- **UI Library**: Material-UI or Ant Design
- **Real-time Collaboration**: Yjs + y-websocket

### Backend
- **Runtime**: Node.js with Express or NestJS
- **WebSocket**: Socket.io
- **CRDT Library**: Yjs (JavaScript) or Automerge
- **Authentication**: JWT with bcrypt

### Database & Cache
- **Primary DB**: PostgreSQL 14+ (JSONB support for CRDT state)
- **Cache**: Redis 7+ (for sessions, CRDT state, pub/sub)
- **Search**: ElasticSearch 8+ (optional, for task search)

### Infrastructure (Small Scale)
- **Hosting**: Single cloud provider (AWS/GCP/Azure)
- **Compute**:
  - 2-3 application servers (4GB RAM each)
  - 1 PostgreSQL instance (8GB RAM)
  - 1 Redis instance (4GB RAM)
- **Load Balancer**: Cloud provider LB (ALB/Cloud Load Balancer)
- **CDN**: CloudFront/CloudFlare for static assets

---

## CRDT Implementation Details

### Why CRDT for This Scale?

Even with 500-1000 users, CRDT provides:
1. **Offline Support**: Users can work offline and sync later
2. **No Locking**: No need for complex distributed locks
3. **Guaranteed Convergence**: All clients eventually reach same state
4. **Better UX**: No merge conflict dialogs

### Yjs Integration

```javascript
// Example CRDT structure for a task
const taskDoc = new Y.Doc()
const task = taskDoc.getMap('task')

task.set('id', uuid)
task.set('title', new Y.Text('Buy groceries'))
task.set('description', new Y.Text(''))
task.set('priority', 'high')
task.set('tags', new Y.Array(['shopping', 'urgent']))
task.set('status', 'pending')
task.set('assignedTo', userId)
task.set('dueDate', timestamp)

// Sync updates via WebSocket
const wsProvider = new WebsocketProvider(
  'wss://api.todoapp.com/collab',
  `list-${listId}`,
  taskDoc
)
```

### Conflict Resolution Strategy

1. **Different Fields**: Auto-merge (User A edits title, User B edits priority)
2. **Same Text Field**: Operational Transform (both edit description)
3. **Same Primitive Field**: Last-Write-Wins with Lamport timestamp
4. **Array Operations**: CRDT array (insertions/deletions merge)

---

## Scalability Considerations

### Current Scale (500-1000 users)
- **Single Region Deployment**: No need for multi-region
- **Vertical Scaling**: Start with vertical scaling (larger instances)
- **Simple Architecture**: Monolithic application acceptable
- **Database**: Single PostgreSQL instance with read replicas

### Future Scale (10K+ users)
- **Horizontal Scaling**: Add more application servers
- **Database Sharding**: Partition by user_id or list_id
- **Microservices**: Split Auth, Todo, Collaboration services
- **CDN**: Cache static content and API responses
- **Message Queue**: Add RabbitMQ/Kafka for async processing

### Performance Targets
- **API Response Time**: < 200ms (p95)
- **WebSocket Latency**: < 100ms
- **List Load Time**: < 500ms
- **Concurrent Connections**: 200-500 per server

---

## Deployment Architecture

```mermaid
graph TB
    subgraph "Production Environment"
        subgraph "Public Zone"
            CDN[CloudFront CDN]
            LB[Application Load Balancer]
        end

        subgraph "Application Zone"
            APP1[App Server 1<br/>Node.js + WS]
            APP2[App Server 2<br/>Node.js + WS]
        end

        subgraph "Data Zone"
            DB_PRIMARY[(PostgreSQL Primary)]
            DB_REPLICA[(PostgreSQL Replica)]
            REDIS[(Redis Cluster)]
        end

        subgraph "Monitoring"
            LOGS[CloudWatch/ELK]
            METRICS[Prometheus/Grafana]
        end
    end

    CDN --> LB
    LB --> APP1
    LB --> APP2

    APP1 --> DB_PRIMARY
    APP2 --> DB_PRIMARY
    APP1 --> DB_REPLICA
    APP2 --> DB_REPLICA
    APP1 --> REDIS
    APP2 --> REDIS

    APP1 --> LOGS
    APP2 --> LOGS
    DB_PRIMARY --> METRICS
    REDIS --> METRICS

    style CDN fill:#e1f5ff
    style LB fill:#e1f5ff
    style DB_PRIMARY fill:#fff4e1
    style REDIS fill:#fff4e1
```

---

## Security Considerations

### Authentication & Authorization
1. **JWT Tokens**: Short-lived access tokens (15 min) + refresh tokens (7 days)
2. **Password Security**: bcrypt with salt rounds >= 10
3. **Rate Limiting**: 100 requests/min per IP
4. **HTTPS Only**: TLS 1.3 for all connections
5. **WebSocket Auth**: Validate JWT on WS connection

### Data Security
1. **Input Validation**: Sanitize all user inputs
2. **SQL Injection**: Use parameterized queries
3. **XSS Prevention**: Content Security Policy headers
4. **CORS**: Whitelist allowed origins
5. **Encryption**: Encrypt sensitive data at rest

### Access Control
1. **List Access**: Verify user owns or has share access
2. **Operation Validation**: Validate user can perform operation
3. **Share Limits**: Limit shares per list (e.g., 50 users)

---

## Monitoring & Observability

### Key Metrics
1. **Application Metrics**
   - API response times (p50, p95, p99)
   - WebSocket connection count
   - Active collaboration sessions
   - CRDT operation throughput

2. **Infrastructure Metrics**
   - CPU/Memory utilization
   - Database query performance
   - Redis cache hit rate
   - Network I/O

3. **Business Metrics**
   - Active users (DAU/MAU)
   - Lists created per day
   - Collaboration sessions per day
   - Average tasks per list

### Logging
- **Structured Logging**: JSON format with correlation IDs
- **Log Levels**: ERROR, WARN, INFO, DEBUG
- **Retention**: 30 days for application logs

### Alerting
- API error rate > 1%
- WebSocket disconnect rate > 5%
- Database connection pool > 80%
- Response time p95 > 500ms

---

## Cost Estimation (Monthly)

### Infrastructure (AWS Example)
- **Application Servers**: 2 x t3.medium = $60
- **Database**: db.t3.medium = $50
- **Redis**: cache.t3.medium = $40
- **Load Balancer**: ALB = $20
- **Data Transfer**: ~$20
- **Monitoring & Logs**: $30

**Total**: ~$220/month for 500-1000 users ($0.22-$0.44 per user/month)

### Scaling Costs
- At 5K users: ~$500/month
- At 10K users: ~$800/month

---

## Development Roadmap

### Phase 1: MVP (4-6 weeks)
- User authentication
- Basic list CRUD
- Simple task management
- Basic sharing (no CRDT yet)

### Phase 2: Real-time Collaboration (4-6 weeks)
- WebSocket integration
- CRDT implementation
- Real-time updates
- Conflict resolution

### Phase 3: Advanced Features (4-6 weeks)
- Advanced task properties
- Search functionality
- User presence indicators
- Offline support

### Phase 4: Production Ready (2-4 weeks)
- Performance optimization
- Security hardening
- Monitoring & alerting
- Load testing

---

## Testing Strategy

### Unit Testing
- Service layer logic
- CRDT operations
- API endpoints
- Utility functions

### Integration Testing
- Database operations
- Redis caching
- WebSocket connections
- CRDT synchronization

### E2E Testing
- User registration flow
- List creation and sharing
- Collaborative editing scenarios
- Conflict resolution

### Performance Testing
- Load testing (500 concurrent users)
- WebSocket stress testing
- Database query optimization
- Cache efficiency

---

## Conclusion

This system design provides a scalable, real-time collaborative todo list application using CRDT for conflict-free concurrent editing. The architecture is optimized for 500-1000 users while maintaining flexibility for future growth.

### Key Highlights
- Real-time collaboration with WebSocket
- CRDT-based conflict resolution (Yjs)
- Simple sharing model
- Advanced task management
- Cost-effective for small-medium scale
- Clear path to scale

### Trade-offs Made
1. **CRDT Complexity**: More complex than simple last-write-wins, but better UX
2. **Simple Sharing**: No role-based permissions for simplicity
3. **Monolithic Architecture**: Easier to manage at this scale
4. **Single Region**: Cost-effective for current scale

This design can be implemented incrementally, starting with MVP and adding real-time features progressively.
