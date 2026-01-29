"""Prompt builder for constructing LLM prompts."""

from dsar_query_generator.models.schema import SchemaRegistry

SYSTEM_PROMPT_TEMPLATE = """You are a SQL query generator for Data Subject Access Requests (DSAR).

## Your Role
Generate SQL queries that retrieve a user's personal data based on natural language requests.

## Constraints - YOU MUST FOLLOW THESE STRICTLY
1. ONLY generate SELECT queries - never INSERT, UPDATE, DELETE, DROP, or any other statement type
2. ALWAYS use parameterized queries with $1, $2, $3, etc. as placeholders - NEVER include literal values
3. The first parameter ($1) is ALWAYS the user_id being queried
4. NEVER expose columns that are not in the allowed schema below
5. ONLY query tables listed in the schema below
6. Maximum of {max_tables} tables per query

## Available Schema
{schema_description}

## Output Format
Respond with a JSON object containing:
{{
    "sql": "SELECT ... FROM ... WHERE user_id = $1 ...",
    "params": ["<user_id>", "<any other param values>"],
    "tables_accessed": ["table1", "table2"],
    "columns_returned": ["col1", "col2"],
    "confidence": "high" | "medium" | "low"
}}

## Confidence Levels
- "high": Clear intent, exact table match, simple query structure
- "medium": Some inference required, multiple interpretations possible
- "low": Unusual request, complex joins, edge cases

## Special Cases
- If the request is ambiguous, set confidence to "low" and include your best interpretation
- If the request asks for data from multiple unrelated tables, generate separate queries in a "queries" array
- If the request is about data deletion, modification, or anything other than data access, respond with:
  {{"out_of_scope": true, "reason": "This system only handles data access requests"}}
- If you cannot understand the request, respond with:
  {{"clarification_needed": true, "message": "...", "suggestions": ["option1", "option2"]}}

Remember: The generated query will be reviewed by a human before execution. Prioritize safety and accuracy."""

USER_PROMPT_TEMPLATE = """Generate a SQL query for the following DSAR request:

User ID: {user_id}
Request: {natural_language_request}

Respond only with the JSON object, no additional text."""


class PromptBuilder:
    """Builds prompts for LLM query generation."""

    def __init__(self, schema_registry: SchemaRegistry, max_tables: int = 5) -> None:
        """Initialize prompt builder.

        Args:
            schema_registry: Schema registry containing allowed tables/columns.
            max_tables: Maximum number of tables allowed per query.
        """
        self._schema = schema_registry
        self._max_tables = max_tables

    def build_system_prompt(self) -> str:
        """Build the system prompt with schema information."""
        schema_description = self._schema.get_schema_description()
        return SYSTEM_PROMPT_TEMPLATE.format(
            schema_description=schema_description,
            max_tables=self._max_tables,
        )

    def build_user_prompt(self, user_id: str, natural_language_request: str) -> str:
        """Build the user prompt with the specific request.

        Args:
            user_id: ID of the user whose data is being requested.
            natural_language_request: Natural language description of the data request.

        Returns:
            Formatted user prompt string.
        """
        return USER_PROMPT_TEMPLATE.format(
            user_id=user_id,
            natural_language_request=natural_language_request,
        )

    def build_messages(
        self, user_id: str, natural_language_request: str
    ) -> list[dict[str, str]]:
        """Build complete message list for LLM API call.

        Args:
            user_id: ID of the user whose data is being requested.
            natural_language_request: Natural language description of the data request.

        Returns:
            List of message dicts with 'role' and 'content' keys.
        """
        return [
            {"role": "system", "content": self.build_system_prompt()},
            {
                "role": "user",
                "content": self.build_user_prompt(user_id, natural_language_request),
            },
        ]
