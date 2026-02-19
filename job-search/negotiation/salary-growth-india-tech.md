# Salary Growth & Career Trajectory in India's Tech Industry

A comprehensive guide to compensation structures, growth curves, and strategic career planning for software engineers and engineering leaders in India.

---

## Table of Contents

- [Salary Curve by Experience](#salary-curve-by-experience)
- [FAANG-Tier Compensation Structure](#faang-tier-compensation-structure)
- [Company-Specific Base Salary Numbers](#company-specific-base-salary-numbers)
- [In-Hand Post-Tax Estimates](#in-hand-post-tax-estimates)
- [Career Growth Projection from ₹1 Cr Base](#career-growth-projection-from-1-cr-base)
- [Key Takeaways](#key-takeaways)

---

## Salary Curve by Experience

### Industry-Wide Overview (All Company Tiers)

| Experience | Typical CTC Range (LPA) | Growth Characteristics |
|---|---|---|
| 0–1 yr (Fresher) | 3–12 | Huge variance by college tier & company |
| 1–3 yrs | 6–20 | Steep; job switches yield 30–70% hikes |
| 3–5 yrs | 10–30 | Still strong growth, specialization begins |
| 5–7 yrs | 18–45 | Growth decelerates, first fork in the road |
| 7–10 yrs | 25–60 | First plateau for many at 15–25 LPA (services) |
| 10–12 yrs | 30–80 | Plateau solidifies unless at top-tier companies |
| 12–15 yrs | 35–1 Cr+ | Gap between top 5% and median widens to 3–5x |
| 15+ yrs | Role-dependent | Salary is a function of role & impact, not YoE |

### Growth Curve Shape

```mermaid
graph LR
    subgraph "Salary Growth Curve — India Tech"
        direction LR
        A["0-3 yrs<br/>📈 STEEP<br/>30-70% hikes<br/>via switching"] --> B["3-7 yrs<br/>📈 MODERATE<br/>Specialization<br/>matters"]
        B --> C["7-12 yrs<br/>📊 DECELERATING<br/>First plateau<br/>zone"]
        C --> D["12+ yrs<br/>📉 FLAT for median<br/>Role-dependent<br/>for top performers"]
    end
```

### The Two Diverging Paths

```mermaid
flowchart TD
    START["Software Engineer<br/>0-5 yrs | 3-30 LPA"] --> MID["Mid-Career Fork<br/>5-8 yrs"]

    MID -->|"Upskills + switches<br/>to product companies"| TOP_PATH["Top Performer Path"]
    MID -->|"Stays in services<br/>or stagnates"| MED_PATH["Median Path"]

    TOP_PATH --> T1["Senior IC / EM<br/>8-12 yrs | 50-95 LPA"]
    T1 --> T2["Staff+ / Director<br/>12-15 yrs | 1-2 Cr"]
    T2 --> T3["Principal / VP<br/>15+ yrs | 2-4 Cr+"]

    MED_PATH --> M1["Senior Developer<br/>8-12 yrs | 20-35 LPA"]
    M1 --> M2["Tech Lead / Manager<br/>12-15 yrs | 30-50 LPA"]
    M2 --> M3["Plateau Zone<br/>15+ yrs | 35-60 LPA"]

    style TOP_PATH fill:#2d6a4f,color:#fff
    style MED_PATH fill:#bc4749,color:#fff
    style T3 fill:#2d6a4f,color:#fff
    style M3 fill:#bc4749,color:#fff
```

### Plateau Breakers vs Plateau Traps

```mermaid
mindmap
  root((Career<br/>Trajectory))
    Plateau Breakers
      Company Tier Upgrade
        Service → Product → FAANG
      Specialization
        ML/AI, Distributed Systems, Platform/Infra
      Management Track
        Director/VP roles at scale
      Equity/RSUs
        30-60% of TC at top companies
      Geography Arbitrage
        Remote US/EU roles from India
    Plateau Traps
      Same Company 5+ yrs
        8-12% annual raises don't keep pace
      Services Ecosystem
        Comp ceiling is real
      Breadth Without Depth
        No standout specialization
      Under-negotiating
        Leaving 20-40% on the table
```

---

## FAANG-Tier Compensation Structure

### IC Track — Total Compensation

| Level | Title | YoE | Base (LPA) | Bonus (LPA) | RSUs/yr (LPA) | Total Comp (LPA) |
|---|---|---|---|---|---|---|
| L3 / SDE-1 | Software Engineer | 0–2 | 15–22 | 2–4 | 5–12 | **22–38** |
| L4 / SDE-2 | Software Engineer II | 2–5 | 22–32 | 4–6 | 10–25 | **36–60** |
| L5 / Senior | Senior SWE | 5–10 | 30–45 | 6–10 | 20–45 | **55–95** |
| L6 / Staff | Staff SWE | 8–15 | 40–55 | 8–15 | 35–70 | **85–140** |
| L7 / Sr Staff | Senior Staff SWE | 12–20 | 50–65 | 12–20 | 60–120 | **120–200+** |
| L8 / Principal | Principal Engineer | 15–25+ | 60–75 | 15–25 | 100–200+ | **175–300+** |
| L9+ / Fellow | Distinguished / Fellow | 20+ | Rare in India | — | — | **250–400+** |

### EM Track — Total Compensation

| Level | Title | YoE | Team Size | Total Comp (LPA) |
|---|---|---|---|---|
| M0 / L5 | Engineering Manager | 7–12 | 5–10 ICs | **60–100** |
| M1 / L6 | Senior EM | 10–15 | 15–30 ICs | **90–150** |
| M2 / L7 | Director of Engineering | 12–18 | 40–80 ICs | **130–220** |
| M3 / L8 | Senior Director | 15–22 | 80–200+ ICs | **180–300+** |
| VP / L9+ | VP of Engineering | 18+ | Org-level | **250–400+** |

### Compensation Mix by Level

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'pie1': '#2d6a4f', 'pie2': '#e9c46a', 'pie3': '#e76f51'}}}%%
pie title L3 (SDE-1) — Comp Mix
    "Base (65%)" : 65
    "Bonus (10%)" : 10
    "RSUs (25%)" : 25
```

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'pie1': '#2d6a4f', 'pie2': '#e9c46a', 'pie3': '#e76f51'}}}%%
pie title L5 (Senior) — Comp Mix
    "Base (48%)" : 48
    "Bonus (10%)" : 10
    "RSUs (42%)" : 42
```

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'pie1': '#2d6a4f', 'pie2': '#e9c46a', 'pie3': '#e76f51'}}}%%
pie title L7 (Sr Staff) — Comp Mix
    "Base (30%)" : 30
    "Bonus (8%)" : 8
    "RSUs (62%)" : 62
```

### Level Progression & Jump Economics

```mermaid
flowchart LR
    L3["L3<br/>SDE-1<br/>22-38 LPA"] -->|"+40-60%"| L4["L4<br/>SDE-2<br/>36-60 LPA"]
    L4 -->|"+50-70%"| L5["L5<br/>Senior<br/>55-95 LPA"]
    L5 -->|"+60-80%<br/>⚠️ HARDEST JUMP"| L6["L6<br/>Staff<br/>85-140 LPA"]
    L6 -->|"+40-60%"| L7["L7<br/>Sr Staff<br/>120-200 LPA"]
    L7 -->|"+30-50%"| L8["L8<br/>Principal<br/>175-300+ LPA"]

    style L5 fill:#e76f51,color:#fff
    style L6 fill:#2d6a4f,color:#fff
```

### Typical Timeline Between Levels

```mermaid
gantt
    title Typical Career Timeline at FAANG (India)
    dateFormat YYYY
    axisFormat %Y

    section IC Track
    L3 - SDE-1           :l3, 2024, 2y
    L4 - SDE-2           :l4, after l3, 3y
    L5 - Senior (many plateau here) :crit, l5, after l4, 5y
    L6 - Staff            :l6, after l5, 5y
    L7 - Senior Staff     :l7, after l6, 6y
    L8 - Principal (very rare) :l8, after l7, 5y

    section EM Track
    EM (L5)              :em5, 2031, 4y
    Senior EM (L6)       :em6, after em5, 4y
    Director (L7)        :em7, after em6, 5y
    Senior Director (L8) :em8, after em7, 5y
```

---

## Company-Specific Base Salary Numbers

### Google India

| Level | Base (LPA) | Monthly Gross |
|---|---|---|
| L3 | 18–22 LPA | ₹1.50L – ₹1.83L |
| L4 | 25–32 LPA | ₹2.08L – ₹2.67L |
| L5 | 35–45 LPA | ₹2.92L – ₹3.75L |
| L6 | 45–55 LPA | ₹3.75L – ₹4.58L |
| L7 | 55–65 LPA | ₹4.58L – ₹5.42L |

Strong RSU grants. Refreshers generous for top performers. L5 is the terminal level for many.

### Amazon India

| Level | Base (LPA) | Monthly Gross |
|---|---|---|
| L4 (SDE-1) | 16–22 LPA | ₹1.33L – ₹1.83L |
| L5 (SDE-2) | 22–32 LPA | ₹1.83L – ₹2.67L |
| L6 (SDE-3) | 30–42 LPA | ₹2.50L – ₹3.50L |
| L7 (Principal) | 40–55 LPA | ₹3.33L – ₹4.58L |

RSU vesting is **back-loaded**: 5% / 15% / 40% / 40%. Year 1–2 comp lower, padded with sign-on. Year 3–4 is when real money hits.

### Microsoft India

| Level | Base (LPA) | Monthly Gross |
|---|---|---|
| L59 (SDE) | 16–20 LPA | ₹1.33L – ₹1.67L |
| L61 (SDE-2) | 22–30 LPA | ₹1.83L – ₹2.50L |
| L63 (Senior) | 32–42 LPA | ₹2.67L – ₹3.50L |
| L65 (Principal) | 42–55 LPA | ₹3.50L – ₹4.58L |
| L67 (Partner) | 55–70 LPA | ₹4.58L – ₹5.83L |

Most **base-heavy** FAANG. Generally best work-life balance in India.

### Apple India

| Level | Base (LPA) | Monthly Gross |
|---|---|---|
| ICT2 | 18–24 LPA | ₹1.50L – ₹2.00L |
| ICT3 | 26–35 LPA | ₹2.17L – ₹2.92L |
| ICT4 | 36–48 LPA | ₹3.00L – ₹4.00L |
| ICT5 | 48–60 LPA | ₹4.00L – ₹5.00L |

### Base Salary Comparison Across Companies

```mermaid
xychart-beta
    title "Base Salary by Level — FAANG India (LPA, midpoint)"
    x-axis ["L3/SDE-1", "L4/SDE-2", "L5/Senior", "L6/Staff", "L7/Sr Staff"]
    y-axis "Base Salary (LPA)" 10 --> 70
    bar [20, 28, 40, 50, 60]
    bar [19, 27, 37, 48, 62]
    bar [18, 26, 37, 48, 55]
```

---

## In-Hand Post-Tax Estimates

| Gross Monthly | Approx Tax (Old Regime ~30%) | In-Hand Monthly |
|---|---|---|
| ₹1.50L | ~₹30K | ~₹1.20L |
| ₹2.00L | ~₹45K | ~₹1.55L |
| ₹2.50L | ~₹60K | ~₹1.90L |
| ₹3.00L | ~₹78K | ~₹2.22L |
| ₹3.75L | ~₹1.02L | ~₹2.73L |
| ₹4.50L | ~₹1.28L | ~₹3.22L |
| ₹5.50L | ~₹1.60L | ~₹3.90L |
| ₹6.25L | ~₹1.85L | ~₹4.40L |

> Assumes old tax regime with standard deductions and 80C.

---

## Career Growth Projection from ₹1 Cr Base

**Starting point:** Senior Engineering Manager, ₹1 Cr base, no bonus or RSUs.

### Scenario Overview

```mermaid
flowchart TD
    NOW["📍 TODAY<br/>Senior EM | ₹1 Cr Base<br/>All Cash, No Equity"]

    NOW --> S1["🟢 Scenario 1<br/>Stay & Grow Organically"]
    NOW --> S2["🔵 Scenario 2<br/>Move to FAANG"]
    NOW --> S3["🟠 Scenario 3<br/>Startup VP/CTO"]
    NOW --> S4["🟣 Scenario 4<br/>Consulting / Fractional CTO"]

    S1 --> S1R["10yr: ₹2.0-2.5 Cr base<br/>Low risk, low ceiling"]
    S2 --> S2R["10yr: ₹3.0-4.5 Cr TC<br/>Medium risk, high ceiling"]
    S3 --> S3R["10yr: ₹1.5 Cr base + ₹0-50 Cr equity<br/>High risk, uncapped"]
    S4 --> S4R["10yr: ₹2.0-4.0 Cr earnings<br/>Medium risk, flexible"]

    style NOW fill:#264653,color:#fff
    style S1 fill:#2d6a4f,color:#fff
    style S2 fill:#1d3557,color:#fff
    style S3 fill:#e76f51,color:#fff
    style S4 fill:#6a4c93,color:#fff
```

### Scenario 1 — Stay & Grow Organically (Same Company Type)

High-base / no-equity companies (Indian startups, non-FAANG MNCs).

| Year | Role | Expected Base | Annual Growth |
|---|---|---|---|
| Now | Senior EM | ₹1.00 Cr | — |
| Year 1–2 | Senior EM → Director | ₹1.10–1.20 Cr | 10–12% |
| Year 3–4 | Director of Engineering | ₹1.25–1.45 Cr | 8–12% |
| Year 5–6 | Senior Director | ₹1.45–1.70 Cr | 8–10% |
| Year 7–8 | VP Engineering | ₹1.70–2.00 Cr | 8–10% |
| Year 9–10 | VP / SVP Engineering | ₹2.00–2.50 Cr | 5–10% |

```mermaid
flowchart LR
    Y0["Year 0<br/>Sr EM<br/>₹1.0 Cr"] --> Y2["Year 2<br/>Director<br/>₹1.2 Cr"]
    Y2 --> Y5["Year 5<br/>Sr Director<br/>₹1.5 Cr"]
    Y5 --> Y8["Year 8<br/>VP Engg<br/>₹1.85 Cr"]
    Y8 --> Y10["Year 10<br/>VP/SVP<br/>₹2.0-2.5 Cr"]

    style Y0 fill:#264653,color:#fff
    style Y10 fill:#2d6a4f,color:#fff
```

**Conservative estimate (with a stall):** ₹1.6–2.0 Cr.

### Scenario 2 — Move to FAANG (Equity Enters the Picture)

| Year | Role | Base | Bonus | RSUs/yr | Total Comp |
|---|---|---|---|---|---|
| Year 1 | EM L6 (lateral) | 50–55 LPA | 8–10 LPA | 40–70 LPA | ₹1.0–1.35 Cr |
| Year 2–3 | EM L6 (refreshers) | 55–60 LPA | 10–12 LPA | 55–85 LPA | ₹1.2–1.55 Cr |
| Year 4–5 | Director L7 | 60–68 LPA | 12–18 LPA | 80–130 LPA | ₹1.5–2.2 Cr |
| Year 6–8 | Sr Director L8 | 68–78 LPA | 15–25 LPA | 130–220 LPA | ₹2.1–3.2 Cr |
| Year 9–10 | Sr Director / VP | 75–85 LPA | 20–30 LPA | 200–350 LPA | ₹3.0–4.5 Cr |

```mermaid
flowchart LR
    Y0["Year 0<br/>EM L6<br/>TC ₹1.0 Cr<br/>⚠️ Base drops to 55L"] --> Y3["Year 3<br/>EM L6<br/>TC ₹1.4 Cr<br/>Refreshers kick in"]
    Y3 --> Y5["Year 5<br/>Director L7<br/>TC ₹2.0 Cr"]
    Y5 --> Y8["Year 8<br/>Sr Dir L8<br/>TC ₹2.8 Cr"]
    Y8 --> Y10["Year 10<br/>VP<br/>TC ₹3.5-4.5 Cr"]

    style Y0 fill:#e76f51,color:#fff
    style Y10 fill:#1d3557,color:#fff
```

> **The psychological catch:** Base drops from ₹1 Cr to ~₹55 LPA. Feels like a 45% pay cut. TC surpasses current comp within 2–3 years and significantly ahead by Year 5+.

### Scenario 3 — Startup VP/CTO (Binary Outcome)

```mermaid
flowchart TD
    START["VP Engg / CTO<br/>₹1.0-1.5 Cr base<br/>+ 0.5-2% equity"]
    START --> BUILD["Build for 3-5 years<br/>Base: ₹1.2-1.8 Cr"]
    BUILD --> SUCCESS["🎯 IPO / Acquisition<br/>Equity: ₹5-50 Cr"]
    BUILD --> FAIL["❌ Startup fails<br/>Equity: ₹0"]

    style SUCCESS fill:#2d6a4f,color:#fff
    style FAIL fill:#bc4749,color:#fff
```

### Scenario 4 — Consulting / Fractional CTO

| Year | Mode | Annual Earnings |
|---|---|---|
| Year 1–2 | Full-time + side consulting | ₹1.0–1.3 Cr |
| Year 3–5 | Fractional CTO (2–3 clients) | ₹1.5–2.5 Cr |
| Year 6–10 | Advisory + consulting firm | ₹2.0–4.0 Cr |

### 10-Year Outcome Comparison

```mermaid
quadrantChart
    title 10-Year Strategy Comparison
    x-axis "Low Risk" --> "High Risk"
    y-axis "Low Reward" --> "High Reward"
    "Stay & Grow": [0.2, 0.3]
    "FAANG Move": [0.45, 0.7]
    "Remote US Co": [0.4, 0.55]
    "Consulting": [0.5, 0.5]
    "Startup CTO": [0.85, 0.9]
```

| Strategy | 10-Year Base | 10-Year TC | Risk |
|---|---|---|---|
| Stay & grow organically | ₹1.6–2.0 Cr | ₹1.6–2.0 Cr | Low |
| Switch to FAANG | ₹65–85 LPA (capped) | ₹3.0–4.5 Cr | Medium |
| Startup VP/CTO | ₹1.2–1.8 Cr | ₹1.5 Cr – ₹50 Cr | High |
| Consulting / Fractional | N/A | ₹2.0–4.0 Cr | Medium |
| Remote for US company | ₹1.5–2.5 Cr | ₹2.0–3.5 Cr | Medium |

### The Compounding Reality Check

```
10% annual raise on ₹1 Cr over 10 years  = ₹2.59 Cr (nominal)
Inflation at ~6% annually                 = erodes real value
Real purchasing power after 10 years      ≈ ₹1.45 Cr (in today's money)

→ Only ~45% real growth over a decade without strategic moves.
```

---

## Key Takeaways

```mermaid
mindmap
  root((Strategic<br/>Insights))
    Salary Curve
      Steep 0-5 yrs
      Moderate 5-10 yrs
      Flat 10+ yrs for median
      Role-dependent at senior levels
    FAANG Economics
      Base caps at 55-75 LPA
      RSUs are the real differentiator
      L5→L6 is the hardest jump
      Each level above L6 halves headcount
    At ₹1 Cr Base
      All-cash = maximum optionality
      No golden handcuffs
      Equity is the unlock for 3-4x growth
      Next 2-3 yrs are highest-leverage window
    Career Moves
      Company tier upgrade = biggest lever
      Negotiation = 20-40% swing
      Director ceiling in India for global orgs
      Age 35-42 is prime window for strategic moves
```

### The One-Line Summary

> Without equity entering the picture, base salary alone will roughly 1.5–2.5x over the next decade. To get to 3–4x+, you need meaningful equity compensation or a startup bet. The all-cash ₹1 Cr is a great foundation — the question is whether to trade some stability for higher upside.

---

*Last updated: February 2026. All figures are approximate and based on publicly available data, community reports (levels.fyi, Glassdoor, Blind), and industry knowledge. Individual outcomes vary significantly.*
