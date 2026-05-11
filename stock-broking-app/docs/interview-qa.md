# Mock Interview Q&A: Stock Broking App for Indian Equity Markets

This document is a mock system design interview sheet for a FAANG-level discussion on building a stock broker platform similar to Zerodha for India.

Use it to practice:

- opening structure
- tradeoff articulation
- deep-dive follow-ups
- failure scenario handling

## 1. How would you start the interview?

I would first clarify scope. I’d confirm whether we are designing only the broker platform and not the exchange matching engine, and whether we should focus on equities first with room to extend into F&O later. Then I’d identify the most important requirements: low-latency order placement, correctness for balances and positions, and massive read fan-out for market data. After that I’d propose a high-level design that separates the order path from the quote distribution path.

## 2. What are the core functional requirements?

- user onboarding and authentication
- live quote streaming
- order placement, modification, and cancellation
- order book and trade book
- positions, holdings, and funds
- notifications and statements

## 3. What are the core non-functional requirements?

- correctness for orders and balances
- low latency for trading actions
- high availability during market hours
- resilience during market-open spikes
- full auditability
- strong security and access control

## 4. What is the most important architectural idea in this design?

The most important decision is to separate the correctness-critical order and risk path from the very high-fan-out market data path. These two workloads have different scaling patterns and different failure tolerance. If they share too much infrastructure, quote traffic can degrade trading reliability.

## 5. What services would you have at a high level?

- API gateway
- auth service
- order API
- OMS
- RMS
- exchange adapters
- market data ingest and websocket gateways
- portfolio service
- funds/ledger service
- notification service
- reporting and reconciliation jobs

## 6. Why do you need both OMS and RMS?

OMS manages the order lifecycle and is the source of truth for order states. RMS decides whether the order is allowed before it goes to the exchange. Separating them keeps risk policy independent from lifecycle management and makes the system easier to evolve and reason about.

## 7. Describe the order placement flow.

The client sends an order request with an idempotency key. The gateway authenticates and rate-limits it. The order API validates schema and deduplicates retries. OMS persists the initial order state. RMS performs synchronous checks like margin and product eligibility. If validation passes, OMS transitions the order to a validated state and sends it through exchange adapters. Exchange responses then drive further OMS transitions, and downstream events update positions, funds, and notifications.

## 8. Why is idempotency mandatory?

Because order placement is retried under real network failures. Without idempotency, a timeout at the client can produce duplicate orders. In a trading system that is a correctness failure, not just a UX issue. A client-generated idempotency key plus broker-side mapping is required.

## 9. What consistency model would you choose?

I would use strong consistency for order acceptance, ledger changes, margin blocking, and final persisted order states. I would accept eventual consistency for dashboards, notifications, P&L widgets, and reports. This keeps correctness where it matters while preserving scalability.

## 10. What database would you use?

For orders, trades, ledger, and audit records, I would use a relational OLTP system because transactional integrity matters. For caching and hot state, I’d use Redis or in-memory stores. For event propagation, I’d use a stream platform like Kafka. For analytics and reporting, I’d use a separate analytical store.

## 11. How would you shard the system?

I would shard user-centric transactional data by `user_id` or trading account ID, because most queries and invariants are naturally scoped to an account. Reference data like instruments can be stored separately. I would also partition event streams by keys that preserve ordering where needed, such as account ID or order ID.

## 12. How do you scale market data?

Market data is a fan-out problem more than a compute problem. I would ingest and normalize exchange feeds once, partition by instrument or topic, keep the latest quote in memory, and distribute via websocket gateways that track client subscriptions. This path should be horizontally scalable and isolated from order placement.

## 13. How do you handle market-open spikes?

I would explicitly design for burst capacity rather than average load. That means pre-scaling gateway and websocket capacity, warming caches before market open, precomputing hot risk snapshots where safe, and protecting order APIs with stronger priority and tighter rate limiting than read-heavy APIs.

## 14. What happens if RMS is down or slow?

The system should fail closed. If RMS cannot make a safe decision, the order should not be sent to the exchange. In trading, uncertainty should not result in accidental acceptance.

## 15. What happens if the exchange adapter loses connectivity?

New outbound sends should pause if state is uncertain. Orders already persisted in OMS remain durable. Once connectivity is restored, the adapter should reconcile exchange-visible state before replaying or resending. The design must avoid double submission under reconnect scenarios.

## 16. How do you keep positions and holdings up to date?

I would use execution events to update near-real-time positions and intraday views. Final holdings truth may also depend on settlement and depository integrations, so I’d maintain materialized read models for fast UX and periodically reconcile them against back-office sources.

## 17. How do you handle duplicate callbacks from external systems?

Every external callback must be processed idempotently. That usually means a durable event ID, deduplication keys, or deterministic state transition checks. If a duplicate fill or ACK arrives, OMS should recognize it and avoid corrupting state.

## 18. What are the hardest parts of this system?

- exactly-once user semantics over unreliable networks
- market-open burst handling
- low-latency RMS at scale
- exchange connectivity failure recovery
- maintaining user trust through consistent visible state

## 19. How do you design the UI state during partial failures?

The UI should reflect the OMS state machine rather than pretending every request is instantly final. If exchange confirmation is delayed, the order can be shown as processing or pending exchange acknowledgement. A transparent timeline is better than hiding uncertainty.

## 20. What security controls are important?

- MFA and device trust
- encryption in transit and at rest
- RBAC for operators
- audit logs for privileged actions
- PII segregation and masking
- secure secrets management
- anomaly detection for abuse and fraud

## 21. How would you observe the system?

I would track:

- order placement latency
- RMS latency
- exchange ACK latency
- rejection rate by reason
- websocket connection count
- market data lag
- event consumer lag
- database replication lag

I would also keep per-order structured traces for debugging user complaints and operational incidents.

## 22. What if the interviewer asks you to simplify?

I would say that V1 can support equities only, basic order types, single-region multi-AZ deployment, and limited derived analytics. The core idea to preserve even in a simplified version is the separation of order/risk from market data distribution.

## 23. What if the interviewer asks about tradeoffs?

The main tradeoff is between correctness and latency. I would spend consistency budget only on the financial invariants: orders, margins, and ledger. For everything else, I’d lean on event-driven asynchronous propagation. Another tradeoff is complexity versus resilience: replay and reconciliation add complexity, but in a broker they are necessary, not optional.

## 24. What if the interviewer asks why not use a single database for everything?

A single database can work at small scale, but it becomes a bad fit here because the workloads are too different. Trading writes need strong consistency and low contention, quote traffic needs high fan-out and in-memory distribution, and analytics needs large scans. Mixing them creates avoidable coupling and bottlenecks.

## 25. What if the interviewer asks about CAP or distributed systems theory?

I would explain it in practical terms. For trading decisions and ledger mutations, I prefer consistency over availability under uncertainty. For dashboards and notifications, temporary staleness is acceptable. The design is not ideologically CP or AP everywhere; it uses different consistency choices for different business invariants.

## 26. What are good questions to ask the interviewer?

- Are we designing only equities or also derivatives?
- Should I include onboarding and KYC, or focus only on trading?
- Do you want deeper detail on order flow, storage, or scaling?
- Should I optimize primarily for peak market-hours latency or for operational simplicity?

## 27. What is a strong closing summary?

I would summarize the system as three separated planes: order and risk, market data, and back office. The order plane is synchronous, durable, and correctness-first. The market data plane is high-throughput and horizontally scalable. The back-office plane is event-driven and reconciliation-heavy. That separation, combined with idempotency, auditable state transitions, and burst-oriented scaling, is what makes the design credible for a large Indian retail broker.

## 28. Practice 2-Minute Answer

I’d design the broker around a strict separation of concerns. The trading path would go through gateway, order API, OMS, RMS, and exchange adapters, with durable state transitions and idempotency on every request and callback. The market data path would separately ingest and normalize exchange feeds, then fan them out through websocket gateways backed by in-memory caches, so quote volume cannot disrupt order placement. For storage, I’d use a relational system for orders, trades, ledger, and audit, a stream platform for propagation and replay, and caches plus materialized views for user-facing reads like holdings and positions. I’d design for market-open bursts, multi-AZ reliability, and replay plus reconciliation after failures, while using strong consistency only where financial correctness requires it.
