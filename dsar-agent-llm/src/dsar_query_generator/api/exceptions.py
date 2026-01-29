"""Custom exceptions and error handlers for the API."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from dsar_query_generator.services.llm_client import LLMError, LLMProviderError, LLMTimeoutError
from dsar_query_generator.services.query_generator import QueryGeneratorError
from dsar_query_generator.services.sql_validator import SQLValidationError


class DSARError(Exception):
    """Base exception for DSAR errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "dsar_error",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class AmbiguousRequestError(DSARError):
    """Request is ambiguous and needs clarification."""

    def __init__(self, message: str, suggestions: list[str] | None = None):
        super().__init__(
            message=message,
            error_code="ambiguous_request",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"suggestions": suggestions or []},
        )
        self.suggestions = suggestions or []


class OutOfScopeError(DSARError):
    """Request is outside the scope of the system."""

    def __init__(self, message: str, detected_intent: str, escalation_path: str):
        super().__init__(
            message=message,
            error_code="out_of_scope",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "detected_intent": detected_intent,
                "escalation_path": escalation_path,
            },
        )
        self.detected_intent = detected_intent
        self.escalation_path = escalation_path


class ValidationFailedError(DSARError):
    """Generated query failed validation."""

    def __init__(self, message: str, validation_errors: list[str], attempts: int = 1):
        super().__init__(
            message=message,
            error_code="validation_failed",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={
                "validation_errors": validation_errors,
                "attempts": attempts,
            },
        )
        self.validation_errors = validation_errors
        self.attempts = attempts


class ServiceUnavailableError(DSARError):
    """Service is temporarily unavailable."""

    def __init__(self, message: str, retry_after_seconds: int = 60):
        super().__init__(
            message=message,
            error_code="service_unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"retry_after_seconds": retry_after_seconds},
        )
        self.retry_after_seconds = retry_after_seconds


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers with the FastAPI app."""

    @app.exception_handler(DSARError)
    async def dsar_error_handler(request: Request, exc: DSARError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                **exc.details,
            },
        )

    @app.exception_handler(LLMTimeoutError)
    async def llm_timeout_handler(request: Request, exc: LLMTimeoutError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={
                "error": "llm_timeout",
                "message": "The AI service took too long to respond. Please try again.",
                "timeout_seconds": exc.timeout_seconds,
            },
        )

    @app.exception_handler(LLMProviderError)
    async def llm_provider_handler(request: Request, exc: LLMProviderError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "llm_provider_error",
                "message": "The AI service is temporarily unavailable. Please try again.",
            },
        )

    @app.exception_handler(LLMError)
    async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "llm_error",
                "message": "An error occurred while generating the query. Please try again.",
            },
        )

    @app.exception_handler(QueryGeneratorError)
    async def query_generator_handler(request: Request, exc: QueryGeneratorError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "generation_error",
                "message": "Failed to generate query. Please try again or rephrase your request.",
            },
        )

    @app.exception_handler(SQLValidationError)
    async def validation_handler(request: Request, exc: SQLValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "validation_error",
                "message": "The generated query failed security validation.",
                "validation_errors": exc.errors,
            },
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_handler(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors.append({
                "field": field,
                "message": error["msg"],
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "validation_error",
                "message": "Request validation failed",
                "errors": errors,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log the actual exception for debugging
        import structlog
        logger = structlog.get_logger()
        logger.exception("unhandled_exception", error=str(exc))

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred. Please try again.",
            },
        )
