"""Pytest configuration and fixtures."""

import os
from pathlib import Path
from typing import AsyncGenerator

# Set test environment variables before any imports that use settings
os.environ["DSAR_OPENAI_API_KEY"] = "test-api-key-for-testing"
os.environ["DSAR_JWT_SECRET_KEY"] = "dev-secret-key-change-in-production"

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from dsar_query_generator.api.auth import create_token
from dsar_query_generator.config.settings import Settings, get_settings
from dsar_query_generator.main import app
from dsar_query_generator.models.schema import SchemaRegistry, TableSchema

# Clear cached settings to pick up test environment
get_settings.cache_clear()


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        jwt_secret_key="test-secret-key-for-testing-only",
        jwt_algorithm="HS256",
        jwt_expire_minutes=60,
        rate_limit_requests=1000,
        rate_limit_window_seconds=3600,
        llm_provider="openai",
        openai_api_key="test-api-key",
        max_tables_per_query=5,
        schema_registry_path=Path("config/schema_registry.yaml"),
        audit_log_path=Path("/tmp/test_audit.jsonl"),
    )


@pytest.fixture
def test_schema_registry() -> SchemaRegistry:
    """Create a test schema registry."""
    return SchemaRegistry(
        tables={
            "users": TableSchema(
                description="User profile information",
                allowed_columns=["id", "email", "name", "phone", "created_at"],
                excluded_columns=["password_hash", "internal_flags"],
            ),
            "trips": TableSchema(
                description="Trip history",
                allowed_columns=["id", "user_id", "origin", "destination", "fare", "started_at"],
                excluded_columns=["internal_score", "fraud_flags"],
            ),
            "payments": TableSchema(
                description="Payment transaction records",
                allowed_columns=["id", "user_id", "amount", "currency", "created_at", "status"],
                excluded_columns=["payment_token", "card_fingerprint"],
            ),
            "ratings": TableSchema(
                description="User ratings and reviews",
                allowed_columns=["id", "user_id", "trip_id", "score", "comment", "created_at"],
                excluded_columns=["internal_review_flags"],
            ),
        },
        blocked_tables=["audit_logs", "security_events", "employee_data"],
    )


@pytest.fixture
def auth_token(test_settings: Settings) -> str:
    """Create a valid JWT token for testing."""
    return create_token(
        agent_id="test-agent-001",
        email="test-agent@company.com",
        roles=["dsar:read"],
        settings=test_settings,
    )


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """Create authorization headers for testing."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def test_client() -> TestClient:
    """Create a test client for synchronous testing."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
