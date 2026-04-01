# Happy Flow: End-to-End Successful Transfer

> **Scenario:** Priya (verified user in the US) sends **$1,000 USD** to her father **Rajesh's HDFC bank account** in India.  
> She opens the app on a Tuesday afternoon, taps a few buttons, and 30 minutes later Rajesh gets an SMS confirming the money has landed.  
> Here is everything that happens in between.

---

## Step 1 -- Quote Creation (200ms)

Priya opens the app and fills in the transfer form:

| Field | Value |
|---|---|
| Send amount | $1,000.00 USD |
| Receive currency | INR |
| Recipient | Rajesh Sharma (saved) |
| Funding method | ACH (linked Bank of America account) |

The **Quote Engine** springs into action:

1. Fetches the cached mid-market rate: **83.42 INR/USD** (sourced from Reuters, cached < 5s ago).
2. Applies the corridor margin of 0.5%: **applied rate = 83.00 INR/USD**.
3. Calculates the fee: **$1.50** (ACH funding $0.50 + India bank deposit corridor fee $1.00).
4. Estimates delivery: **~4 hours** (IMPS rail available, partner healthy).

**Response to Priya's screen:**

```
Rajesh receives:  ₹83,000.00
Exchange rate:    1 USD = 83.00 INR
Fee:              $1.50
You pay:          $1,001.50
Arrives:          ~4 hours
```

The quote is locked for **45 seconds** with `quote_id: Q-abc123`. A countdown timer appears on Priya's screen. She has 45 seconds to confirm before the rate expires.

---

## Step 2 -- Transfer Initiation (100ms)

Priya taps **"Send $1,001.50"**. Her app fires:

```
POST /v1/transfers
{
  "quote_id": "Q-abc123",
  "recipient_id": "R-rajesh-456",
  "funding_source_id": "FS-boa-789",
  "idempotency_key": "priya-20260401-143022-abc"
}
```

The **Transfer Orchestrator** validates the quote hasn't expired (it's been 12 seconds -- plenty of time), confirms the recipient is active, and creates the transfer record:

| Field | Value |
|---|---|
| `transfer_id` | `T-xyz789` |
| `status` | `CREATED` |
| `created_at` | `2026-04-01T14:30:22Z` |

**Event published:** `transfer.initiated`

Priya sees a confirmation screen: *"Your transfer is on its way!"* with a progress tracker showing Step 1 of 4 lit up.

---

## Step 3 -- Funding via ACH (async, pre-funded for trusted users)

The **Funding Service** initiates an ACH debit of **$1,001.50** from Priya's linked Bank of America checking account.

Normally ACH takes 1-3 business days to settle. But Priya is a **trusted user** -- she has completed 12 previous transfers over 8 months, all without chargebacks. Her trust score is 92/100.

So the platform **pre-funds** this transfer: it advances the $1,001.50 from its own float pool, allowing the transfer to proceed immediately. When the ACH settles in 2 days, the float is replenished.

| Field | Value |
|---|---|
| `transfer_id` | `T-xyz789` |
| `status` | `FUNDED` |
| `funding_method` | `ACH_PREFUNDED` |

**Event published:** `transfer.funded`

> If Priya were a new user, the transfer would pause here until the ACH clears -- adding 1-3 business days to delivery. Trust scoring is what makes "instant" transfers possible for repeat customers.

---

## Step 4 -- Compliance Screening (300ms)

The **Compliance Engine** runs four checks in parallel against the transfer:

| Check | Result | Detail |
|---|---|---|
| Sanctions (OFAC, EU, UN) | CLEAR | Neither Priya nor Rajesh appear on any watchlist |
| PEP screening | NOT_PEP | No politically exposed person match |
| Velocity check | WITHIN_LIMITS | 3rd transfer this month, $2,800 cumulative (limit: $10,000/month) |
| Pattern analysis (ML) | LOW_RISK | Risk score: 0.08 (threshold: 0.65) |

All four checks pass. The transfer is **auto-approved** -- no manual review needed.

| Field | Value |
|---|---|
| `transfer_id` | `T-xyz789` |
| `status` | `SCREENING_PASSED` |
| `risk_score` | `0.08` |
| `review_type` | `AUTO_APPROVED` |

**Event published:** `transfer.screened`

> Transfers with a risk score above 0.65 get routed to a human compliance analyst. About 2-3% of transfers hit that threshold. Priya's straightforward recurring transfer to a family member scores well below it.

---

## Step 5 -- FX Conversion (50ms)

The **Treasury Service** executes the currency conversion from the platform's pre-funded USD liquidity pool.

No market order is placed for this individual transfer -- the platform batches its FX exposure and hedges at the portfolio level. Priya's $1,000 is converted at the locked rate of 83.00.

**Ledger entries (double-entry bookkeeping):**

| Entry | Account | Direction | Amount |
|---|---|---|---|
| 1 | `sender_funds_usd` | DEBIT | $1,000.00 |
| 2 | `sender_funds_inr` | CREDIT | ₹83,000.00 |
| 3 | `fee_revenue` | CREDIT | $1.50 |
| 4 | `sender_funding_hold` | DEBIT | $1.50 |

Every dollar in, every rupee out -- the books always balance.

| Field | Value |
|---|---|
| `transfer_id` | `T-xyz789` |
| `status` | `CONVERTED` |
| `fx_rate_applied` | `83.00` |
| `converted_amount` | `₹83,000.00` |

**Event published:** `transfer.converted`

---

## Step 6 -- Route Selection (30ms)

The **Routing Engine** evaluates available disbursement partners for the India corridor:

| Partner | Rail | Health Score | Cost | Estimated Time | Decision |
|---|---|---|---|---|---|
| Partner A | IMPS | 0.95 | $0.20 | ~30 min | **SELECTED** |
| Partner B | NEFT | 0.88 | $0.15 | ~2 hours | Backup |
| Partner C | UPI | 0.91 | $0.10 | ~5 min | Ineligible (bank deposit only) |

Partner A wins: strong health score, reasonable cost, and fast delivery via IMPS (Immediate Payment Service -- India's real-time payment rail).

Partner B is tagged as the **automatic failover**. If Partner A doesn't confirm delivery within 45 minutes, the system retries through Partner B on NEFT.

| Field | Value |
|---|---|
| `transfer_id` | `T-xyz789` |
| `status` | `ROUTED` |
| `partner` | `partner_a` |
| `rail` | `IMPS` |
| `failover_partner` | `partner_b` |

**Event published:** `transfer.routed`

---

## Step 7 -- Disbursement (~30 minutes)

The **Payout Service** sends the disbursement instruction to Partner A:

```json
{
  "partner_ref": "PAY-T-xyz789",
  "beneficiary_name": "RAJESH SHARMA",
  "beneficiary_account": "HDFC-XXXX-XXXX-4532",
  "beneficiary_ifsc": "HDFC0001234",
  "amount": 8300000,
  "currency": "INR",
  "rail": "IMPS"
}
```

Partner A queues the IMPS transfer to Rajesh's HDFC account. **28 minutes later**, the webhook fires back:

```json
{
  "event": "payout.completed",
  "partner_ref": "IMPS-98765",
  "status": "SUCCESS",
  "completed_at": "2026-04-01T14:58:45Z"
}
```

The money has landed in Rajesh's account.

| Field | Value |
|---|---|
| `transfer_id` | `T-xyz789` |
| `status` | `DELIVERED` |
| `partner_ref` | `IMPS-98765` |
| `delivered_at` | `2026-04-01T14:58:45Z` |

**Event published:** `transfer.delivered`

**Notifications triggered:**

- **Priya** receives a push notification: *"$1,000 delivered! Rajesh received ₹83,000 in his HDFC account."*
- **Priya** receives an SMS: *"Your transfer T-xyz789 has been delivered. ₹83,000 credited to Rajesh's account."*
- **Rajesh** receives an SMS: *"₹83,000 has been credited to your HDFC account ending 4532 from Priya via [Platform]. Ref: IMPS-98765."*

Priya's progress tracker now shows all four steps complete with a green checkmark.

---

## Step 8 -- Settlement (end of day, batch)

At **8:00 PM UTC**, the **Settlement Engine** kicks off the daily batch for the India corridor via Partner A:

| Metric | Value |
|---|---|
| Total transfers today | 3,200 |
| Total INR disbursed | ₹19.92 Cr (~$2.4M) |
| Priya's transfer | 1 of 3,200 |
| Settlement method | Single wire from nostro account |

Instead of 3,200 individual wires, the platform sends **one net settlement** of $2.4M from its USD nostro account to Partner A's settlement account. Partner A already disbursed the funds from its own float (just like our platform pre-funded Priya's ACH).

| Field | Value |
|---|---|
| `transfer_id` | `T-xyz789` |
| `status` | `SETTLED` |
| `settlement_batch` | `BATCH-20260401-IND-A` |
| `settled_at` | `2026-04-01T20:00:00Z` |

**Event published:** `transfer.settled`

Priya never sees this step. It's invisible infrastructure -- but it's what makes the unit economics work.

---

## Timing Summary

| Phase | Duration | Cumulative |
|---|---|---|
| Quote creation | 200ms | 200ms |
| Transfer initiation | 100ms | 300ms |
| Funding (pre-funded) | ~0ms (async) | 300ms |
| Compliance screening | 300ms | 600ms |
| FX conversion | 50ms | 650ms |
| Route selection | 30ms | 680ms |
| Disbursement | ~28 min | ~28 min |
| Settlement | EOD batch | EOD |

- **System processing time:** ~680ms (everything the platform controls)
- **Partner processing time:** ~28 minutes (IMPS through Partner A)
- **User-perceived time:** ~30 minutes from tap to delivery
- **Settlement:** Same-day batch at 8 PM UTC

---

## Sequence Diagram

```mermaid
sequenceDiagram
    actor Priya
    participant App as Mobile App
    participant QE as Quote Engine
    participant TO as Transfer Orchestrator
    participant FS as Funding Service
    participant CE as Compliance Engine
    participant TS as Treasury Service
    participant RE as Routing Engine
    participant PS as Payout Service
    participant PA as Partner A (IMPS)
    participant NS as Notification Service
    actor Rajesh

    Note over Priya, Rajesh: Step 1 — Quote Creation (200ms)
    Priya->>App: Send $1,000 USD → INR to Rajesh
    App->>QE: GET /v1/quotes?amount=1000&from=USD&to=INR
    QE-->>QE: Mid-market rate 83.42, apply 0.5% margin
    QE-->>App: rate=83.00, fee=$1.50, receive=₹83,000, quote_id=Q-abc123
    App-->>Priya: "Rajesh receives ₹83,000 — Confirm?"

    Note over Priya, Rajesh: Step 2 — Transfer Initiation (100ms)
    Priya->>App: Tap "Send $1,001.50"
    App->>TO: POST /v1/transfers {quote_id, recipient_id, idempotency_key}
    TO-->>TO: Create T-xyz789, status=CREATED
    TO--)NS: Event: transfer.initiated
    TO-->>App: transfer_id=T-xyz789
    App-->>Priya: "Transfer on its way!"

    Note over Priya, Rajesh: Step 3 — Funding (async, pre-funded)
    TO->>FS: Fund transfer T-xyz789
    FS-->>FS: ACH debit $1,001.50 initiated
    FS-->>FS: Trusted user (score 92) → pre-fund from float
    FS--)TO: Status → FUNDED
    FS--)NS: Event: transfer.funded

    Note over Priya, Rajesh: Step 4 — Compliance Screening (300ms)
    TO->>CE: Screen transfer T-xyz789
    par Sanctions Check
        CE-->>CE: OFAC, EU, UN → CLEAR
    and PEP Check
        CE-->>CE: NOT_PEP
    and Velocity Check
        CE-->>CE: 3rd this month, $2,800 cumulative → OK
    and Pattern Analysis
        CE-->>CE: ML risk score = 0.08 → LOW_RISK
    end
    CE--)TO: Status → SCREENING_PASSED, auto-approved
    CE--)NS: Event: transfer.screened

    Note over Priya, Rajesh: Step 5 — FX Conversion (50ms)
    TO->>TS: Convert $1,000 at rate 83.00
    TS-->>TS: Debit sender_funds_usd $1,000
    TS-->>TS: Credit sender_funds_inr ₹83,000
    TS--)TO: Status → CONVERTED
    TS--)NS: Event: transfer.converted

    Note over Priya, Rajesh: Step 6 — Route Selection (30ms)
    TO->>RE: Select route for INR bank deposit
    RE-->>RE: Partner A (IMPS): health=0.95, cost=$0.20 → SELECTED
    RE-->>RE: Partner B (NEFT): health=0.88 → backup
    RE--)TO: Status → ROUTED, partner=A, rail=IMPS
    RE--)NS: Event: transfer.routed

    Note over Priya, Rajesh: Step 7 — Disbursement (~30 min)
    TO->>PS: Disburse ₹83,000 via Partner A
    PS->>PA: Payout instruction (IMPS to HDFC-XXXX-4532)
    PA-->>PA: Process IMPS transfer (~28 min)
    PA->>PS: Webhook: payout.completed, ref=IMPS-98765
    PS--)TO: Status → DELIVERED
    PS--)NS: Event: transfer.delivered
    NS->>Priya: Push: "$1,000 delivered! ₹83,000 credited."
    NS->>Priya: SMS: "Transfer T-xyz789 delivered."
    NS->>Rajesh: SMS: "₹83,000 credited to HDFC-4532. Ref: IMPS-98765"

    Note over Priya, Rajesh: Step 8 — Settlement (8 PM UTC batch)
    TO->>TS: Batch settlement for India/Partner A
    TS-->>TS: Net 3,200 transfers → $2.4M single wire
    TS--)TO: Status → SETTLED, batch=BATCH-20260401-IND-A
    TS--)NS: Event: transfer.settled
```

---

## Ledger Entries Flow

```mermaid
flowchart TD
    subgraph funding ["Funding (Step 3)"]
        F1["Priya's Bank Account\n(external)"]
        F2["Platform Float Pool\n(USD)"]
        F3["Sender Funding Hold\n$1,001.50"]
        F1 -- "ACH debit $1,001.50\n(settles in 2 days)" --> F3
        F2 -- "Pre-fund advance\n$1,001.50 (immediate)" --> F3
    end

    subgraph conversion ["FX Conversion (Step 5)"]
        C1["Sender Funds USD\nDEBIT $1,000.00"]
        C2["Sender Funds INR\nCREDIT ₹83,000.00"]
        C3["Fee Revenue\nCREDIT $1.50"]
        C4["Sender Funding Hold\nDEBIT $1.50"]
        F3 -- "Split principal\nand fee" --> C1
        F3 -- "Fee portion" --> C4
        C1 -- "Convert at 83.00" --> C2
        C4 -- "Recognize fee" --> C3
    end

    subgraph disbursement ["Disbursement (Step 7)"]
        D1["Partner A Payable\nDEBIT ₹83,000.00"]
        D2["Rajesh's HDFC Account\n(external)"]
        C2 -- "Payout instruction" --> D1
        D1 -- "IMPS transfer\nRef: IMPS-98765" --> D2
    end

    subgraph settlement ["Settlement (Step 8)"]
        S1["Platform Nostro (USD)\nDEBIT $2.4M"]
        S2["Partner A Settlement\nCREDIT $2.4M"]
        D1 -. "Included in batch\n1 of 3,200 transfers" .-> S1
        S1 -- "Single net wire\nBATCH-20260401-IND-A" --> S2
    end

    style funding fill:#e8f4f8,stroke:#2980b9
    style conversion fill:#fef9e7,stroke:#f39c12
    style disbursement fill:#eafaf1,stroke:#27ae60
    style settlement fill:#f4ecf7,stroke:#8e44ad
```

---

## Notification Timeline

```mermaid
flowchart LR
    subgraph timeline ["Timeline of Events"]
        direction TB

        T0["14:30:22 UTC\nTransfer Created"]
        T1["14:30:22 UTC\nFunded (pre-funded)"]
        T2["14:30:22 UTC\nScreening Passed"]
        T3["14:30:23 UTC\nConverted"]
        T4["14:30:23 UTC\nRouted to Partner A"]
        T5["14:58:45 UTC\nDelivered"]
        T6["20:00:00 UTC\nSettled"]

        T0 --> T1 --> T2 --> T3 --> T4 --> T5 --> T6
    end

    subgraph priya_notifs ["Priya Receives"]
        direction TB
        P1["14:30:22 — Push Notification\n'Your transfer is on its way!\nRajesh will receive ₹83,000.'"]
        P2["14:30:23 — In-App Update\nProgress tracker: processing"]
        P3["14:58:45 — Push Notification\n'$1,000 delivered! Rajesh received\n₹83,000 in his HDFC account.'"]
        P4["14:58:45 — SMS\n'Your transfer T-xyz789 has been\ndelivered. ₹83,000 credited.'"]
        P5["14:58:46 — Email\nDetailed receipt with rate,\nfee breakdown, and ref number."]

        P1 --> P2 --> P3 --> P4 --> P5
    end

    subgraph rajesh_notifs ["Rajesh Receives"]
        direction TB
        R1["14:58:45 — SMS\n'₹83,000 credited to your HDFC\naccount ending 4532 from Priya.\nRef: IMPS-98765'"]
        R2["14:58:45 — Bank Notification\nHDFC push/SMS confirming\n₹83,000 IMPS credit"]

        R1 --> R2
    end

    T0 ~~~ P1
    T5 ~~~ P3
    T5 ~~~ R1

    style timeline fill:#f8f9fa,stroke:#6c757d
    style priya_notifs fill:#e8f4f8,stroke:#2980b9
    style rajesh_notifs fill:#eafaf1,stroke:#27ae60
```

---

## What Made This Transfer Fast

Looking back at Priya's transfer, a few design decisions kept the experience under 30 minutes:

1. **Pre-funding for trusted users** skipped the 1-3 day ACH wait. Priya's trust score of 92 (built over 12 clean transfers) unlocked this.
2. **Parallel compliance checks** ran all four screens simultaneously in 300ms instead of sequentially (~1.2s).
3. **Pre-funded liquidity pools** meant no real-time market order for the FX conversion -- just an internal ledger move in 50ms.
4. **Smart routing** picked IMPS (real-time rail) over NEFT (batch rail), shaving hours off delivery.
5. **Batch settlement** decoupled the partner payment from the user experience -- Rajesh got his money at 2:58 PM, but the platform settled with Partner A at 8:00 PM.

The result: 680ms of system processing, ~28 minutes of partner processing, and a father in India who can see ₹83,000 in his account before his daughter in the US has finished her afternoon coffee.
