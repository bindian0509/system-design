# Moniepoint — Engineering Manager Interview Cheatsheet
### Round: Project Planning, Execution & Product Thinking

---

## What They're Really Evaluating

```mermaid
mindmap
  root((EM Interview))
    Project Complexity
      Cross-functional teams
      Technical scope
      Ambiguity handling
    Team Management
      OKR to delivery mapping
      Sprint ceremonies
      Estimation & risk
    Stakeholder Engagement
      Communication cadence
      Misalignment handling
      Escalation judgment
    Performance Management
      High performer growth
      Underperformer support
      Remote team dynamics
    Leadership & Empathy
      Mentoring
      Conflict resolution
      Psychological safety
```

---

## 1. Project Complexity & Scope

### The 3-Layer Articulation

Always frame complex projects across three dimensions:

```mermaid
graph LR
    A["Business Problem<br/>(What & Why)"] --> D["Your Story"]
    B["Technical Challenge<br/>(How)"] --> D
    C["Human Coordination<br/>(Who & When)"] --> D
```

**Example:**
> "The **business problem** was onboarding drop-off at payment step. The **technical challenge** was integrating 3 third-party payment rails with inconsistent APIs. The **human coordination challenge** was aligning mobile, backend, and compliance teams with conflicting release schedules."

### Scope Discipline

- Use change request processes when scope expands mid-project
- Run discovery spikes and PoCs to reduce ambiguity early
- Document decisions with explicit tradeoffs, not just outcomes

---

## 2. Team Management

### 2a. Planning Hierarchy

```mermaid
graph TD
    OKR["OKR / Business Goal"]
    E["Epic"]
    F["Feature"]
    S["Story"]
    T["Task / Sub-task"]

    OKR --> E
    E --> F
    F --> S
    S --> T

    style OKR fill:#1a1a2e,color:#fff
    style E fill:#16213e,color:#fff
    style F fill:#0f3460,color:#fff
    style S fill:#533483,color:#fff
    style T fill:#e94560,color:#fff
```

### 2b. Estimation Approach

| Phase | Technique | Notes |
|---|---|---|
| Discovery / Roadmap | T-shirt sizing (S/M/L/XL) | Speed over precision |
| Sprint planning | Story points + team velocity | Anchor to historical data |
| Risk buffer | +20–30% on unknowns | Justify explicitly |
| Dependencies | Mapped upfront | External > internal risk |

### 2c. Risk Evaluation Matrix

```mermaid
quadrantChart
    title Risk Prioritization Matrix
    x-axis Low Probability --> High Probability
    y-axis Low Impact --> High Impact
    quadrant-1 Mitigate Actively
    quadrant-2 Monitor & Contingency Plan
    quadrant-3 Accept
    quadrant-4 Transfer or Reduce
    Third-party API instability: [0.7, 0.8]
    Team member unavailability: [0.4, 0.6]
    Minor tooling issues: [0.3, 0.2]
    Compliance approval delay: [0.6, 0.9]
    Infra provisioning lag: [0.5, 0.5]
```

### 2d. Dependency Management

```mermaid
graph LR
    subgraph Internal
        S1[Squad A - Auth]
        S2[Squad B - Payments]
    end
    subgraph External
        T1[3rd Party KYC API]
        T2[Core Banking System]
    end
    subgraph Temporal
        D1["Legal Sign-off<br/>Week 3"]
        D2["Infra Provisioning<br/>Week 1"]
    end

    S2 -->|depends on| S1
    S2 -->|integrates| T1
    S2 -->|integrates| T2
    S1 -->|blocked until| D2
    T1 -->|gated by| D1
```

> "I maintained a dependency map surfaced in planning, not during execution. I owned the resolution of external dependencies — I didn't wait for them to become blockers."

---

### 2e. Sprint Ceremonies — Purpose Over Ritual

```mermaid
timeline
    title Sprint Lifecycle (2-week sprint)
    Day 1 : Sprint Planning
           : Stories refined & pointed
           : Team commits to sprint goal
    Day 1-9 : Daily Standup
            : Blockers surfaced, not status
            : 15-min max
    Day 7 : Mid-sprint check
           : Scope risk assessment
           : Re-prioritize if needed
    Day 9 : Backlog Refinement
           : Groom next sprint's stories
           : Engineers shape requirements
    Day 10 : Sprint Review
            : Demo tied to OKR outcome
            : Sprint Retrospective
            : Systemic issues only
            : Action items tracked
```

**Ceremony philosophy:**
- Planning → "We're here to commit, not clarify."
- Standup → "What's blocked? Not what's done."
- Review → "Here's the metric movement, not just the feature."
- Retro → "Systemic patterns, not one-off vents."

### 2f. Detecting Delivery Drift — Early Signals

```mermaid
flowchart TD
    S1[Velocity dropping for 2+ sprints] --> A[Investigate]
    S2[Stories rolling over consistently] --> A
    S3[PR review cycles getting longer] --> A
    S4[Quieter standups, vague answers] --> A
    S5[Scope creep without change request] --> A

    A --> B{Root Cause}
    B --> C["Estimation problem<br/>→ Re-calibrate pointing"]
    B --> D["Team fatigue<br/>→ Reduce WIP, check workload"]
    B --> E["Technical debt blocker<br/>→ Spike + prioritize paydown"]
    B --> F["Unclear requirements<br/>→ Tighten Definition of Ready"]
```

### 2g. Measuring Impact — Outcome Not Output

Always connect delivery to the OKR:

```mermaid
graph LR
    OKR["OKR: Reduce onboarding<br/>drop-off by 15%"]
    I1["Initiative 1<br/>Simplify KYC flow"]
    I2["Initiative 2<br/>Faster payment method linking"]
    I3["Initiative 3<br/>Recover abandoned sessions"]

    L1["Leading Indicator<br/>Step completion rate"]
    L2["Leading Indicator<br/>Time-to-first-payment"]
    L3["Leading Indicator<br/>Session recovery rate"]

    LAG["Lagging Indicator<br/>Onboarding conversion %"]

    OKR --> I1 & I2 & I3
    I1 --> L1 --> LAG
    I2 --> L2 --> LAG
    I3 --> L3 --> LAG
```

---

## 3. Stakeholder Engagement

### Stakeholder Mapping

```mermaid
quadrantChart
    title Stakeholder Map
    x-axis Low Interest --> High Interest
    y-axis Low Influence --> High Influence
    quadrant-1 Manage Closely
    quadrant-2 Keep Satisfied
    quadrant-3 Monitor
    quadrant-4 Keep Informed
    CTO: [0.8, 0.9]
    Product Lead: [0.9, 0.7]
    Compliance Team: [0.5, 0.8]
    Finance Stakeholder: [0.3, 0.7]
    Engineering Team: [0.9, 0.4]
    End Users: [0.6, 0.2]
```

### Communication Cadence

| Stakeholder | Frequency | Format |
|---|---|---|
| High influence + interest | Weekly | 1:1 + written digest |
| High influence + low interest | Bi-weekly | Executive summary (3 bullets) |
| Low influence + high interest | On milestones | Update email |
| Engineering team | Daily | Standup + async Slack |

**Weekly project digest format:**
```
✅ What we shipped
⚠️  What's at risk
🙏 What I need from you
```

### Escalation Decision Tree

```mermaid
flowchart TD
    P[Problem Identified]
    P --> Q1{"Can I resolve<br/>with my authority?"}
    Q1 -->|Yes| R1[Resolve & document]
    Q1 -->|No| Q2{"Timeline at risk<br/>or stakeholder blocked?"}
    Q2 -->|No| R2["Continue tracking,<br/>flag in next digest"]
    Q2 -->|Yes| Q3{"Have I followed up<br/>at least twice?"}
    Q3 -->|No| R3["Follow up with<br/>documented trail"]
    Q3 -->|Yes| R4["Escalate to manager<br/>with context + recommendation"]
```

> Never say you never escalated. That signals you hide problems.

---

## 4. Performance Management

### Performance Diagnosis Framework

```mermaid
flowchart TD
    O[Observe declining performance]
    O --> Q1{"Is it Capability<br/>or Motivation?"}

    Q1 -->|Capability| Q2{"Is it systemic<br/>or individual?"}
    Q1 -->|Motivation| Q3{"Clear expectations<br/>been set?"}

    Q2 -->|Systemic| R1["Fix process/tooling<br/>or reassign ownership"]
    Q2 -->|Individual| R2["Skill gap plan<br/>+ pairing + resources"]

    Q3 -->|No| R3["Set explicit expectations<br/>with measurable outcomes"]
    Q3 -->|Yes| Q4{Personal circumstances?}
    Q4 -->|Yes| R4["Support plan<br/>+ temporary accommodation"]
    Q4 -->|No| R5["Structured PIP with<br/>clear milestones"]

    R2 --> FF["Check-in cadence<br/>+ document progress"]
    R3 --> FF
    R5 --> FF
    FF --> DEC{Improving?}
    DEC -->|Yes| G["Positive reinforcement<br/>+ close loop"]
    DEC -->|No| H["Decision point<br/>+ honest conversation"]
```

### High Performers — Growth, Not Just Output

| Risk | Signal | Response |
|---|---|---|
| Boredom | Asking for "more work" repeatedly | Give stretch problems, not more of the same |
| Undervalued | Quiet in planning, disengaged in retros | Give visibility: demos, cross-team forums |
| Burnout | High output + declining quality | Protect their time, reduce WIP |
| Leaving | Job market conversations | Career path conversation, not a counter-offer |

> "I made sure high performers had visibility and worked on problems they hadn't solved before. The goal was to grow their ceiling, not just their throughput."

### Remote Team Principles

```mermaid
graph TD
    A[Remote Team Effectiveness]

    A --> B["Async First<br/>Decisions in writing, not Slack"]
    A --> C["Defined Overlap Hours<br/>For real-time collaboration"]
    A --> D["Over-communicate Context<br/>Why, not just what"]
    A --> E["Small Early Wins<br/>Build trust with new members"]
    A --> F["Documentation as Artifact<br/>If it's not written, it didn't happen"]
```

---

## 5. Mentoring, Leadership & Conflict Resolution

### Mentoring — Deliberate, Not Accidental

**Skill alignment model:**

```mermaid
graph TD
    A["What the engineer<br/>is strong at"]
    B["What the engineer<br/>wants to grow in"]
    C["What the team needs"]
    M["Mentoring<br/>Opportunity"]

    A --- M
    B --- M
    C --- M
```

**Techniques:**
- Pairing on unfamiliar domains
- Code reviews as teaching moments, not just approval gates
- Shadow stakeholder conversations to grow communication skills
- Structured feedback: **Observe → Impact → Suggest**

> "Here's what I observed, here's the impact it had on the team, here's what I'd try differently."

### Conflict Resolution — Position vs. Interest

```mermaid
flowchart LR
    C[Conflict Between Engineers]
    C --> U1["Understand Party A's<br/>underlying interest"]
    C --> U2["Understand Party B's<br/>underlying interest"]
    U1 & U2 --> SF["Find shared ground<br/>team/product goal"]
    SF --> S["Structure a conversation<br/>with written proposals"]
    S --> O["Outcome: best of both<br/>or data-driven decision"]
```

**Concrete technique:**
> "I asked each engineer to write a 1-page doc: problem statement, proposed approach, tradeoffs. Then we reviewed together. The conflict became a design discussion."

---

## STAR Story Bank — Prepare These 5

```mermaid
graph LR
    STAR["STAR + L<br/>Situation<br/>Task<br/>Action<br/>Result<br/>Learning"]

    S1["Project Off-Track Recovery<br/>→ Risk management under pressure"]
    S2["Saying No to a Stakeholder<br/>→ Scope control & communication"]
    S3["Managing an Underperformer<br/>→ Empathy + performance management"]
    S4["Cross-functional Conflict<br/>→ Stakeholder alignment"]
    S5["A Technical Decision Gone Wrong<br/>→ Self-awareness & learning"]

    STAR --> S1 & S2 & S3 & S4 & S5
```

> Always add the **L — Learning**: "Here's what I'd do differently." This signals maturity, not weakness.

---

## Seniority Language Patterns

| Junior phrasing | Senior phrasing |
|---|---|
| "I kept everyone updated." | "I created visibility so stakeholders could make informed decisions." |
| "We balanced speed and quality." | "We had a healthy tension between shipping speed and quality — here's how we managed it." |
| "We used Agile." | "Here's how we adapted our process to the specific constraints of this project." |
| "Things went wrong but we fixed it." | "I own this outcome — here's what I should have caught earlier." |
| "We had good communication." | "I established explicit communication contracts with each stakeholder group." |

---

## Anti-patterns That Signal Disqualification

- Vague answers with no specifics
- Attributing success entirely to yourself
- No self-awareness about past failures
- Describing conflict avoidance as conflict resolution
- Not connecting delivery to business outcome
- "We never had to escalate" (signals problems were hidden)

---

## Closing Question to Ask Them

> "What does a great engineering leader look like at Moniepoint 12 months in — what would they have shipped, what relationships would they have built, and what problems would they have made smaller?"

This signals you're already thinking about **impact**, not just the interview.

---

*Prepared for Moniepoint EM Interview — Project Planning, Execution & Product Thinking Round*
