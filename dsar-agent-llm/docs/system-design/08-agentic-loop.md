# Agentic Loop: Research → Generate → Verify → Refine

## Overview

The DSAR Query Generator uses an **agentic loop** pattern rather than a single-shot LLM call. This approach treats the LLM as an agent that iteratively works toward a correct solution, with verification gates that catch and correct errors.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AGENTIC LOOP                                       │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
     │  RESEARCH  │────▶│  GENERATE  │────▶│   VERIFY   │────▶│   REFINE   │
     │            │     │            │     │            │     │            │
     │ Understand │     │ Create SQL │     │ Validate   │     │ Fix errors │
     │ request    │     │ query      │     │ output     │     │ and retry  │
     └────────────┘     └────────────┘     └────────────┘     └─────┬──────┘
                                                                    │
                                                                    │ Loop back
                                                                    ▼
                                                            ┌────────────┐
                                                            │  GENERATE  │
                                                            │  (retry)   │
                                                            └────────────┘
```

---

## Why Agentic Over Single-Shot?

### Single-Shot Limitations

| Problem | Example | Impact |
|---------|---------|--------|
| No self-correction | LLM outputs invalid SQL | Request fails |
| No context refinement | Ambiguous request | Wrong interpretation |
| All-or-nothing | One parsing error | Complete failure |
| No learning from errors | Same mistake repeated | Consistent failures |

### Agentic Advantages

| Benefit | Mechanism | Impact |
|---------|-----------|--------|
| Self-correction | Error feedback in prompt | Higher success rate |
| Iterative refinement | Multi-turn conversation | Better accuracy |
| Graceful degradation | Partial success possible | Lower failure rate |
| Error-aware generation | Learn from validation | Fewer repeated errors |

---

## Phase 1: RESEARCH

### Purpose
Understand the user's request and map it to the available schema before generating any SQL.

### Process

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RESEARCH PHASE                                     │
└─────────────────────────────────────────────────────────────────────────────┘

    Input: "Show me my payment transactions from last year"

    ┌────────────────────────────────────────────────────────────────────┐
    │  1. INTENT CLASSIFICATION                                          │
    │                                                                     │
    │  • Data access request ✓                                           │
    │  • Not deletion request                                            │
    │  • Not modification request                                        │
    │  • Scope: Single user's data                                       │
    └────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │  2. ENTITY EXTRACTION                                              │
    │                                                                     │
    │  • "payment transactions" → payments table                         │
    │  • "last year" → date range: 2024-01-01 to 2025-01-01             │
    │  • "my" → user_id filter                                           │
    └────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │  3. SCHEMA MAPPING                                                 │
    │                                                                     │
    │  Available tables: users, trips, payments, ratings                 │
    │  Matched: payments                                                 │
    │  Relevant columns: id, amount, currency, created_at, status        │
    └────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │  4. AMBIGUITY CHECK                                                │
    │                                                                     │
    │  • Clear intent? ✓                                                 │
    │  • Single interpretation? ✓                                        │
    │  • Proceed to GENERATE                                             │
    └────────────────────────────────────────────────────────────────────┘
```

### Ambiguity Handling

When research phase detects ambiguity:

```
    Input: "Show me my data"

    ┌────────────────────────────────────────────────────────────────────┐
    │  AMBIGUITY DETECTED                                                │
    │                                                                     │
    │  • "data" is too broad                                             │
    │  • Multiple tables could apply                                     │
    │  • No time constraint specified                                    │
    │                                                                     │
    │  Response:                                                         │
    │  {                                                                 │
    │    "clarification_needed": true,                                   │
    │    "message": "Please specify which data you need",                │
    │    "suggestions": [                                                │
    │      "trip history",                                               │
    │      "payment records",                                            │
    │      "profile information",                                        │
    │      "ratings and reviews"                                         │
    │    ]                                                               │
    │  }                                                                 │
    └────────────────────────────────────────────────────────────────────┘
```

---

## Phase 2: GENERATE

### Purpose
Create a syntactically correct, semantically appropriate SQL query based on research findings.

### Process

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GENERATE PHASE                                     │
└─────────────────────────────────────────────────────────────────────────────┘

    Research Output:
    • Table: payments
    • Columns: id, amount, currency, created_at, status
    • Filters: user_id = $1, created_at in 2024
    • User ID: usr_abc123

    ┌────────────────────────────────────────────────────────────────────┐
    │  LLM GENERATION                                                    │
    │                                                                     │
    │  System Prompt:                                                    │
    │  - Role: SQL generator                                             │
    │  - Constraints: SELECT only, parameterized, schema-bound           │
    │  - Schema: [tables and columns]                                    │
    │  - Output format: JSON with sql, params, tables, columns           │
    │                                                                     │
    │  User Prompt:                                                      │
    │  - User ID: usr_abc123                                             │
    │  - Request: "payment transactions from last year"                  │
    └────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │  GENERATED OUTPUT                                                  │
    │                                                                     │
    │  {                                                                 │
    │    "sql": "SELECT id, amount, currency, created_at, status         │
    │            FROM payments                                           │
    │            WHERE user_id = $1                                      │
    │            AND created_at >= $2                                    │
    │            AND created_at < $3",                                   │
    │    "params": ["usr_abc123", "2024-01-01", "2025-01-01"],          │
    │    "tables_accessed": ["payments"],                                │
    │    "columns_returned": ["id", "amount", "currency",                │
    │                         "created_at", "status"],                   │
    │    "confidence": "high"                                            │
    │  }                                                                 │
    └────────────────────────────────────────────────────────────────────┘
```

### Generation Guidelines

```python
# Generation constraints enforced by prompt
GENERATION_RULES = """
1. ONLY SELECT statements
2. ALWAYS use $1, $2, $3 for parameters
3. First parameter ($1) MUST be user_id
4. ONLY include columns from allowed list
5. NEVER include excluded columns
6. Maximum 5 tables per query
7. Use explicit column names (no SELECT *)
"""
```

---

## Phase 3: VERIFY

### Purpose
Validate the generated SQL against all security and correctness constraints.

### Validation Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           VERIFY PHASE                                       │
└─────────────────────────────────────────────────────────────────────────────┘

    Generated SQL → Validation Pipeline

    ┌──────────────────┐
    │  1. JSON Parse   │──── Invalid JSON? ──────▶ REFINE (parse error)
    └────────┬─────────┘
             │ Valid
             ▼
    ┌──────────────────┐
    │  2. SQL Parse    │──── Invalid syntax? ────▶ REFINE (syntax error)
    └────────┬─────────┘
             │ Valid
             ▼
    ┌──────────────────┐
    │  3. Statement    │──── Not SELECT? ────────▶ REFINE (wrong type)
    │     Type Check   │
    └────────┬─────────┘
             │ SELECT
             ▼
    ┌──────────────────┐
    │  4. Table        │──── Blocked table? ─────▶ REFINE (table error)
    │     Allowlist    │
    └────────┬─────────┘
             │ All allowed
             ▼
    ┌──────────────────┐
    │  5. Column       │──── Excluded column? ───▶ REFINE (column error)
    │     Allowlist    │
    └────────┬─────────┘
             │ All allowed
             ▼
    ┌──────────────────┐
    │  6. Parameter    │──── Literal values? ────▶ REFINE (param error)
    │     Check        │
    └────────┬─────────┘
             │ Parameterized
             ▼
    ┌──────────────────┐
    │  7. Complexity   │──── Too many tables? ───▶ REFINE (complexity)
    │     Check        │
    └────────┬─────────┘
             │ Within limits
             ▼
    ┌──────────────────┐
    │  ✅ VALID        │
    │  Proceed to      │
    │  audit + return  │
    └──────────────────┘
```

### Validation Implementation

```python
class QueryValidator:
    def validate(self, generated: GeneratedQuery, schema: SchemaRegistry) -> ValidationResult:
        errors = []

        # 1. Parse SQL
        try:
            parsed = sqlparse.parse(generated.sql)
            if not parsed:
                return ValidationResult(valid=False, errors=["Empty SQL"])
            stmt = parsed[0]
        except Exception as e:
            return ValidationResult(valid=False, errors=[f"SQL parse error: {e}"])

        # 2. Check statement type
        stmt_type = stmt.get_type()
        if stmt_type != "SELECT":
            errors.append(f"Only SELECT allowed, got: {stmt_type}")

        # 3. Extract and validate tables
        tables = self._extract_tables(stmt)
        for table in tables:
            if table in schema.blocked_tables:
                errors.append(f"Blocked table: {table}")
            elif table not in schema.tables:
                errors.append(f"Unknown table: {table}")

        # 4. Validate columns
        for table in tables:
            if table in schema.tables:
                allowed = schema.tables[table].allowed_columns
                excluded = schema.tables[table].excluded_columns
                for col in self._extract_columns_for_table(stmt, table):
                    if col in excluded:
                        errors.append(f"Excluded column: {table}.{col}")
                    elif col not in allowed:
                        errors.append(f"Unknown column: {table}.{col}")

        # 5. Check parameterization
        if self._contains_literal_user_id(generated.sql, generated.params):
            errors.append("Query contains literal user ID; must use $1")

        # 6. Check complexity
        if len(tables) > 5:
            errors.append(f"Too many tables: {len(tables)} (max 5)")

        return ValidationResult(valid=len(errors) == 0, errors=errors)
```

---

## Phase 4: REFINE

### Purpose
When verification fails, provide error context to the LLM and request a corrected query.

### Refinement Process

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           REFINE PHASE                                       │
└─────────────────────────────────────────────────────────────────────────────┘

    Validation Error: "Excluded column: users.password_hash"

    ┌────────────────────────────────────────────────────────────────────┐
    │  REFINEMENT PROMPT                                                 │
    │                                                                     │
    │  Previous attempt failed validation:                               │
    │  - Error: "Excluded column: users.password_hash"                   │
    │                                                                     │
    │  Your query included the column 'password_hash' from the 'users'   │
    │  table, which is not allowed. Please regenerate the query          │
    │  using only these allowed columns for 'users':                     │
    │  - id, email, name, phone, created_at                              │
    │                                                                     │
    │  Original request: "Show me my user profile"                       │
    │  User ID: usr_abc123                                               │
    └────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │  LLM REGENERATION                                                  │
    │                                                                     │
    │  {                                                                 │
    │    "sql": "SELECT id, email, name, phone, created_at               │
    │            FROM users WHERE user_id = $1",                         │
    │    "params": ["usr_abc123"],                                       │
    │    "tables_accessed": ["users"],                                   │
    │    "columns_returned": ["id", "email", "name", "phone",            │
    │                         "created_at"],                             │
    │    "confidence": "high"                                            │
    │  }                                                                 │
    └────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                              Back to VERIFY
```

### Refinement Limits

```python
MAX_REFINEMENT_ATTEMPTS = 2

async def generate_with_refinement(request: DSARRequest) -> DSARResponse:
    messages = prompt_builder.build_messages(request)

    for attempt in range(MAX_REFINEMENT_ATTEMPTS + 1):
        # Generate
        response = await llm_client.complete(messages)
        generated = parse_llm_response(response)

        # Verify
        validation = validator.validate(generated, schema)

        if validation.valid:
            return DSARResponse(
                request_id=request.request_id,
                generated_query=generated,
                confidence=generated.confidence,
            )

        # Refine (add error context)
        if attempt < MAX_REFINEMENT_ATTEMPTS:
            messages.append({
                "role": "assistant",
                "content": response.content,
            })
            messages.append({
                "role": "user",
                "content": build_refinement_prompt(validation.errors),
            })

    # Max attempts exceeded
    return DSARResponse(
        request_id=request.request_id,
        error="Failed to generate valid query after refinement",
        validation_errors=validation.errors,
    )
```

---

## Complete Loop Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COMPLETE AGENTIC LOOP                                 │
└─────────────────────────────────────────────────────────────────────────────┘

                            ┌───────────────┐
                            │    Request    │
                            │    Received   │
                            └───────┬───────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      RESEARCH       │
                         │   ┌─────────────┐   │
                         │   │Parse intent │   │
                         │   │Map to schema│   │
                         │   │Check clarity│   │
                         │   └─────────────┘   │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
             ┌────────────┐                 ┌────────────────┐
             │   Clear    │                 │    Ambiguous   │
             │  Intent    │                 │    Request     │
             └─────┬──────┘                 └───────┬────────┘
                   │                                │
                   ▼                                ▼
         ┌─────────────────────┐           ┌────────────────┐
         │      GENERATE       │           │    Return      │
         │   ┌─────────────┐   │           │  Clarification │
         │   │Build prompt │   │           │    Response    │
         │   │Call LLM     │   │           └────────────────┘
         │   │Parse JSON   │   │
         │   └─────────────┘   │
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │       VERIFY        │
         │   ┌─────────────┐   │
         │   │Parse SQL    │   │
         │   │Check tables │   │
         │   │Check columns│   │
         │   │Check params │   │
         │   └─────────────┘   │
         └──────────┬──────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
 ┌────────────┐          ┌────────────┐
 │   Valid    │          │  Invalid   │
 └─────┬──────┘          └─────┬──────┘
       │                       │
       │                       ▼
       │              ┌─────────────────────┐
       │              │       REFINE        │
       │              │   ┌─────────────┐   │
       │              │   │Add errors   │   │
       │              │   │to context   │   │
       │              │   │Request fix  │   │
       │              │   └─────────────┘   │
       │              └──────────┬──────────┘
       │                         │
       │              ┌──────────┴──────────┐
       │              ▼                     ▼
       │       ┌────────────┐        ┌────────────┐
       │       │  Retry     │        │ Max Retries│
       │       │  (Loop)    │        │  Exceeded  │
       │       └──────┬─────┘        └─────┬──────┘
       │              │                    │
       │              │                    ▼
       │              │             ┌────────────┐
       │              │             │   Return   │
       │              │             │   Error    │
       │              │             └────────────┘
       │              │
       │              └────────▶ GENERATE
       │
       ▼
┌─────────────────────┐
│     COMPLETE        │
│  ┌─────────────┐    │
│  │Write audit  │    │
│  │Return query │    │
│  │+ metadata   │    │
│  └─────────────┘    │
└─────────────────────┘
```

---

## Benefits of Agentic Loop

| Benefit | Mechanism |
|---------|-----------|
| **Higher accuracy** | Errors are caught and corrected |
| **Self-healing** | LLM learns from validation failures |
| **Graceful degradation** | Partial failures don't crash system |
| **Audit trail** | Each attempt is logged |
| **Transparency** | User sees refinement history |
| **Schema enforcement** | Multiple validation layers |

---

## Configuration

```python
AGENTIC_CONFIG = {
    # Maximum refinement attempts before failure
    "max_refinement_attempts": 2,

    # Whether to include previous attempts in refinement prompt
    "include_attempt_history": True,

    # Timeout for entire agentic loop
    "loop_timeout_seconds": 30,

    # Whether to return partial results on timeout
    "return_partial_on_timeout": False,
}
```
