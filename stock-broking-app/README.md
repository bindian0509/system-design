# Stock Broking App for Indian Equity Markets

This document is a FAANG-level system design interview write-up for building a stock broking and trading platform for Indian equity markets, similar in spirit to Zerodha.

The goal is not to replicate every regulatory or exchange-specific integration detail, but to produce a defensible large-scale design that handles millions of users, high market-open traffic, strict correctness requirements, and low-latency order handling.

## 1. Problem Statement

Design a stock broker trading application for Indian equity markets that allows retail users to:

- onboard and complete KYC
- maintain trading and demat accounts
- view live market data
- place, modify, and cancel orders
- track positions, holdings, margins, funds, and trade history
- receive contract notes, alerts, and compliance notifications

The platform should support millions of users and operate reliably during market peaks, especially around pre-open and opening minutes.

## 2. Indian Market Context

A credible design must account for the Indian ecosystem:

- Exchanges: NSE, BSE
- Segments: Equity cash first, extensible to F&O, commodities, currency
- Broker responsibilities:
  - user onboarding and KYC
  - order capture and risk validation
  - exchange connectivity
  - trade confirmations
  - funds and margin tracking
  - holdings and demat integration
- Depositories: CDSL, NSDL
- Clearing and settlement entities exist outside the app boundary, but integrations matter
- Market timings matter operationally:
  - pre-open burst traffic
  - market open spike
  - intraday steady flow
  - closing spike
  - off-hours back-office processing

For interview scope, we focus on the broker platform, not exchange internals.

## 3. Scope

### In Scope

- mobile/web API backend
- authentication and session management
- market data distribution inside the broker app
- order management
- risk management and margin checks
- portfolio, holdings, ledger, and reporting views
- notifications
- observability, reliability, and scale strategy

### Out of Scope

- building the stock exchange matching engine
- deep settlement engine implementation
- advanced charting internals
- full tax/reporting rule engine
- AML/fraud models in depth

## 4. Functional Requirements

1. User signup, login, MFA, device/session management
2. KYC profile, bank account linking, nominee details, account status
3. Watchlists and instrument search
4. Live quotes, market depth, OHLC, circuit limits
5. Order placement:
   - market
   - limit
   - stop-loss
   - CNC / delivery
   - MIS / intraday
6. Order modify and cancel
7. Order book, trade book, positions, holdings
8. Funds, margins, realized/unrealized P&L
9. Notifications for order status changes and compliance events
10. End-of-day statements and contract notes

## 5. Non-Functional Requirements

1. High correctness:
   - no duplicate order submission
   - accurate user balances and positions
   - auditable state transitions
2. High availability during market hours
3. Low latency for order placement and status visibility
4. Massive fan-out for market data
5. Strong consistency where money, orders, and positions are involved
6. Eventual consistency acceptable for analytics, reports, and dashboards
7. Full audit trail for compliance and dispute handling
8. Strong security and least-privilege access

## 6. Traffic and Capacity Assumptions

Assume:

- 20 million registered users
- 3 million DAU on active trading days
- 800,000 to 1.5 million concurrent users during market hours
- 150,000 to 300,000 concurrent quote-stream subscribers at peak
- 50,000 to 100,000 order requests per second during peak bursts
- market data updates for thousands of instruments, with very high fan-out

Interview note:
Peak behavior matters more than daily averages. Market open is the real design driver.

## 7. High-Level Architecture

```text
Clients (iOS / Android / Web)
        |
   API Gateway + WAF + Rate Limiting
        |
   Auth Service
   User/Profile Service
   Portfolio Service
   Funds/Margin Service
   Order API Service
   Market Data Gateway
   Notification Service
        |
   -----------------------------------------
   |                  |                    |
Order/Risk Plane   Data Plane         Backoffice Plane
   |                  |                    |
OMS API           Market Data Ingest   Reporting/Statements
RMS Engine        Tick Normalization   Reconciliation
Order Router       Quote Fan-out       Ledger/Contract Notes
Exchange Adapters  Cache/WebSockets    Compliance Jobs
   |
NSE/BSE Connectivity
```

Core separation:

- Order/Risk Plane handles money-sensitive synchronous flows
- Data Plane handles heavy read and streaming traffic
- Backoffice Plane handles slower operational and reporting workflows

This separation prevents quote traffic from affecting order correctness.

## 8. Core Components

### 8.1 API Gateway

Responsibilities:

- request authentication
- rate limiting
- bot and abuse control
- request routing
- API versioning

Important rule:
Order APIs should have stricter rate policies than read APIs.

### 8.2 Auth Service

Handles:

- login
- MFA/OTP/TOTP
- token issuance
- session revocation
- device trust

Design choice:
Use short-lived access tokens and refresh flows. For highly sensitive actions such as adding bank accounts or API key generation, require step-up auth.

### 8.3 Market Data Platform

Responsibilities:

- ingest exchange/vendor feeds
- normalize instrument identifiers
- publish LTP, bid/ask, OHLC, volume, depth
- distribute via WebSocket/SSE to clients

Typical design:

1. Feed handlers ingest raw ticks
2. Normalizers convert to internal schema
3. Pub-sub backbone distributes by instrument/topic
4. In-memory fan-out gateways manage client subscriptions
5. Redis/in-memory cache stores latest quote snapshot

Key scaling idea:
Do not route market data through the same path as order placement.

### 8.4 Order Management System (OMS)

OMS is the system of record for the order lifecycle.

Responsibilities:

- create order records
- assign broker order IDs
- track state transitions
- persist order timeline
- coordinate with RMS and exchange adapters
- expose order book and status APIs

Example order states:

- RECEIVED
- VALIDATED
- REJECTED_RISK
- SENT_TO_EXCHANGE
- ACKNOWLEDGED
- PARTIALLY_FILLED
- FILLED
- CANCEL_PENDING
- CANCELLED
- EXCHANGE_REJECTED

Design rule:
Every state transition must be idempotent and auditable.

### 8.5 Risk Management System (RMS)

RMS performs pre-trade validation before orders reach the exchange.

Checks include:

- account enabled status
- product eligibility
- available cash or margin
- position limits
- price band / circuit checks
- quantity freeze limits
- risk blocks / compliance holds

RMS must be fast and conservative.

Tradeoff:

- fully synchronous RMS gives correctness
- aggressive precomputation of user margin state reduces latency

### 8.6 Exchange Connectivity Layer

Responsibilities:

- adapt internal order format to exchange protocol
- maintain persistent sessions with exchange gateways
- handle ACK/reject/fill/cancel callbacks
- reconnect and replay safely after failures

Critical property:
This layer must support exactly-once observable behavior from the user perspective, even if underlying connectivity is at-least-once.

### 8.7 Portfolio and Holdings Service

Serves:

- current holdings
- net positions
- intraday positions
- average buy price
- realized/unrealized P&L

Data sources:

- execution events
- end-of-day settlement files
- depository sync for final holdings truth

Pattern:
Use event-driven materialized views for fast reads, with reconciliation against back-office truth.

### 8.8 Funds and Ledger Service

Tracks:

- cash balance
- blocked margin
- realized proceeds
- withdrawals
- payout status

This requires stronger consistency than watchlists or quote views.

### 8.9 Notification Service

Channels:

- push
- SMS
- email
- in-app notifications

Events:

- order accepted/rejected
- trade executed
- margin shortfall
- payout processed
- compliance communications

Use async event-driven delivery. Notifications should never block order acceptance.

## 9. Order Placement Flow

### 9.1 Happy Path

1. Client sends `PlaceOrder`
2. API Gateway authenticates and rate-limits
3. Order API validates request schema and idempotency key
4. OMS creates order with `RECEIVED`
5. RMS performs synchronous risk checks
6. If passed, OMS moves order to `VALIDATED`
7. Exchange adapter sends order to exchange
8. Exchange ACK received
9. OMS updates state to `ACKNOWLEDGED`
10. Fill events update trade book, positions, ledger, and notifications

### 9.2 Failure Cases

- duplicate client retries
  - solved with idempotency key plus broker order ID mapping
- RMS timeout
  - fail closed, do not send order
- exchange ACK delayed
  - show `PENDING/PROCESSING`, reconcile asynchronously
- exchange adapter restart
  - recover from durable order log and callback replay

## 10. Data Model

### Core Entities

- User
- TradingAccount
- DematAccount
- Instrument
- Order
- Trade
- Position
- Holding
- LedgerEntry
- MarginSnapshot
- Notification

### Example Order Schema

```json
{
  "order_id": "BROKER_20260506_ABC123",
  "client_order_id": "uuid-from-client",
  "user_id": "U123",
  "instrument_id": "NSE_EQ_INFY",
  "exchange": "NSE",
  "side": "BUY",
  "order_type": "LIMIT",
  "product": "CNC",
  "quantity": 10,
  "price": 1450.50,
  "status": "ACKNOWLEDGED",
  "created_at": "2026-05-06T09:15:01Z",
  "updated_at": "2026-05-06T09:15:02Z"
}
```

## 11. Storage Strategy

Different workloads need different databases.

### OLTP Database

Use a relational database for:

- users
- accounts
- orders
- trades
- ledger
- audit records

Why relational:

- transactional guarantees
- indexing flexibility
- strong consistency
- auditable mutations

Sharding approach:

- shard by `user_id` for user-centric datasets
- keep reference data separate
- ensure order lookups by both `order_id` and `user_id`

### Cache

Use Redis or equivalent for:

- session data
- hot quote snapshots
- rate limit counters
- recent margin snapshots
- websocket subscription metadata

### Event Log / Stream

Use Kafka or equivalent for:

- order events
- trade events
- market data fan-out pipeline
- notification events
- audit feed
- reconciliation jobs

### Analytical Store

Use OLAP/data lake for:

- reports
- BI
- product analytics
- risk analytics

Do not run heavy analytics on the trading OLTP store.

## 12. API Design

Example APIs:

```text
POST   /v1/orders
PUT    /v1/orders/{orderId}
DELETE /v1/orders/{orderId}
GET    /v1/orders
GET    /v1/trades
GET    /v1/positions
GET    /v1/holdings
GET    /v1/funds
GET    /v1/instruments/search?q=infy
WS     /v1/marketdata/stream
```

Important API detail:
`POST /orders` should require a client-generated idempotency key.

## 13. Consistency Model

Not everything needs the same consistency.

### Strong Consistency Required

- order acceptance decision
- ledger updates
- margin block/unblock
- final persisted order state

### Eventual Consistency Acceptable

- dashboard summaries
- notifications
- analytics
- P&L widgets with slight lag

Interview signal:
Strong consistency is expensive. Use it only where business correctness demands it.

## 14. Scaling Strategy

### Read Scaling

- CDN for static assets
- quote caches
- websocket fan-out clusters
- read replicas for non-critical reads
- precomputed portfolio views

### Write Scaling

- partition orders by user/account
- use append-only order event streams
- isolate OMS write path from reporting
- async downstream consumers for non-blocking side effects

### Burst Handling

Peak load is bursty, not smooth.

Design for:

- queue buffering between ingress and async consumers
- controlled backpressure
- circuit breakers on non-critical services
- priority preservation for order path over secondary features

## 15. Reliability and Fault Tolerance

### Multi-AZ Design

All critical services should run across multiple availability zones.

### Failure Scenarios

1. Market data feed disruption
   - show stale quote indicator
   - keep order plane isolated
2. Redis failure
   - degrade watchlists/session optimizations
   - do not lose durable orders
3. OMS node failure
   - stateless nodes recover from database + event log
4. Exchange adapter disconnect
   - stop fresh sends if state is uncertain
   - reconcile before replay
5. Database primary issue
   - promote standby
   - maintain strict recovery and reconciliation procedures

### Disaster Recovery

- periodic snapshots
- cross-region backups
- immutable audit/event storage
- documented replay and reconciliation runbooks

For interview:
Cross-region active-active for trading is hard because of consistency and regulatory constraints. Active-passive is easier to defend.

## 16. Security and Compliance

Requirements:

- encryption in transit and at rest
- HSM/KMS-backed key management
- RBAC for internal operators
- audit logs for every privileged action
- PII segregation and masking
- secure secrets management
- suspicious activity monitoring

Operational controls:

- maker-checker flows for sensitive back-office actions
- immutable audit trail
- device fingerprinting and anomaly detection

## 17. Observability

Track:

- order placement latency p50/p95/p99
- RMS decision latency
- exchange ACK latency
- rejection rate by reason
- websocket connection count
- quote lag and staleness
- consumer lag on event streams
- DB replication lag
- failed notifications

Also capture:

- distributed traces on order path
- structured order lifecycle logs
- business dashboards for fill rate and risk rejects

## 18. Back-of-the-Envelope Capacity

Example:

- 100k peak order requests/sec
- average order payload 1 KB
- raw ingress about 100 MB/sec before replication and overhead
- if each order produces 5 to 10 internal events, internal event throughput becomes 500k to 1M events/sec

Market data is often larger operationally than order traffic because:

- thousands of instruments
- continuous tick updates
- huge subscription fan-out

This is why market data infrastructure must be independently scalable.

## 19. Bottlenecks and Interview Tradeoffs

### Bottleneck 1: Market Open Burst

Mitigation:

- aggressive autoscaling before market open
- warm websocket clusters
- precomputed margin snapshots
- queue-based smoothing for async consumers

### Bottleneck 2: Database Contention on Order Tables

Mitigation:

- append-heavy design
- careful indexing
- partitioning by user/account/time
- offload reads to materialized views

### Bottleneck 3: Duplicate Orders From Client Retries

Mitigation:

- mandatory idempotency keys
- deterministic duplicate detection window

### Bottleneck 4: Inconsistent User View During Partial Failures

Mitigation:

- order state machine as source of truth
- timeline visibility in UI
- background reconciliation jobs

## 20. Suggested Deep-Dive Discussion in Interview

If the interviewer asks to go deeper, pick one:

1. Order lifecycle and exactly-once user semantics
2. RMS design and margin calculations
3. Market data fan-out architecture
4. Data partitioning for orders and positions
5. Failure recovery when exchange callbacks are delayed or duplicated

This is usually better than trying to over-design everything at once.

## 21. Evolution Roadmap

### V1

- equities only
- core order types
- single-region multi-AZ
- basic market data
- fundamental holdings and positions

### V2

- options/futures
- richer margin engine
- advanced charting
- broker APIs for algo trading
- recommendation and analytics layer

### V3

- multi-broker partnerships
- portfolio analytics and tax intelligence
- advanced risk and fraud systems

## 22. Crisp Interview Summary

The design should separate the low-latency, correctness-critical order path from the high-fan-out market data path. Orders go through an OMS + RMS + exchange adapter pipeline with strong consistency, idempotency, auditability, and durable state transitions. Read-heavy user experiences such as quotes, holdings views, and notifications are served through caches, materialized views, and async event-driven services. The system is scaled for market-open bursts, not average traffic, and reliability is driven by multi-AZ deployment, replayable event logs, reconciliation workflows, and strict observability.

## 23. A Good 2-Minute Verbal Answer

If asked to summarize verbally:

> I would design the broker platform around three separated planes: the order/risk plane, the market data plane, and the back-office plane. The order path is synchronous and correctness-first: client request, idempotency check, OMS persistence, RMS validation, exchange routing, and then event-driven updates for trades, positions, and notifications. Market data is independently ingested, normalized, and fanned out through websocket gateways with heavy caching because it is a much larger read-scaling problem than the order path. For storage, I’d use a relational system for orders, trades, ledger, and audit trails, Kafka for event propagation, Redis for hot caches, and derived materialized views for user dashboards. I’d design explicitly for market-open bursts, multi-AZ resilience, replay and reconciliation after failures, and strong consistency only for balances, margins, and final order state.

## 24. What Interviewers Usually Evaluate

- Did you separate critical write paths from noisy read paths?
- Did you identify correctness vs latency tradeoffs?
- Did you handle burst traffic instead of average traffic?
- Did you define clear data ownership and consistency boundaries?
- Did you account for Indian broker realities like exchanges, KYC, margins, holdings, and settlement integration?

If you can defend those five points clearly, the design is already at a strong interview level.
