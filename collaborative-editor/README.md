# Real-Time Collaborative Document Editor

A distributed collaborative editing system supporting rich text documents (formatting, tables, embedded media, comments) with 10-100 concurrent editors per document and full offline support.

## Overview

This system design demonstrates how to build a Google Docs-like collaborative editor using **CRDTs (Conflict-free Replicated Data Types)** for conflict-free merging with eventual consistency guarantees.

## Key Features

- **Real-time collaboration**: Multiple users editing simultaneously with sub-100ms latency
- **Rich text support**: Formatting, tables, embedded media, comments
- **Full offline support**: Edit while disconnected, automatic sync on reconnection
- **Scalability**: Supports 10-100 concurrent editors per document
- **Durability**: No data loss even during network partitions

## Architecture Highlights

| Component | Technology | Purpose |
|-----------|------------|---------|
| Conflict Resolution | CRDT (Yjs-style) | Automatic merge without central coordination |
| Real-time Transport | WebSocket | Bidirectional, low-latency communication |
| State Store | Redis Cluster | Fast CRDT state access |
| Durability | Kafka/Pulsar | Operation log for recovery |
| Offline Storage | IndexedDB | Client-side persistence |
| Presence | Redis Pub/Sub | Cursor/selection broadcast |

## Key Design Decisions

1. **CRDT over OT** - Full offline support requires operations that merge automatically
2. **Causal Consistency** - Balances correctness guarantees with performance
3. **Separate Presence Channel** - Different durability/latency requirements from edit stream
4. **Snapshot-based Compaction** - Bounds state size growth from CRDT tombstones

## Documentation

### Design Documents

| Document | Description |
|----------|-------------|
| [Architecture Overview](docs/01-architecture-overview.md) | High-level system architecture and components |
| [CRDT Design](docs/02-crdt-design.md) | Data model, operation types, merge semantics |
| [Sync Protocol](docs/03-sync-protocol.md) | WebSocket protocol, state vectors, delta sync |
| [Offline Support](docs/04-offline-support.md) | Local-first architecture, IndexedDB, sync queue |
| [Presence Service](docs/05-presence-service.md) | Cursor tracking, user awareness, ephemeral state |
| [Snapshot & Compaction](docs/06-snapshot-compaction.md) | State size management, garbage collection |
| [Testing Strategy](docs/07-testing-strategy.md) | Property-based testing, simulation, fuzzing |
| [Failure Modes](docs/08-failure-modes.md) | Failure scenarios and mitigations |
| [Capacity Planning](docs/09-capacity-planning.md) | Infrastructure sizing, performance estimates |
| [API Contracts](docs/10-api-contracts.md) | REST and WebSocket API specifications |

### Architecture Decision Records (ADRs)

| ADR | Decision |
|-----|----------|
| [ADR-001](adr/001-crdt-vs-ot.md) | CRDT over Operational Transformation |
| [ADR-002](adr/002-crdt-library-choice.md) | Yjs-style CRDT architecture |
| [ADR-003](adr/003-consistency-model.md) | Causal consistency model |
| [ADR-004](adr/004-presence-separation.md) | Separate presence from edit stream |
| [ADR-005](adr/005-offline-strategy.md) | Local-first offline architecture |

### Diagrams

All architecture diagrams use Mermaid syntax and are embedded in the documentation. A consolidated diagram reference is available at [diagrams/architecture-diagrams.md](docs/diagrams/architecture-diagrams.md).

## Quick Reference

### Scale Parameters

- **Documents**: 10,000 active
- **Concurrent Editors**: 50 average per document (max 100)
- **Operations**: ~1M ops/second system-wide
- **Latency Target**: <100ms for operation broadcast

### Trade-offs Summary

| Decision | Chose | Over | Rationale |
|----------|-------|------|-----------|
| Conflict Resolution | CRDT | OT | Offline-first requirement |
| Consistency | Causal | Strong/Eventual | Balance guarantees and performance |
| Presence Channel | Separate | Combined | Different durability requirements |
| Compaction | Snapshot-based | Log compaction | Simpler recovery |
| Testing | Simulation-first | E2E-first | Reproducibility |

## Technology Stack

- **Backend**: Stateless microservices (any language)
- **State Store**: Redis Cluster
- **Message Queue**: Kafka or Pulsar
- **Object Storage**: S3-compatible for snapshots
- **Client Storage**: IndexedDB
- **Transport**: WebSocket with fallback to SSE

## License

This system design is part of a learning repository for distributed systems patterns.
