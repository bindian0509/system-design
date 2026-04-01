# Digital Remittance Platform -- System Architecture

## Table of Contents

1. [Overview](#overview)
2. [Service Decomposition](#service-decomposition)
3. [Cross-Cutting Concerns](#cross-cutting-concerns)
4. [Tech Stack with Rationale](#tech-stack-with-rationale)
5. [Transfer Orchestration](#transfer-orchestration)
6. [Service Interaction Diagram](#service-interaction-diagram)
7. [Communication Patterns](#communication-patterns)
8. [Deployment Topology](#deployment-topology)
9. [Design Rationale](#design-rationale)

---

## Overview

This document describes the architecture of a digital remittance platform enabling cross-border money transfers. The platform allows senders to fund transfers via bank debit, card, or bank transfer, and delivers funds to recipients through bank deposit, mobile wallet, or cash pickup across multiple currency corridors.

The system handles regulatory compliance (KYC/AML/CFT), real-time FX quoting, multi-rail payout routing, and double-entry ledger accounting -- all under strict consistency and auditability requirements mandated by financial regulators.

**Key Non-Functional Requirements:**

| Requirement | Target |
|---|---|
| Transfer initiation latency (quote to confirmed) | < 2 seconds |
| Daily transfer volume | 500K--1M transactions |
| FX quote freshness | < 500ms staleness |
| System availability | 99.95% (excluding scheduled maintenance) |
| Audit trail retention | 7 years minimum |
| RPO / RTO | RPO < 1 min, RTO < 15 min |

---

## Service Decomposition

The platform is decomposed into 10 bounded-context services. Each service owns its data store, exposes a well-defined API contract, and communicates through a combination of synchronous REST/gRPC calls and asynchronous Kafka events.

### 1. User & KYC Service

**Responsibility:** User registration, authentication profile management, identity verification, document storage, and KYC tier management.

| Aspect | Detail |
|---|---|
| Data store | PostgreSQL (user profiles, KYC records) + S3 (identity documents) |
| Key entities | User, IdentityDocument, KYCVerification, KYCTier |
| External integrations | Onfido/Jumio (ID verification), Trulioo (global identity checks) |
| Sync APIs | `POST /users/register`, `GET /users/{id}/kyc-status`, `POST /users/{id}/verify` |
| Events produced | `user.registered`, `kyc.tier-upgraded`, `kyc.verification-failed` |
| Events consumed | None |

**KYC Tier Model:**

- **Tier 0** -- Email/phone verified. No transfers permitted.
- **Tier 1** -- Basic ID verified. Transfer limit: $1,000/month.
- **Tier 2** -- Enhanced due diligence (proof of address, source of funds). Transfer limit: $50,000/month.
- **Tier 3** -- Business accounts with full documentation. Custom limits.

The service enforces that transfer initiation requests are rejected unless the sender meets the minimum KYC tier required for the corridor and amount.

---

### 2. Quote Engine

**Responsibility:** Real-time FX rate retrieval, fee calculation, delivery time estimation, and quote locking with a guaranteed TTL.

| Aspect | Detail |
|---|---|
| Data store | Redis (quote cache, locked quotes), TimescaleDB (FX rate time-series) |
| Key entities | Quote, FXRate, FeeSchedule, CurrencyPair |
| External integrations | Reuters/Bloomberg (market rates), internal FX & Treasury Service |
| Sync APIs | `POST /quotes` (create), `GET /quotes/{id}` (retrieve locked quote) |
| Events produced | `quote.created`, `quote.expired`, `quote.locked` |
| Events consumed | `fx.rate-updated` |

**Quote Locking Mechanism:**

When a user requests a quote, the engine locks the FX rate for a configurable TTL (typically 30--60 seconds). The locked quote is stored in Redis with an expiry key. If the user confirms the transfer within the TTL, the locked rate is honored. If the TTL expires, the quote is invalidated and the user must request a new one.

**Fee Calculation:**

Fees are a function of: `(source_currency, target_currency, amount, funding_method, delivery_method, user_tier)`. The fee schedule is stored as a table of rules evaluated in priority order. The engine also applies any active promotional pricing.

---

### 3. Funding Service

**Responsibility:** Collect sender funds through multiple payment methods -- bank debit (ACH/SEPA), card charge (Visa/Mastercard), or bank transfer (wire/Faster Payments).

| Aspect | Detail |
|---|---|
| Data store | PostgreSQL (funding transactions, payment method tokens) |
| Key entities | FundingTransaction, PaymentMethod, FundingAttempt |
| External integrations | Stripe/Adyen (card processing), Plaid (bank account linking), banking APIs (ACH/SEPA) |
| Sync APIs | `POST /funding/collect`, `GET /funding/{id}/status` |
| Events produced | `funding.initiated`, `funding.completed`, `funding.failed` |
| Events consumed | `transfer.confirmed` (triggers fund collection) |

**Idempotency:** Every funding request carries an idempotency key (stored in Redis with 24h TTL). Duplicate requests with the same key return the original response without re-charging the sender.

**Retry Policy:** Failed card charges are retried up to 2 times with exponential backoff. Failed bank debits are not retried automatically (they require user intervention due to insufficient funds or revoked authorization).

---

### 4. Compliance (AML/CFT) Service

**Responsibility:** Sanctions screening, transaction monitoring, suspicious activity report (SAR) generation, and regulatory hold management.

| Aspect | Detail |
|---|---|
| Data store | PostgreSQL (screening results, case management), Elasticsearch (pattern matching, historical analysis) |
| Key entities | ScreeningResult, ComplianceCase, SARReport, WatchlistEntry, RiskScore |
| External integrations | Dow Jones/Refinitiv (sanctions lists), Chainalysis (if crypto corridors), GoAML (regulatory reporting) |
| Sync APIs | `POST /compliance/screen` (synchronous screening in transfer path) |
| Events produced | `compliance.cleared`, `compliance.held`, `compliance.escalated`, `sar.filed` |
| Events consumed | `transfer.initiated`, `user.registered`, `funding.completed` |

**Screening Pipeline:**

1. **Sanctions check** -- Name matching against OFAC, EU, UN, HMT sanctions lists. Uses fuzzy matching (Jaro-Winkler similarity >= 0.85) to catch transliteration variants.
2. **PEP screening** -- Politically Exposed Persons database lookup.
3. **Transaction pattern analysis** -- Velocity checks (frequency, cumulative amount per rolling window), structuring detection (amounts just below reporting thresholds), geographic risk scoring.
4. **Disposition** -- Auto-clear, auto-hold, or escalate to compliance analyst queue.

Screening is **synchronous** in the transfer critical path. Target latency: < 200ms for sanctions check, with a circuit breaker fallback to queue-based async screening if the external provider is degraded.

---

### 5. FX & Treasury Service

**Responsibility:** Execute currency conversions at locked rates, manage hedging positions, and maintain liquidity pools per currency.

| Aspect | Detail |
|---|---|
| Data store | PostgreSQL (conversion records, hedge positions), TimescaleDB (rate history) |
| Key entities | ConversionOrder, HedgePosition, LiquidityPool, CurrencyPosition |
| External integrations | Liquidity providers (Citi, JPMorgan FX Connect), central bank feeds |
| Sync APIs | `POST /fx/convert`, `GET /fx/positions/{currency}` |
| Events produced | `fx.conversion-executed`, `fx.rate-updated`, `fx.liquidity-low` |
| Events consumed | `transfer.funded` (triggers conversion), `quote.locked` |

**Hedging Strategy:**

The service maintains a rolling hedge for each high-volume corridor. When the aggregate exposure in a currency pair exceeds a threshold (e.g., $500K USD equivalent), the service automatically executes a forward contract with a liquidity provider. Low-volume corridors are hedged on a per-transaction basis.

**Liquidity Pool Management:**

Each target currency has a pre-funded liquidity pool. The service monitors pool levels and triggers replenishment when the balance drops below a configurable watermark. Alerts fire at the low-watermark; automatic replenishment executes at the critical-watermark.

---

### 6. Routing & Corridors Service

**Responsibility:** Select the optimal payout rail for each transfer based on corridor, amount, delivery method, cost, speed, and partner health.

| Aspect | Detail |
|---|---|
| Data store | PostgreSQL (corridor configurations, partner contracts), Redis (partner health scores) |
| Key entities | Corridor, PayoutRail, PartnerConfig, HealthScore, RoutingRule |
| External integrations | Payout partners (Thunes, Terrapay, local bank APIs) |
| Sync APIs | `POST /routing/select-rail`, `GET /corridors/{id}/rails` |
| Events produced | `routing.rail-selected`, `routing.partner-degraded` |
| Events consumed | `disbursement.failed` (triggers re-routing), `partner.health-updated` |

**Partner Health Scoring:**

Each payout partner is scored on a 0--100 scale based on rolling metrics:

- Success rate (last 1h, 24h, 7d) -- weighted 40%
- Median latency (last 1h) -- weighted 25%
- Error rate by type (timeout, reject, system error) -- weighted 20%
- Cost per transaction -- weighted 15%

If a partner's health score drops below 50, the service automatically fails over to the next-best rail for new transfers. Existing in-flight transfers on the degraded partner are monitored but not rerouted unless they fail.

**Routing Decision Tree:**

```
1. Filter rails by: corridor supported, delivery method, amount range
2. Exclude rails with health score < 50
3. Rank remaining by: cost (40%), speed (35%), reliability (25%)
4. Select top-ranked rail; store runner-up as fallback
```

---

### 7. Ledger Service

**Responsibility:** Double-entry bookkeeping for every money movement, internal account balance tracking, and reconciliation trigger generation.

| Aspect | Detail |
|---|---|
| Data store | PostgreSQL (journal entries, account balances) -- append-only writes |
| Key entities | JournalEntry, Account, LedgerTransaction, TrialBalance |
| External integrations | None (internal service only) |
| Sync APIs | `POST /ledger/entries` (record entry), `GET /ledger/accounts/{id}/balance` |
| Events produced | `ledger.entry-posted`, `ledger.reconciliation-triggered`, `ledger.balance-alert` |
| Events consumed | `funding.completed`, `fx.conversion-executed`, `disbursement.completed`, `settlement.completed` |

**Double-Entry Model:**

Every money movement produces a debit and a credit entry. The sum of all debits must equal the sum of all credits at all times. Example for a funded transfer:

```
funding.completed:
  Debit:  sender_funds_receivable    $100.00 USD
  Credit: sender_liability           $100.00 USD

fx.conversion-executed:
  Debit:  sender_liability           $100.00 USD
  Credit: usd_pool                   $100.00 USD
  Debit:  gbp_pool                    £78.50 GBP
  Credit: recipient_payable           £78.50 GBP
```

**Reconciliation:**

The ledger triggers reconciliation jobs at configurable intervals (default: every 4 hours). Reconciliation compares internal ledger balances against external bank statement feeds and flags discrepancies exceeding a configurable threshold ($0.01 for individual entries, $100 for aggregate).

---

### 8. Settlement Service

**Responsibility:** Batch settlement with banking and payout partners, nostro/vostro account management, and net settlement position calculation.

| Aspect | Detail |
|---|---|
| Data store | PostgreSQL (settlement batches, nostro/vostro positions) |
| Key entities | SettlementBatch, NostroAccount, VostroAccount, SettlementInstruction, NetPosition |
| External integrations | SWIFT (MT103/MT202), partner settlement APIs, correspondent banks |
| Sync APIs | `POST /settlement/batches/create`, `GET /settlement/batches/{id}` |
| Events produced | `settlement.batch-created`, `settlement.completed`, `settlement.failed` |
| Events consumed | `disbursement.completed`, `ledger.reconciliation-triggered` |

**Batching Strategy:**

Settlements are batched per partner per currency with configurable cut-off times (typically aligned with banking cut-off windows). The service computes net positions to minimize the number of actual wire transfers:

```
Partner A (GBP corridor):
  Gross outflows: 150 transfers = £425,000
  Gross inflows:   30 transfers = £ 82,000
  Net settlement:                 £343,000 (single wire)
```

**Nostro/Vostro Management:**

The service tracks balances across nostro accounts (our accounts at partner banks) and vostro accounts (partner accounts at our bank). It generates alerts when balances approach operational minimums and triggers top-up requests.

---

### 9. Disbursement Service

**Responsibility:** Deliver funds to the recipient through the selected payout rail -- bank deposit, mobile wallet credit, or cash pickup enablement.

| Aspect | Detail |
|---|---|
| Data store | PostgreSQL (disbursement records, recipient details) |
| Key entities | Disbursement, Recipient, PayoutInstruction, DisbursementAttempt |
| External integrations | Payout partners (per corridor), mobile money APIs (M-Pesa, GCash), cash pickup networks (Western Union, MoneyGram agent networks) |
| Sync APIs | `POST /disbursements/execute`, `GET /disbursements/{id}/status` |
| Events produced | `disbursement.initiated`, `disbursement.completed`, `disbursement.failed` |
| Events consumed | `routing.rail-selected`, `fx.conversion-executed` |

**Delivery Methods:**

| Method | Typical Latency | Confirmation |
|---|---|---|
| Bank deposit (SWIFT) | 1--3 business days | MT199 confirmation |
| Bank deposit (local rails) | Minutes to hours | Partner API callback |
| Mobile wallet | Seconds to minutes | Partner API callback |
| Cash pickup | Available within hours | Pickup confirmation from agent |

**Retry and Failover:**

If a disbursement attempt fails (partner timeout, invalid account, insufficient partner liquidity), the service:
1. Records the failure reason.
2. If retryable (timeout, transient error): retry up to 3 times with exponential backoff.
3. If non-retryable (invalid account): emit `disbursement.failed` for the orchestrator to handle (may require user correction).
4. If partner-level failure: request re-routing from the Routing Service to an alternate rail.

---

### 10. Notification Service

**Responsibility:** Multi-channel delivery of transfer status updates, promotional messages, and compliance-required communications.

| Aspect | Detail |
|---|---|
| Data store | PostgreSQL (notification logs, user preferences), Redis (rate limiting, dedup) |
| Key entities | Notification, NotificationTemplate, ChannelPreference, DeliveryAttempt |
| External integrations | Twilio (SMS), SendGrid (email), Firebase/APNs (push notifications) |
| Sync APIs | `POST /notifications/send`, `GET /notifications/user/{id}` |
| Events produced | `notification.delivered`, `notification.failed` |
| Events consumed | `transfer.*`, `funding.*`, `disbursement.*`, `compliance.*`, `kyc.*` |

**Channel Priority and Fallback:**

```
1. Push notification (if app installed and user opted in)
2. SMS (for critical transfer updates -- funded, delivered, failed)
3. Email (for all events + receipts + compliance communications)
```

If the primary channel fails delivery (bounce, undeliverable), the service falls back to the next channel. Compliance-required notifications (e.g., transfer receipts mandated by CFPB Regulation E) must be delivered via at least one confirmed channel.

**Rate Limiting:** Maximum 10 notifications per user per hour to prevent spam during high-frequency transfer scenarios.

---

## Cross-Cutting Concerns

### API Gateway

**Technology:** Kong (self-managed on EKS) or AWS ALB + API Gateway depending on the corridor's regulatory requirements for data residency.

**Responsibilities:**
- TLS termination
- Request routing to backend services
- Rate limiting (per API key, per user, per IP)
- Request/response transformation
- API versioning (`/v1/`, `/v2/`)
- Request logging for audit trail

### Authentication & Authorization

**Technology:** OAuth 2.0 + OpenID Connect with MFA enforcement.

- **Access tokens:** Short-lived JWTs (15 min TTL) signed with RS256.
- **Refresh tokens:** Opaque tokens stored server-side with 30-day TTL, single-use rotation.
- **MFA:** Required for transfer initiation above Tier 1 limits. Supports TOTP (Google Authenticator), SMS OTP, and hardware security keys (FIDO2/WebAuthn).
- **Service-to-service auth:** Mutual TLS (mTLS) within the service mesh, with JWT-based service identity for cross-cluster calls.

### Event Bus

**Technology:** Apache Kafka (MSK on AWS).

- **Cluster:** 6 brokers across 3 AZs, replication factor 3, min ISR 2.
- **Partitioning:** Transfer events partitioned by `transfer_id` to guarantee ordering per transfer.
- **Retention:** 30 days hot retention, then tiered to S3 via Kafka Connect for 7-year cold storage (regulatory requirement).
- **Schema registry:** Confluent Schema Registry with Avro schemas. All events versioned with backward-compatible evolution.
- **Consumer groups:** Each service has its own consumer group, enabling independent consumption rates and replay.

### Service Mesh

**Technology:** Istio on EKS.

**Capabilities:**
- Mutual TLS between all services (zero-trust networking)
- Circuit breaking (5xx threshold: 50% over 30s window triggers open circuit)
- Retry policies (2 retries, 100ms--1s jittered backoff)
- Request-level observability (distributed tracing via Jaeger, metrics via Prometheus)
- Traffic splitting for canary deployments

### Observability Stack

| Layer | Tool | Purpose |
|---|---|---|
| Metrics | Prometheus + Grafana | Service-level SLIs/SLOs, business KPIs |
| Logging | Fluentd + OpenSearch | Structured JSON logs, audit trail |
| Tracing | Jaeger (OpenTelemetry) | End-to-end transfer latency breakdown |
| Alerting | PagerDuty + Grafana Alerts | On-call rotation, escalation policies |

---

## Tech Stack with Rationale

### Language Choices

| Service | Language | Rationale |
|---|---|---|
| Quote Engine | Go | Sub-millisecond GC pauses critical for rate-sensitive quoting. High concurrency via goroutines for parallel rate fetches from multiple liquidity providers. |
| Routing & Corridors | Go | Low-latency routing decisions in the transfer critical path. Partner health scoring requires high-throughput metric aggregation. |
| Funding Service | Go | High-concurrency payment processing. Go's standard library has strong HTTP client support for integrating with diverse payment processor APIs. |
| Compliance (AML/CFT) | Java/Kotlin | Mature rules engine ecosystem (Drools, Easy Rules). Rich libraries for fuzzy string matching (sanctions screening). JVM's long-running process model suits continuous transaction monitoring. |
| Settlement | Java/Kotlin | Complex batch processing well-served by Spring Batch. Strong JDBC ecosystem for multi-database reconciliation. ISO 20022 / SWIFT message parsing libraries available on JVM. |
| Ledger Service | Java/Kotlin | Financial arithmetic precision (BigDecimal). Mature transaction management (Spring @Transactional). Double-entry bookkeeping logic benefits from the type system. |
| FX & Treasury | Java/Kotlin | Quantitative finance libraries (QuantLib JVM bindings). Complex hedging strategies implemented as stateful domain models. |
| User & KYC | Go or Kotlin | Either works. Go if latency in the registration flow is prioritized; Kotlin if the team prefers consistency with other Java services. |
| Disbursement | Go | High concurrency for parallel payout partner API calls. Resilience patterns (circuit breakers, retries) cleanly expressed with goroutines and channels. |
| Notification | Go | Fan-out to multiple channels (email, SMS, push) benefits from goroutine concurrency model. |

### Data Stores

| Store | Use Case | Rationale |
|---|---|---|
| **PostgreSQL** | Primary OLTP for all services | ACID guarantees are non-negotiable for money movement. Serializable isolation for ledger writes prevents double-spend. Rich indexing (GIN, GiST) for compliance text search. Mature replication (streaming + logical) for HA. |
| **Redis** | Quote caching, rate limiting, idempotency keys, session store | Sub-millisecond reads for quote lookups. TTL-based expiry maps naturally to quote lock windows and idempotency key lifetimes. Atomic operations (INCR, SETNX) for rate limiting counters. |
| **TimescaleDB** | FX rate time-series | Hypertable partitioning optimized for time-range queries on rate history. Continuous aggregates for pre-computed OHLC candles. Compression for long-term rate storage. Compatible with PostgreSQL (same driver, same SQL). |
| **Elasticsearch / OpenSearch** | Compliance pattern matching, audit log search | Full-text search with fuzzy matching for sanctions screening. Aggregation pipelines for transaction pattern detection. Kibana/OpenSearch Dashboards for compliance analyst investigations. |
| **S3** | Document storage, Kafka cold tier, backups | Durable (11 nines) storage for KYC documents. Lifecycle policies for regulatory retention periods. Server-side encryption (SSE-S3) for data at rest. |

### Infrastructure

| Component | Technology | Rationale |
|---|---|---|
| Container orchestration | Amazon EKS | Managed Kubernetes reduces operational burden. Pod-level resource isolation between services. HPA for scaling based on transfer volume. |
| Event streaming | Amazon MSK (Kafka) | Managed Kafka with multi-AZ replication. No operational overhead for broker management, patching, ZooKeeper (KRaft mode). |
| Secrets management | AWS Secrets Manager + HashiCorp Vault | Vault for dynamic database credentials (short-lived, auto-rotated). Secrets Manager for API keys with automatic rotation. |
| CI/CD | GitHub Actions + ArgoCD | GitOps model: ArgoCD syncs Kubernetes manifests from Git. GitHub Actions for build, test, container image push. |
| CDN / Edge | CloudFront | Static asset delivery for mobile/web clients. Edge-level DDoS mitigation via AWS Shield. |

---

## Transfer Orchestration

The end-to-end transfer lifecycle is managed by a **Transfer Orchestrator** implementing the **Saga pattern** with explicit compensation actions.

### Saga Steps

| Step | Action | Compensation (on failure) |
|---|---|---|
| 1. Lock Quote | Reserve FX rate for TTL | Release quote lock |
| 2. Collect Funds | Charge sender via selected payment method | Refund sender |
| 3. Screen Transfer | Run AML/CFT compliance checks | Release held funds (if auto-cleared path) |
| 4. Convert Currency | Execute FX conversion at locked rate | Reverse conversion, credit source currency pool |
| 5. Route Transfer | Select optimal payout rail | N/A (stateless selection) |
| 6. Disburse Funds | Deliver to recipient via selected rail | Retry via alternate rail, or reverse and refund sender |

### Orchestrator State Machine

```
QUOTE_PENDING
    |--[quote locked]--> FUNDING_PENDING
    |--[quote failed]--> FAILED

FUNDING_PENDING
    |--[funds collected]--> SCREENING_PENDING
    |--[funding failed]--> FAILED

SCREENING_PENDING
    |--[compliance cleared]--> CONVERSION_PENDING
    |--[compliance held]--> ON_HOLD
    |--[compliance rejected]--> COMPENSATING (refund sender)

CONVERSION_PENDING
    |--[conversion executed]--> ROUTING_PENDING
    |--[conversion failed]--> COMPENSATING (refund sender)

ROUTING_PENDING
    |--[rail selected]--> DISBURSEMENT_PENDING
    |--[no rail available]--> COMPENSATING (reverse conversion, refund)

DISBURSEMENT_PENDING
    |--[disbursement completed]--> COMPLETED
    |--[disbursement failed, retryable]--> DISBURSEMENT_RETRYING
    |--[disbursement failed, non-retryable]--> COMPENSATING (reverse conversion, refund)

ON_HOLD
    |--[analyst clears]--> CONVERSION_PENDING
    |--[analyst rejects]--> COMPENSATING (refund sender)

COMPENSATING
    |--[all compensations complete]--> REFUNDED
    |--[compensation failed]--> REQUIRES_MANUAL_INTERVENTION
```

The orchestrator persists its state in PostgreSQL. Each state transition is recorded as an event in Kafka for audit purposes. The orchestrator uses a polling-based recovery mechanism: a background job scans for transfers stuck in any state for longer than a configurable timeout and triggers either retry or compensation.

---

## Service Interaction Diagram

```mermaid
flowchart TB
    subgraph Clients
        WEB[Web App]
        MOB[Mobile App]
    end

    subgraph Cross-Cutting
        GW[API Gateway<br/>Kong / ALB]
        AUTH[Auth Service<br/>OAuth2 + MFA]
        KAFKA[Event Bus<br/>Kafka MSK]
        MESH[Service Mesh<br/>Istio]
    end

    subgraph Core Services
        USER[User & KYC<br/>Service]
        QUOTE[Quote Engine]
        FUND[Funding<br/>Service]
        COMP[Compliance<br/>AML/CFT Service]
        FX[FX & Treasury<br/>Service]
        ROUTE[Routing &<br/>Corridors Service]
        LEDGER[Ledger<br/>Service]
        SETTLE[Settlement<br/>Service]
        DISB[Disbursement<br/>Service]
        NOTIF[Notification<br/>Service]
    end

    ORCH[Transfer<br/>Orchestrator]

    WEB & MOB --> GW
    GW --> AUTH
    GW --> USER
    GW --> QUOTE
    GW --> ORCH

    ORCH -->|1. Lock Quote| QUOTE
    ORCH -->|2. Collect Funds| FUND
    ORCH -->|3. Screen| COMP
    ORCH -->|4. Convert| FX
    ORCH -->|5. Select Rail| ROUTE
    ORCH -->|6. Disburse| DISB

    FUND -->|Post entries| LEDGER
    FX -->|Post entries| LEDGER
    DISB -->|Post entries| LEDGER
    SETTLE -->|Post entries| LEDGER

    LEDGER -->|Reconciliation triggers| SETTLE

    ORCH -.->|Events| KAFKA
    KAFKA -.->|Transfer events| NOTIF
    KAFKA -.->|Transfer events| COMP
    KAFKA -.->|Settlement triggers| SETTLE
    KAFKA -.->|Rate updates| QUOTE

    MESH -.->|mTLS, Circuit Breaking| Core Services
```

---

## Communication Patterns

```mermaid
flowchart LR
    subgraph Synchronous -- REST/gRPC
        direction TB
        A1[Client] -->|REST| A2[API Gateway]
        A2 -->|REST| A3[Orchestrator]
        A3 -->|gRPC| A4[Quote Engine]
        A3 -->|gRPC| A5[Funding Service]
        A3 -->|gRPC| A6[Compliance Service]
        A3 -->|gRPC| A7[FX & Treasury]
        A3 -->|gRPC| A8[Routing Service]
        A3 -->|gRPC| A9[Disbursement Service]
        A5 -->|gRPC| A10[Ledger Service]
        A7 -->|gRPC| A10
        A9 -->|gRPC| A10
    end

    subgraph Asynchronous -- Kafka Events
        direction TB
        B1[Orchestrator] -.->|transfer.state-changed| B2[Kafka]
        B3[Funding Service] -.->|funding.completed| B2
        B4[FX & Treasury] -.->|fx.rate-updated| B2
        B5[Disbursement] -.->|disbursement.completed| B2
        B6[Compliance] -.->|compliance.cleared| B2
        B2 -.->|Subscribe| B7[Notification Service]
        B2 -.->|Subscribe| B8[Settlement Service]
        B2 -.->|Subscribe| B9[Compliance Service]
        B2 -.->|Subscribe| B10[Ledger Service]
    end
```

**When to use synchronous vs. asynchronous:**

| Pattern | When Used | Examples |
|---|---|---|
| **Synchronous (gRPC)** | In the transfer critical path where the next step depends on the result of the current step. Latency budget: < 200ms per hop. | Orchestrator calling Quote Engine to lock a rate; Compliance screening before conversion. |
| **Asynchronous (Kafka)** | When the producer does not need to wait for the consumer to process the event. Used for side effects, analytics, and decoupled workflows. | Notification dispatch on transfer status change; Settlement batching after disbursement. |
| **Sync with async fallback** | Compliance screening: normally synchronous, but if the external screening provider is slow, the request is queued and the transfer enters an ON_HOLD state. | Compliance Service with circuit breaker. |

---

## Deployment Topology

```mermaid
flowchart TB
    subgraph Primary Region -- us-east-1
        subgraph AZ-1a
            EKS1a[EKS Node Group]
            RDS1a[(RDS Primary<br/>PostgreSQL)]
            MSK1a[MSK Broker 1]
        end
        subgraph AZ-1b
            EKS1b[EKS Node Group]
            RDS1b[(RDS Standby<br/>PostgreSQL)]
            MSK1b[MSK Broker 2]
        end
        subgraph AZ-1c
            EKS1c[EKS Node Group]
            MSK1c[MSK Broker 3]
        end

        ALB1[ALB / API Gateway]
        REDIS1[(ElastiCache<br/>Redis Cluster)]
        S3P[(S3 Buckets<br/>Documents + Kafka Cold Tier)]
        VAULT1[HashiCorp Vault]

        ALB1 --> EKS1a & EKS1b & EKS1c
        EKS1a & EKS1b & EKS1c --> RDS1a
        EKS1a & EKS1b & EKS1c --> REDIS1
        EKS1a & EKS1b & EKS1c --> MSK1a & MSK1b & MSK1c
        RDS1a -.->|Streaming Replication| RDS1b
    end

    subgraph DR Region -- eu-west-1
        subgraph AZ-2a
            EKS2a[EKS Node Group<br/>Standby]
            RDS2a[(RDS Read Replica<br/>PostgreSQL)]
            MSK2a[MSK Broker<br/>Mirror]
        end
        subgraph AZ-2b
            EKS2b[EKS Node Group<br/>Standby]
        end

        ALB2[ALB / API Gateway<br/>Standby]
        REDIS2[(ElastiCache<br/>Redis Standby)]

        ALB2 --> EKS2a & EKS2b
        EKS2a & EKS2b --> RDS2a
        EKS2a & EKS2b --> REDIS2
    end

    R53[Route 53<br/>DNS Failover]
    CF[CloudFront<br/>CDN]

    CF --> R53
    R53 -->|Active| ALB1
    R53 -.->|Failover| ALB2
    RDS1a -.->|Cross-Region Replication| RDS2a
    MSK1a -.->|MirrorMaker 2| MSK2a
    S3P -.->|Cross-Region Replication| S3DR[(S3 Replica<br/>eu-west-1)]
```

**Scaling Strategy:**

| Component | Scaling Mechanism | Trigger |
|---|---|---|
| EKS pods | Horizontal Pod Autoscaler (HPA) | CPU > 70% or custom metric (requests/sec) |
| EKS nodes | Cluster Autoscaler / Karpenter | Pending pods due to insufficient node capacity |
| RDS | Vertical scaling (instance resize) + read replicas | CPU > 80% sustained, connection count near limit |
| Redis | ElastiCache cluster mode with resharding | Memory utilization > 75% |
| Kafka | Add brokers + rebalance partitions | Partition lag > 10,000 messages sustained |

**DR Failover Process:**

1. Route 53 health check detects primary ALB unhealthy (3 consecutive failures, 30s interval).
2. DNS failover routes traffic to DR region ALB.
3. DR EKS nodes scale up from standby (pre-warmed with min 2 replicas per service).
4. RDS read replica in DR region is promoted to primary (automated via RDS event subscription + Lambda).
5. Kafka consumers in DR region switch from mirror topic to local topic.
6. Estimated RTO: < 15 minutes. RPO: < 1 minute (async replication lag).

---

## Design Rationale

### Why Service-per-Domain over Modular Monolith?

A modular monolith was considered and rejected for the following reasons:

1. **Regulatory isolation.** Different services fall under different regulatory regimes. The Compliance Service must be auditable independently, with its own change management process, access controls, and deployment cadence. Coupling it into a monolith means a bug fix in the Quote Engine triggers a re-audit of the Compliance module. Separate deployability is a regulatory requirement, not an architectural preference.

2. **Failure isolation.** A memory leak in the Notification Service must not bring down the Funding Service. In a monolith, even with module boundaries, services share a process, a thread pool, and a heap. In a money-movement system, cascading failures from a non-critical service to a critical service is an unacceptable risk.

3. **Independent scaling.** The Quote Engine handles 10--50x more requests than the Settlement Service (every page view triggers a quote; settlements batch daily). Scaling a monolith means scaling everything together, wasting compute on services that don't need it.

4. **Team autonomy.** A remittance platform requires specialists -- compliance engineers, treasury/FX domain experts, payment integration engineers. Each team needs to own their service end-to-end: schema, deployment, on-call. A monolith forces coordination overhead that slows all teams to the speed of the slowest.

5. **Technology heterogeneity.** Go is measurably better for the Quote Engine's latency requirements. Java/Kotlin is measurably better for the Compliance Service's rules engine requirements. A monolith forces a single runtime.

**When a monolith would be correct:** If the team is < 10 engineers, the product is pre-product-market-fit, and the regulatory environment is simple (single corridor, single jurisdiction). Start with a modular monolith and extract services as the domain boundaries stabilize.

### Why Saga over Two-Phase Commit (2PC)?

The transfer lifecycle spans 6 independent services, each with its own data store. 2PC was rejected because:

1. **Availability.** 2PC requires all participants to be available for the prepare phase. If any participant is down, the entire transaction blocks. In a remittance platform, payout partners have variable availability (especially in emerging markets). A saga tolerates partial failures -- it compensates rather than blocks.

2. **Latency.** 2PC requires two network round-trips to every participant (prepare + commit). With 6 participants across services that call external providers, the latency would be measured in seconds. A saga executes steps sequentially but does not hold locks across services, so each step commits independently.

3. **Heterogeneous data stores.** 2PC requires an XA-compatible transaction coordinator and XA-compatible data stores. Redis, Kafka, and external partner APIs do not support XA. The saga pattern works with any data store because each step is a local transaction.

4. **Long-running transactions.** A transfer can be ON_HOLD for days (pending compliance review). 2PC cannot hold locks for days. A saga models this naturally as a state machine with a durable state and explicit transitions.

5. **Compensation semantics map to the business domain.** "Refund the sender" is a real business operation, not just a database rollback. Compliance regulations may require that the refund itself is screened. The saga's explicit compensation steps model these business realities; 2PC's automatic rollback does not.

**Trade-off acknowledged:** Sagas introduce eventual consistency. Between the time funds are collected and the transfer is completed, the system is in an intermediate state. This is mitigated by: (a) the orchestrator's state machine making every intermediate state explicit and queryable, (b) notifications keeping the user informed of progress, and (c) idempotent operations at every step to handle retries safely.

### Why Kafka over RabbitMQ?

Both are mature messaging systems. Kafka was selected for this use case because:

1. **Durable, replayable audit trail.** Financial regulation requires that every event in a transfer's lifecycle be retained and replayable for 7 years. Kafka's log-based storage with configurable retention (hot + cold tier to S3) provides this natively. RabbitMQ is a message broker -- once a message is consumed and acknowledged, it is gone. Rebuilding audit trails from RabbitMQ requires a separate persistence layer.

2. **Ordering guarantees.** Transfer events must be processed in order (you cannot disburse before funding). Kafka guarantees ordering within a partition. By partitioning on `transfer_id`, all events for a single transfer are ordered. RabbitMQ does not guarantee ordering across consumers in a competing-consumer pattern.

3. **Consumer independence.** Each service consumes at its own pace from its own consumer group. The Notification Service can fall behind without affecting the Settlement Service. Adding a new consumer (e.g., an analytics pipeline) does not require reconfiguring existing consumers. In RabbitMQ, adding a new consumer to an existing queue means sharing the messages (competing consumer) or creating a new binding (exchange/queue topology management).

4. **Throughput at scale.** At 500K--1M transfers/day, with an average of 8 events per transfer, the event bus handles 4--8M events/day. Kafka brokers handle this with commodity hardware. RabbitMQ can handle this volume but requires more careful tuning of prefetch counts, queue mirroring, and memory management.

5. **Stream processing.** The Compliance Service's transaction monitoring requires windowed aggregations (e.g., total amount sent by a user in the last 24 hours). Kafka Streams or ksqlDB can compute these aggregations directly on the event stream. With RabbitMQ, this requires an external stream processing system.

**When RabbitMQ would be correct:** For task-queue semantics (e.g., "process this notification and forget it"), RabbitMQ's flexible routing (topic, fanout, header exchanges) and per-message TTL are simpler. If the system did not have regulatory retention requirements and did not need ordering, RabbitMQ would be a lighter-weight choice. In this architecture, RabbitMQ could complement Kafka for non-critical workloads (e.g., internal alerts, batch job scheduling), but Kafka is the backbone.

---

## Appendix: Key API Contracts (Summary)

### Transfer Initiation

```
POST /v1/transfers
Authorization: Bearer <jwt>
Idempotency-Key: <uuid>

{
  "sender_id": "usr_abc123",
  "recipient": {
    "name": "Jane Doe",
    "account_number": "GB29NWBK60161331926819",
    "bank_code": "NWBKGB2L",
    "delivery_method": "bank_deposit"
  },
  "source_currency": "USD",
  "target_currency": "GBP",
  "source_amount": 1000.00,
  "funding_method": "bank_debit",
  "quote_id": "qt_xyz789"
}

Response 201:
{
  "transfer_id": "txn_def456",
  "status": "FUNDING_PENDING",
  "quoted_rate": 0.7850,
  "fee": 4.99,
  "estimated_delivery": "2026-04-02T14:00:00Z",
  "created_at": "2026-04-01T10:30:00Z"
}
```

### Transfer Status

```
GET /v1/transfers/txn_def456

Response 200:
{
  "transfer_id": "txn_def456",
  "status": "DISBURSEMENT_PENDING",
  "status_history": [
    {"status": "QUOTE_PENDING", "at": "2026-04-01T10:30:00Z"},
    {"status": "FUNDING_PENDING", "at": "2026-04-01T10:30:01Z"},
    {"status": "SCREENING_PENDING", "at": "2026-04-01T10:30:15Z"},
    {"status": "CONVERSION_PENDING", "at": "2026-04-01T10:30:16Z"},
    {"status": "ROUTING_PENDING", "at": "2026-04-01T10:30:17Z"},
    {"status": "DISBURSEMENT_PENDING", "at": "2026-04-01T10:30:18Z"}
  ],
  "source_amount": 1000.00,
  "source_currency": "USD",
  "target_amount": 780.01,
  "target_currency": "GBP",
  "fee": 4.99,
  "rate": 0.7850
}
```
