# Sample Interview Problems — Playlist Director of Engineering

Based on the prep guidance for both rounds, tailored to the Payments Pillar context.

---

## Round 1: API Design

> **Format:** You are given a problem and asked to design the API from scratch. You'll be evaluated on REST maturity, naming conventions, error handling, idempotency, extensibility, and how you think about edge cases. You drive the conversation.

---

### Problem 1: Payment Checkout API for Fitness Classes

**Prompt:**

> "Mindbody allows fitness studios to accept payments from customers booking classes. Design the API for the checkout flow — from a customer selecting a class to completing payment. The API should support multiple payment methods, promo codes, and package/membership billing."

**What they'll evaluate:**

- Resource modeling: `Class`, `Booking`, `Cart`, `Payment`, `Invoice`
- Do you separate booking intent from payment? (two-phase: reserve → pay)
- How do you handle:
  - Promo code validation and stacking rules
  - Partial payments (e.g., credits + card)
  - Package deduction (customer has a 10-class pack)
  - Membership auto-billing vs. pay-per-class
  - Failed payment after booking is confirmed
  - Concurrent booking for last spot in a class
- Idempotency on payment endpoints
- Webhook design for async payment confirmation to studio
- API versioning strategy
- Error response consistency

**Key endpoints to propose:**

```
POST   /api/v1/bookings                    -- reserve a spot
POST   /api/v1/bookings/{id}/checkout      -- initiate payment
GET    /api/v1/bookings/{id}/invoice       -- price breakdown
POST   /api/v1/payments                    -- process payment
POST   /api/v1/payments/{id}/refund        -- refund
POST   /api/v1/promo-codes/validate        -- check promo code
GET    /api/v1/customers/{id}/wallet       -- credits, packages, memberships
```

**Follow-ups they'll push:**

- "What happens if the class is full by the time payment completes?"
- "How does your API handle a customer who has a 10-class pack AND a promo code AND a partial card charge?"
- "A studio wants real-time booking notifications — how do you design the webhook contract?"
- "How do you prevent double-charging on a retry?"

---

### Problem 2: Merchant Onboarding & Payout API

**Prompt:**

> "We need to onboard fitness studios as merchants on our payment platform. Design the API for merchant registration, KYC verification, payment configuration, and payouts (settlements to merchant bank accounts)."

**What they'll evaluate:**

- Multi-step onboarding flow (progressive disclosure vs. single form)
- KYC/KYB verification as async process with status polling or webhooks
- How you model merchant payment configuration (accepted methods, currencies, PSP preferences)
- Payout/settlement API design
  - Batch payouts vs. real-time
  - Payout schedule (daily, weekly, custom)
  - Handling holds, reserves, and chargeback deductions
- PCI-DSS considerations — where does sensitive data live?
- Multi-tenant isolation in API design
- Role-based access: merchant admin vs. staff vs. platform admin

**Key endpoints to propose:**

```
POST   /api/v1/merchants                           -- register
GET    /api/v1/merchants/{id}                       -- retrieve
PUT    /api/v1/merchants/{id}/verification          -- submit KYC docs
GET    /api/v1/merchants/{id}/verification/status   -- check KYC status
PUT    /api/v1/merchants/{id}/payment-config        -- configure PSP, methods
GET    /api/v1/merchants/{id}/balance               -- available, pending, reserved
POST   /api/v1/merchants/{id}/payouts               -- trigger manual payout
GET    /api/v1/merchants/{id}/payouts               -- list payouts
GET    /api/v1/merchants/{id}/payouts/{payoutId}    -- payout details
POST   /api/v1/merchants/{id}/payouts/{payoutId}/retry -- retry failed payout
```

**Follow-ups:**

- "KYC takes 2-48 hours. How does your API communicate status changes?"
- "A merchant disputes a chargeback deduction from their payout. How does the API model this?"
- "How do you handle a payout that partially fails (10 out of 12 line items succeed)?"

---

### Problem 3: Subscription Billing API

**Prompt:**

> "ClassPass and studio memberships require recurring billing. Design the API for creating subscription plans, enrolling customers, handling billing cycles, proration on plan changes, and dunning (failed payment retries)."

**What they'll evaluate:**

- Plan vs. Subscription separation (plan is the template, subscription is the instance)
- Billing cycle management (monthly, annual, custom)
- Proration logic when upgrading/downgrading mid-cycle
- Dunning flow: retry schedule, grace period, involuntary churn
- Pause/resume subscription
- Trial periods and conversion
- Webhook events for subscription lifecycle

**Key endpoints to propose:**

```
POST   /api/v1/plans                               -- create plan
GET    /api/v1/plans/{id}                           -- plan details
POST   /api/v1/subscriptions                        -- enroll customer
GET    /api/v1/subscriptions/{id}                   -- subscription details
POST   /api/v1/subscriptions/{id}/cancel            -- cancel (immediate vs. end of period)
POST   /api/v1/subscriptions/{id}/pause             -- pause with resume date
POST   /api/v1/subscriptions/{id}/change-plan       -- upgrade/downgrade
GET    /api/v1/subscriptions/{id}/upcoming-invoice   -- preview next charge
GET    /api/v1/subscriptions/{id}/invoices           -- billing history
```

**Follow-ups:**

- "Customer upgrades from $30/month to $50/month on day 15. Show me the proration calculation and how your API returns it."
- "Payment fails on renewal. Walk me through the dunning flow — retries, notifications, grace period, cancellation."
- "How do you handle a timezone difference — customer in Sydney, studio in LA — for billing cycle dates?"

---

### Problem 4: Multi-Location Gift Card / Stored Value API

**Prompt:**

> "Mindbody merchants want to sell gift cards that can be redeemed across multiple studio locations. Design the API for issuing, redeeming, checking balance, and transferring gift cards."

**What they'll evaluate:**

- Gift card as a stored-value instrument — ledger-based design
- Multi-location redemption: which merchant bears the cost?
- Partial redemption (use $30 of $50 card + card for remainder)
- Preventing double-spend (concurrent redemption at two locations)
- Bulk issuance (corporate gifts)
- Expiration policies and regulatory compliance (varies by state/country)
- Fraud prevention (velocity checks on redemption)

---

### Problem 5: Parking Lot API (Likely Problem Based on Your Intel)

See the full design in `parking_lot_system_design.md`. This is the most likely API design problem given your earlier information about "API Design Review (parking lot)."

---

## Round 2: TDD (Technical Design Document Review)

> **Format:** You are given a pre-written technical design document. It contains intentional gaps, questionable decisions, and areas that need improvement. Your job is to **review it as if an engineer on your team wrote it** — identify issues, ask clarifying questions, suggest alternatives, and guide towards a better design. You must drive the conversation.

> **Key skills tested:** Scalability thinking, distributed systems knowledge, capacity planning, identifying missing pieces, giving constructive technical feedback, communication.

---

### Problem 1: Review a Design for "Real-Time Class Availability System"

**The document you'd receive (summary):**

> **Title:** Real-Time Class Availability for Mindbody Studios
>
> **Context:** Studios list classes on Mindbody. Customers see available spots in real-time across the mobile app and website. Currently, availability is queried directly from the database on every page load, causing high latency during peak hours (6-8 AM, 5-7 PM).
>
> **Proposed Design:**
> - Move from direct DB queries to a Redis cache layer
> - Cache TTL of 5 minutes per studio
> - When a booking is made, invalidate the cache entry for that studio
> - Single Redis instance in us-east-1
> - The booking service writes to MySQL, then invalidates Redis
> - Mobile app polls every 10 seconds for updates
>
> **Scale:** 100,000 studios, ~2M classes/week, peak 50K concurrent users

**Issues you should identify:**

| # | Issue | What to Say |
|---|-------|-------------|
| 1 | **Single Redis instance = SPOF** | "What happens when this Redis node goes down? You need at least a Redis Cluster or Sentinel setup for HA. What's your fallback — stale cache or DB query?" |
| 2 | **5-minute TTL is too long** | "If a class has 1 spot left and someone books it, other users see 1 spot for up to 5 minutes. This leads to overbooking. Have you considered event-driven invalidation instead of TTL-based?" |
| 3 | **Cache invalidation race condition** | "Write to MySQL then invalidate Redis — what if the app crashes between the two? You have stale cache with no invalidation. Consider write-through cache or CDC (Change Data Capture) from MySQL binlog." |
| 4 | **Polling every 10 seconds at 50K users** | "50K users * 1 request/10s = 5,000 QPS just for polling. Have you considered WebSockets or Server-Sent Events to push updates instead?" |
| 5 | **No capacity planning** | "What's the memory requirement for caching 100K studios? What's the expected Redis hit rate? What are the p99 latency targets?" |
| 6 | **Single region** | "All users in us-east-1? What about users in APAC or Europe? Consider a multi-region cache or CDN-based approach." |
| 7 | **No monitoring or fallback** | "How do you detect cache staleness? What metrics would you track? What's the degradation path?" |
| 8 | **Missing consistency model** | "The doc doesn't state the consistency requirement. Is eventual consistency acceptable? If so, what's the SLA — 1 second? 5 seconds? 30 seconds?" |

**How to drive the conversation:**

- "I see the problem statement, but I'd like to understand the business impact. How many overbookings happen today? What's the revenue impact?"
- "Before jumping to Redis, can we talk about the access patterns? How many reads vs. writes per second?"
- "I'd suggest an event-driven architecture here — booking events published to Kafka, a consumer updates Redis. This eliminates the invalidation race condition."

---

### Problem 2: Review a Design for "Payment Retry & Recovery System"

**The document you'd receive (summary):**

> **Title:** Automated Payment Retry for Failed Recurring Charges
>
> **Context:** 8% of monthly subscription renewals fail on first attempt. Currently, failed payments are retried manually by support. We want to automate retry logic.
>
> **Proposed Design:**
> - On payment failure, add to a retry queue (SQS)
> - Retry 3 times: immediately, after 24 hours, after 72 hours
> - After 3 failures, cancel subscription and notify customer
> - Use the same payment method for all retries
> - Retry logic runs as a Lambda function triggered by SQS
>
> **Scale:** 5M active subscriptions, ~400K failures/month

**Issues you should identify:**

| # | Issue | What to Say |
|---|-------|-------------|
| 1 | **Immediate retry is wasteful** | "If the card was declined for insufficient funds, retrying immediately won't help. The first retry should be after 4-6 hours (paycheck timing). What decline codes are you seeing — is it NSF, expired card, or issuer decline?" |
| 2 | **Fixed retry schedule ignores decline reason** | "A hard decline (stolen card, closed account) should not be retried at all. A soft decline (NSF, rate limit) can be retried. You need to classify decline codes and route differently." |
| 3 | **Same payment method only** | "What if the card is expired? You should prompt the customer to update their payment method via email/push before the next retry. Some customers have multiple payment methods on file." |
| 4 | **Cancel after 3 failures is aggressive** | "Industry standard is a 7-14 day grace period with multiple touchpoints (email, SMS, in-app). Immediate cancellation after 72 hours loses revenue. What's the reactivation rate after cancellation?" |
| 5 | **No smart retry timing** | "Research shows Tuesday/Wednesday mornings after payday have higher success rates. Consider ML-based or data-driven retry timing instead of fixed intervals." |
| 6 | **SQS doesn't guarantee ordering** | "What if retries process out of order? You could charge a customer after they've already updated their payment method and been charged successfully. Need idempotency + status checks before each retry." |
| 7 | **No metrics or success targets** | "What's the target recovery rate? Industry benchmark is 50-70% recovery. How will you measure this? What dashboards and alerts do you need?" |
| 8 | **Missing dunning communication flow** | "The doc focuses on technical retry but ignores the customer communication strategy. When do you email? When do you show in-app banners? When do you degrade service vs. hard cutoff?" |

---

### Problem 3: Review a Design for "Multi-PSP Payment Routing"

**The document you'd receive (summary):**

> **Title:** Payment Service Provider Routing Layer
>
> **Context:** We currently use Stripe for all payments. We want to add Adyen and Braintree to improve reliability, reduce costs, and support local payment methods for international expansion.
>
> **Proposed Design:**
> - Add an abstraction layer between our payment service and PSPs
> - Route based on a static configuration: US → Stripe, EU → Adyen, APAC → Braintree
> - Each PSP has an adapter implementing a common interface
> - On failure, retry with the same PSP 3 times before failing
> - Store all PSP credentials in environment variables
>
> **Scale:** 15M transactions/month, $500M annual GMV

**Issues you should identify:**

| # | Issue | What to Say |
|---|-------|-------------|
| 1 | **Static routing misses the point** | "Static geo-routing doesn't optimize for cost or success rate. You should route based on: card BIN country, PSP success rate (last N hours), transaction cost, and PSP health. This is a smart routing problem." |
| 2 | **No failover to another PSP** | "Retrying 3 times on the same PSP when it's down wastes time. On the first 5xx or timeout, you should cascade to the next PSP. The retry-same-PSP approach only makes sense for transient errors (429, network blip)." |
| 3 | **Credentials in env vars** | "At $500M GMV, PCI-DSS Level 1 requires proper secrets management. Use AWS Secrets Manager or Vault, with rotation policies. Env vars are visible in process listings and crash dumps." |
| 4 | **Missing idempotency across PSPs** | "If you fail over from Stripe to Adyen, how do you prevent double-charging? You need a platform-level idempotency key that maps to PSP-specific references. What's your idempotency store and TTL?" |
| 5 | **No tokenization strategy** | "If a card is tokenized with Stripe, you can't use that token with Adyen. You need network-level tokenization (Visa/Mastercard tokens) or a token vault that stores raw PANs (increases PCI scope). This is a critical architectural decision that's missing." |
| 6 | **No cost analysis** | "What's the per-transaction cost on each PSP? Are there volume discounts? What's the projected savings? Without this, how do you justify the engineering investment?" |
| 7 | **Missing circuit breaker** | "How do you detect PSP degradation? You need a circuit breaker pattern — track failure rate over a sliding window, open circuit at threshold, probe periodically. What are the thresholds?" |
| 8 | **No reconciliation** | "With 3 PSPs, settlement reconciliation becomes complex. How do you reconcile daily? What happens when amounts don't match? Who owns the reconciliation pipeline?" |

---

### Problem 4: Review a Design for "Event-Driven Booking Notifications"

**The document you'd receive (summary):**

> **Title:** Real-Time Booking Notifications System
>
> **Context:** Studios want instant notifications when customers book, cancel, or modify classes. Currently notifications are sent via a cron job that runs every 5 minutes.
>
> **Proposed Design:**
> - Replace cron with Kafka event streaming
> - Booking service publishes events to a Kafka topic
> - Notification service consumes events and sends push notifications, SMS, and email
> - Single Kafka cluster, 3 partitions, replication factor 2
> - Notification service sends all channels (push + SMS + email) synchronously before committing the Kafka offset
>
> **Scale:** 2M bookings/week, 100K studios, notifications to studio owner + staff

**Issues you should identify:**

| # | Issue | What to Say |
|---|-------|-------------|
| 1 | **Synchronous multi-channel send blocks the consumer** | "If the SMS provider is slow (2-3s), you block processing of all other events. Send each channel asynchronously — fan out to separate queues per channel (email queue, SMS queue, push queue). Each can fail and retry independently." |
| 2 | **Replication factor 2 is risky** | "With RF=2 and 3 brokers, losing 1 broker can cause data loss if the remaining replica is behind. Use RF=3 (industry standard) for durability." |
| 3 | **3 partitions is likely under-provisioned** | "2M bookings/week = ~3.3 events/sec average, ~15/sec peak. 3 partitions is fine for throughput, but partition by studio_id to ensure ordered processing per studio. How many consumer instances do you plan?" |
| 4 | **No dead letter queue** | "What happens when a notification permanently fails (invalid phone number, unsubscribed email)? You need a DLQ for failed events with alerting and manual review." |
| 5 | **No delivery tracking or deduplication** | "How do you know a notification was actually delivered? What if Kafka rebalances and the same event is processed twice — does the customer get duplicate SMS?" |
| 6 | **Missing notification preferences** | "Does the doc consider user preferences? Some studio owners want push only, some want email only. Where are preferences stored and how does the notification service check them?" |
| 7 | **No rate limiting for SMS/email** | "SMS providers have rate limits. If 500 bookings happen simultaneously for one studio (e.g., class opens), you'll hit provider limits. Need per-provider rate limiting with backpressure." |
| 8 | **No mention of templates or localization** | "How are notification messages templated? What about multi-language support for international studios? This is a content architecture question that affects the API contract." |

---

### Problem 5: Review a Design for "Merchant Dashboard Analytics"

**The document you'd receive (summary):**

> **Title:** Real-Time Revenue Analytics Dashboard for Studios
>
> **Context:** Studio owners want a dashboard showing revenue, bookings, and customer metrics in real-time. Currently, reports are generated nightly via a batch ETL job.
>
> **Proposed Design:**
> - Stream all booking and payment events to Elasticsearch
> - Kibana dashboards for studio owners
> - Real-time aggregations using Elasticsearch aggregation queries
> - Each studio owner gets a Kibana login
> - Retain all data in Elasticsearch for 2 years
>
> **Scale:** 100K studios, 15M transactions/month, dashboard accessed by ~30K daily active users

**Issues you should identify:**

| # | Issue | What to Say |
|---|-------|-------------|
| 1 | **Kibana for 30K non-technical users is wrong** | "Studio owners are not engineers. Kibana is an ops tool. You need a purpose-built dashboard with pre-built views, filters, and visualizations. Consider embedding a BI tool (Metabase, Looker) or building custom frontend with pre-computed aggregates." |
| 2 | **Elasticsearch is expensive for 2-year retention** | "15M txns/month * 24 months * ~1KB = ~360 GB in ES. Hot storage in ES is expensive. Use a tiered approach: real-time (last 7 days) in ES, recent (90 days) in a read-optimized DB, historical in S3 + Athena." |
| 3 | **Multi-tenant security in Kibana** | "How do you prevent Studio A from seeing Studio B's data? Kibana's multi-tenancy is limited. You need row-level security, which ES supports but is complex to manage at 100K tenants." |
| 4 | **Real-time aggregations at scale won't perform** | "Running aggregation queries on raw events for 30K concurrent users will crush ES. Pre-compute aggregates (daily revenue, weekly bookings) via a stream processor (Flink, Kafka Streams) and serve pre-built summaries." |
| 5 | **Missing access patterns analysis** | "What queries will studio owners actually run? Top 5 revenue metrics, booking trends by day, customer retention — these are known and can be materialized. Don't build a general-purpose query engine when you need 10 specific views." |
| 6 | **No caching layer** | "If 30K users load their dashboard hourly, that's 30K * 16 hours = 480K queries/day. Many will return the same data (updated hourly). Add a Redis cache in front of pre-computed views." |
| 7 | **PCI considerations** | "Payment data in Elasticsearch — is this in PCI scope? Card last-4, amounts, and customer info in a search index needs proper access controls, encryption at rest, and audit logging." |

---

## General Preparation Tips for Both Rounds

### For API Design Round

1. **Always start with resources, not endpoints** — model the domain first
2. **Ask clarifying questions before designing** — "What's the primary use case? Who are the consumers? What's the expected QPS?"
3. **Show pagination, error handling, and idempotency unprompted** — this signals seniority
4. **Use consistent naming** — plural nouns for collections, kebab-case, clear hierarchy
5. **Think about backwards compatibility** — "If we add EV charging later, does this API still work?"
6. **Connect to payments naturally** — given the role, show you think about auth/capture, refunds, settlements in every problem

### For TDD Review Round

1. **Read the whole document before commenting** — don't nitpick line 1
2. **Start with the problem statement** — "Is the problem well-defined? Are the success criteria measurable?"
3. **Check for missing sections:**
   - Capacity planning / back-of-envelope math
   - Failure modes and recovery
   - Monitoring and alerting
   - Security and compliance
   - Migration strategy from current system
   - Rollback plan
4. **Challenge assumptions with data** — "You say 5-minute TTL is fine. Let's do the math: at peak, that means X stale reads. Is that acceptable?"
5. **Offer alternatives, don't just criticize** — "Instead of polling, consider SSE. Here's why..."
6. **Drive to closure** — "Given these concerns, I'd recommend three changes: (1)..., (2)..., (3)... Shall we prioritize?"
7. **Think about organizational impact** — "Who owns this service in production? What's the on-call story? Does this create a new operational burden?"

### Framework for Reviewing Any Design Doc

```
1. Problem Definition     → Is the problem clearly stated? Are goals measurable?
2. Scope                  → What's in scope? What's explicitly out? Are there hidden assumptions?
3. Scale                  → Numbers: QPS, storage, bandwidth. Do they add up?
4. Architecture           → Is the service decomposition sensible? Too many services? Too few?
5. Data Model             → Right database? Right schema? Indexing strategy?
6. API Contract           → RESTful? Consistent? Versioned? Error handling?
7. Consistency Model      → Strong vs. eventual? Is the choice justified?
8. Failure Modes          → What breaks? How do you detect it? How do you recover?
9. Security               → PCI scope? Auth? Data encryption? Secrets management?
10. Operational Readiness → Monitoring? Alerting? Runbooks? On-call?
11. Migration Plan        → How do you get from current state to this design?
12. Cost                  → Infrastructure cost? Justified by business value?
```
