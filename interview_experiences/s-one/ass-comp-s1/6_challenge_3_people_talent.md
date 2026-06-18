# Challenge 3: People & Talent Management

As a Senior Engineering Manager, your ability to align strong engineering personalities and protect team morale during turbulence is just as critical as your system design skills.

## 1. Technical Conflict Resolution: Engineer A vs. Engineer B

**The Conflict:** 
*   **Engineer A:** Wants a stream-processing layer (Flink/Kafka Streams) for real-time Alert Coalescing. (Pro: Scalable, low latency. Con: Operational complexity).
*   **Engineer B:** Wants to write raw events to a DB and use async background cron jobs to coalesce. (Pro: Fast to build, simple. Con: High database load, higher latency).

**The Managerial Approach (Data-Driven Mediation):**
My role is not to dictate the architecture top-down, but to facilitate a framework where the *right* technical answer reveals itself through data, ensuring both engineers feel heard and commit to the final decision.

1.  **De-escalate & Re-align on Constraints:** I would pull both engineers into a room and re-center the conversation on the project's Non-Functional Requirements (NFRs): **Billions of daily events and a < 5-minute detection SLA.**
2.  **Request a Mini-RFC / Whiteboarding Session:** I would ask them to mathematically model their solutions against the constraints.
    *   *Evaluating Engineer B's approach:* If an agent sends 50 events in 10 minutes, and we have 5 million agents, we are writing 250 million raw events to the DB very quickly. A cron job then has to scan millions of rows every minute to find matches, group them, and update their state. We would calculate the DB IOPS required for this.
    *   *Evaluating Engineer A's approach:* Flink handles "Tumbling Windows" natively in memory. It keeps the 50 events in state, and when the 10-minute window closes, it emits exactly *one* alert to the DB.
3.  **The "Aha" Moment & Decision:** The back-of-the-napkin math will clearly show that Engineer B's database-polling approach will melt the database at our scale and likely violate the 5-minute SLA. By letting the math do the talking, Engineer B can gracefully concede without bruising their ego. 
4.  **Disagree and Commit:** We officially commit to Engineer A's stream processing approach. To address Engineer B's valid concern about "infrastructure complexity", I would assign Engineer B to lead the operational readiness (CI/CD, observability) of the Flink cluster, giving them ownership of the risk they identified.

---

## 2. Maintaining Morale Through Distractions & Delays

Handling the gateway delay (Task 2) and the legacy support spike can easily burn out a team. Here is how I maintain engagement:

*   **The "Umbrella" Strategy:** The most demoralizing thing for engineers is constant context-switching. By creating the 2-person "Tiger Team" for the legacy issue, I shield the remaining 8 engineers entirely. They don't attend the support meetings; they stay in the flow state building the MVP.
*   **Reframing Delays as Opportunities:** The Gateway delay could cause a loss of momentum. I would reframe building the "Telemetry Simulator" from a *workaround* into an *engineering achievement*. When the simulator hits 1 billion simulated events per day, we celebrate that milestone publicly.
*   **Investing in Growth:** I would use the buffer time created by the delay to invest in the team's skills. If we committed to Flink (from the conflict resolution above), I'd sponsor time for the team to take Flink masterclasses or certifications, turning idle time into career growth.
*   **Radical Transparency (No Blame):** I would be completely open about the Gateway team's delays in our weekly syncs, focusing strictly on timeline impacts without badmouthing the other team. "They are facing scaling challenges, so we are adapting. Here is our new path forward."

---

## 3. Project Management Gantt Chart

Below is the execution timeline spanning Q1 (MVP) and Q2 (GA), reflecting the parallel execution of the Simulator, the Tiger Team handling the legacy bug, and the delayed integration with the Gateway Team.

```mermaid
gantt
    title Singularity Health Center - Execution Roadmap
    dateFormat  YYYY-MM-DD
    axisFormat  %b %Y
    
    section Infrastructure & Mocks
    Design & Architecture Sync       :done,    des1, 2026-07-01, 7d
    Define Protobuf Contracts        :done,    des2, 2026-07-08, 5d
    Build Telemetry Simulator (Go)   :active,  mock1, 2026-07-15, 14d
    Setup Kafka & Flink Clusters     :         infra1, 2026-07-15, 14d
    
    section Legacy Tech Debt
    Tiger Team: Investigate Spike    :crit,    leg1, 2026-07-05, 3d
    Apply Band-Aid (Timeout Config)  :crit,    leg2, 2026-07-08, 2d
    Monitor Legacy Stability         :         leg3, 2026-07-10, 14d

    section Q1: MVP Development (Simulated)
    Backend: Flink Rules Engine      :         mvp1, 2026-07-29, 21d
    Backend: Management API (Java)   :         mvp2, 2026-07-29, 21d
    Frontend: React Read-only UI     :         mvp3, 2026-08-05, 21d
    Performance Load Testing         :         mvp4, 2026-08-26, 14d
    Internal Dogfooding Release      :milestone, m1, 2026-09-09, 0d
    
    section Core Integration
    Gateway Team Resolves Delay      :crit,    gw1, 2026-09-01, 0d
    Integrate Real Telemetry Stream  :         int1, 2026-09-09, 14d
    Beta Customer Rollout            :milestone, m2, 2026-09-23, 0d
    
    section Q2: General Availability
    Alert Coalescing & Routing       :         ga1, 2026-09-25, 21d
    Custom User Rule Creation UI     :         ga2, 2026-09-25, 21d
    Historical ClickHouse Dashboards :         ga3, 2026-10-05, 21d
    Global GA Launch                 :milestone, m3, 2026-11-01, 0d
```
