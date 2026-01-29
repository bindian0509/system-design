"""API routes for DSAR Query Generator."""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from dsar_query_generator.api.auth import AgentClaims, get_current_agent
from dsar_query_generator.api.rate_limiter import RateLimitInfo, check_rate_limit
from dsar_query_generator.config.settings import Settings, get_settings
from dsar_query_generator.models.llm import (
    LLMClarificationResponse,
    LLMGeneratedQuery,
    LLMMultiQueryResponse,
    LLMOutOfScopeResponse,
)
from dsar_query_generator.models.requests import (
    ClarificationResponse,
    DSARRequest,
    DSARResponse,
    ErrorResponse,
    GeneratedQuery,
    OutOfScopeResponse,
)
from dsar_query_generator.services.audit_logger import get_audit_logger
from dsar_query_generator.services.query_generator import QueryGenerator, QueryGeneratorError
from dsar_query_generator.services.schema_registry import get_schema_registry_service
from dsar_query_generator.services.sql_validator import SQLValidator, ValidationResult

logger = structlog.get_logger()

router = APIRouter()


def get_query_generator() -> QueryGenerator:
    """Dependency to get query generator instance."""
    schema_service = get_schema_registry_service()
    return QueryGenerator(schema_registry=schema_service.registry)


def get_sql_validator() -> SQLValidator:
    """Dependency to get SQL validator instance."""
    schema_service = get_schema_registry_service()
    settings = get_settings()
    return SQLValidator(
        schema_registry=schema_service.registry,
        max_tables=settings.max_tables_per_query,
    )


@router.post(
    "/dsar/generate-query",
    response_model=DSARResponse | ClarificationResponse | OutOfScopeResponse,
    responses={
        200: {"description": "Query generated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Generate SQL query from natural language DSAR request",
    description="""
    Converts a natural language Data Subject Access Request (DSAR) into a
    parameterized SQL query. The generated query is validated against security
    constraints and logged for audit purposes.

    The response includes:
    - The generated SQL query with parameter placeholders ($1, $2, etc.)
    - Parameter values to bind
    - Tables and columns accessed
    - Confidence level (high/medium/low)
    - Any warnings about the generated query
    """,
)
async def generate_query(
    request: DSARRequest,
    agent: Annotated[AgentClaims, Depends(get_current_agent)],
    rate_limit: Annotated[RateLimitInfo, Depends(check_rate_limit)],
    generator: Annotated[QueryGenerator, Depends(get_query_generator)],
    validator: Annotated[SQLValidator, Depends(get_sql_validator)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DSARResponse | ClarificationResponse | OutOfScopeResponse:
    """Generate a SQL query from a natural language DSAR request."""
    log = logger.bind(
        request_id=request.request_id,
        agent_id=agent.agent_id,
        user_id=request.user_id,
    )

    audit_logger = get_audit_logger()

    log.info("processing_dsar_request")

    try:
        # Generate query using LLM
        llm_response = await generator.generate(
            user_id=request.user_id,
            natural_language_request=request.natural_language_request,
        )

        # Handle clarification needed
        if isinstance(llm_response, LLMClarificationResponse):
            log.info("clarification_needed", message=llm_response.message)
            await audit_logger.log_request(
                request_id=request.request_id,
                agent_id=agent.agent_id,
                agent_email=agent.email,
                subject_user_id=request.user_id,
                original_request=request.natural_language_request,
                response_status="clarification_needed",
                model_version=generator.model_version,
            )
            return ClarificationResponse(
                message=llm_response.message,
                suggestions=llm_response.suggestions,
            )

        # Handle out of scope
        if isinstance(llm_response, LLMOutOfScopeResponse):
            log.info("out_of_scope", reason=llm_response.reason)
            await audit_logger.log_request(
                request_id=request.request_id,
                agent_id=agent.agent_id,
                agent_email=agent.email,
                subject_user_id=request.user_id,
                original_request=request.natural_language_request,
                response_status="out_of_scope",
                model_version=generator.model_version,
            )
            return OutOfScopeResponse(
                message=llm_response.reason,
                escalation_path="DSAR-DELETION-QUEUE",
            )

        # Handle multi-query response
        if isinstance(llm_response, LLMMultiQueryResponse):
            return await _handle_multi_query(
                request=request,
                agent=agent,
                llm_response=llm_response,
                generator=generator,
                validator=validator,
                audit_logger=audit_logger,
                log=log,
                settings=settings,
            )

        # Handle single query response
        return await _handle_single_query(
            request=request,
            agent=agent,
            llm_response=llm_response,
            generator=generator,
            validator=validator,
            audit_logger=audit_logger,
            log=log,
            settings=settings,
        )

    except QueryGeneratorError as e:
        log.error("query_generation_failed", error=str(e))
        await audit_logger.log_request(
            request_id=request.request_id,
            agent_id=agent.agent_id,
            agent_email=agent.email,
            subject_user_id=request.user_id,
            original_request=request.natural_language_request,
            response_status="error",
            error_message=str(e),
            model_version=generator.model_version,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query generation failed. Please try again.",
        )


async def _handle_single_query(
    request: DSARRequest,
    agent: AgentClaims,
    llm_response: LLMGeneratedQuery,
    generator: QueryGenerator,
    validator: SQLValidator,
    audit_logger,
    log,
    settings: Settings,
) -> DSARResponse:
    """Handle a single query response from LLM."""
    max_retries = 2
    current_response = llm_response
    all_validation_errors: list[str] = []

    for attempt in range(max_retries + 1):
        # Validate the generated query
        validation = validator.validate(current_response)

        if validation.valid:
            # Success - log and return
            log.info(
                "query_validated",
                tables=current_response.tables_accessed,
                confidence=current_response.confidence,
            )

            await audit_logger.log_request(
                request_id=request.request_id,
                agent_id=agent.agent_id,
                agent_email=agent.email,
                subject_user_id=request.user_id,
                original_request=request.natural_language_request,
                generated_sql=current_response.sql,
                params=current_response.params,
                tables_accessed=current_response.tables_accessed,
                columns_returned=current_response.columns_returned,
                confidence=current_response.confidence,
                model_version=generator.model_version,
                validation_passed=True,
                response_status="success",
            )

            return DSARResponse(
                request_id=request.request_id,
                generated_query=GeneratedQuery(
                    sql=current_response.sql,
                    params=current_response.params,
                    tables_accessed=current_response.tables_accessed,
                    columns_returned=current_response.columns_returned,
                ),
                confidence=current_response.confidence,
                requires_review=True,
                warnings=validation.warnings,
            )

        # Validation failed
        all_validation_errors.extend(validation.errors)
        log.warning(
            "validation_failed",
            attempt=attempt + 1,
            errors=validation.errors,
        )

        if attempt < max_retries:
            # Try refinement
            refined = await generator.generate_with_refinement(
                user_id=request.user_id,
                natural_language_request=request.natural_language_request,
                validation_errors=validation.errors,
                previous_sql=current_response.sql,
            )

            if isinstance(refined, LLMGeneratedQuery):
                current_response = refined
            else:
                # Refinement returned non-query response, break
                break

    # Max retries exceeded
    log.error(
        "validation_failed_after_retries",
        errors=all_validation_errors,
    )

    await audit_logger.log_request(
        request_id=request.request_id,
        agent_id=agent.agent_id,
        agent_email=agent.email,
        subject_user_id=request.user_id,
        original_request=request.natural_language_request,
        generated_sql=current_response.sql,
        validation_passed=False,
        validation_errors=all_validation_errors,
        model_version=generator.model_version,
        response_status="validation_failed",
    )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": "validation_failed",
            "message": "Could not generate a valid query after multiple attempts",
            "validation_errors": list(set(all_validation_errors)),
        },
    )


async def _handle_multi_query(
    request: DSARRequest,
    agent: AgentClaims,
    llm_response: LLMMultiQueryResponse,
    generator: QueryGenerator,
    validator: SQLValidator,
    audit_logger,
    log,
    settings: Settings,
) -> DSARResponse:
    """Handle a multi-query response from LLM."""
    validated_queries: list[GeneratedQuery] = []
    all_tables: list[str] = []
    all_warnings: list[str] = []
    overall_confidence = "high"

    for i, query in enumerate(llm_response.queries):
        validation = validator.validate(query)

        if not validation.valid:
            log.warning(
                "multi_query_validation_failed",
                query_index=i,
                errors=validation.errors,
            )
            # For multi-query, we skip invalid queries but continue
            all_warnings.append(f"Query {i+1} failed validation: {validation.errors}")
            continue

        validated_queries.append(
            GeneratedQuery(
                sql=query.sql,
                params=query.params,
                tables_accessed=query.tables_accessed,
                columns_returned=query.columns_returned,
            )
        )
        all_tables.extend(query.tables_accessed)
        all_warnings.extend(validation.warnings)

        # Downgrade confidence if any query is lower
        if query.confidence == "low":
            overall_confidence = "low"
        elif query.confidence == "medium" and overall_confidence == "high":
            overall_confidence = "medium"

    if not validated_queries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation_failed",
                "message": "All generated queries failed validation",
                "warnings": all_warnings,
            },
        )

    # Log the successful multi-query response
    await audit_logger.log_request(
        request_id=request.request_id,
        agent_id=agent.agent_id,
        agent_email=agent.email,
        subject_user_id=request.user_id,
        original_request=request.natural_language_request,
        generated_sql="; ".join(q.sql for q in validated_queries),
        tables_accessed=list(set(all_tables)),
        confidence=overall_confidence,
        model_version=generator.model_version,
        validation_passed=True,
        response_status="success",
    )

    return DSARResponse(
        request_id=request.request_id,
        generated_queries=validated_queries,
        confidence=overall_confidence,
        requires_review=True,
        warnings=all_warnings,
        note=llm_response.note or "Multiple queries generated - results should be assembled by reviewer",
    )


@router.get(
    "/dsar/schema",
    summary="Get available schema for DSAR queries",
    description="Returns the list of tables and columns available for DSAR queries.",
)
async def get_schema(
    agent: Annotated[AgentClaims, Depends(get_current_agent)],
) -> dict:
    """Get the schema available for DSAR queries."""
    schema_service = get_schema_registry_service()
    registry = schema_service.registry

    tables = {}
    for table_name, table_schema in registry.tables.items():
        if table_name not in registry.blocked_tables:
            tables[table_name] = {
                "description": table_schema.description,
                "columns": table_schema.allowed_columns,
            }

    return {"tables": tables}
