# Technology Choices

## Stack Overview

| Layer | Technology | Version |
|-------|------------|---------|
| API Framework | FastAPI | 0.109+ |
| Runtime | Python | 3.11+ |
| LLM Provider | OpenAI / Anthropic | Latest |
| SQL Parsing | sqlparse | 0.5+ |
| Auth | python-jose (JWT) | 3.3+ |
| Config | Pydantic Settings | 2.x |
| Logging | structlog | 24.x |
| Testing | pytest + pytest-asyncio | 8.x |

---

## Component-by-Component Rationale

### 1. API Framework: FastAPI

**Choice:** FastAPI over Flask, Django, Express

| Factor | FastAPI | Flask | Django | Express |
|--------|---------|-------|--------|---------|
| Async Support | Native | Extension | Limited | Native |
| Type Safety | Pydantic built-in | Manual | Manual | TypeScript optional |
| Auto Docs | OpenAPI native | Extension | Extension | Manual |
| Performance | High | Medium | Medium | High |
| Learning Curve | Low | Low | High | Low |

**Rationale:**
1. **Native async** - LLM API calls are I/O bound; async handling improves throughput
2. **Pydantic integration** - Request/response validation with zero boilerplate
3. **OpenAPI docs** - Auto-generated API documentation for support team integration
4. **Python ecosystem** - Rich LLM libraries (openai, anthropic SDKs)

**Trade-offs:**
- Less mature than Flask/Django for some enterprise patterns
- Smaller ecosystem of plugins

---

### 2. LLM Provider: OpenAI GPT-4 / Anthropic Claude

**Choice:** GPT-4-turbo or Claude 3.5 Sonnet

| Factor | GPT-4 Turbo | Claude 3.5 Sonnet | GPT-3.5 |
|--------|-------------|-------------------|---------|
| SQL Quality | Excellent | Excellent | Good |
| Instruction Following | Excellent | Excellent | Moderate |
| Cost (per 1M tokens) | ~$10/$30 | ~$3/$15 | ~$0.5/$1.5 |
| Latency | 2-5s | 2-5s | 1-2s |
| JSON Mode | Native | Via prompting | Native |

**Rationale:**
1. **Accuracy over cost** - Query correctness is critical; cheaper models make more mistakes
2. **Structured output** - Both handle JSON output reliably with proper prompting
3. **Multi-provider support** - Avoid vendor lock-in; switch based on performance/cost

**Trade-offs:**
- Higher cost than smaller models
- Higher latency than GPT-3.5

**Why not fine-tuning?**
- Schema changes frequently; fine-tuned models need retraining
- Prompt engineering with context injection is more maintainable
- No training data collection burden

---

### 3. SQL Parser: sqlparse

**Choice:** sqlparse (Python) over node-sql-parser, ANTLR

| Factor | sqlparse | node-sql-parser | ANTLR |
|--------|----------|-----------------|-------|
| Language | Python | JavaScript | Java/Any |
| Parse Quality | Good | Good | Excellent |
| Complexity | Low | Low | High |
| Maintenance | Active | Active | Complex |
| Use Case | Validation | Validation | Full AST |

**Rationale:**
1. **Python native** - No cross-language bridges needed
2. **Sufficient for validation** - We need to validate, not transform queries
3. **Simple API** - Parse, identify statement type, extract identifiers
4. **Well-maintained** - Regular updates, good community

**Trade-offs:**
- Less precise than full SQL grammar parsers
- May not catch all edge cases in complex SQL

**Validation approach:**
```python
import sqlparse

def validate_query(sql: str) -> bool:
    parsed = sqlparse.parse(sql)
    # Check statement type
    # Extract table names
    # Extract column names
    # Verify parameterization
```

---

### 4. Authentication: JWT with python-jose

**Choice:** JWT over Session tokens, OAuth (for internal auth)

| Factor | JWT | Session Tokens | OAuth 2.0 |
|--------|-----|----------------|-----------|
| Stateless | Yes | No | Depends |
| Scalability | Excellent | Needs store | Excellent |
| Complexity | Low | Low | High |
| Expiration | Built-in | Manual | Built-in |

**Rationale:**
1. **Stateless** - No session store needed; scales horizontally
2. **Standard** - Well-understood, library support everywhere
3. **Self-contained** - Token includes agent ID, roles, expiry
4. **SSO integration** - Easy to integrate with existing company SSO

**Trade-offs:**
- Token revocation requires blocklist (or short expiry)
- Token size larger than session ID

---

### 5. Configuration: Pydantic Settings

**Choice:** Pydantic Settings over python-dotenv, configparser

| Factor | Pydantic Settings | python-dotenv | configparser |
|--------|-------------------|---------------|--------------|
| Type Safety | Excellent | None | None |
| Validation | Built-in | None | None |
| Env Vars | Native | Native | Manual |
| Defaults | Yes | No | Yes |

**Rationale:**
1. **Type safety** - Catch config errors at startup, not runtime
2. **Validation** - Ensure required values are present
3. **12-factor app** - Environment variable support for containers
4. **Pydantic ecosystem** - Consistent with FastAPI patterns

---

### 6. Logging: structlog

**Choice:** structlog over logging, loguru

| Factor | structlog | logging | loguru |
|--------|-----------|---------|--------|
| Structured | Native | Manual | Good |
| JSON Output | Native | Formatter | Native |
| Context | Excellent | Manual | Good |
| Performance | High | Medium | High |

**Rationale:**
1. **Structured logs** - JSON output for log aggregation systems
2. **Context propagation** - Attach request_id, agent_id to all logs
3. **Compliance** - Audit trail requires structured, parseable logs
4. **Cloud-native** - Works well with CloudWatch, Datadog, etc.

---

## Infrastructure Choices

### Container Runtime: Docker + Kubernetes

**Rationale:**
- Standard enterprise deployment pattern
- Horizontal scaling for load spikes
- Health checks and auto-restart
- ConfigMaps for schema registry updates

### Secrets Management: Kubernetes Secrets / AWS Secrets Manager

**Rationale:**
- Never store API keys in code or config files
- Rotation support for LLM API keys
- Audit trail for secret access

### Observability: OpenTelemetry

**Rationale:**
- Standard for distributed tracing
- Vendor-agnostic (works with Jaeger, Datadog, etc.)
- Track LLM latency, error rates, token usage

---

## Decision Matrix

| Decision | Options Considered | Selected | Key Factor |
|----------|-------------------|----------|------------|
| Language | Python, Node.js, Go | Python | LLM SDK maturity |
| Framework | FastAPI, Flask, Django | FastAPI | Async + types |
| LLM | GPT-4, Claude, Llama | GPT-4/Claude | Accuracy |
| SQL Parser | sqlparse, ANTLR | sqlparse | Simplicity |
| Auth | JWT, Session, OAuth | JWT | Stateless scaling |
| Logging | structlog, logging | structlog | JSON native |
| Config | Pydantic, dotenv | Pydantic | Type safety |
