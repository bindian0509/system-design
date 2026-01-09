# Data Patterns

This section covers patterns for managing data consistency, state, and transactions in distributed systems. These patterns help solve the fundamental challenges of maintaining data integrity across multiple services.

## Overview

```mermaid
flowchart TB
    subgraph Patterns[Data Pattern Selection]
        Problem[Data Problem] --> Q1{Need transaction across services?}

        Q1 -->|Yes, strong consistency| TwoPC[Two-Phase Commit]
        Q1 -->|Yes, eventual consistency| Saga[Saga Pattern]
        Q1 -->|No| Q2{Need separate read/write models?}

        Q2 -->|Yes| CQRS
        Q2 -->|No| Q3{Need complete audit history?}

        Q3 -->|Yes| EventSourcing[Event Sourcing]
        Q3 -->|No| Traditional[Traditional CRUD]
    end
```

## Patterns in This Category

| Pattern | Document | Best For |
|---------|----------|----------|
| CQRS | [cqrs.md](./cqrs.md) | Separate read/write scaling and optimization |
| Event Sourcing | [event-sourcing.md](./event-sourcing.md) | Complete audit trails, temporal queries |
| Saga | [saga-pattern.md](./saga-pattern.md) | Distributed transactions with eventual consistency |
| Two-Phase Commit | [two-phase-commit.md](./two-phase-commit.md) | Strong consistency across services |
| Outbox | [outbox-pattern.md](./outbox-pattern.md) | Reliable event publishing, dual-write problem |

## Comparison Matrix

| Aspect | CQRS | Event Sourcing | Saga | 2PC | Outbox |
|--------|------|----------------|------|-----|--------|
| **Consistency** | Eventually | Eventually | Eventually | Strong | Eventually |
| **Complexity** | Medium | High | High | Medium | Low |
| **Performance** | High (reads) | Replay overhead | Good | Poor (blocking) | Good |
| **Audit Trail** | Optional | Complete | Partial | None | Partial |
| **Scalability** | Excellent | Good | Good | Poor | Excellent |
| **Use Case** | Read-heavy apps | Financial, legal | Long-running txns | ACID required | Reliable events |

## Decision Framework

### Consistency vs. Availability Trade-off

```mermaid
quadrantChart
    title Consistency vs Availability
    x-axis Low Availability --> High Availability
    y-axis Eventual Consistency --> Strong Consistency
    quadrant-1 2PC
    quadrant-2 Saga
    quadrant-3 CQRS
    quadrant-4 Event Sourcing
    TwoPhaseCommit: [0.3, 0.9]
    SagaPattern: [0.7, 0.4]
    CQRS: [0.8, 0.3]
    EventSourcing: [0.6, 0.5]
```

### When to Use Each Pattern

| Scenario | Recommended Pattern |
|----------|---------------------|
| E-commerce checkout | Saga (order → payment → inventory) |
| Banking transactions | 2PC or Saga with compensation |
| Reporting dashboard | CQRS (separate read model) |
| Financial audit | Event Sourcing |
| Inventory management | CQRS + Event Sourcing |
| Travel booking | Saga (flight → hotel → car) |
| Microservice events | Outbox (reliable publishing) |

## Pattern Combinations

These patterns often work together:

```mermaid
flowchart LR
    subgraph Combined[CQRS + Event Sourcing]
        Commands --> EventStore[(Event Store)]
        EventStore --> Projections[Projections]
        Projections --> ReadDB[(Read DB)]
        Queries --> ReadDB
    end
```

**Common Combinations:**
- **CQRS + Event Sourcing**: Events as the source of truth, optimized read models
- **Saga + Event Sourcing**: Event-driven saga orchestration
- **CQRS + Saga**: Complex workflows with optimized queries
- **Saga + Outbox**: Reliable saga step execution with guaranteed delivery
- **CQRS + Outbox**: Reliable sync of read models from write model

## The CAP Theorem Context

Understanding when to use each pattern requires understanding CAP trade-offs:

| Pattern | Favors | Trade-off |
|---------|--------|-----------|
| 2PC | Consistency | Reduces availability (blocking) |
| Saga | Availability | Eventual consistency |
| CQRS | Availability | Read model may be stale |
| Event Sourcing | Partition tolerance | Eventual consistency |

## Related Patterns

- [Pub/Sub](../05-messaging-patterns/pub-sub.md) - Event distribution for CQRS
- [Message Queue](../05-messaging-patterns/message-queue.md) - Reliable saga step execution
- [Circuit Breaker](../03-resilience-patterns/circuit-breaker.md) - Protect during saga failures
