# ADR-003: Causal Consistency Model

## Status

**Accepted**

## Context

We need to define the consistency guarantees our system provides. This affects:
- How users perceive collaborative editing
- What invariants we must maintain
- System complexity and performance

The main consistency models to consider:
1. **Strong consistency** (linearizability): All operations appear in a single global order
2. **Causal consistency**: Operations are ordered by causality, concurrent ops may vary
3. **Eventual consistency**: All replicas eventually converge, no ordering guarantees

## Decision

We will provide **Causal Consistency** guarantees.

## Rationale

### Consistency Models Comparison

| Model | Ordering Guarantee | Performance | Complexity |
|-------|-------------------|-------------|------------|
| Strong (Linearizability) | Total order, real-time | High latency, low availability | High |
| Causal | Causal order preserved | Low latency, high availability | Medium |
| Eventual | None guaranteed | Lowest latency | Low |

### Why Not Strong Consistency?

Strong consistency (linearizability) would mean:
- Every operation appears to happen at a single instant
- All users see operations in the same order
- Requires coordination (consensus protocols like Raft/Paxos)

**Problems for collaborative editing**:
1. **Latency**: User must wait for global coordination before seeing their edit
2. **Availability**: Network partition = no editing allowed
3. **Unnecessary**: Users don't need globally consistent view for text editing

### Why Not Plain Eventual Consistency?

Eventual consistency only guarantees convergence, not ordering.

**Problems**:
1. **Confusing UX**: Your own edits might appear out of order
2. **Lost context**: You might see a reply before the original message
3. **Broken dependencies**: A deletion might appear before the insert it deletes

### Why Causal Consistency?

Causal consistency provides these guarantees:

1. **Read your writes**: You always see your own operations in order
2. **Monotonic reads**: Once you see something, you don't "unsee" it
3. **Causal ordering**: If A happened-before B, everyone sees A before B
4. **Concurrent freedom**: Operations without causal relationship may appear in different orders

### Happens-Before Relationship

```
Operation A happens-before Operation B if:
1. A and B are from same client, and A was created first
2. B references something created by A
3. There exists C where A happens-before C and C happens-before B

If neither A happens-before B nor B happens-before A:
  → A and B are concurrent
  → May appear in any order (but deterministically!)
```

### Example Scenario

```
Timeline:
  t1: User A types "Hello" (op A1)
  t2: User B types "World" (op B1)
  t3: User A sees B's edit, adds "!" (op A2)

Causal relationships:
  A1 → A2 (same user)
  B1 → A2 (A2 depends on seeing B1)
  A1 ∥ B1 (concurrent)

Valid orderings:
  ✓ A1, B1, A2
  ✓ B1, A1, A2
  ✗ A2, A1, B1 (violates A1 → A2)
  ✗ A2, B1, A1 (violates B1 → A2)
```

### How CRDTs Provide Causal Consistency

Our CRDT design inherently provides causal consistency through:

1. **State Vectors**: Track what each client has seen
   ```typescript
   // Client only sends ops after incorporating all known ops
   if (canApply(op, stateVector)) {
     apply(op);
     stateVector[op.client] = op.clock;
   } else {
     buffer(op);  // Wait for dependencies
   }
   ```

2. **Operation Dependencies**: Each operation references its causal parents
   ```typescript
   interface Operation {
     id: { client: number; clock: number };
     origin: ItemID;  // Causal dependency
     // ...
   }
   ```

3. **Deterministic Merge**: Concurrent operations merge deterministically
   - Same set of operations → same final state
   - Order of application doesn't matter (commutativity)

## Consequences

### Positive

1. **Low latency**: No coordination needed for local operations
2. **High availability**: Works during network partitions
3. **Intuitive behavior**: Users see sensible ordering
4. **Offline support**: Naturally handles disconnected editing

### Negative

1. **Concurrent ambiguity**: Two users might see different orderings temporarily
2. **No global time**: Can't say "who typed first" for concurrent edits
3. **Complexity**: Must track causality, buffer out-of-order messages

### User Experience Implications

**What users experience**:
- Their own edits appear immediately
- Others' edits appear in a sensible order
- No "jumping" or reordering of already-seen content
- After sync, everyone has the same document

**What users might notice**:
- Concurrent edits might interleave differently for different users
- "Last writer wins" for concurrent formatting changes
- Conflict resolution is automatic but might not match intent

## Implementation Requirements

1. **State Vector Tracking**
   - Every client maintains its state vector
   - Included in sync requests for delta computation

2. **Operation Buffering**
   - Operations received out of causal order are buffered
   - Applied when dependencies arrive

3. **Causal Delivery**
   - Server ensures operations are delivered in causal order
   - Uses state vectors to determine readiness

4. **Idempotent Application**
   - Duplicate operations are safely ignored
   - Enables at-least-once delivery

## Alternatives Considered

### Session Consistency

Weaker than causal, only guarantees consistency within a session. Rejected because:
- Confusing when user has multiple tabs
- Doesn't match user expectations

### Strong Eventual Consistency (SEC)

Same as our choice - CRDTs provide SEC. This is essentially what we're implementing.

### Bounded Staleness

Guarantee data is at most N seconds old. Rejected because:
- Doesn't help with ordering
- Adds complexity without clear benefit for text editing

## References

- [Causal Consistency Definition](https://jepsen.io/consistency/models/causal)
- [CRDTs and Strong Eventual Consistency](https://hal.inria.fr/inria-00609399)
- [Lamport Clocks](https://lamport.azurewebsites.net/pubs/time-clocks.pdf)
- [Vector Clocks](https://en.wikipedia.org/wiki/Vector_clock)
