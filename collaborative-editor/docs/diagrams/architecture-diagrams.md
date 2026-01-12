# Architecture Diagrams

This document consolidates all Mermaid diagrams used throughout the collaborative editor system design.

## System Overview

### High-Level Architecture

```mermaid
flowchart TB
    subgraph clients [Client Layer]
        C1[Client 1<br/>Editor + Local CRDT]
        C2[Client 2<br/>Editor + Local CRDT]
        C3[Client N<br/>Editor + Local CRDT]
    end

    subgraph gateway [Gateway Layer]
        WS[WebSocket Gateway<br/>Connection Management]
        LB[Load Balancer<br/>Sticky Sessions]
    end

    subgraph services [Service Layer]
        DS[Document Service<br/>CRDT Merge Engine]
        PS[Presence Service<br/>Cursor/Selection Broadcast]
        SS[Snapshot Service<br/>Compaction Worker]
    end

    subgraph storage [Storage Layer]
        CRDT_Store[(CRDT State Store<br/>Redis Cluster)]
        Snapshots[(Snapshot Store<br/>S3/Postgres)]
        OpLog[(Operation Log<br/>Kafka/Pulsar)]
    end

    subgraph readonly [Read Path]
        RC[Read Replicas<br/>For Viewers]
        CDN[CDN<br/>Static Assets]
    end

    C1 & C2 & C3 <--> LB
    LB <--> WS
    WS <--> DS & PS
    DS <--> CRDT_Store & OpLog
    SS <--> CRDT_Store & Snapshots
    DS --> RC
    RC --> C1 & C2 & C3
```

### System Context

```mermaid
flowchart TB
    subgraph users [Users]
        U1[Editor User 1]
        U2[Editor User 2]
        U3[Viewer User]
    end

    subgraph system [Collaborative Editor System]
        API[API Gateway]
        Core[Core Services]
        Storage[Storage Layer]
    end

    subgraph external [External Systems]
        Auth[Authentication Provider]
        CDN[CDN]
        Monitoring[Observability Stack]
    end

    U1 & U2 & U3 <--> API
    API <--> Core
    Core <--> Storage
    API <--> Auth
    U3 --> CDN
    Core --> Monitoring
```

---

## CRDT Data Model

### Document Structure

```mermaid
flowchart TD
    Doc[Y.Doc<br/>Document Root]
    Doc --> Meta[Y.Map<br/>Document Metadata]
    Doc --> Content[Y.Array<br/>Block Array]
    
    Content --> B1[Block 1<br/>Paragraph]
    Content --> B2[Block 2<br/>Table]
    Content --> B3[Block 3<br/>Image]
    
    B1 --> T1[Y.Text<br/>Formatted Text]
    B2 --> Rows[Y.Array<br/>Table Rows]
    B3 --> ImgData[Y.Map<br/>Image Data]
    
    Rows --> R1[Y.Array<br/>Row 1 Cells]
    R1 --> C1[Y.Doc<br/>Cell Content]
    R1 --> C2[Y.Doc<br/>Cell Content]
    
    T1 --> Chars[Characters<br/>with unique IDs]
```

---

## Sync Protocol

### WebSocket Connection Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant WS as WebSocket Gateway
    participant DS as Document Service
    participant Store as CRDT Store

    C->>WS: Connect(docId, lastKnownVersion)
    WS->>DS: Subscribe(docId, clientId)
    DS->>Store: GetStateVector(docId)
    Store-->>DS: StateVector
    DS->>Store: GetMissingSince(clientVector)
    Store-->>DS: MissingOperations
    DS-->>WS: SyncResponse(operations, currentVector)
    WS-->>C: InitialSync(operations)
    
    loop Editing Session
        C->>WS: Operations(batch)
        WS->>DS: ApplyOperations(batch)
        DS->>Store: Merge + Persist
        DS-->>WS: Broadcast(batch, excludeSender)
        WS-->>C: RemoteOperations(batch)
    end
```

### Connection State Machine

```mermaid
stateDiagram-v2
    [*] --> Disconnected
    
    Disconnected --> Connecting: Network available
    Connecting --> Syncing: Connected
    Connecting --> Disconnected: Connection failed
    
    Syncing --> Online: Sync complete
    Syncing --> Disconnected: Connection lost
    
    Online --> Syncing: Remote changes
    Online --> Syncing: Local changes
    Online --> Disconnected: Connection lost
    
    Disconnected --> Offline: User continues editing
    Offline --> Connecting: Network available
```

---

## Offline Support

### Client Architecture

```mermaid
flowchart TB
    subgraph client [Client Architecture]
        Editor[Rich Text Editor]
        LocalCRDT[Local CRDT State]
        IndexedDB[(IndexedDB<br/>Persistent Storage)]
        SyncQueue[Sync Queue<br/>Pending Operations]
        
        Editor <--> LocalCRDT
        LocalCRDT <--> IndexedDB
        LocalCRDT --> SyncQueue
    end

    subgraph network [Network Layer]
        WSClient[WebSocket Client<br/>with Reconnection]
        SyncEngine[Sync Engine<br/>Vector Clock Comparison]
    end

    SyncQueue --> WSClient
    WSClient <--> SyncEngine
    SyncEngine -->|Remote Ops| LocalCRDT
```

### Sync Flow

```mermaid
flowchart TD
    Start[Connection State Change] --> Check{Online?}
    
    Check -->|Yes| SendVector[Send State Vector]
    Check -->|No| QueueOps[Queue Operations Locally]
    
    SendVector --> ReceiveMissing[Receive Missing Operations]
    ReceiveMissing --> ApplyRemote[Apply Remote to Local CRDT]
    ApplyRemote --> SendLocal[Send Local Queue]
    SendLocal --> ReceiveAck[Receive Acknowledgments]
    ReceiveAck --> ClearQueue[Clear Acknowledged from Queue]
    ClearQueue --> Done[Sync Complete]
    
    QueueOps --> LocalEdit[Continue Editing Locally]
    LocalEdit --> Start
```

---

## Presence Service

### Presence Architecture

```mermaid
flowchart TB
    subgraph presence [Presence Architecture]
        Client1[Client 1] -->|Cursor Position| PubSub[Redis Pub/Sub]
        Client2[Client 2] -->|Selection| PubSub
        PubSub -->|Broadcast| Client1 & Client2 & Client3[Client 3]
    end
```

---

## Snapshot and Compaction

### Compaction Flow

```mermaid
flowchart LR
    subgraph active [Active State]
        Ops1[Op 1] --> Ops2[Op 2] --> Ops3[Op 3] --> Current[Current CRDT State]
    end
    
    subgraph compaction [Compaction Process]
        Snapshot[Create Snapshot<br/>Full document state]
        GC[Garbage Collect<br/>Tombstones older than threshold]
        Prune[Prune Op Log<br/>Keep only since snapshot]
    end
    
    Current --> Snapshot
    Snapshot --> GC --> Prune
    
    subgraph result [Compacted State]
        NewSnapshot[Snapshot v42]
        RecentOps[Recent Ops Only]
    end
    
    Prune --> NewSnapshot & RecentOps
```

### Compaction Sequence

```mermaid
sequenceDiagram
    participant Trigger as Compaction Trigger
    participant CS as Compaction Service
    participant DS as Document Service
    participant Clients as Active Clients
    participant Store as Storage

    Trigger->>CS: Document needs compaction
    CS->>DS: Get current state
    DS-->>CS: CRDT state + stats
    
    CS->>CS: Create snapshot
    CS->>CS: Identify safe-to-delete tombstones
    
    CS->>Store: Write snapshot
    Store-->>CS: Snapshot ID
    
    CS->>DS: Broadcast snapshot notification
    DS->>Clients: snapshot_available
    
    loop Wait for acknowledgments
        Clients-->>DS: snapshot_ack
        DS-->>CS: Client acked
    end
    
    alt All clients acked
        CS->>DS: Apply compaction
        DS->>Store: Prune op log
        CS->>CS: Mark compaction complete
    else Some clients offline
        CS->>CS: Schedule retry
    end
```

---

## Testing Strategy

### Testing Pyramid

```mermaid
flowchart TB
    subgraph pyramid [Testing Pyramid]
        E2E[E2E Tests<br/>Real browsers, real network<br/>Slowest, most realistic]
        Integration[Integration Tests<br/>Multiple services, controlled network<br/>Medium speed]
        Simulation[Deterministic Simulation<br/>Fake time, fake network<br/>Fast, reproducible]
        Property[Property-Based Tests<br/>QuickCheck/Hypothesis<br/>Fast, exhaustive]
        Unit[Unit Tests<br/>Single function/class<br/>Fastest]
    end
    
    E2E --> Integration --> Simulation --> Property --> Unit
```

### Simulation Framework

```mermaid
flowchart LR
    subgraph simulation [Simulation Framework]
        Seed[Random Seed] --> Scheduler[Deterministic Scheduler]
        Scheduler --> FakeTime[Fake Time<br/>Controllable clock]
        Scheduler --> FakeNetwork[Fake Network<br/>Controllable partitions]
        Scheduler --> FakeStorage[Fake Storage<br/>Controllable failures]
    end
    
    subgraph scenarios [Chaos Scenarios]
        S1[Network Partition]
        S2[Message Reordering]
        S3[Message Duplication]
        S4[Clock Skew]
        S5[Storage Failure]
    end
    
    simulation --> S1 & S2 & S3 & S4 & S5
```

---

## Data Flow

### Write Path

```mermaid
sequenceDiagram
    participant Client
    participant LocalCRDT as Local CRDT
    participant IndexedDB
    participant WSGateway as WebSocket Gateway
    participant DocService as Document Service
    participant Redis
    participant Kafka
    participant OtherClients as Other Clients

    Client->>LocalCRDT: User types character
    LocalCRDT->>LocalCRDT: Apply operation locally
    LocalCRDT->>Client: Update UI immediately
    LocalCRDT->>IndexedDB: Persist locally
    LocalCRDT->>WSGateway: Send operation batch
    WSGateway->>DocService: Forward operations
    DocService->>DocService: Validate operations
    DocService->>Redis: Merge into state
    DocService->>Kafka: Append to log
    DocService->>WSGateway: Broadcast to others
    WSGateway->>OtherClients: Send remote operations
    OtherClients->>OtherClients: Merge into local CRDT
```

### Read Path

```mermaid
flowchart LR
    Viewer[Viewer Client] --> CDN
    CDN -->|Cache Miss| ReadReplica[Read Replica]
    ReadReplica --> SnapshotStore[(Snapshot Store)]
    
    Editor[Editor Client] --> DS[Document Service]
    DS -->|Async Update| ReadReplica
```

---

## Infrastructure

### Scaling Architecture

```mermaid
flowchart TB
    subgraph gateway [WebSocket Gateway Cluster]
        G1[Gateway 1<br/>50K connections]
        G2[Gateway 2<br/>50K connections]
        G3[Gateway 3<br/>50K connections]
        GN[...<br/>x 10 total]
    end
    
    LB[Load Balancer] --> G1 & G2 & G3 & GN
```

### Failure Recovery

```mermaid
flowchart TD
    Error[Error Received] --> Check{Error Type}
    
    Check -->|Retryable| Backoff[Exponential Backoff]
    Backoff --> Retry[Retry Operation]
    
    Check -->|Auth Error| Refresh[Refresh Token]
    Refresh -->|Success| Retry
    Refresh -->|Failure| Logout[Force Logout]
    
    Check -->|Version Mismatch| FullSync[Full Resync]
    
    Check -->|Rate Limited| Wait[Wait retryAfter]
    Wait --> Retry
    
    Check -->|Unrecoverable| Notify[Notify User]
```

---

## Usage Notes

All diagrams in this document use Mermaid syntax. To render:

1. **GitHub/GitLab**: Renders natively in Markdown
2. **VS Code**: Use Mermaid extension
3. **Web**: Use [Mermaid Live Editor](https://mermaid.live/)
4. **Documentation sites**: Most support Mermaid (Docusaurus, MkDocs, etc.)

### Diagram Conventions

- **Rounded rectangles**: Services/components
- **Cylinders**: Databases/storage
- **Arrows**: Data flow direction
- **Subgraphs**: Logical groupings
- **Sequence diagrams**: Time-ordered interactions
- **State diagrams**: State machines
- **Flowcharts**: Decision flows
