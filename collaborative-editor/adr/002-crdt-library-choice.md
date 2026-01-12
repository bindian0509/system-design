# ADR-002: Yjs-style CRDT Architecture

## Status

**Accepted**

## Context

Having decided to use CRDTs (see [ADR-001](001-crdt-vs-ot.md)), we need to choose a specific CRDT implementation approach. The main options are:

1. **Yjs-style**: Position-based, optimized for text, smaller wire format
2. **Automerge-style**: Actor-based, general-purpose, richer metadata
3. **Custom implementation**: Build from scratch for our specific needs

## Decision

We will use a **Yjs-inspired architecture** for our CRDT implementation.

For production, we would use the actual Yjs library or Y-CRDT (Rust port). For learning purposes in this design, we specify a Yjs-compatible approach.

## Rationale

### Comparison of CRDT Flavors

| Aspect | Yjs-style | Automerge-style |
|--------|-----------|-----------------|
| Memory overhead | Lower (~25 bytes/char) | Higher (~40 bytes/char) |
| Wire format size | Smaller deltas | Larger deltas |
| Rich text support | Excellent (designed for it) | Good (improving) |
| Offline performance | Optimized | Good |
| JSON document support | Y.Map, Y.Array | Native JSON CRDT |
| Maturity | 7+ years, battle-tested | 5+ years, active development |
| Production users | Notion, Figma, Coda | Some, growing |

### Why Yjs-style Wins

1. **Designed for text editing**
   - Y.Text is specifically optimized for rich text
   - Marks (formatting) are first-class citizens
   - Block-level structures supported natively

2. **Memory efficiency matters**
   - 100KB document = ~4MB CRDT state with Yjs
   - Same document = ~6MB with Automerge
   - At scale (10,000 documents), this is significant

3. **Delta encoding**
   - Yjs updates are typically 50-70% smaller than Automerge
   - Critical for mobile and low-bandwidth scenarios
   - Reduces server bandwidth costs

4. **Proven at scale**
   - Notion uses Yjs for millions of documents
   - Figma's CRDTs are Yjs-inspired
   - Linear, Coda, and others validate the approach

### Key Yjs Concepts We Adopt

#### Item Structure
```typescript
interface Item {
  id: ItemID;           // {client, clock} - globally unique
  content: any;         // Text, embed, or nested structure
  origin: ItemID;       // Left neighbor at creation
  rightOrigin: ItemID;  // Right neighbor at creation
  left: ItemID;         // Current left neighbor
  right: ItemID;        // Current right neighbor
  deleted: boolean;     // Tombstone flag
}
```

#### State Vector
```typescript
// Tracks what operations each client has produced
type StateVector = { [clientId: number]: number };
```

#### Document Structure
```typescript
// Composable CRDT types
Y.Doc      // Root container
Y.Text     // Rich text with marks
Y.Array    // Ordered list
Y.Map      // Key-value store
```

### Why Not Automerge

Automerge has compelling features but doesn't fit our use case as well:

1. **Heavier metadata**: Actor history tracking adds overhead
2. **General-purpose design**: We specifically need text editing
3. **Binary format changes**: Recent format migrations add risk
4. **Less text-focused**: Y.Text has more mature rich text support

### Why Not Build from Scratch

1. **Correctness is hard**: CRDTs have subtle edge cases
2. **Time to market**: Yjs-style is well-documented
3. **Community knowledge**: Easier to hire/onboard with known patterns
4. **Testing**: Can validate against reference implementations

## Consequences

### Positive

1. **Efficient text editing**: Yjs is purpose-built for this
2. **Smaller payloads**: Better mobile experience, lower costs
3. **Rich ecosystem**: Editor bindings (ProseMirror, Slate, etc.)
4. **Proven patterns**: Can learn from Notion, Figma experiences

### Negative

1. **Less flexible**: Optimized for text, not arbitrary JSON
2. **Documentation gaps**: Some advanced features poorly documented
3. **Vendor adjacent**: Heavily influenced by one library's choices

### Risks

1. **Yjs divergence**: If Yjs changes direction, we must adapt
   - Mitigation: Our design is Yjs-inspired, not Yjs-dependent

2. **Complex nested structures**: Tables, embeds need careful design
   - Mitigation: Follow established patterns from Notion's engineering blog

## Implementation Notes

### Binary Encoding

We adopt Yjs's efficient binary encoding:
- Variable-length integers for IDs
- Client ID table for compression
- Delta-encoded clocks
- Run-length encoding for content

### Integration with Editors

Yjs has bindings for major editors:
- y-prosemirror (ProseMirror)
- y-codemirror (CodeMirror)
- y-slate (Slate)
- y-quill (Quill)

This ecosystem is a significant advantage.

## References

- [Yjs GitHub](https://github.com/yjs/yjs)
- [Yjs Internals](https://github.com/yjs/yjs/blob/main/INTERNALS.md)
- [Y-CRDT (Rust port)](https://github.com/y-crdt/y-crdt)
- [Automerge](https://automerge.org/)
- [Notion Engineering Blog on CRDTs](https://www.notion.so/blog/data-model-behind-notion)
