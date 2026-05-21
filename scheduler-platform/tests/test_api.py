"""
Basic unit tests for API routes.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "scheduler-platform"
    assert "version" in data


def test_create_job_unauthorized(client):
    """Test creating job without authorization."""
    response = client.post(
        "/api/v1/jobs",
        json={
            "name": "test-job",
            "team_id": "team-001",
            "payload": {"data": "test"},
        }
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@patch('api.routes_jobs.get_user_info')
@patch('api.routes_jobs.get_db')
def test_create_job_with_auth(mock_db, mock_user_info, client):
    """Test creating job with valid authorization."""
    # Mock user info
    mock_user_info.return_value = {
        "user_id": "user-001",
        "teams": ["team-001"],
        "roles": {"team-001": "admin"}
    }

    # Mock database
    mock_session = MagicMock()
    mock_db.return_value = mock_session

    # This test would need proper mocking setup
    # In production, use fixtures to set up test database
    pass
