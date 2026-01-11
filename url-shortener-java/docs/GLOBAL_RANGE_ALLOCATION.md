# Global Region-Based Range Allocation

## Overview

The URL shortener uses a **distributed counter with region-based range allocation** to ensure:
- **Zero cross-region coordination** for most ID generation operations
- **Guaranteed global uniqueness** across all regions
- **High throughput** (millions of IDs per second per region)
- **Predictable capacity planning** for each region

---

## Global ID Space Division

The total ID space (62^7 = 3.52 trillion unique codes) is divided equally among three primary regions:

```mermaid
pie showData
    title Global ID Space Distribution (3.52 Trillion Codes)
    "🇺🇸 US-EAST-1 (Americas)" : 1173871535403
    "🇪🇺 EU-WEST-1 (Europe)" : 1173871535403
    "🇮🇳 AP-SOUTH-1 (India/Asia)" : 1173871535402
```

### Region Range Mapping

```mermaid
block-beta
    columns 3

    block:US:1
        columns 1
        US_Header["🇺🇸 US-EAST-1"]
        US_Range["Range: 0 - 1.17T"]
        US_Codes["Codes: 0000000 - 0LY7VK2"]
        US_Cap["Capacity: 1.17 Trillion"]
    end

    block:EU:1
        columns 1
        EU_Header["🇪🇺 EU-WEST-1"]
        EU_Range["Range: 1.17T - 2.34T"]
        EU_Codes["Codes: 0LY7VK3 - 0zXdWV5"]
        EU_Cap["Capacity: 1.17 Trillion"]
    end

    block:IN:1
        columns 1
        IN_Header["🇮🇳 AP-SOUTH-1"]
        IN_Range["Range: 2.34T - 3.52T"]
        IN_Codes["Codes: 0zXdWV6 - ZZZZZZZ"]
        IN_Cap["Capacity: 1.17 Trillion"]
    end
```

---

## How It Works

### 1. Region Assignment

When the application starts, it identifies its region from the `AWS_REGION` environment variable:

```java
@Value("${AWS_REGION:us-east-1}")
private String awsRegion;

// Maps to predefined range
RegionConfig config = RegionConfig.fromAwsRegion(awsRegion);
// US -> range 0 to 1.17T
// EU -> range 1.17T to 2.34T
// IN -> range 2.34T to 3.52T
```

### 2. Batch Allocation Architecture

```mermaid
flowchart TB
    subgraph DDB["DynamoDB Counter Table"]
        US_Counter["us-east-1#COUNTER<br/>current_value: 50,000,000"]
        EU_Counter["eu-west-1#COUNTER<br/>current_value: 1,173,900,000,000"]
        IN_Counter["ap-south-1#COUNTER<br/>current_value: 2,347,750,000,000"]
    end

    subgraph US_Region["🇺🇸 US-EAST-1 Region"]
        US_Pod1["Pod 1<br/>Range: 0 - 999,999"]
        US_Pod2["Pod 2<br/>Range: 1M - 1,999,999"]
        US_Pod3["Pod 3<br/>Range: 2M - 2,999,999"]
    end

    subgraph EU_Region["🇪🇺 EU-WEST-1 Region"]
        EU_Pod1["Pod 1<br/>Range: 1.17T - 1.17T+1M"]
        EU_Pod2["Pod 2<br/>Range: 1.17T+1M - 1.17T+2M"]
    end

    subgraph IN_Region["🇮🇳 AP-SOUTH-1 Region"]
        IN_Pod1["Pod 1<br/>Range: 2.34T - 2.34T+1M"]
        IN_Pod2["Pod 2<br/>Range: 2.34T+1M - 2.34T+2M"]
    end

    US_Counter --> US_Pod1 & US_Pod2 & US_Pod3
    EU_Counter --> EU_Pod1 & EU_Pod2
    IN_Counter --> IN_Pod1 & IN_Pod2
```

### 3. Atomic Increment

The allocation uses DynamoDB's atomic update to prevent collisions:

```java
UpdateItemRequest.builder()
    .tableName("url_shortener_counters")
    .key(Map.of("pk", AttributeValue.fromS("us-east-1#COUNTER")))
    .updateExpression(
        "SET current_value = if_not_exists(current_value, :start) + :batch, " +
        "last_allocated = :timestamp"
    )
    .conditionExpression("current_value < :max")  // Stay within region bounds
    .returnValues(ReturnValue.UPDATED_OLD)        // Return old value as our range start
    .build();
```

### 4. Local ID Generation

```mermaid
sequenceDiagram
    participant App as Application Pod
    participant AtomicCounter as AtomicLong (Local)
    participant Encoder as Base62 Encoder

    Note over App: Generate new short code

    App->>AtomicCounter: getAndIncrement()
    AtomicCounter-->>App: 456789

    App->>Encoder: encode(456789)
    Note over Encoder: 456789 → Base62
    Encoder-->>App: "00007Dj"

    App->>App: Return short code
```

### 5. Prefetch Strategy

```mermaid
stateDiagram-v2
    [*] --> Normal: Pod starts with allocated range

    Normal --> Normal: Generate IDs locally
    Normal --> Prefetch: 90% range used

    Prefetch --> Prefetch: Async request new range
    Prefetch --> Normal: New range received

    Normal --> Exhausted: 100% range used (rare)
    Exhausted --> Normal: Wait for new range
```

---

## Request Flow

### Create URL Request - Mumbai User

```mermaid
sequenceDiagram
    participant User as 👤 User in Mumbai
    participant R53 as Route 53
    participant IN_App as AP-SOUTH-1 App
    participant IN_Counter as Local Counter
    participant DDB as DynamoDB Global Tables

    User->>R53: POST /api/v1/urls
    Note over R53: Latency-based routing
    R53->>IN_App: Route to closest region

    IN_App->>IN_Counter: getAndIncrement()
    Note over IN_Counter: Value: 2,347,800,000,789
    IN_Counter-->>IN_App: 2347800000789

    IN_App->>IN_App: encode(2347800000789)
    Note over IN_App: Result: "1N34DeF"

    IN_App->>DDB: Save ShortUrl
    Note over DDB: Replicated globally
    DDB-->>IN_App: Saved

    IN_App-->>User: {"shortCode": "1N34DeF"}
```

---

## Concurrent Requests - Global

```mermaid
sequenceDiagram
    participant NY as 👤 New York
    participant FR as 👤 Frankfurt
    participant MU as 👤 Mumbai

    participant US as 🇺🇸 US-EAST-1
    participant EU as 🇪🇺 EU-WEST-1
    participant IN as 🇮🇳 AP-SOUTH-1

    par Simultaneous Requests
        NY->>US: Create URL
        FR->>EU: Create URL
        MU->>IN: Create URL
    end

    Note over US: Counter: 1,234,567
    Note over EU: Counter: 1,173,900,000,456
    Note over IN: Counter: 2,347,800,000,789

    par Generate Codes (No Coordination!)
        US->>US: encode → "0000Pdj"
        EU->>EU: encode → "0M12AbC"
        IN->>IN: encode → "1N34DeF"
    end

    US-->>NY: "0000Pdj"
    EU-->>FR: "0M12AbC"
    IN-->>MU: "1N34DeF"

    Note over NY,MU: ✅ All codes guaranteed unique!
```

---

## Capacity Planning

### Per-Region Capacity

```mermaid
xychart-beta
    title "Years of Capacity per Region (at 167M URLs/month)"
    x-axis ["US-EAST-1", "EU-WEST-1", "AP-SOUTH-1"]
    y-axis "Years" 0 --> 600
    bar [584, 584, 584]
```

| Region | Range Size | At 167M URLs/month | Years until exhaustion |
|--------|------------|--------------------|-----------------------|
| US-EAST-1 | 1.17 trillion | 584+ years | Way beyond planning horizon |
| EU-WEST-1 | 1.17 trillion | 584+ years | Way beyond planning horizon |
| AP-SOUTH-1 | 1.17 trillion | 584+ years | Way beyond planning horizon |

### Batch Size Considerations

| Batch Size | At 1K URLs/sec | At 10K URLs/sec | Recommended For |
|------------|----------------|-----------------|-----------------|
| 10,000 | 10 seconds | 1 second | Development/Testing |
| 100,000 | 100 seconds | 10 seconds | Small deployments |
| 1,000,000 | ~17 minutes | ~100 seconds | Production (default) |
| 10,000,000 | ~2.8 hours | ~17 minutes | High-traffic production |

---

## Identifying Code Origin

Each short code can be traced back to its origin region:

```mermaid
flowchart LR
    Code["Short Code<br/>0M12AbC"] --> Decode["Decode Base62"]
    Decode --> Value["Numeric Value<br/>1,173,900,000,456"]
    Value --> Check{"Value Range?"}
    Check -->|"0 - 1.17T"| US["🇺🇸 US-EAST-1"]
    Check -->|"1.17T - 2.34T"| EU["🇪🇺 EU-WEST-1"]
    Check -->|"2.34T - 3.52T"| IN["🇮🇳 AP-SOUTH-1"]
```

```java
// Decode and identify region
String code = "0M12AbC";
long value = idGenerator.decode(code);
// value = 1,173,900,000,456

RegionConfig region = RegionConfig.fromNumericValue(value);
// region = EU_WEST_1

// API endpoint: GET /api/v1/status/decode?code=0M12AbC
{
  "code": "0M12AbC",
  "numericValue": 1173900000456,
  "region": "eu-west-1",
  "regionCode": "EU"
}
```

---

## Monitoring

### Key Metrics

```prometheus
# Current range utilization
url_shortener_range_used{region="us-east-1"} 456789
url_shortener_range_remaining{region="us-east-1"} 543211
url_shortener_range_utilization_percent{region="us-east-1"} 45.67

# Allocation events
url_shortener_range_allocations_total{region="us-east-1"} 5
url_shortener_range_allocation_duration_seconds{region="us-east-1"} 0.023
```

### Monitoring Dashboard

```mermaid
flowchart TB
    subgraph Metrics["Prometheus Metrics"]
        RangeUsed["range_used"]
        RangeRemaining["range_remaining"]
        Allocations["allocations_total"]
    end

    subgraph Grafana["Grafana Dashboard"]
        Gauge["Range Utilization Gauge"]
        Graph["Allocation Rate Graph"]
        Alert["Exhaustion Alert"]
    end

    RangeUsed --> Gauge
    RangeRemaining --> Gauge
    Allocations --> Graph
    Gauge --> Alert
```

### API Endpoints

```bash
# Get current allocation status
GET /api/v1/status/allocation
{
  "region": "us-east-1",
  "rangeStart": 0,
  "rangeEnd": 999999,
  "currentValue": 456789,
  "used": 456789,
  "remaining": 543211,
  "usagePercent": 45.67
}

# Get all region configurations
GET /api/v1/status/regions
[
  {
    "awsRegion": "us-east-1",
    "shortCode": "US",
    "rangeStart": 0,
    "rangeEnd": 1173871535402,
    "capacity": 1173871535403,
    "capacityFormatted": "1.17 trillion",
    "firstCode": "0000000",
    "lastCode": "0LY7VK2"
  },
  ...
]
```

---

## Failure Scenarios

### 1. DynamoDB Unavailable

```mermaid
flowchart TD
    Start["Instance Starts"] --> Allocate["Try to Allocate Range"]
    Allocate --> Timeout{"DynamoDB Timeout?"}
    Timeout -->|Yes| Retry["Retry with Exponential Backoff"]
    Retry --> Timeout
    Timeout -->|No| Success["Range Allocated ✅"]
    Retry -->|Max Retries| Fail["Fail Startup ❌"]
```

### 2. Region Exhaustion (Theoretical)

```mermaid
flowchart TD
    Counter["Counter reaches region max"] --> Condition["ConditionExpression fails"]
    Condition --> Exception["IllegalStateException"]
    Exception --> Alert["🚨 Alert Triggered"]
    Alert --> Manual["Manual Intervention Required"]
    Manual --> Options{"Options"}
    Options --> NewRegion["Expand to new region"]
    Options --> LongerCode["Increase code length"]
```

### 3. Instance Crash Mid-Range

```mermaid
flowchart LR
    Allocated["Allocated: 1M - 2M"] --> Used["Used: 1M - 1.5M"]
    Used --> Crash["💥 Instance Crashes"]
    Crash --> Lost["Lost: 1.5M - 2M<br/>(500K IDs)"]
    Lost --> Impact["Impact: 0.00004%<br/>of 1.17T capacity"]
    Impact --> OK["✅ Negligible"]
```

---

## DynamoDB Global Tables Architecture

```mermaid
flowchart TB
    subgraph US["🇺🇸 US-EAST-1"]
        US_App["Application"]
        US_DDB[("DynamoDB<br/>Replica")]
    end

    subgraph EU["🇪🇺 EU-WEST-1"]
        EU_App["Application"]
        EU_DDB[("DynamoDB<br/>Replica")]
    end

    subgraph IN["🇮🇳 AP-SOUTH-1"]
        IN_App["Application"]
        IN_DDB[("DynamoDB<br/>Replica")]
    end

    US_App --> US_DDB
    EU_App --> EU_DDB
    IN_App --> IN_DDB

    US_DDB <-->|"Automatic<br/>Replication"| EU_DDB
    EU_DDB <-->|"Automatic<br/>Replication"| IN_DDB
    IN_DDB <-->|"Automatic<br/>Replication"| US_DDB
```

---

## Terraform Configuration

```hcl
# DynamoDB Global Table for counters
resource "aws_dynamodb_table" "counters" {
  name         = "url_shortener_counters"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  # Enable global tables for multi-region
  replica {
    region_name = "us-east-1"
  }

  replica {
    region_name = "eu-west-1"
  }

  replica {
    region_name = "ap-south-1"
  }

  tags = {
    Name        = "url-shortener-counters"
    Environment = "production"
  }
}

# Initialize counter values for each region
resource "aws_dynamodb_table_item" "us_counter" {
  table_name = aws_dynamodb_table.counters.name
  hash_key   = aws_dynamodb_table.counters.hash_key

  item = jsonencode({
    pk            = { S = "us-east-1#COUNTER" }
    current_value = { N = "0" }
    range_start   = { N = "0" }
    range_end     = { N = "1173871535402" }
  })
}

resource "aws_dynamodb_table_item" "eu_counter" {
  table_name = aws_dynamodb_table.counters.name
  hash_key   = aws_dynamodb_table.counters.hash_key

  item = jsonencode({
    pk            = { S = "eu-west-1#COUNTER" }
    current_value = { N = "1173871535403" }
    range_start   = { N = "1173871535403" }
    range_end     = { N = "2347743070805" }
  })
}

resource "aws_dynamodb_table_item" "ap_counter" {
  table_name = aws_dynamodb_table.counters.name
  hash_key   = aws_dynamodb_table.counters.hash_key

  item = jsonencode({
    pk            = { S = "ap-south-1#COUNTER" }
    current_value = { N = "2347743070806" }
    range_start   = { N = "2347743070806" }
    range_end     = { N = "3521614606207" }
  })
}
```

---

## Summary

```mermaid
mindmap
  root((Global Range<br/>Allocation))
    Uniqueness
      Non-overlapping ranges
      No collisions possible
    Performance
      Local AtomicLong
      Millions IDs/second
    Coordination
      Only batch allocation
      Every ~1M IDs
    Availability
      Independent regions
      No single point of failure
    Capacity
      584+ years per region
      At 167M URLs/month
    Traceability
      Code → Value → Region
      Full audit trail
```

| Aspect | Implementation |
|--------|----------------|
| **Uniqueness** | Guaranteed by non-overlapping region ranges |
| **Coordination** | Only needed for batch allocation (every ~1M IDs) |
| **Throughput** | Millions of IDs/second (local AtomicLong) |
| **Availability** | Each region operates independently |
| **Capacity** | 584+ years per region at 167M URLs/month |
| **Traceability** | Code → Numeric value → Region mapping |
