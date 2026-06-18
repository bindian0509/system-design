# Challenge 2: Execution, Delivery & Operational Distractions

As an Engineering Manager, system design is only half the job. This section covers the tactical realities of leading a team of 10 engineers through dependencies, legacy tech debt, and phased delivery.

## 1. Phasing & Multi-Quarter Roadmap (MVP vs. GA)

To deliver value quickly and mitigate risk, the rollout is broken into strict phases.

### Q1: The MVP (De-Risking the Core)
*   **Goal:** Prove the end-to-end pipeline (Kafka -> Flink -> Redis -> UI) works at scale without triggering alert fatigue.
*   **Scope:**
    *   Only 2 default rules: *Low Disk Space* (Stateless) and *Agent Offline / Missing Heartbeat* (Stateful).
    *   Read-only UI Console (no custom rule creation yet).
    *   No external alerting (no PagerDuty/Emails). Anomalies only show in the UI console to prevent false-positive spam.
*   **Audience:** SentinelOne internal deployments (Dogfooding) and 5-10 trusted Beta customers.

### Q2: General Availability (GA)
*   **Goal:** Full customer rollout and platform extensibility.
*   **Scope:**
    *   User-defined custom rules (e.g., "Alert if Version < X").
    *   Full Alerting Service integration (Webhooks, Email, Slack, PagerDuty) with deduplication.
    *   Historical dashboards querying ClickHouse for 30-day trends.
*   **Audience:** All customers globally (Millions of endpoints).

---

## 2. Dependency Risk: The Gateway Delay

**The Problem:** The core Ingestion Gateway team is delayed by 2 months. We cannot get real telemetry routed to our Kafka topics.

**The Managerial Response (The "Mock & Decouple" Strategy):**
You cannot let your team of 10 engineers sit idle or act as victims of another team's delay. We must decouple our progress from theirs.

1.  **Contract-Driven Development:** Immediately align with the Gateway team on the exact `Protobuf` schema and Kafka topic structure. Freeze this contract.
2.  **Build a High-Scale Simulator:** Allocate 1-2 backend engineers to write a Go-based "Telemetry Load Generator." This tool will generate fake, randomized telemetry matching the agreed Protobuf schema and pump it directly into our Kafka topics at production scale (billions of events).
3.  **Parallel Execution:** 
    *   The backend team uses the simulator to performance test the Flink cluster, Redis, and ClickHouse under maximum load.
    *   The frontend team uses the simulated data to build and refine the React UI.
4.  **The Result:** When the Gateway team finally delivers in 2 months, our downstream system is already built, load-tested, and UI-polished. The integration becomes a simple plumbing check rather than a massive bottleneck.

---

## 3. Operational Drain: Legacy Service Spike

**The Problem:** A 40% spike in customer support escalations because the legacy heartbeat service is falsely showing agents as "Offline". This is draining the team's resources and threatening the Health Center MVP timeline.

**The Managerial Response (The "Triage & Box" Strategy):**
As an engineering leader, you must balance customer trust (fixing the live issue) with strategic progress (delivering the new MVP). You cannot ignore the support tickets, but you also cannot halt the MVP or do a massive rewrite of a system that is about to be deprecated.

1.  **Isolate the Distraction (The Tiger Team):** Do *not* put all 10 engineers on the legacy bug. Rotate 2 senior engineers into a short-lived "Tiger Team" timeboxed to exactly 1 week. The other 8 engineers must remain heads-down on the Health Center MVP.
2.  **Apply a Tactical Band-Aid, Not a Cure:** The goal of the Tiger Team is to stop the bleeding, not to achieve architectural purity on a dying system.
    *   *Investigation:* The false "Offlines" are likely due to temporary network blips, database connection timeouts in the legacy system, or a recent OS update altering heartbeat intervals.
    *   *The Fix:* If the legacy system flags an agent offline after 3 minutes of no heartbeat, simply **increase the threshold to 10 minutes** via a config change. 
3.  **Manage Stakeholder Expectations:** 
    *   Inform Customer Support and Product that you have applied a mitigation. 
    *   Acknowledge the trade-off: The system will be slower to report *actual* offline agents, but the 40% spike in false alarms will vanish instantly, closing the support tickets.
    *   Reiterate that the true, highly-accurate fix is the new Flink-based Health Center MVP, protecting the team's mandate to finish the new project.
