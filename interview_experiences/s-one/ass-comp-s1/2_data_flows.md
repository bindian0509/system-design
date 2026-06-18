# Singularity Health Center: Data Flows

This document details the specific data flows for different operations in the Singularity Health Center. Understanding these flows is critical for a Senior Engineering Manager to articulate how the system behaves under various conditions.

## 1. Event Ingestion Flow

The standard path for a health telemetry event coming from an endpoint agent into the platform.

```mermaid
sequenceDiagram
    participant Agent as SentinelOne Agent
    participant GW as API Gateway (Go)
    participant Kafka as Event Bus (Kafka)
    participant Flink as Stream Processor (Flink)
    participant Redis as State Store (Redis)
    participant TSDB as Time Series DB (ClickHouse)

    Agent->>GW: gRPC Telemetry Event (Batch)
    GW->>GW: Auth & Rate Limit Check
    GW->>Kafka: Publish to `raw_telemetry` topic (Partition key: agent_id)
    GW-->>Agent: 200 OK (Acknowledge receipt)
    
    Kafka->>Flink: Consume `raw_telemetry`
    
    par Update State
        Flink->>Redis: Upsert Last Known State
    and Store for History
        Flink->>TSDB: Batch Insert Metrics
    end
```

### Key Considerations:
*   **Asynchronous Acknowledgement**: The gateway acknowledges the agent as soon as the message is safely stored in Kafka. It does *not* wait for Flink to process the event, ensuring low latency for the agent.
*   **Batching**: Agents send events in batches, and the Gateway writes to Kafka in batches to optimize network and disk I/O.

## 2. Stateless Anomaly Detection Flow (e.g., Low Disk Space, Tampering)

These are rules that can be evaluated on a single event without needing historical context.

```mermaid
sequenceDiagram
    participant Kafka as Event Bus (Kafka)
    participant Flink as Stream Processor (Flink)
    participant Rules as Rule Engine
    participant AlertQ as Alert Kafka Topic
    participant AlertSvc as Alerting Service
    participant User as Customer Admin

    Kafka->>Flink: Consume Event (e.g., disk_space = 5%)
    Flink->>Rules: Evaluate Event against Tenant Rules
    Rules-->>Flink: Match Found! (Rule: Disk < 10%)
    
    Flink->>AlertQ: Publish Anomaly Event
    AlertQ->>AlertSvc: Consume Anomaly
    AlertSvc->>AlertSvc: Deduplication Check (Has this alert fired recently?)
    AlertSvc->>User: Dispatch Alert (Email/Webhook)
```

## 3. Stateful Anomaly Detection Flow (Connectivity Loss / Missing Heartbeat)

This is the hardest problem to solve at scale: How do you detect that an event *did not* arrive?

### The Flink Timer State Approach

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant Flink as Flink Processor
    participant Timer as Flink Internal Timer (RocksDB)
    participant AlertQ as Alert Topic

    Agent->>Flink: Heartbeat Event (t=0)
    Flink->>Timer: Register Timer for t+5 mins
    
    Note over Agent, Flink: Agent goes offline (Network loss)
    
    Timer-->>Flink: Timer Fires at t+5 mins (No new heartbeat seen)
    Flink->>AlertQ: Emit "Connectivity Loss" Anomaly
    
    Note over Agent, Flink: Agent comes back online
    
    Agent->>Flink: Heartbeat Event (t=10)
    Flink->>AlertQ: Emit "Connectivity Restored" Event
    Flink->>Timer: Register New Timer for t+15 mins
```

### Why this is an Interview Differentiator:
Many candidates will suggest querying a database via a cron job (e.g., `SELECT * FROM agents WHERE last_seen < NOW() - 5 mins`). 
**Why cron is bad:** Running a cron job across millions of rows every minute is incredibly resource-intensive and doesn't scale.
**Why Stream Processing (Timers/Session Windows) is better:** The stream processor only keeps track of active timers in memory (or fast local state like RocksDB). When the time expires, it fires automatically. It converts a "polling" problem into an "event-driven" solution.
