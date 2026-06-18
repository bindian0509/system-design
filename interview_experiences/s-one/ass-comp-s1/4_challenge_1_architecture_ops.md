# Challenge 1: Architectural Strategy & Operations

As the Senior Engineering Manager inheriting a full-stack team of 10 engineers (Backend, Frontend, QA), the scope changes significantly. We do *not* own the central ingestion; we consume from it. Our team's boundary starts at the Event Bus (Kafka) and ends at the SentinelOne Console UI.

## 1. Updated High-Level Architecture

Since we consume telemetry from a central Ingestion Gateway, our architecture is optimized for high-throughput stream processing and low-latency API reads.

```mermaid
graph TD
    subgraph Central Infrastructure (Outside Team Scope)
        A[Millions of Agents] --> B(Central Ingestion Gateway)
        B --> C[(Central Telemetry Kafka)]
    end
    
    subgraph APLAT Health Center (Our Scope)
        C -->|Consume| D[Stream Processor: Apache Flink]
        
        D <-->|State/Timers| E[(Redis: State & Cache)]
        D -->|Aggregates| F[(ClickHouse: Time Series)]
        D -->|Anomalies| G[(Alerts Kafka Topic)]
        
        G --> H[Platform Alerting Service]
        H -->|Notify| I(Email / Webhook)
        
        J[Health Management API Java] -->|Query Fast| E
        J -->|Query Historical| F
        J -->|Config| K[(PostgreSQL: Rules)]
        
        L[Frontend: React Console] -->|REST < 200ms| J
    end
```

## 2. Scale & Performance Strategy

**Requirement:** Process billions of daily requests. Detect anomalies < 5 minutes. API latency < 200ms.

*   **Sub-5 Minute Detection:** Apache Flink handles billions of events with sub-second processing latency. By utilizing Flink's Event-Time Windowing and Timer State, detecting a missing heartbeat (connectivity loss) at exactly the 5-minute mark is natively supported and highly scalable.
*   **API Latency < 200ms:** To guarantee ultra-fast UI rendering for the React console:
    *   **Hot Path (Current State):** The UI queries the Java Management API, which reads directly from **Redis**. Redis provides sub-millisecond read latency, easily meeting the < 200ms requirement.
    *   **Cold Path (Historical Trends):** The API queries **ClickHouse**, a columnar database optimized for massive aggregations, ensuring even complex historical charts render quickly.

## 3. Reusable Platform Services

As a platform team (APLAT), we should build components that other teams can leverage:
1.  **Platform Alerting Service (Notification Engine):** Other teams at SentinelOne also need to send Emails/Webhooks. We will build this as an independent gRPC microservice with deduplication, rate-limiting, and tenant-preference routing.
2.  **Dynamic Rule Engine Library:** The engine that evaluates `disk_space < 10%` can be packaged as a shared library (Go module or Java package) or a sidecar, allowing other feature teams to inject custom telemetry evaluation rules without rewriting the core engine.

## 4. Observability & Reliability Strategy

To ensure operational excellence for a Tier-1 service:
*   **Metrics (Prometheus & Grafana):** Focus on the **RED metrics** (Rate, Errors, Duration) for APIs. For streaming, the most critical metric is **Kafka Consumer Lag** (how far behind the processor is from the central ingestion).
*   **Tracing (OpenTelemetry):** Distributed tracing across the central gateway -> Flink -> API -> Frontend. This is vital to prove exactly *where* latency is introduced.
*   **Logging (ELK / Datadog):** Structured JSON logs with injected `tenant_id` and `agent_id` for fast querying.
*   **Resiliency:** Implement Circuit Breakers in the Java API (e.g., Resilience4j) to prevent cascading failures if ClickHouse slows down.

---

## 5. Handling the Sev-1 Incident

**Scenario:** The Health Center *silently* stops processing incoming agent events. No alerts are firing, but the UI shows stale data.

### Phase 1: Detection & Triage
*   **The Missing Alert:** If processing stops "silently", it means CPU/Memory metrics might look healthy. The primary alert that *should* catch this is **"Kafka Consumer Lag > Threshold"**.
*   **Action:** Acknowledge the Sev-1 in PagerDuty. Open a war room (Slack/Zoom). Assign roles (Incident Commander, Scribe, Lead Investigator).

### Phase 2: Investigation (The "Why")
If consumer lag is skyrocketing, but the Flink cluster is up, we look for three common culprits:
1.  **The Poison Pill:** A malformed telemetry event from the Central Gateway is causing a deserialization exception in Flink. Flink fails, restarts from the last checkpoint, hits the same message, and loops infinitely.
2.  **External Dependency Block:** Flink is trying to write to Redis or ClickHouse, but the connection pool is exhausted or the DB is slow. Backpressure propagates up to Kafka, pausing consumption.
3.  **Thread Deadlocks:** A bug in the recent Java/Go code deployment is causing worker threads to hang.

### Phase 3: Mitigation
*   **If Poison Pill:** Temporarily configure the Kafka consumer to "Dead Letter Queue (DLQ)" the failing partition/message and skip it, unblocking the pipeline.
*   **If External Dependency:** Temporarily disable the failing sink (e.g., stop writing to ClickHouse) if Redis is the primary UI driver, operating in a degraded but alive state.
*   **If Bad Deployment:** Immediately trigger a rollback in ArgoCD to the previous known-good Helm chart.

### Phase 4: Post-Mortem (COE - Correction of Errors)
*   **Blameless Review:** Why didn't our CI/CD catch the poison pill? Why did the UI not show a "Data Stale" banner when the backend lagged?
*   **Action Items:** Implement strict schema validation at the central gateway (Protobuf). Add a "Data Freshness" heartbeat monitor that pings the end-to-end system every minute.
