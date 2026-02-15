# 10 — SLI / SLO / SLA / Error Budget & Alerting

## Terminology

```mermaid
graph LR
    SLI["SLI<br/>Service Level Indicator<br/><b>What we measure</b>"]
    SLO["SLO<br/>Service Level Objective<br/><b>What we target internally</b>"]
    SLA["SLA<br/>Service Level Agreement<br/><b>What we promise externally</b>"]
    EB["Error Budget<br/><b>How much failure<br/>we can tolerate</b>"]

    SLI -->|"Measured against"| SLO
    SLO -->|"Stricter than"| SLA
    SLO -->|"Derives"| EB

    style SLI fill:#4a90d9,color:#fff
    style SLO fill:#50c878,color:#000
    style SLA fill:#f5a623,color:#000
    style EB fill:#7b68ee,color:#fff
```

**Key principle:** SLO is always stricter than SLA. If SLA promises 99.9%, SLO targets 99.95%. The gap is your safety margin — if you breach SLO, you have time to react before breaching SLA and owing customers remediation.

---

## SLIs (Service Level Indicators)

### Defining Good SLIs

An SLI must be a **ratio**: good events / total events. Not an average, not a percentile on its own. The ratio gives us a number between 0 and 1 (or 0% and 100%) that directly maps to SLO thresholds and error budgets.

### Write Path SLIs

```mermaid
graph TD
    subgraph "SLI 1: Write Availability"
        W1_NUM["Good: POST requests returning<br/>202 Accepted"]
        W1_DEN["Total: All POST requests received"]
        W1_CALC["SLI = 202 responses / total POST requests"]
        W1_NUM --> W1_CALC
        W1_DEN --> W1_CALC
    end

    subgraph "SLI 2: Write Latency"
        W2_NUM["Good: POST requests completing<br/>in < 100ms"]
        W2_DEN["Total: All successful POST requests"]
        W2_CALC["SLI = requests < 100ms / total successful requests"]
        W2_NUM --> W2_CALC
        W2_DEN --> W2_CALC
    end

    subgraph "SLI 3: Data Durability"
        W3_NUM["Good: Accepted logs (202'd) that<br/>appear in MySQL within 5 min"]
        W3_DEN["Total: All accepted logs (202'd)"]
        W3_CALC["SLI = queryable within 5min / total accepted"]
        W3_NUM --> W3_CALC
        W3_DEN --> W3_CALC
    end

    style W1_CALC fill:#4a90d9,color:#fff
    style W2_CALC fill:#4a90d9,color:#fff
    style W3_CALC fill:#4a90d9,color:#fff
```

| SLI | Formula | What It Captures |
|---|---|---|
| **Write Availability** | `count(POST returning 202) / count(all POST requests)` | Can clients send logs? |
| **Write Latency** | `count(POST < 100ms) / count(successful POST requests)` | Is the POST endpoint responsive? |
| **Data Durability** | `count(accepted logs queryable within 5 min) / count(all accepted logs)` | Do accepted logs actually reach MySQL? |

### Read Path SLIs

```mermaid
graph TD
    subgraph "SLI 4: Read Availability"
        R1_NUM["Good: GET requests returning<br/>200 OK (full or partial results)"]
        R1_DEN["Total: All valid GET requests"]
        R1_CALC["SLI = 200 responses / total valid GET requests"]
        R1_NUM --> R1_CALC
        R1_DEN --> R1_CALC
    end

    subgraph "SLI 5: Read Latency"
        R2_NUM["Good: GET requests completing<br/>in < 5 seconds"]
        R2_DEN["Total: All successful GET requests"]
        R2_CALC["SLI = requests < 5s / total successful requests"]
        R2_NUM --> R2_CALC
        R2_DEN --> R2_CALC
    end

    subgraph "SLI 6: Read Completeness"
        R3_NUM["Good: GET requests served with<br/>data from all shards (no partial)"]
        R3_DEN["Total: All successful GET requests"]
        R3_CALC["SLI = complete responses / total successful requests"]
        R3_NUM --> R3_CALC
        R3_DEN --> R3_CALC
    end

    style R1_CALC fill:#4a90d9,color:#fff
    style R2_CALC fill:#4a90d9,color:#fff
    style R3_CALC fill:#4a90d9,color:#fff
```

| SLI | Formula | What It Captures |
|---|---|---|
| **Read Availability** | `count(GET returning 200) / count(valid GET requests)` | Can clients query logs? |
| **Read Latency** | `count(GET < 5s) / count(successful GET requests)` | Are queries responsive? |
| **Read Completeness** | `count(GET with all shards responding) / count(successful GET requests)` | Are query results complete? |

### Pipeline Health SLI

| SLI | Formula | What It Captures |
|---|---|---|
| **Ingestion Freshness** | `count(logs queryable within 60s of POST) / count(all accepted logs)` | End-to-end pipeline delay |

---

## SLOs (Service Level Objectives)

### Setting Realistic Targets

Each SLO is based on the architecture's failure characteristics. Overpromising creates alert fatigue. Underpromising wastes engineering capacity.

```mermaid
graph TB
    subgraph "SLO Hierarchy by Criticality"
        TIER1["Tier 1 (Highest)<br/>Write Availability: 99.95%<br/>Data Durability: 99.95%"]
        TIER2["Tier 2 (High)<br/>Write Latency: 99.9%<br/>Ingestion Freshness: 99.9%"]
        TIER3["Tier 3 (Standard)<br/>Read Availability: 99.9%<br/>Read Latency: 99.5%<br/>Read Completeness: 99.5%"]
    end

    TIER1 --> TIER2 --> TIER3

    style TIER1 fill:#ff6b6b,color:#fff
    style TIER2 fill:#f5a623,color:#000
    style TIER3 fill:#50c878,color:#000
```

### SLO Targets with Justification

#### Tier 1 — Critical (Protect Data Ingestion)

| SLI | SLO Target | Rolling Window | Justification |
|---|---|---|---|
| **Write Availability** | **99.95%** | 30 days | POST is stateless → Kafka. Only fails if both LB and Kafka are down. 99.99% is unrealistic because Kafka partition leader elections and LB config changes cause brief blips. |
| **Data Durability** | **99.95%** | 30 days | Accepted logs must reach MySQL. Loss comes from: writer worker crash (buffer lost: ~5K rows), MySQL shard crash (unreplicated: ~5.5K rows), Kafka retention exceeded (catastrophic). 99.95% allows for the first two. |

**Why not 99.99% for Write Availability?**

```mermaid
graph LR
    subgraph "99.99% would require"
        A["Redundant LBs<br/>with sub-second failover"]
        B["Multi-region Kafka<br/>with synchronous replication"]
        C["Zero-downtime deployments<br/>with no errors during rollout"]
        D["Cost: ~3-5x infrastructure"]
    end

    subgraph "99.95% allows"
        E["Single-region Kafka<br/>with RF=3"]
        F["Rolling deployments<br/>with brief error windows"]
        G["Standard LB failover<br/>(5-10 second detection)"]
        H["Cost: baseline"]
    end

    style A fill:#ff6b6b,color:#fff
    style D fill:#ff6b6b,color:#fff
    style E fill:#50c878,color:#000
    style H fill:#50c878,color:#000
```

#### Tier 2 — High (Protect User Experience)

| SLI | SLO Target | Rolling Window | Justification |
|---|---|---|---|
| **Write Latency** (< 100ms) | **99.9%** | 30 days | POST is fire-and-forward. P99 should be <50ms normally. 0.1% budget covers GC pauses, Kafka producer backpressure during spikes, and network jitter. |
| **Ingestion Freshness** (< 60s) | **99.9%** | 30 days | Log should be queryable within 60 seconds. Budget covers: Kafka consumer lag spikes, writer batch flush delays, MySQL replication lag. |

#### Tier 3 — Standard (Operational Queries)

| SLI | SLO Target | Rolling Window | Justification |
|---|---|---|---|
| **Read Availability** | **99.9%** | 30 days | Scatter-gather across 40+ shards. Any shard replica down = degraded. With partial results, we can maintain 99.9%. Without partial results, even one replica outage across 45 shards drops availability. |
| **Read Latency** (< 5s) | **99.5%** | 30 days | Large range queries (3600s window) scan millions of rows. Tail latency is inherently variable. 99.5% allows 0.5% of queries to exceed 5s (cold cache, large result sets, shard stragglers). |
| **Read Completeness** | **99.5%** | 30 days | All 45 shards must respond. Even with replicas, 1 in 45 being briefly unavailable during failover is expected. 99.5% accommodates ~2.2 hours of partial results per month. |

**Why Read SLOs are lower than Write SLOs:**

```mermaid
graph TB
    subgraph "Write Path"
        W1["2-3 components<br/>(API → Kafka)"]
        W2["Stateless, simple"]
        W3["Failure = data loss risk"]
    end

    subgraph "Read Path"
        R1["45+ components<br/>(scatter to all shards)"]
        R2["Complex aggregation"]
        R3["Failure = temporary inconvenience"]
    end

    W1 --> WHY_W["Higher SLO justified:<br/>fewer moving parts,<br/>higher blast radius"]
    R1 --> WHY_R["Lower SLO realistic:<br/>more moving parts,<br/>lower blast radius"]

    style WHY_W fill:#50c878,color:#000
    style WHY_R fill:#f5a623,color:#000
```

---

## SLA (Service Level Agreement)

SLA is the **external promise** with financial or contractual consequences. Always set below the internal SLO to provide a safety buffer.

```mermaid
graph LR
    subgraph "Buffer Between SLO and SLA"
        SLO_W["Write Availability<br/>SLO: 99.95%"]
        SLA_W["Write Availability<br/>SLA: 99.9%"]
        BUF_W["Buffer: 0.05%<br/>= ~21.6 min/month"]

        SLO_R["Read Availability<br/>SLO: 99.9%"]
        SLA_R["Read Availability<br/>SLA: 99.5%"]
        BUF_R["Buffer: 0.4%<br/>= ~2.9 hours/month"]

        SLO_W --> BUF_W --> SLA_W
        SLO_R --> BUF_R --> SLA_R
    end

    style SLO_W fill:#50c878,color:#000
    style SLA_W fill:#f5a623,color:#000
    style BUF_W fill:#4a90d9,color:#fff
    style SLO_R fill:#50c878,color:#000
    style SLA_R fill:#f5a623,color:#000
    style BUF_R fill:#4a90d9,color:#fff
```

| SLI | SLO (Internal) | SLA (External) | Buffer |
|---|---|---|---|
| Write Availability | 99.95% | **99.9%** | 0.05% (~21.6 min/month) |
| Data Durability | 99.95% | **99.9%** | 0.05% |
| Write Latency (< 100ms) | 99.9% | **99.5%** | 0.4% |
| Read Availability | 99.9% | **99.5%** | 0.4% |
| Read Latency (< 5s) | 99.5% | **99.0%** | 0.5% |
| Ingestion Freshness (< 60s) | 99.9% | **99.5%** | 0.4% |

### SLA Breach Consequences

| Breach Level | Condition | Consequence |
|---|---|---|
| Level 1 | Any SLA metric below target for 1 day | Incident report within 48 hours |
| Level 2 | Any SLA metric below target for 7 days in a month | Service credit (10% of monthly cost) |
| Level 3 | Any SLA metric below target for 15+ days in a month | Service credit (30%) + executive review |

---

## Error Budget Calculation

### What Is Error Budget?

```
Error Budget = 1 - SLO

If SLO = 99.95%, Error Budget = 0.05%
This means: 0.05% of requests (or time) are ALLOWED to fail.
```

The error budget is a **spending account for unreliability**. You can "spend" it on deployments, experiments, planned maintenance, or unexpected failures. When it runs out, you freeze changes and focus on reliability.

### Monthly Error Budgets

#### Write Availability (SLO: 99.95%)

```
Error Budget = 0.05%

In time:
  30 days × 24 hours × 60 min = 43,200 minutes/month
  43,200 × 0.0005 = 21.6 minutes of downtime allowed

In requests:
  250,000 RPS × 86,400 sec/day × 30 days = 648,000,000,000 requests/month
  648B × 0.0005 = 324,000,000 failed requests allowed per month
  = ~324M errors/month
  = ~125 errors/second sustained (if spread evenly)
```

#### Data Durability (SLO: 99.95%)

```
Error Budget = 0.05%

In logs:
  648B logs accepted/month
  648B × 0.0005 = 324,000,000 logs allowed to be lost
  = ~324M lost logs/month
  = ~125 logs/second sustained loss rate
```

#### Read Availability (SLO: 99.9%)

```
Error Budget = 0.1%

In time:
  43,200 min × 0.001 = 43.2 minutes of downtime allowed

In requests (assuming ~1,000 queries/sec):
  1,000 × 86,400 × 30 = 2,592,000,000 requests/month
  2.59B × 0.001 = 2,592,000 failed queries allowed
  = ~2.59M query failures/month
```

### Complete Error Budget Table

```mermaid
graph TD
    subgraph "Monthly Error Budgets"
        subgraph "Write Availability (99.95%)"
            WA["Budget: 0.05%<br/>= 21.6 min downtime<br/>= 324M failed requests"]
        end
        subgraph "Data Durability (99.95%)"
            DD["Budget: 0.05%<br/>= 324M lost logs"]
        end
        subgraph "Write Latency (99.9%)"
            WL["Budget: 0.1%<br/>= 648M slow requests<br/>(> 100ms)"]
        end
        subgraph "Read Availability (99.9%)"
            RA["Budget: 0.1%<br/>= 43.2 min downtime<br/>= 2.59M failed queries"]
        end
        subgraph "Read Latency (99.5%)"
            RL["Budget: 0.5%<br/>= 12.96M slow queries<br/>(> 5 seconds)"]
        end
        subgraph "Ingestion Freshness (99.9%)"
            IF["Budget: 0.1%<br/>= 648M stale logs<br/>(> 60s delay)"]
        end
    end

    style WA fill:#ff6b6b,color:#fff
    style DD fill:#ff6b6b,color:#fff
    style WL fill:#f5a623,color:#000
    style RA fill:#f5a623,color:#000
    style RL fill:#50c878,color:#000
    style IF fill:#f5a623,color:#000
```

| SLI | SLO | Error Budget (%) | Monthly Time Budget | Monthly Request Budget |
|---|---|---|---|---|
| Write Availability | 99.95% | 0.05% | 21.6 min | 324M failed POSTs |
| Data Durability | 99.95% | 0.05% | — | 324M lost logs |
| Write Latency | 99.9% | 0.1% | — | 648M slow POSTs (>100ms) |
| Read Availability | 99.9% | 0.1% | 43.2 min | 2.59M failed GETs |
| Read Latency | 99.5% | 0.5% | — | 12.96M slow GETs (>5s) |
| Ingestion Freshness | 99.9% | 0.1% | — | 648M stale logs (>60s) |

### Error Budget Policies

```mermaid
flowchart TD
    CHECK["Monthly error budget check"] --> REMAINING{Budget remaining?}

    REMAINING -->|"> 50% remaining"| GREEN["GREEN<br/>Normal operations<br/>Deploy freely<br/>Run experiments"]
    REMAINING -->|"25-50% remaining"| YELLOW["YELLOW<br/>Caution<br/>Reduce deploy frequency<br/>No risky experiments"]
    REMAINING -->|"< 25% remaining"| ORANGE["ORANGE<br/>Warning<br/>Only critical deployments<br/>Focus on reliability work"]
    REMAINING -->|"0% — exhausted"| RED["RED<br/>FREEZE<br/>No deployments except fixes<br/>All hands on reliability<br/>Postmortem required"]

    style GREEN fill:#50c878,color:#000
    style YELLOW fill:#f5a623,color:#000
    style ORANGE fill:#ff6b6b,color:#fff
    style RED fill:#8b0000,color:#fff
```

| Budget Status | Action |
|---|---|
| **> 50% remaining** | Normal velocity. Deploy, experiment, iterate. |
| **25-50% remaining** | Reduce deployment frequency. Skip non-critical changes. Review recent incidents. |
| **< 25% remaining** | Only critical/security deployments. Redirect engineering to reliability improvements. |
| **Exhausted (0%)** | **Change freeze.** No deployments except reliability fixes. Mandatory postmortem. Leadership review. |

---

## Burn Rate & Multi-Window Alerting

### What Is Burn Rate?

```
Burn Rate = rate of error budget consumption relative to the natural rate

Natural rate: consuming 100% of budget evenly over 30 days
Burn Rate 1.0 = consuming budget at exactly the allowed rate
Burn Rate 2.0 = consuming budget 2x faster → exhausted in 15 days
Burn Rate 14.4 = consuming budget 14.4x faster → exhausted in ~2 days
```

### Multi-Window, Multi-Burn-Rate Alerting

The key insight from the Google SRE Workbook: a **single-threshold alert** either fires too late (low burn rate) or too often (low threshold). Multi-window alerting solves this by combining a short window (detect fast) with a long window (confirm sustained).

```mermaid
graph TB
    subgraph "Alert Level 1: PAGE (Critical)"
        P_SHORT["Short window: 5 min<br/>Burn rate > 14.4x"]
        P_LONG["Long window: 1 hour<br/>Burn rate > 14.4x"]
        P_SHORT & P_LONG -->|"BOTH true"| PAGE["PAGE on-call<br/>Budget exhausted in ~2 days<br/>if sustained"]
    end

    subgraph "Alert Level 2: PAGE (High)"
        H_SHORT["Short window: 30 min<br/>Burn rate > 6x"]
        H_LONG["Long window: 6 hours<br/>Burn rate > 6x"]
        H_SHORT & H_LONG -->|"BOTH true"| HIGH["PAGE on-call<br/>Budget exhausted in ~5 days<br/>if sustained"]
    end

    subgraph "Alert Level 3: TICKET (Warning)"
        T_SHORT["Short window: 2 hours<br/>Burn rate > 3x"]
        T_LONG["Long window: 24 hours<br/>Burn rate > 3x"]
        T_SHORT & T_LONG -->|"BOTH true"| TICKET["Create ticket<br/>Budget exhausted in ~10 days<br/>if sustained"]
    end

    subgraph "Alert Level 4: LOG (Informational)"
        L_WINDOW["Window: 24 hours<br/>Burn rate > 1x"]
        L_WINDOW --> LOG["Log warning<br/>Budget being consumed<br/>faster than planned"]
    end

    style PAGE fill:#8b0000,color:#fff
    style HIGH fill:#ff6b6b,color:#fff
    style TICKET fill:#f5a623,color:#000
    style LOG fill:#50c878,color:#000
```

### Alert Configuration Per SLI

#### Write Availability (SLO: 99.95%, Budget: 0.05%)

```
Error rate threshold at each burn rate:

  Burn Rate 14.4x → error rate = 14.4 × 0.05% = 0.72%
  At 250k RPS: 0.72% = 1,800 errors/sec sustained over 5 min

  Burn Rate 6x   → error rate = 6 × 0.05% = 0.30%
  At 250k RPS: 0.30% = 750 errors/sec sustained over 30 min

  Burn Rate 3x   → error rate = 3 × 0.05% = 0.15%
  At 250k RPS: 0.15% = 375 errors/sec sustained over 2 hours

  Burn Rate 1x   → error rate = 1 × 0.05% = 0.05%
  At 250k RPS: 0.05% = 125 errors/sec sustained over 24 hours
```

| Level | Burn Rate | Short Window | Long Window | Error Rate | Errors/sec | Action |
|---|---|---|---|---|---|---|
| **PAGE (P1)** | 14.4x | 5 min | 1 hour | 0.72% | 1,800/sec | Wake on-call. Budget gone in 2 days. |
| **PAGE (P2)** | 6x | 30 min | 6 hours | 0.30% | 750/sec | Page on-call. Budget gone in 5 days. |
| **TICKET** | 3x | 2 hours | 24 hours | 0.15% | 375/sec | Create JIRA ticket. Budget gone in 10 days. |
| **LOG** | 1x | — | 24 hours | 0.05% | 125/sec | Dashboard warning. On track to exhaust budget. |

#### Read Availability (SLO: 99.9%, Budget: 0.1%)

| Level | Burn Rate | Short Window | Long Window | Error Rate | Action |
|---|---|---|---|---|---|
| **PAGE (P1)** | 14.4x | 5 min | 1 hour | 1.44% | Wake on-call |
| **PAGE (P2)** | 6x | 30 min | 6 hours | 0.60% | Page on-call |
| **TICKET** | 3x | 2 hours | 24 hours | 0.30% | Create ticket |
| **LOG** | 1x | — | 24 hours | 0.10% | Dashboard warning |

#### Data Durability (SLO: 99.95%, Budget: 0.05%)

```
Measured differently: compare logs accepted (Kafka offset) vs logs in MySQL.

Durability deficit = accepted_count - queryable_count
Deficit rate = durability deficit per hour / accepted per hour
```

| Level | Condition | Window | Action |
|---|---|---|---|
| **PAGE (P1)** | Deficit rate > 0.72% | 5 min + 1 hour | Wake on-call. Logs being lost. |
| **PAGE (P2)** | Kafka consumer lag > 1 hour of data | 30 min | Page on-call. Pipeline stalled. |
| **TICKET** | Deficit rate > 0.15% | 2 hours + 24 hours | Create ticket. Slow data loss. |
| **LOG** | Any DLQ messages | 1 hour | Log. Investigate bad records. |

#### Ingestion Freshness (SLO: 99.9%, Budget: 0.1%)

```
Measured by: synthetic log injection.
Every 30 seconds, inject a canary log via POST.
Measure time until it appears in GET results.
Freshness = canary round-trip time.
```

| Level | Condition | Window | Action |
|---|---|---|---|
| **PAGE (P1)** | Canary freshness > 5 min | 5 min + 1 hour | Wake on-call. Pipeline severely backed up. |
| **PAGE (P2)** | Canary freshness > 2 min | 30 min + 6 hours | Page on-call. Pipeline degraded. |
| **TICKET** | Canary freshness > 60s | 2 hours + 24 hours | Create ticket. Approaching SLO boundary. |
| **LOG** | Canary freshness > 30s | 24 hours | Dashboard warning. |

---

## Alert Flow Architecture

```mermaid
graph TB
    subgraph "Data Sources"
        API_M["API Server Metrics<br/>(request count, errors, latency)"]
        KF_M["Kafka Metrics<br/>(consumer lag, produce rate)"]
        MY_M["MySQL Metrics<br/>(query latency, replication lag)"]
        CANARY["Canary Logs<br/>(synthetic freshness probe)"]
    end

    subgraph "Metrics Pipeline"
        PROM["Prometheus<br/>(scrape every 15s)"]
        API_M & KF_M & MY_M & CANARY --> PROM
    end

    subgraph "Alert Evaluation"
        RULES["Recording Rules<br/>(precompute burn rates<br/>for each SLI)"]
        PROM --> RULES
        RULES --> ALERT["Alertmanager<br/>(multi-window evaluation)"]
    end

    subgraph "Alert Routing"
        ALERT -->|"P1: PAGE"| PD["PagerDuty<br/>Wake on-call<br/>Phone + SMS"]
        ALERT -->|"P2: PAGE"| SLACK_URG["Slack #incidents<br/>+ PagerDuty"]
        ALERT -->|"TICKET"| JIRA["JIRA ticket<br/>auto-created"]
        ALERT -->|"LOG"| SLACK["Slack #observability<br/>informational"]
    end

    subgraph "Dashboards"
        GRAF["Grafana<br/>Error budget dashboard<br/>Burn rate visualizations<br/>SLI trends"]
        PROM --> GRAF
    end

    style PD fill:#8b0000,color:#fff
    style SLACK_URG fill:#ff6b6b,color:#fff
    style JIRA fill:#f5a623,color:#000
    style SLACK fill:#50c878,color:#000
```

### Prometheus Recording Rules (Example)

```yaml
# Pre-compute error ratios for burn rate alerting
groups:
  - name: sli_write_availability
    interval: 30s
    rules:
      # Error ratio over various windows
      - record: sli:write_availability:error_ratio_5m
        expr: |
          1 - (
            sum(rate(http_requests_total{endpoint="/logs",method="POST",code="202"}[5m]))
            /
            sum(rate(http_requests_total{endpoint="/logs",method="POST"}[5m]))
          )

      - record: sli:write_availability:error_ratio_1h
        expr: |
          1 - (
            sum(rate(http_requests_total{endpoint="/logs",method="POST",code="202"}[1h]))
            /
            sum(rate(http_requests_total{endpoint="/logs",method="POST"}[1h]))
          )

      - record: sli:write_availability:error_ratio_6h
        expr: |
          1 - (
            sum(rate(http_requests_total{endpoint="/logs",method="POST",code="202"}[6h]))
            /
            sum(rate(http_requests_total{endpoint="/logs",method="POST"}[6h]))
          )

      - record: sli:write_availability:error_ratio_24h
        expr: |
          1 - (
            sum(rate(http_requests_total{endpoint="/logs",method="POST",code="202"}[24h]))
            /
            sum(rate(http_requests_total{endpoint="/logs",method="POST"}[24h]))
          )

  - name: sli_write_availability_alerts
    rules:
      # P1 PAGE: 14.4x burn rate over 5min AND 1h
      - alert: WriteAvailabilityBurnRateCritical
        expr: |
          sli:write_availability:error_ratio_5m > (14.4 * 0.0005)
          and
          sli:write_availability:error_ratio_1h > (14.4 * 0.0005)
        labels:
          severity: page_p1
        annotations:
          summary: "Write availability burning error budget at 14.4x rate"
          description: "Budget will be exhausted in ~2 days at this rate"

      # P2 PAGE: 6x burn rate over 30min AND 6h
      - alert: WriteAvailabilityBurnRateHigh
        expr: |
          sli:write_availability:error_ratio_30m > (6 * 0.0005)
          and
          sli:write_availability:error_ratio_6h > (6 * 0.0005)
        labels:
          severity: page_p2
        annotations:
          summary: "Write availability burning error budget at 6x rate"

      # TICKET: 3x burn rate over 2h AND 24h
      - alert: WriteAvailabilityBurnRateWarning
        expr: |
          sli:write_availability:error_ratio_2h > (3 * 0.0005)
          and
          sli:write_availability:error_ratio_24h > (3 * 0.0005)
        labels:
          severity: ticket
        annotations:
          summary: "Write availability burning error budget at 3x rate"
```

---

## Error Budget Dashboard

### What to Display

```mermaid
graph TB
    subgraph "Error Budget Dashboard (Grafana)"
        subgraph "Row 1: Budget Status"
            B1["Write Availability<br/>Budget: 72% remaining<br/>🟢 GREEN"]
            B2["Data Durability<br/>Budget: 45% remaining<br/>🟡 YELLOW"]
            B3["Read Availability<br/>Budget: 88% remaining<br/>🟢 GREEN"]
        end

        subgraph "Row 2: Burn Rate (Current)"
            BR1["Write Avail Burn Rate<br/>Current: 0.8x<br/>Projected: exhaust in 37.5 days"]
            BR2["Durability Burn Rate<br/>Current: 1.6x<br/>Projected: exhaust in 18.7 days"]
            BR3["Read Avail Burn Rate<br/>Current: 0.4x<br/>Projected: exhaust in 75 days"]
        end

        subgraph "Row 3: Trending (30-day)"
            T1["Budget consumption over time<br/>(line chart, budget remaining vs days)"]
        end

        subgraph "Row 4: Incident Impact"
            I1["Incidents this month: 2<br/>Total budget consumed by incidents: 18%<br/>Largest: MySQL shard failover (12%)"]
        end
    end

    style B1 fill:#50c878,color:#000
    style B2 fill:#f5a623,color:#000
    style B3 fill:#50c878,color:#000
```

### Key Dashboard Panels

| Panel | Visualization | Purpose |
|---|---|---|
| Budget Remaining (%) | Gauge per SLI | At-a-glance health |
| Burn Rate (current) | Single stat with color thresholds | Is budget being consumed too fast? |
| Budget Consumption Over Time | Time series (30-day) | Trending — are things getting worse? |
| Error Rate vs SLO Threshold | Time series with horizontal SLO line | Are we above or below the line? |
| Incident Impact Log | Table | Which incidents consumed how much budget? |
| Days Until Exhaustion | Single stat | Projected budget exhaustion date at current burn rate |

---

## Summary: SLI → SLO → SLA → Error Budget → Alerts

```mermaid
graph LR
    SLI["SLI<br/>(measure)"] -->|"target"| SLO["SLO<br/>(99.95%)"]
    SLO -->|"weaker"| SLA["SLA<br/>(99.9%)"]
    SLO -->|"derive"| EB["Error Budget<br/>(0.05% = 21.6 min)"]
    EB -->|"consumption rate"| BR["Burn Rate"]
    BR -->|"multi-window"| ALERT["Alerts<br/>(P1/P2/Ticket/Log)"]
    ALERT -->|"route"| ACTION["PagerDuty<br/>Slack<br/>JIRA"]
    EB -->|"policy"| FREEZE["Change Freeze<br/>when exhausted"]

    style SLI fill:#4a90d9,color:#fff
    style SLO fill:#50c878,color:#000
    style SLA fill:#f5a623,color:#000
    style EB fill:#7b68ee,color:#fff
    style ALERT fill:#ff6b6b,color:#fff
    style FREEZE fill:#8b0000,color:#fff
```

| Layer | Write Availability | Data Durability | Read Availability | Read Latency |
|---|---|---|---|---|
| **SLI** | 202s / total POSTs | queryable / accepted | 200s / total GETs | GETs < 5s / total |
| **SLO** | 99.95% | 99.95% | 99.9% | 99.5% |
| **SLA** | 99.9% | 99.9% | 99.5% | 99.0% |
| **Error Budget** | 21.6 min/month | 324M logs/month | 43.2 min/month | 12.96M queries/month |
| **P1 Alert** | 14.4x burn, 5m+1h | deficit > 0.72% | 14.4x burn, 5m+1h | 14.4x burn, 5m+1h |
| **P2 Alert** | 6x burn, 30m+6h | lag > 1h data | 6x burn, 30m+6h | 6x burn, 30m+6h |
| **Ticket** | 3x burn, 2h+24h | deficit > 0.15% | 3x burn, 2h+24h | 3x burn, 2h+24h |
