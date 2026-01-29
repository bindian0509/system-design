# Error Handling

## Error Categories

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ERROR TAXONOMY                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  CLIENT ERRORS (4xx)                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  400 Bad Request        │ Invalid request payload, missing fields           │
│  401 Unauthorized       │ Missing or invalid JWT token                      │
│  403 Forbidden          │ Valid token but insufficient permissions          │
│  422 Unprocessable      │ Valid JSON but semantic validation failed         │
│  429 Too Many Requests  │ Rate limit exceeded                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  SERVER ERRORS (5xx)                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  500 Internal Error     │ Unexpected server failure                         │
│  502 Bad Gateway        │ LLM provider unreachable                          │
│  503 Service Unavailable│ Service overloaded or in maintenance              │
│  504 Gateway Timeout    │ LLM provider timeout                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  BUSINESS LOGIC ERRORS (200 with error payload)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  clarification_needed   │ Request is ambiguous, need user input             │
│  out_of_scope          │ Request is for deletion/modification               │
│  validation_failed     │ Generated query failed safety checks               │
│  generation_failed     │ LLM could not generate valid query                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Error Response Formats

### HTTP Error Response

```json
{
  "error": "validation_error",
  "detail": "Request body validation failed",
  "request_id": "req_abc123",
  "errors": [
    {
      "field": "user_id",
      "message": "Field is required"
    }
  ]
}
```

### Clarification Needed Response

```json
{
  "status": "clarification_needed",
  "request_id": "dsar-12345",
  "message": "Your request is ambiguous. Please specify which data you need.",
  "suggestions": [
    "trip history",
    "payment records",
    "profile information",
    "ratings and reviews"
  ],
  "original_request": "show me my data"
}
```

### Out of Scope Response

```json
{
  "status": "out_of_scope",
  "request_id": "dsar-12345",
  "message": "This system handles data access requests only. Deletion requests require a different workflow.",
  "escalation_path": "DSAR-DELETION-QUEUE",
  "detected_intent": "data_deletion",
  "original_request": "delete all my payment history"
}
```

### Validation Failed Response

```json
{
  "status": "validation_failed",
  "request_id": "dsar-12345",
  "message": "The generated query could not pass safety validation after multiple attempts.",
  "validation_errors": [
    "Query references blocked table: audit_logs",
    "Query includes excluded column: users.password_hash"
  ],
  "attempts": 3,
  "recommendation": "Please rephrase your request or contact support for manual handling."
}
```

### Generation Failed Response

```json
{
  "status": "generation_failed",
  "request_id": "dsar-12345",
  "message": "Could not generate a query for this request.",
  "reason": "The request does not map to any available data tables.",
  "original_request": "show me my quantum entanglement records"
}
```

---

## Error Handling by Component

### API Gateway

```python
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "request_id": request.state.request_id,
        },
    )

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": "Request body validation failed",
            "request_id": request.state.request_id,
            "errors": [
                {"field": e["loc"][-1], "message": e["msg"]}
                for e in exc.errors()
            ],
        },
    )

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": f"Rate limit of {exc.limit} requests per hour exceeded",
            "retry_after_seconds": exc.retry_after,
            "request_id": request.state.request_id,
        },
        headers={"Retry-After": str(exc.retry_after)},
    )
```

### LLM Service

```python
class LLMServiceError(Exception):
    """Base exception for LLM service errors."""
    pass

class LLMProviderError(LLMServiceError):
    """LLM provider returned an error or is unreachable."""
    def __init__(self, provider: str, status_code: int, message: str):
        self.provider = provider
        self.status_code = status_code
        self.message = message
        super().__init__(f"{provider} error ({status_code}): {message}")

class LLMResponseParseError(LLMServiceError):
    """Could not parse LLM response as expected JSON."""
    def __init__(self, raw_response: str, parse_error: str):
        self.raw_response = raw_response
        self.parse_error = parse_error
        super().__init__(f"Failed to parse LLM response: {parse_error}")

class LLMTimeoutError(LLMServiceError):
    """LLM request timed out."""
    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        super().__init__(f"LLM request timed out after {timeout_seconds}s")


async def call_llm_with_error_handling(
    messages: list[dict],
    timeout: float = 30.0,
) -> LLMResponse:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                LLM_API_URL,
                json={"messages": messages},
                headers={"Authorization": f"Bearer {API_KEY}"},
            )

        if response.status_code != 200:
            raise LLMProviderError(
                provider="openai",
                status_code=response.status_code,
                message=response.text,
            )

        return parse_llm_response(response.json())

    except httpx.TimeoutException:
        raise LLMTimeoutError(timeout)
    except json.JSONDecodeError as e:
        raise LLMResponseParseError(response.text, str(e))
```

### Query Validator

```python
@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str] = field(default_factory=list)

class ValidationError(Exception):
    """Query validation failed."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {', '.join(errors)}")

class QueryValidator:
    def validate(self, query: GeneratedQuery, schema: SchemaRegistry) -> ValidationResult:
        errors = []
        warnings = []

        # ... validation checks ...

        if errors:
            raise ValidationError(errors)

        return ValidationResult(valid=True, errors=[], warnings=warnings)
```

---

## Error Recovery Strategies

### Retry with Backoff

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((LLMTimeoutError, LLMProviderError)),
)
async def call_llm_with_retry(messages: list[dict]) -> LLMResponse:
    return await call_llm(messages)
```

### Fallback to Secondary Provider

```python
async def call_llm_with_fallback(messages: list[dict]) -> LLMResponse:
    providers = [
        ("openai", openai_client),
        ("anthropic", anthropic_client),
    ]

    last_error = None
    for provider_name, client in providers:
        try:
            return await client.complete(messages)
        except LLMProviderError as e:
            logger.warning(f"{provider_name} failed: {e}")
            last_error = e
            continue

    raise LLMServiceError(f"All providers failed. Last error: {last_error}")
```

### Graceful Degradation

```python
async def generate_query(request: DSARRequest) -> DSARResponse:
    try:
        # Try full agentic loop
        return await full_agentic_generation(request)
    except LLMServiceError as e:
        logger.error(f"LLM service failed: {e}")
        # Return helpful error instead of 500
        return DSARResponse(
            request_id=request.request_id,
            status="generation_failed",
            message="Query generation service is temporarily unavailable. Please try again later.",
            retry_after_seconds=60,
        )
```

---

## Error Logging

### Structured Error Logs

```python
import structlog

logger = structlog.get_logger()

async def handle_request(request: DSARRequest) -> DSARResponse:
    log = logger.bind(
        request_id=request.request_id,
        user_id=request.user_id,
        agent_email=request.requester_email,
    )

    try:
        result = await generate_query(request)
        log.info("query_generated", tables=result.tables_accessed)
        return result

    except ValidationError as e:
        log.warning(
            "validation_failed",
            errors=e.errors,
            attempt_count=e.attempt_count,
        )
        return create_validation_error_response(request, e)

    except LLMServiceError as e:
        log.error(
            "llm_service_error",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        return create_service_error_response(request, e)

    except Exception as e:
        log.exception("unexpected_error", error=str(e))
        raise
```

### Error Metrics

```python
from prometheus_client import Counter, Histogram

# Error counters
errors_total = Counter(
    "dsar_errors_total",
    "Total errors by type",
    ["error_type", "component"],
)

# Error latency (time to error)
error_latency = Histogram(
    "dsar_error_latency_seconds",
    "Time until error occurred",
    ["error_type"],
)

# Usage
errors_total.labels(error_type="validation_failed", component="validator").inc()
error_latency.labels(error_type="llm_timeout").observe(30.0)
```

---

## User-Facing Error Messages

### Principles

1. **Clear** - Explain what went wrong
2. **Actionable** - Tell user what to do next
3. **Safe** - Never expose internal details
4. **Consistent** - Same format for all errors

### Error Message Templates

| Error Type | User Message |
|------------|--------------|
| Rate limit | "You've exceeded the request limit. Please wait {time} before trying again." |
| Ambiguous request | "Your request is ambiguous. Please choose from: {suggestions}" |
| Out of scope | "This request type is not supported. For {intent}, please use {escalation_path}." |
| Validation failed | "We couldn't generate a safe query for this request. Please rephrase or contact support." |
| Service unavailable | "The query service is temporarily unavailable. Please try again in a few minutes." |
| Timeout | "Your request took too long to process. Please try a simpler query." |

### Example Implementation

```python
ERROR_MESSAGES = {
    "rate_limit": "You've exceeded the request limit of {limit} per hour. "
                  "Please wait {wait_time} before trying again.",
    "clarification_needed": "Your request is ambiguous. "
                           "Please specify which data you need: {suggestions}",
    "out_of_scope": "This system handles data access requests only. "
                   "For {intent} requests, please submit to {escalation_path}.",
    "validation_failed": "We couldn't generate a safe query for this request. "
                        "Please try rephrasing or contact support for manual handling.",
    "service_unavailable": "The query service is temporarily unavailable. "
                          "Please try again in a few minutes.",
    "timeout": "Your request took too long to process. "
              "Please try a simpler, more specific query.",
}

def format_error_message(error_type: str, **kwargs) -> str:
    template = ERROR_MESSAGES.get(error_type, "An unexpected error occurred.")
    return template.format(**kwargs)
```

---

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ERROR HANDLING FLOW                                   │
└─────────────────────────────────────────────────────────────────────────────┘

    Request Received
          │
          ▼
    ┌───────────────┐
    │ Auth Check    │──── Fail ────▶ 401 Unauthorized
    └───────┬───────┘
            │ Pass
            ▼
    ┌───────────────┐
    │ Rate Check    │──── Exceed ──▶ 429 Too Many Requests
    └───────┬───────┘
            │ OK
            ▼
    ┌───────────────┐
    │ Validate Body │──── Invalid ─▶ 400/422 Bad Request
    └───────┬───────┘
            │ Valid
            ▼
    ┌───────────────┐
    │ Research Phase│──── Ambiguous ▶ 200 + clarification_needed
    └───────┬───────┘
            │ Clear
            ▼
    ┌───────────────┐
    │ Generate Phase│──── LLM Fail ─▶ Retry/Fallback
    └───────┬───────┘                      │
            │                              │ All fail
            │                              ▼
            │                         502/504 + retry info
            │
            ▼
    ┌───────────────┐
    │ Verify Phase  │──── Invalid ──▶ Refine (retry)
    └───────┬───────┘                      │
            │                              │ Max retries
            │                              ▼
            │                         200 + validation_failed
            │
            ▼
    ┌───────────────┐
    │ Audit + Return│
    │   200 OK      │
    └───────────────┘
```

---

## Monitoring and Alerting

### Error Rate Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Error rate (all) | > 1% | > 5% |
| Validation failures | > 10% | > 25% |
| LLM timeouts | > 5% | > 15% |
| Auth failures | > 0.5% | > 2% |
| Rate limit hits | > 10/hour/agent | > 50/hour/agent |

### Alert Configuration

```yaml
# Prometheus alerting rules
groups:
  - name: dsar-query-generator
    rules:
      - alert: HighErrorRate
        expr: rate(dsar_errors_total[5m]) / rate(dsar_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate in DSAR Query Generator"
          description: "Error rate is {{ $value | printf \"%.2f\" }}%"

      - alert: LLMProviderDown
        expr: rate(dsar_errors_total{error_type="llm_provider_error"}[5m]) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "LLM provider errors detected"
```
