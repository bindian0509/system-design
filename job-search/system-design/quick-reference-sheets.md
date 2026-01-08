# System Design Quick Reference Sheets

> **Purpose**: One-pager summaries of each design for quick interview prep
> **Usage**: Review before interviews, use as mental framework during whiteboard sessions

---

## Design Portfolio Overview

| Design | Domain | Best For | Key Concepts |
|--------|--------|----------|--------------|
| Seller Payment System | Fintech | PhonePe, Razorpay, Stripe | Async processing, idempotency, state machines |
| Financial Clearing House | Fintech | Banks, NPCI, Visa | Multilateral netting, settlement, graph algorithms |
| Uber Eats Feed | Consumer | Swiggy, Zomato, DoorDash | Geo-indexing, ranking, caching |
| Uber Cart System | E-commerce | Flipkart, Amazon, Uber | Multi-tenant, offline-first, state sync |
| Crash Detection | IoT/ML | Insurance, Fleet | Stream processing, ML inference, real-time alerts |
| E-commerce Listing | Consumer | Flipkart, Amazon | Search, catalog, merchandising |

---

## 1. Seller-Side Payment System

### One-Liner
> Async payment system for paying sellers with aggregated payouts, idempotent processing, and comprehensive audit trails.

### Problem Statement
- E-commerce platform needs to pay sellers for their sales
- Payment gateway charges per-transfer fee → need to aggregate
- Must handle gateway delays (~1 min processing)
- Zero tolerance for duplicate or dropped payments

### Architecture Diagram (Mental Model)
```
OrderService → Queue → BalanceService → PayoutScheduler → PaymentProcessor → Gateway
                              ↓                                    ↓
                          Pending → Available              PENDING → PROCESSING → COMPLETED
                                                                          ↓
                                                                    Audit Log
```

### Key Components
| Component | Responsibility |
|-----------|----------------|
| Order Consumer | Listen to order events, update seller balances |
| Balance Service | Track pending/available balance per seller |
| Payout Scheduler | Trigger payouts based on schedule (daily/weekly/threshold) |
| Payment Processor | Execute payments via gateway with retry logic |
| Audit Service | Immutable log of all state transitions |

### Key Design Decisions
1. **Aggregation**: Batch orders per seller per payout cycle → O(sellers) fees instead of O(orders)
2. **Idempotency**: Every payment has idempotency key → prevents duplicates
3. **State Machine**: PENDING → PROCESSING → COMPLETED/FAILED → ensures exactly-once
4. **Settlement Window**: 7-day hold before balance becomes available (chargeback protection)

### State Machine
```
PENDING → PROCESSING → COMPLETED
                ↓
              FAILED → (retry) → PENDING
                ↓ (max retries)
             CANCELLED → DLQ
```

### Trade-offs
| Decision | Trade-off |
|----------|-----------|
| Aggregation | Lower fees but delayed payouts |
| Async processing | Scalable but complex failure handling |
| Idempotency | Safe but requires key management |

### Interview Tips
- Start with requirements clarification (volume, SLA, failure tolerance)
- Emphasize idempotency and exactly-once semantics
- Discuss settlement window for financial compliance
- Mention PCI-DSS if storing payment details

---

## 2. Financial Clearing House

### One-Liner
> Interbank settlement system using multilateral netting to minimize actual money movements between banks.

### Problem Statement
- Banks exchange millions of checks/transfers daily
- Moving money has costs (fees, liquidity requirements)
- Need to "net out" obligations to minimize transfers
- Calculate pairwise balances + optimize settlements

### Algorithm Overview

**Part 1: Pairwise Balance Calculation**
```
Input: [Chase→BoA: $100, BoA→Chase: $60]
Output: Chase owes BoA $40

For each (BankA, BankB) pair where A < B alphabetically:
  balance = sum(A→B) - sum(B→A)
  if balance > 0: A owes B
  if balance < 0: B owes A
```

**Part 2: Multilateral Netting (Minimize Transfers)**
```
Input: Pairwise balances
Output: Minimum set of settlement instructions

Algorithm (Greedy):
1. Calculate net position per bank (all inflows - outflows)
2. Separate into creditors (positive) and debtors (negative)
3. Use max-heaps to match largest creditor with largest debtor
4. Generate transfer for min(credit, debt)
5. Repeat until all positions zero

Result: N-1 transfers for N banks (optimal)
```

### Example
```
9 transactions between 3 banks:
Gross: $5,757 in transfers

After netting:
  Chase pays Wells Fargo: $204
  BoA pays Wells Fargo: $183

Net: $387 in transfers
Netting Efficiency: 93.3%
```

### Key Design Decisions
| Decision | Rationale |
|----------|-----------|
| Decimal for amounts | Avoid floating-point errors |
| Immutable transactions | Audit trail, idempotency |
| Greedy heap-based netting | O(N log N), optimal transfer count |
| Two-phase settlement | Exactly-once guarantee with saga pattern |

### Interview Tips
- Start with simple example (3 banks)
- Explain pairwise calculation clearly first
- Then introduce netting optimization
- Discuss batch vs real-time trade-offs
- Mention AML/compliance for financial systems

---

## 3. Uber Eats Restaurant Feed

### One-Liner
> High-performance geo-indexed restaurant feed with personalized ranking serving 10K+ QPS at <200ms P99.

### Problem Statement
- Show restaurants that can deliver to user's location
- Handle 10M+ restaurants globally
- Personalized ranking by relevance
- Dynamic availability (breaks, closures, delivery zones)

### Architecture Diagram (Mental Model)
```
Client → API Gateway → Geo Cache → Geo Index (ES) → Ranking Service → DB
                          ↓                              ↓
                      H3/Geohash                    ML Scorer
```

### Key Components
| Component | Technology | Purpose |
|-----------|------------|---------|
| Geo Index | ElasticSearch | Geo_point queries |
| Geo Cache | Redis | H3 cell → restaurant IDs |
| Ranking Service | Custom + ML | Score by distance, rating, ETA |
| State Cache | Redis | Real-time availability |

### Spatial Indexing Strategy (H3 - Uber's Technology)
```
Resolution 6: ~3.2km edge → Rural
Resolution 7: ~1.2km edge → Suburban
Resolution 8: ~461m edge  → Urban
Resolution 9: ~174m edge  → Hyper-dense (Manhattan)
```

**Why H3 over Geohash:**
- Hexagons approximate circles better (delivery radius)
- All 6 neighbors equidistant (no corner artifacts)
- Native k-ring queries for radius search

### Caching Strategy
| Layer | TTL | Hit Rate |
|-------|-----|----------|
| CDN (static) | 24h | 95% |
| Geo-cell IDs | 60s | 80% |
| Restaurant details | 5min | 90% |
| User preferences | 30min | 85% |

### Ranking Formula
```python
score = w1 * distance_score +      # Closer is better
        w2 * rating_score +         # Higher rating better
        w3 * eta_score +            # Lower ETA better
        w4 * personalization_score  # User history
```

### Interview Tips
- Start with scale (10M restaurants, 10K QPS)
- Explain geo-indexing choice (H3 vs geohash)
- Discuss caching strategy for hot spots
- Cover dynamic filtering (closed restaurants)
- Mention sharding strategy for geo data

---

## 4. Uber Cart System

### One-Liner
> Multi-merchant cart supporting multiple fulfillment types, family accounts, offline-first behavior, and 3rd party integrations.

### Problem Statement
- Cart for Uber's full ecosystem (Eats, Grocery, Package)
- Multi-merchant carts (items from different stores)
- Family accounts with teen sub-users
- Works offline, syncs when online
- Third-party partner integrations (different capabilities)

### Architecture Diagram
```
Mobile App → API Gateway → Cart Service → Cart DB (sharded by user_id)
                               ↓
                             Kafka
                               ↓
            Order Service → Fulfillment Orchestrator → Delivery/Pickup/Ride
```

### Fulfillment Types
| Type | Flow |
|------|------|
| DELIVERY | Driver assigned → At merchant → In transit → Delivered |
| PICKUP | Order ready → User notified → User picks up |
| PICKUP_WITH_RIDE | Order + Ride booked → Ride to merchant → Pick up |

### Sub-User Access Model
```
VIEW_ONLY    → See parent's orders only
LIMITED      → Order with restrictions (spending, merchant, time)
SUPERVISED   → Requires parent approval
FULL         → All capabilities
```

### Offline-First Architecture
```
UI → State Manager → Local DB (SQLite/Realm)
         ↓
    Sync Queue → Sync Manager → Backend API
                       ↓
              Conflict Resolver
```

**Conflict Resolution:**
- Price changed → Remote wins (safety)
- Quantity conflict → Merge deltas
- Item deleted → Prompt user

### Partner Integration
```
Partner declares capabilities:
  - CREATE_ORDER: ✅
  - MODIFY_ORDER: ⚠️ (15 min window)
  - CANCEL_ORDER: ⚠️ (before preparing)
  - SUBSTITUTIONS: ✅
  - REAL_TIME_TRACKING: ❌
```

### Key Design Decisions
| Decision | Rationale |
|----------|-----------|
| Multi-merchant cart | UX - don't force separate checkouts |
| Event-driven (Kafka) | Loose coupling between services |
| Capability-based partners | Runtime validation of operations |
| Offline-first | Mobile users have spotty connectivity |

### Interview Tips
- Cover fulfillment polymorphism
- Explain sub-user permission model
- Discuss offline sync and conflict resolution
- Mention event sourcing for cart state
- Cover partner integration challenges

---

## 5. Trucking Crash Detection System

### One-Liner
> Real-time IoT system processing sensor data from 1M vehicles for instant crash detection and predictive warnings.

### Problem Statement
- 1M vehicles, 100+ telematics providers
- 10-50 data points per vehicle per second
- Detect crashes in <5 seconds
- Notify stakeholders in <30 seconds
- Predict high-risk patterns before incidents

### Architecture Diagram
```
1M Vehicles → 100+ Providers → API Gateway → Normalizer → Kafka (10M/s)
                                                              ↓
                                                         Flink → ML Models
                                                              ↓
                                                        Alert Router → SMS/Push
```

### Data Flow
```
Vehicle → Provider (~50ms) → Ingestion (~10ms) → Kafka → Flink → ML → Alert
                                                                           ↓
                                                              Total: ~500ms detection
                                                                     <30s notification
```

### Key Components
| Component | Technology | Purpose |
|-----------|------------|---------|
| Ingestion | REST/gRPC | Handle multiple provider formats |
| Normalizer | Custom | Unified schema from varied inputs |
| Stream Processing | Flink | Real-time event processing |
| ML Models | TensorFlow | Crash detection, severity classification |
| Alert Router | Custom | Priority-based notification routing |

### ML Pipeline
```
Features:
  - Accelerometer (sudden deceleration)
  - Gyroscope (vehicle orientation change)
  - Speed delta
  - GPS position change

Models:
  - Crash Detection (binary: crash/no-crash)
  - Severity Classification (minor/moderate/severe)
  - Predictive Risk (based on driver patterns)
```

### Flink Window Processing
```java
stream
  .keyBy(vehicleId)
  .window(TumblingEventTimeWindows.of(Time.seconds(5)))
  .process(new CrashDetectionFunction())
```

### Scale Parameters
| Metric | Value |
|--------|-------|
| Vehicles | 1,000,000 |
| Providers | 100+ |
| Events/second | 10-50M |
| Detection latency | <500ms |
| Notification latency | <30s |

### Interview Tips
- Start with scale (1M vehicles × 10-50 events/sec)
- Explain provider normalization challenge
- Cover Flink windowing for streaming
- Discuss ML model inference latency
- Mention late data handling strategies

---

## Interview Delivery Framework

### The 5-Step Approach

**1. Requirements (3-5 min)**
```
Functional: What does the system do?
Non-functional: Scale, latency, availability
Out of scope: What are we NOT designing?
```

**2. High-Level Design (10 min)**
```
Draw boxes and arrows
Name each component
Explain data flow
```

**3. Deep Dive (15-20 min)**
```
Pick 2-3 components to detail
Discuss data models
Cover APIs
```

**4. Scale & Trade-offs (5-10 min)**
```
Bottlenecks and solutions
Sharding strategy
Caching layers
```

**5. Wrap-up (2-3 min)**
```
Summarize key decisions
Mention extensions
Ask if interviewer wants to go deeper on anything
```

### Common Follow-up Questions

| Topic | Questions to Prepare |
|-------|---------------------|
| Scaling | "How would you handle 10x traffic?" |
| Failure | "What happens if X fails?" |
| Consistency | "How do you handle concurrent writes?" |
| Migration | "How would you migrate from monolith?" |
| Cost | "How would you reduce infrastructure costs?" |

---

## Quick Reference: Technology Choices

| Problem | Technology | Why |
|---------|------------|-----|
| Async processing | Kafka | Durability, replay, ordering |
| Geo-indexing | ElasticSearch + H3 | Native geo queries |
| Caching | Redis | Speed, data structures |
| Primary DB | PostgreSQL | ACID, JSON support |
| Stream processing | Flink | Exactly-once, windowing |
| Scheduling | Temporal/Airflow | Reliability, visibility |
| ML serving | TensorFlow Serving | Low-latency inference |
| Search | ElasticSearch | Full-text, aggregations |

