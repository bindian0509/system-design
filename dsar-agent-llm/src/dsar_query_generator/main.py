"""FastAPI application entry point."""

import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from dsar_query_generator.api.exceptions import register_exception_handlers
from dsar_query_generator.api.routes import router
from dsar_query_generator.config.settings import get_settings

settings = get_settings()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to add request context for logging."""

    async def dispatch(self, request: Request, call_next):
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind request context to logger
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )

        # Store request ID in request state for later use
        request.state.request_id = request_id

        # Log request start
        logger.info("request_started")

        try:
            response = await call_next(request)

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Log request completion
            logger.info(
                "request_completed",
                status_code=response.status_code,
            )

            return response
        except Exception as e:
            logger.exception("request_failed", error=str(e))
            raise


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="LLM-powered DSAR SQL Query Generator",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request context middleware
app.add_middleware(RequestContextMiddleware)

# Register exception handlers
register_exception_handlers(app)

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness check endpoint.

    Verifies that all dependencies are available.
    """
    # Check schema registry is loadable
    try:
        from dsar_query_generator.services.schema_registry import get_schema_registry_service
        schema_service = get_schema_registry_service()
        _ = schema_service.registry
    except Exception as e:
        logger.error("readiness_check_failed", error=str(e))
        return {"status": "not_ready", "error": "Schema registry not available"}

    return {"status": "ready"}


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(
        "application_starting",
        title=settings.api_title,
        version=settings.api_version,
        llm_provider=settings.llm_provider,
    )

    # Pre-load schema registry
    from dsar_query_generator.services.schema_registry import get_schema_registry_service
    try:
        schema_service = get_schema_registry_service()
        schema = schema_service.registry
        logger.info(
            "schema_loaded",
            tables=list(schema.tables.keys()),
            blocked_tables=schema.blocked_tables,
        )
    except Exception as e:
        logger.error("schema_load_failed", error=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("application_shutting_down")
