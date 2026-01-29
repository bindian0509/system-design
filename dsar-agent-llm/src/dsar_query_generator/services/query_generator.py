"""Query generator service that orchestrates LLM query generation."""

import structlog

from dsar_query_generator.config.settings import Settings, get_settings
from dsar_query_generator.models.llm import (
    LLMClarificationResponse,
    LLMGeneratedQuery,
    LLMMultiQueryResponse,
    LLMOutOfScopeResponse,
    LLMResponse,
)
from dsar_query_generator.models.schema import SchemaRegistry
from dsar_query_generator.services.llm_client import (
    BaseLLMClient,
    LLMError,
    create_llm_client,
    parse_llm_json_response,
)
from dsar_query_generator.services.prompt_builder import PromptBuilder

logger = structlog.get_logger()


class QueryGeneratorError(Exception):
    """Base exception for query generator errors."""

    pass


class QueryGenerator:
    """Generates SQL queries from natural language using LLM."""

    def __init__(
        self,
        schema_registry: SchemaRegistry,
        llm_client: BaseLLMClient | None = None,
        settings: Settings | None = None,
    ):
        """Initialize query generator.

        Args:
            schema_registry: Schema registry with allowed tables/columns.
            llm_client: LLM client instance. If None, creates one from settings.
            settings: Application settings. If None, loads from environment.
        """
        self._settings = settings or get_settings()
        self._schema = schema_registry
        self._llm_client = llm_client or create_llm_client(self._settings)
        self._prompt_builder = PromptBuilder(
            schema_registry=schema_registry,
            max_tables=self._settings.max_tables_per_query,
        )

    @property
    def model_version(self) -> str:
        """Return the LLM model version being used."""
        return self._llm_client.model_version

    async def generate(
        self,
        user_id: str,
        natural_language_request: str,
    ) -> LLMResponse:
        """Generate SQL query from natural language request.

        Args:
            user_id: ID of the user whose data is being requested.
            natural_language_request: Natural language description of the request.

        Returns:
            LLMResponse containing generated query, clarification request,
            or out-of-scope indication.

        Raises:
            QueryGeneratorError: If generation fails.
        """
        log = logger.bind(
            user_id=user_id,
            request_preview=natural_language_request[:100],
        )

        # Build messages for LLM
        messages = self._prompt_builder.build_messages(
            user_id=user_id,
            natural_language_request=natural_language_request,
        )

        log.debug("calling_llm", model=self._llm_client.model_version)

        try:
            raw_response = await self._llm_client.complete(
                messages=messages,
                temperature=self._settings.llm_temperature,
            )
        except LLMError as e:
            log.error("llm_call_failed", error=str(e))
            raise QueryGeneratorError(f"LLM call failed: {e}") from e

        # Parse JSON response
        try:
            parsed = parse_llm_json_response(raw_response)
        except Exception as e:
            log.error("llm_parse_failed", error=str(e), raw_response=raw_response[:500])
            raise QueryGeneratorError(f"Failed to parse LLM response: {e}") from e

        # Determine response type and parse accordingly
        return self._parse_response(parsed, log)

    def _parse_response(
        self,
        parsed: dict,
        log: structlog.stdlib.BoundLogger,
    ) -> LLMResponse:
        """Parse the LLM response dict into appropriate response type."""
        # Check for clarification needed
        if parsed.get("clarification_needed"):
            log.info("clarification_needed", message=parsed.get("message"))
            return LLMClarificationResponse(
                clarification_needed=True,
                message=parsed.get("message", "Please clarify your request"),
                suggestions=parsed.get("suggestions", []),
            )

        # Check for out of scope
        if parsed.get("out_of_scope"):
            log.info("out_of_scope", reason=parsed.get("reason"))
            return LLMOutOfScopeResponse(
                out_of_scope=True,
                reason=parsed.get("reason", "Request is out of scope"),
            )

        # Check for multiple queries
        if "queries" in parsed:
            log.info("multi_query_response", query_count=len(parsed["queries"]))
            queries = [
                LLMGeneratedQuery(
                    sql=q["sql"],
                    params=q.get("params", []),
                    tables_accessed=q.get("tables_accessed", []),
                    columns_returned=q.get("columns_returned", []),
                    confidence=q.get("confidence", "medium"),
                )
                for q in parsed["queries"]
            ]
            return LLMMultiQueryResponse(
                queries=queries,
                note=parsed.get("note"),
            )

        # Single query response
        log.info(
            "query_generated",
            tables=parsed.get("tables_accessed", []),
            confidence=parsed.get("confidence", "medium"),
        )
        return LLMGeneratedQuery(
            sql=parsed["sql"],
            params=parsed.get("params", []),
            tables_accessed=parsed.get("tables_accessed", []),
            columns_returned=parsed.get("columns_returned", []),
            confidence=parsed.get("confidence", "medium"),
        )

    async def generate_with_refinement(
        self,
        user_id: str,
        natural_language_request: str,
        validation_errors: list[str],
        previous_sql: str,
        max_retries: int = 2,
    ) -> LLMResponse:
        """Generate SQL with refinement based on validation errors.

        This method is called when a previous generation attempt failed
        validation. It includes the errors in the prompt to help the LLM
        correct its output.

        Args:
            user_id: ID of the user whose data is being requested.
            natural_language_request: Original natural language request.
            validation_errors: List of validation errors from previous attempt.
            previous_sql: The SQL that failed validation.
            max_retries: Maximum number of refinement attempts.

        Returns:
            LLMResponse containing refined query.
        """
        log = logger.bind(
            user_id=user_id,
            validation_errors=validation_errors,
        )

        # Build base messages
        messages = self._prompt_builder.build_messages(
            user_id=user_id,
            natural_language_request=natural_language_request,
        )

        # Add the failed attempt and error context
        refinement_prompt = self._build_refinement_prompt(
            previous_sql=previous_sql,
            validation_errors=validation_errors,
        )

        messages.append({"role": "assistant", "content": f'{{"sql": "{previous_sql}"}}'})
        messages.append({"role": "user", "content": refinement_prompt})

        log.debug("calling_llm_for_refinement", model=self._llm_client.model_version)

        try:
            raw_response = await self._llm_client.complete(
                messages=messages,
                temperature=self._settings.llm_temperature,
            )
        except LLMError as e:
            log.error("llm_refinement_failed", error=str(e))
            raise QueryGeneratorError(f"LLM refinement call failed: {e}") from e

        parsed = parse_llm_json_response(raw_response)
        return self._parse_response(parsed, log)

    def _build_refinement_prompt(
        self,
        previous_sql: str,
        validation_errors: list[str],
    ) -> str:
        """Build a refinement prompt based on validation errors."""
        error_list = "\n".join(f"- {error}" for error in validation_errors)

        return f"""Your previous query failed validation with the following errors:

{error_list}

Please fix these issues and generate a corrected query. Remember:
- Only use tables and columns from the allowed schema
- Use parameterized queries ($1, $2, etc.)
- Only generate SELECT statements

Provide the corrected query in the same JSON format."""
