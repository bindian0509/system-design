"""Integration tests for API endpoints."""

import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from dsar_query_generator.api.auth import create_token
from dsar_query_generator.config.settings import Settings
from dsar_query_generator.main import app
from dsar_query_generator.models.llm import LLMGeneratedQuery

# Set a fake API key for tests that need to instantiate the LLM client
os.environ.setdefault("DSAR_OPENAI_API_KEY", "test-api-key-for-testing")


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_health_endpoint_returns_healthy(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_ready_endpoint_returns_ready(self, client: TestClient):
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["ready", "not_ready"]


class TestAuthenticationIntegration:
    """Tests for authentication on API endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(
            jwt_secret_key="dev-secret-key-change-in-production",
            jwt_algorithm="HS256",
        )

    @pytest.fixture
    def valid_token(self, settings: Settings) -> str:
        return create_token(
            agent_id="test-agent",
            email="test@example.com",
            roles=["dsar:read"],
            settings=settings,
        )

    def test_generate_query_without_auth_returns_401(self, client: TestClient):
        response = client.post(
            "/api/v1/dsar/generate-query",
            json={
                "request_id": "test-001",
                "user_id": "user123",
                "natural_language_request": "Show me my payments",
                "requester_email": "agent@example.com",
            },
        )
        # Should get 401 or 403 for missing auth
        assert response.status_code in [401, 403]

    def test_generate_query_with_invalid_token_returns_401(self, client: TestClient):
        response = client.post(
            "/api/v1/dsar/generate-query",
            headers={"Authorization": "Bearer invalid-token"},
            json={
                "request_id": "test-001",
                "user_id": "user123",
                "natural_language_request": "Show me my payments",
                "requester_email": "agent@example.com",
            },
        )
        assert response.status_code == 401

    def test_schema_endpoint_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/v1/dsar/schema")
        assert response.status_code in [401, 403]


class TestGenerateQueryEndpoint:
    """Tests for the generate-query endpoint with mocked LLM."""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(
            jwt_secret_key="dev-secret-key-change-in-production",
            jwt_algorithm="HS256",
        )

    @pytest.fixture
    def auth_headers(self, settings: Settings) -> dict[str, str]:
        token = create_token(
            agent_id="test-agent",
            email="test@example.com",
            roles=["dsar:read"],
            settings=settings,
        )
        return {"Authorization": f"Bearer {token}"}

    def test_invalid_request_body_returns_422(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/api/v1/dsar/generate-query",
            headers=auth_headers,
            json={
                "request_id": "test-001",
                # Missing required fields
            },
        )
        assert response.status_code == 422

    def test_invalid_email_returns_422(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/api/v1/dsar/generate-query",
            headers=auth_headers,
            json={
                "request_id": "test-001",
                "user_id": "user123",
                "natural_language_request": "Show me my payments",
                "requester_email": "not-an-email",
            },
        )
        assert response.status_code == 422


class TestSchemaEndpoint:
    """Tests for the schema endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(
            jwt_secret_key="dev-secret-key-change-in-production",
            jwt_algorithm="HS256",
        )

    @pytest.fixture
    def auth_headers(self, settings: Settings) -> dict[str, str]:
        token = create_token(
            agent_id="test-agent",
            email="test@example.com",
            roles=["dsar:read"],
            settings=settings,
        )
        return {"Authorization": f"Bearer {token}"}

    def test_schema_endpoint_returns_tables(self, client: TestClient, auth_headers: dict):
        response = client.get(
            "/api/v1/dsar/schema",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "tables" in data
        # Should have some tables
        assert len(data["tables"]) > 0

    def test_schema_endpoint_includes_column_info(self, client: TestClient, auth_headers: dict):
        response = client.get(
            "/api/v1/dsar/schema",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Each table should have columns and description
        for table_name, table_info in data["tables"].items():
            assert "columns" in table_info
            assert "description" in table_info
            assert isinstance(table_info["columns"], list)
