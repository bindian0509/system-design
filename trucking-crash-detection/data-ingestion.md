# Data Ingestion Layer

## Overview

The ingestion layer handles the complexity of integrating with 100+ telematics providers, each with different APIs, protocols, and data formats. This is the most critical layer for data quality and system reliability.

---

## Integration Patterns

### Push Model Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PUSH MODEL ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────┐  │
│  │ Provider A   │────▶│           API GATEWAY CLUSTER                    │  │
│  │ (REST)       │     │  ┌────────────────────────────────────────────┐  │  │
│  └──────────────┘     │  │ • TLS Termination                          │  │  │
│                       │  │ • mTLS Client Authentication               │  │  │
│  ┌──────────────┐     │  │ • Rate Limiting (per provider)            │  │  │
│  │ Provider B   │────▶│  │ • Request Validation                       │  │  │
│  │ (Webhook)    │     │  │ • Signature Verification                   │  │  │
│  └──────────────┘     │  └────────────────────────────────────────────┘  │  │
│                       └──────────────────────┬───────────────────────────┘  │
│  ┌──────────────┐                            │                              │
│  │ Provider C   │───┐                        ▼                              │
│  │ (MQTT)       │   │     ┌──────────────────────────────────────────────┐  │
│  └──────────────┘   │     │         PROTOCOL ADAPTERS                     │  │
│                     │     │  ┌────────────┐ ┌────────────┐ ┌────────────┐ │  │
│                     └────▶│  │ REST       │ │ Webhook    │ │ MQTT       │ │  │
│                           │  │ Adapter    │ │ Adapter    │ │ Bridge     │ │  │
│                           │  └────────────┘ └────────────┘ └────────────┘ │  │
│                           └──────────────────────┬───────────────────────┘  │
│                                                  │                          │
│                                                  ▼                          │
│                           ┌──────────────────────────────────────────────┐  │
│                           │        raw-sensor-data (Kafka Topic)         │  │
│                           └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pull Model Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PULL MODEL ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    SCHEDULER SERVICE (Temporal/Airflow)                 │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │ Job: poll_provider_a    │ Interval: 5s   │ Vehicles: 50,000     │  │ │
│  │  │ Job: poll_provider_b    │ Interval: 10s  │ Vehicles: 120,000    │  │ │
│  │  │ Job: poll_provider_c    │ Interval: 3s   │ Vehicles: 80,000     │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────┬───────────────────────────────────┘ │
│                                       │                                     │
│                                       ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                       POLLER WORKER FLEET                               │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │ │
│  │  │ Worker Pool │ │ Worker Pool │ │ Worker Pool │ │ Worker Pool │       │ │
│  │  │ Provider A  │ │ Provider B  │ │ Provider C  │ │ Provider N  │       │ │
│  │  │ (20 pods)   │ │ (30 pods)   │ │ (15 pods)   │ │ (varies)    │       │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │ │
│  │                                                                         │ │
│  │  Features:                                                              │ │
│  │  • Connection pooling per provider                                      │ │
│  │  • Adaptive rate limiting                                               │ │
│  │  • Exponential backoff on failures                                      │ │
│  │  • Checkpoint tracking for resume                                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                     │
│                                       ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                       raw-sensor-data (Kafka Topic)                     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Provider Adapter Pattern

Each telematics provider requires a custom adapter to handle their specific API and data format.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROVIDER ADAPTER PATTERN                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    ProviderAdapter Interface                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │ + authenticate(credentials): AuthToken                         │  │   │
│  │  │ + fetchVehicleData(vehicleId, timeRange): RawData              │  │   │
│  │  │ + parsePayload(rawPayload): NormalizedEvent[]                  │  │   │
│  │  │ + validateSignature(payload, signature): boolean               │  │   │
│  │  │ + getHealthStatus(): ProviderHealth                            │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                       │                                      │
│          ┌────────────────────────────┼────────────────────────────┐        │
│          │                            │                            │        │
│          ▼                            ▼                            ▼        │
│  ┌───────────────┐           ┌───────────────┐           ┌───────────────┐  │
│  │ SamsaraAdapter│           │ GeotabAdapter │           │ VerizonAdapter│  │
│  │               │           │               │           │               │  │
│  │ • OAuth 2.0   │           │ • API Key     │           │ • mTLS        │  │
│  │ • JSON format │           │ • XML format  │           │ • Protobuf    │  │
│  │ • REST API    │           │ • SOAP API    │           │ • gRPC        │  │
│  └───────────────┘           └───────────────┘           └───────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Adapter Configuration (Example)

```yaml
# provider-configs/samsara.yaml
provider:
  id: samsara
  name: "Samsara"
  type: push  # or pull
  protocol: rest

auth:
  type: oauth2
  token_url: "https://api.samsara.com/oauth/token"
  scopes: ["fleet:read", "vehicles:read"]
  refresh_interval: 3600

endpoints:
  webhook:
    path: "/webhooks/samsara"
    signature_header: "X-Samsara-Signature"
    signature_algo: "hmac-sha256"
  api:
    base_url: "https://api.samsara.com/v1"
    rate_limit: 100  # requests per second

data_mapping:
  vehicle_id: "$.vehicle.id"
  timestamp: "$.eventTime"
  gps:
    latitude: "$.location.latitude"
    longitude: "$.location.longitude"
    speed: "$.location.speed"
  accelerometer:
    x: "$.diagnostics.accelerometer.x"
    y: "$.diagnostics.accelerometer.y"
    z: "$.diagnostics.accelerometer.z"
  gyroscope:
    roll: "$.diagnostics.gyroscope.roll"
    pitch: "$.diagnostics.gyroscope.pitch"
    yaw: "$.diagnostics.gyroscope.yaw"

transformations:
  - field: speed
    from_unit: mph
    to_unit: mps  # meters per second
  - field: timestamp
    from_format: "epoch_ms"
    to_format: "iso8601"
```

---

## Data Normalization

### Canonical Event Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["event_id", "vehicle_id", "provider_id", "timestamp", "event_type"],
  "properties": {
    "event_id": {
      "type": "string",
      "format": "uuid",
      "description": "Globally unique event identifier (idempotency key)"
    },
    "vehicle_id": {
      "type": "string",
      "description": "Normalized vehicle identifier"
    },
    "provider_id": {
      "type": "string",
      "description": "Source telematics provider"
    },
    "provider_vehicle_id": {
      "type": "string",
      "description": "Original vehicle ID from provider"
    },
    "policy_id": {
      "type": "string",
      "description": "Associated insurance policy"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "Event timestamp in ISO 8601 UTC"
    },
    "ingestion_timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "When event was received by system"
    },
    "event_type": {
      "type": "string",
      "enum": ["telemetry", "alert", "diagnostic", "camera"]
    },
    "gps": {
      "type": "object",
      "properties": {
        "latitude": {"type": "number", "minimum": -90, "maximum": 90},
        "longitude": {"type": "number", "minimum": -180, "maximum": 180},
        "altitude_m": {"type": "number"},
        "speed_mps": {"type": "number", "minimum": 0},
        "heading_deg": {"type": "number", "minimum": 0, "maximum": 360},
        "accuracy_m": {"type": "number", "minimum": 0}
      }
    },
    "accelerometer": {
      "type": "object",
      "properties": {
        "x_g": {"type": "number", "description": "Longitudinal acceleration (g-force)"},
        "y_g": {"type": "number", "description": "Lateral acceleration (g-force)"},
        "z_g": {"type": "number", "description": "Vertical acceleration (g-force)"},
        "magnitude_g": {"type": "number", "description": "Total magnitude"}
      }
    },
    "gyroscope": {
      "type": "object",
      "properties": {
        "roll_dps": {"type": "number", "description": "Roll rate (degrees/sec)"},
        "pitch_dps": {"type": "number", "description": "Pitch rate (degrees/sec)"},
        "yaw_dps": {"type": "number", "description": "Yaw rate (degrees/sec)"}
      }
    },
    "vehicle_state": {
      "type": "object",
      "properties": {
        "ignition": {"type": "string", "enum": ["on", "off", "accessory"]},
        "odometer_km": {"type": "number"},
        "fuel_level_pct": {"type": "number", "minimum": 0, "maximum": 100},
        "engine_rpm": {"type": "integer"}
      }
    },
    "camera": {
      "type": "object",
      "properties": {
        "event_type": {"type": "string"},
        "video_url": {"type": "string", "format": "uri"},
        "thumbnail_url": {"type": "string", "format": "uri"},
        "duration_sec": {"type": "number"}
      }
    },
    "quality": {
      "type": "object",
      "properties": {
        "score": {"type": "number", "minimum": 0, "maximum": 1},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
        "validation_warnings": {"type": "array", "items": {"type": "string"}}
      }
    }
  }
}
```

---

## Deduplication Strategy

Events can arrive multiple times due to retries, provider bugs, or network issues.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DEDUPLICATION FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Incoming Event                                                              │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │              Generate Idempotency Key                        │            │
│  │  key = hash(provider_id + vehicle_id + timestamp + sensor_hash)          │
│  └─────────────────────────────────────────────────────────────┘            │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │              Check Redis Bloom Filter                        │            │
│  │              (Fast probabilistic check)                      │            │
│  └─────────────────────────────────────────────────────────────┘            │
│       │                                                                      │
│       ├── Definitely NOT seen ──▶ Process event                             │
│       │                                                                      │
│       ├── Maybe seen ──┐                                                     │
│       │                │                                                     │
│       │                ▼                                                     │
│       │   ┌─────────────────────────────────────────────────────┐           │
│       │   │              Check Redis Set (Exact)                 │           │
│       │   │              TTL: 1 hour sliding window             │           │
│       │   └─────────────────────────────────────────────────────┘           │
│       │                │                                                     │
│       │                ├── Not in set ──▶ Process event                     │
│       │                │                                                     │
│       │                └── In set ──▶ Drop as duplicate                     │
│       │                               (increment dup_counter metric)        │
└───────┴──────────────────────────────────────────────────────────────────────┘
```

---

## Rate Limiting & Backpressure

### Per-Provider Rate Limiting

```python
# rate_limiter.py
from dataclasses import dataclass
from redis import Redis
import time

@dataclass
class ProviderRateLimit:
    provider_id: str
    requests_per_second: int
    burst_size: int
    retry_after_seconds: int = 60

class TokenBucketRateLimiter:
    """Token bucket rate limiter backed by Redis"""

    def __init__(self, redis: Redis, config: ProviderRateLimit):
        self.redis = redis
        self.config = config
        self.key = f"rate_limit:{config.provider_id}"

    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens, returns True if allowed"""
        lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local tokens = tonumber(ARGV[4])

        local bucket = redis.call('HMGET', key, 'tokens', 'last_update')
        local current_tokens = tonumber(bucket[1]) or capacity
        local last_update = tonumber(bucket[2]) or now

        -- Refill tokens based on elapsed time
        local elapsed = now - last_update
        local refill = elapsed * rate
        current_tokens = math.min(capacity, current_tokens + refill)

        if current_tokens >= tokens then
            current_tokens = current_tokens - tokens
            redis.call('HMSET', key, 'tokens', current_tokens, 'last_update', now)
            redis.call('EXPIRE', key, 3600)
            return 1
        else
            return 0
        end
        """
        now = time.time()
        result = self.redis.eval(
            lua_script, 1, self.key,
            self.config.burst_size,
            self.config.requests_per_second,
            now, tokens
        )
        return bool(result)
```

### Backpressure Handling

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BACKPRESSURE STRATEGY                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. QUEUE DEPTH MONITORING                                                   │
│     Kafka consumer lag → adaptive polling rate                               │
│                                                                              │
│     Lag < 1000    → Poll at full speed                                       │
│     Lag < 10000   → Poll at 50% rate                                        │
│     Lag < 100000  → Poll at 10% rate, alert ops                             │
│     Lag > 100000  → Pause polling, critical alert                           │
│                                                                              │
│  2. CIRCUIT BREAKER (per provider)                                           │
│     ┌─────────┐      failures > 5       ┌─────────┐                         │
│     │ CLOSED  │ ───────────────────────▶│  OPEN   │                         │
│     └─────────┘                         └─────────┘                         │
│          ▲                                   │                              │
│          │         after 30s timeout         │                              │
│          │      ┌─────────────────────┐      │                              │
│          └──────│    HALF-OPEN        │◀─────┘                              │
│      success    └─────────────────────┘                                     │
│                                                                              │
│  3. LOAD SHEDDING                                                            │
│     When overwhelmed, prioritize:                                            │
│     1. High-value policies (large fleets)                                    │
│     2. Recent crash indicators                                               │
│     3. Vehicles with active alerts                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Provider Onboarding Checklist

When adding a new telematics provider:

| Step | Task | Owner |
|------|------|-------|
| 1 | API documentation review | Engineering |
| 2 | Create provider adapter | Engineering |
| 3 | Define data mapping | Engineering |
| 4 | Authentication setup | DevOps |
| 5 | Rate limit configuration | Engineering |
| 6 | Integration testing | QA |
| 7 | Data quality validation | Data Team |
| 8 | Monitoring dashboards | SRE |
| 9 | Runbook creation | SRE |
| 10 | Production rollout (canary) | Engineering |

---

## Error Handling

```python
# error_handling.py
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class ErrorCategory(Enum):
    TRANSIENT = "transient"      # Retry with backoff
    PROVIDER_ERROR = "provider"  # Provider-side issue, alert
    VALIDATION = "validation"    # Bad data, log and skip
    FATAL = "fatal"              # System error, halt and alert

@dataclass
class IngestionError:
    category: ErrorCategory
    provider_id: str
    vehicle_id: Optional[str]
    message: str
    raw_payload: Optional[bytes]
    retry_count: int = 0

class ErrorHandler:
    MAX_RETRIES = 3

    def handle(self, error: IngestionError):
        match error.category:
            case ErrorCategory.TRANSIENT:
                if error.retry_count < self.MAX_RETRIES:
                    self.schedule_retry(error)
                else:
                    self.send_to_dlq(error)

            case ErrorCategory.PROVIDER_ERROR:
                self.alert_ops(error)
                self.send_to_dlq(error)

            case ErrorCategory.VALIDATION:
                self.log_validation_error(error)
                self.increment_quality_metric(error.provider_id)

            case ErrorCategory.FATAL:
                self.alert_critical(error)
                raise SystemError(error.message)
```

---

## Dead Letter Queue (DLQ) Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DLQ FLOW                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Processing Pipeline                                                         │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────┐     Error     ┌─────────────────────────────────────┐  │
│  │ Process Event   │ ────────────▶ │  ingestion-dlq (Kafka Topic)        │  │
│  └─────────────────┘               │  Retention: 7 days                   │  │
│                                    └─────────────────────────────────────┘  │
│                                                   │                          │
│                                                   ▼                          │
│                                    ┌─────────────────────────────────────┐  │
│                                    │      DLQ Processor                   │  │
│                                    │  • Categorize errors                 │  │
│                                    │  • Aggregate by provider             │  │
│                                    │  • Generate reports                  │  │
│                                    └─────────────────────────────────────┘  │
│                                                   │                          │
│                      ┌────────────────────────────┼─────────────────────┐   │
│                      ▼                            ▼                     ▼   │
│             ┌───────────────┐           ┌───────────────┐      ┌───────────┐│
│             │ Retry Queue   │           │ Manual Review │      │ Archive   ││
│             │ (Fixable)     │           │ Dashboard     │      │ (S3)      ││
│             └───────────────┘           └───────────────┘      └───────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

