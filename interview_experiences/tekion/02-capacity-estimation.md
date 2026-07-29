# 02 — Capacity Estimation

[← Requirements](01-requirements-and-scope.md) · [Index](README.md) · [Next: APIs and Data Model →](03-api-and-data-model.md)

---

## Traffic math

```text
Tenants:            5,000
Flows deployed:     200,000   (~40/tenant, long tail — top 1% have 1000+)

Executions:         2B/day
    2e9 / 86,400                    ≈  23,000 executions/sec  (average)
    Business-hours + timezone clustered; peak factor ≈ 6x
                                    ≈ 140,000 executions/sec  (peak)

Steps per execution: 8 (average)
    23,000 x 8                      ≈ 185,000 steps/sec  (average)
    140,000 x 8                     ≈ 1,100,000 steps/sec (peak)
```

> **The step rate — not the execution rate — sizes the engine.** ~1.1M steps/sec at peak means
> the state machine layer must be horizontally partitioned with **no global lock anywhere on the hot path**.

---

## Payload and storage math

```text
Payload size:   median 4 KB · p99 256 KB · max 100 MB (file-transfer flows)
                Median dominates COUNT; p99+ dominates BYTES.

Trigger payload volume:
    2e9 x 4 KB                      ≈ 8 TB/day

Execution trace metadata:
    8 steps x ~1 KB structured metadata = 8 KB/execution
    2e9 x 8 KB                      ≈ 16 TB/day
    30-day hot + replication        ≈ 1.4 PB

Naive full payload retention (every step input AND output):
    8 steps x 4 KB x 2e9            ≈ 64 TB/day
                                    ≈ 2 PB/month hot        ⚠️
```

### The number that killed the naive design

```mermaid
flowchart TB
    N["Naive: store every<br/>intermediate payload<br/><b>~2 PB/month</b>"]
    N --> W["This is likely a LARGER line item<br/>than ALL compute combined"]

    W --> M1["Mitigation 1<br/><b>Content-addressed storage</b><br/>SHA-256 key → object store<br/>Retries + fan-out re-reference,<br/>never re-copy"]
    W --> M2["Mitigation 2<br/><b>Metadata always,<br/>payloads by policy</b><br/>status, timing, error,<br/>payload hash, size"]
    W --> M3["Mitigation 3<br/><b>Short default retention</b><br/>7 days, opt-in extension<br/>that is explicitly priced"]

    M2 --> P["Policy:<br/>• ALWAYS on failure<br/>• Last N successes per flow-version<br/>  (rolling reference sample)<br/>• ALWAYS for audited flows"]

    style N fill:#8b2c2c,color:#fff
    style P fill:#1f6feb,color:#fff
```

**Why sampling successes is acceptable:** debugging demand is overwhelmingly concentrated on failures and
the runs immediately preceding them. Keeping *all* failures plus a rolling sample of successes covers
"show me what a good run looks like" without paying for two billion of them.

---

## Estimate → design implication

```mermaid
flowchart LR
    E1["1.1M steps/sec peak"] --> D1["Engine horizontally partitioned<br/>No global lock"]
    E2["8 TB/day payloads"] --> D2["Payloads NEVER travel<br/>through the state store"]
    E3["2 PB/mo naive traces"] --> D3["Retention is a<br/>first-class product feature"]
    E4["6x diurnal peak"] --> D4["Shared pooled compute<br/>beats dedicated<br/>Deferrable work → trough"]
    E5["p99 payload 256 KB<br/>max 100 MB"] --> D5["Blob store + references<br/>Streaming, not buffering"]
    E6["Long-tail tenant skew<br/>top 1% have 1000+ flows"] --> D6["Partition by execution_id,<br/>NOT tenant_id"]

    style D1 fill:#1f6feb,color:#fff
    style D2 fill:#1f6feb,color:#fff
    style D3 fill:#1f6feb,color:#fff
    style D4 fill:#1f6feb,color:#fff
    style D5 fill:#1f6feb,color:#fff
    style D6 fill:#1f6feb,color:#fff
```

---

## Diurnal load shape (why pooling wins)

```mermaid
xychart-beta
    title "Executions/sec across a day (6x peak-to-trough)"
    x-axis [00, 03, 06, 09, 12, 15, 18, 21, 24]
    y-axis "Executions/sec (thousands)" 0 --> 150
    line [22, 18, 35, 120, 140, 130, 95, 45, 24]
```

Provisioning for the peak wastes most of the day. Two levers follow directly:

1. **Reserved capacity for the trough, elastic for the peak.**
2. **Deliberately schedule deferrable work into the trough** — batch flows, backfills, reindexing.
   This is simultaneously a cost lever and a product feature ("economy tier" pricing for deferrable flows),
   and it only works if the scheduling primitives exist early.

---

## Uncertainty to validate

| Assumption | Confidence | Why it matters | How to validate |
|---|---|---|---|
| 6x peak factor | Low | Drives a large fraction of the compute budget | Measure real traffic before committing capacity; keep the elastic tier large early |
| 8 steps/execution average | Medium | Sizes the engine directly | Instrument from day one |
| 4 KB median payload | Medium | Sizes storage and cross-AZ transfer | Instrument at ingestion |
| Blob dedup rate | Low | Determines actual content-addressing savings | Measure hash collision/reuse rate in Stage 1 |
