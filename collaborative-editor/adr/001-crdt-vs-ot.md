# ADR-001: CRDT over Operational Transformation

## Status

**Accepted**

## Context

We need to choose a conflict resolution strategy for concurrent document editing. The two main approaches are:

1. **Operational Transformation (OT)**: Transform operations against each other to maintain consistency
2. **Conflict-free Replicated Data Types (CRDTs)**: Data structures that automatically merge without conflicts

Our system has these requirements:
- Full offline support (edit while disconnected, sync later)
- Rich text editing (formatting, tables, embedded media)
- 10-100 concurrent editors per document
- Sub-second sync latency when online

## Decision

We will use **CRDTs** for conflict resolution.

## Rationale

### Comparison Matrix

| Criteria | CRDT | OT | Winner |
|----------|------|-----|--------|
| Offline Support | Native - operations merge automatically | Requires central server for transformation | CRDT |
| Complexity Location | In the data structure (contained) | In transformation functions (spread out) | CRDT |
| Correctness Guarantee | Mathematical (commutativity, idempotency) | Algorithmic (TP1, TP2 puzzles are hard) | CRDT |
| State Size | Grows with history (needs compaction) | Minimal (current state only) | OT |
| Implementation Difficulty | Well-understood libraries exist | Many subtle bugs in practice | CRDT |
| Latency | Can apply locally immediately | May need server round-trip | CRDT |
| Industry Adoption | Figma, Notion, Linear | Google Docs, Microsoft Office | Tie |

### Key Factor: Offline Support

Our requirement for **full offline support** is the decisive factor:

**With OT**:
- Operations must be transformed relative to concurrent operations
- This requires knowing all concurrent operations
- Offline means you can't know what others did
- Syncing after offline requires complex server-side reconciliation
- Many edge cases and failure modes

**With CRDT**:
- Each operation is self-contained with a unique ID
- Operations commute - order doesn't matter
- After offline, just send your operations and receive theirs
- Automatic merge with mathematical guarantee of convergence
- No special handling for offline scenario

### Addressing CRDT Downsides

**State size growth**: We mitigate this with:
- Periodic snapshots (see [ADR-004](004-presence-separation.md))
- Tombstone garbage collection
- State compaction when clients acknowledge snapshots

**Implementation complexity**: We leverage:
- Yjs-inspired architecture (battle-tested at Notion, etc.)
- Comprehensive property-based testing
- Well-understood invariants to verify

### OT's Hidden Complexity

Google Docs uses OT, but:
- They have thousands of engineering hours invested
- Still have subtle bugs reported regularly
- Their OT implementation is not open source
- Known issues: TP2 puzzle, priority puzzle, string-wise transformation

The academic literature on OT correctness is fraught with retracted proofs and discovered bugs in "proven" algorithms.

## Consequences

### Positive

1. **True offline-first**: Users can work offline indefinitely, sync works automatically
2. **Simpler server**: No transformation logic, just merge and broadcast
3. **Mathematical confidence**: CRDT properties are provable, not just tested
4. **Industry momentum**: Modern tools (Figma, Notion) validate this approach

### Negative

1. **State overhead**: ~25 bytes per character vs ~1 byte for plain text
2. **Compaction complexity**: Need snapshot/GC system (additional infrastructure)
3. **Learning curve**: Team must understand CRDT concepts

### Risks

1. **Performance at scale**: Very large documents (100K+ chars) may be slow
   - Mitigation: Chunking, lazy loading, efficient binary encoding

2. **Rich text complexity**: Tables, embeds require careful CRDT design
   - Mitigation: Follow Yjs patterns, extensive testing

## Alternatives Considered

### Hybrid OT/CRDT

Some systems use OT when online and CRDT for offline. Rejected because:
- Doubles implementation complexity
- Edge cases at transition points
- CRDT handles online case well anyway

### Last-Writer-Wins

Simple timestamp-based resolution. Rejected because:
- Loses concurrent edits (unacceptable for collaborative editing)
- Only works for whole-document granularity

### Server-Authoritative with Rebasing

Server always wins, clients rebase local changes. Rejected because:
- Poor offline experience (changes may be rejected)
- Complex rebasing logic
- User may lose work

## References

- [A Comprehensive Study of CRDTs](https://hal.inria.fr/inria-00555588)
- [Yjs Internals](https://github.com/yjs/yjs/blob/main/INTERNALS.md)
- [Real Differences Between OT and CRDT](https://blog.kevinjahns.de/are-crdts-suitable-for-shared-editing/)
- [Google Wave OT Post-Mortem](https://en.wikipedia.org/wiki/Apache_Wave)
