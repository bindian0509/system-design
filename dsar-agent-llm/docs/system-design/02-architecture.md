# Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                       │
│  │ Support Tool │  │ Compliance   │  │    API       │                       │
│  │     UI       │  │   Portal     │  │   Client     │                       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                       │
└─────────┼─────────────────┼─────────────────┼───────────────────────────────┘
          │                 │                 │
          └────────────────┼─────────────────┘
                           │ HTTPS
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GATEWAY LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        API Gateway (FastAPI)                         │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │    │
│  │  │    Auth     │  │    Rate     │  │   Request   │  │  Response  │  │    │
│  │  │ Middleware  │  │   Limiter   │  │  Validator  │  │  Formatter │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SERVICE LAYER                                   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         LLM Service                                  │    │
│  │                                                                      │    │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐           │    │
│  │  │   Prompt     │───▶│    Query     │───▶│   Output     │           │    │
│  │  │   Builder    │    │  Generator   │    │  Validator   │           │    │
│  │  └──────┬───────┘    └──────────────┘    └──────┬───────┘           │    │
│  │         │                   │                    │                   │    │
│  │         │            ┌──────▼───────┐           │                   │    │
│  │         │            │   LLM API    │           │                   │    │
│  │         │            │ (OpenAI/     │           │                   │    │
│  │         │            │  Anthropic)  │           │                   │    │
│  │         │            └──────────────┘           │                   │    │
│  │         │                                        │                   │    │
│  └─────────┼────────────────────────────────────────┼───────────────────┘    │
│            │                                        │                        │
└────────────┼────────────────────────────────────────┼────────────────────────┘
             │                                        │
             ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│                                                                              │
│  ┌──────────────────┐                    ┌──────────────────┐               │
│  │  Schema Registry │                    │   Audit Logger   │               │
│  │    (YAML/JSON)   │                    │    (JSONL/DB)    │               │
│  │                  │                    │                  │               │
│  │  - Tables        │                    │  - Request logs  │               │
│  │  - Columns       │                    │  - Query logs    │               │
│  │  - Blocklists    │                    │  - Validation    │               │
│  └──────────────────┘                    └──────────────────┘               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. API Gateway

**Responsibilities:**
- Authenticate incoming requests (JWT validation)
- Rate limit by agent ID
- Validate request payload
- Route to LLM Service
- Format responses

**Key Design Decisions:**
- Stateless for horizontal scaling
- JWT auth (no session storage needed)
- In-memory rate limiting with Redis option for distributed deployment

### 2. LLM Service

**Subcomponents:**

| Component | Responsibility |
|-----------|----------------|
| Prompt Builder | Constructs system + user prompts with schema context |
| Query Generator | Calls LLM API, parses JSON response |
| Output Validator | Validates SQL syntax, tables, columns, parameterization |

**Design Principles:**
- Single responsibility per subcomponent
- Pluggable LLM providers
- Fail-safe validation (reject on any doubt)

### 3. Schema Registry

**Storage Format:** YAML for human readability, loaded into memory at startup

**Contents:**
```yaml
tables:
  users:
    allowed_columns: [id, email, name, ...]
    excluded_columns: [password_hash, ...]
    description: "User profile data"
blocked_tables:
  - audit_logs
  - security_events
```

**Access Patterns:**
- Read-heavy (loaded once, queried per request)
- Hot-reload capability for schema updates

### 4. Audit Logger

**Log Format:** Structured JSON (JSONL)

**Retention:** 7 years (GDPR compliance)

**Fields Logged:**
- Timestamp, request ID, agent ID
- User ID being queried
- Original request text
- Generated SQL and parameters
- Validation result
- LLM model used

## Data Flow

```
Request → Auth → Rate Limit → Build Prompt → Call LLM → Parse Response
                                    ↑                         ↓
                              Schema Registry           Validate SQL
                                                              ↓
                                                        Audit Log
                                                              ↓
                                                         Response
```

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Kubernetes Cluster                       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Deployment: dsar-query-generator                         │   │
│  │  Replicas: 3 (auto-scale 2-10)                           │   │
│  │                                                           │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                   │   │
│  │  │  Pod 1  │  │  Pod 2  │  │  Pod 3  │                   │   │
│  │  └─────────┘  └─────────┘  └─────────┘                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Service: LoadBalancer                                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐        │
│  │ ConfigMap:    │  │ Secret:       │  │ PVC:          │        │
│  │ schema.yaml   │  │ API keys      │  │ audit-logs    │        │
│  └───────────────┘  └───────────────┘  └───────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```
