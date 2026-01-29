"""Tests for authentication."""

from datetime import datetime, timedelta, timezone

import pytest

from dsar_query_generator.api.auth import AuthError, create_token, decode_token
from dsar_query_generator.config.settings import Settings


class TestAuthentication:
    """Tests for JWT authentication."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create test settings."""
        return Settings(
            jwt_secret_key="test-secret-key",
            jwt_algorithm="HS256",
            jwt_expire_minutes=60,
        )

    def test_create_token_generates_valid_token(self, settings: Settings):
        token = create_token(
            agent_id="agent-001",
            email="agent@example.com",
            roles=["dsar:read"],
            settings=settings,
        )

        assert token is not None
        assert len(token) > 0
        # JWT tokens have 3 parts separated by dots
        assert token.count(".") == 2

    def test_decode_token_extracts_claims(self, settings: Settings):
        token = create_token(
            agent_id="agent-001",
            email="agent@example.com",
            roles=["dsar:read", "dsar:admin"],
            settings=settings,
        )

        claims = decode_token(token, settings)

        assert claims.agent_id == "agent-001"
        assert claims.email == "agent@example.com"
        assert claims.roles == ["dsar:read", "dsar:admin"]
        assert claims.exp > datetime.now(timezone.utc)

    def test_decode_token_with_invalid_token_raises_error(self, settings: Settings):
        with pytest.raises(AuthError):
            decode_token("invalid.token.here", settings)

    def test_decode_token_with_wrong_secret_raises_error(self, settings: Settings):
        token = create_token(
            agent_id="agent-001",
            email="agent@example.com",
            roles=["dsar:read"],
            settings=settings,
        )

        # Create settings with different secret
        wrong_settings = Settings(
            jwt_secret_key="different-secret-key",
            jwt_algorithm="HS256",
        )

        with pytest.raises(AuthError):
            decode_token(token, wrong_settings)

    def test_token_expiration_is_set_correctly(self, settings: Settings):
        token = create_token(
            agent_id="agent-001",
            email="agent@example.com",
            roles=["dsar:read"],
            settings=settings,
            expires_delta_minutes=30,
        )

        claims = decode_token(token, settings)

        # Should expire in approximately 30 minutes
        expected_exp = datetime.now(timezone.utc) + timedelta(minutes=30)
        assert abs((claims.exp - expected_exp).total_seconds()) < 5

    def test_create_token_with_empty_roles(self, settings: Settings):
        token = create_token(
            agent_id="agent-001",
            email="agent@example.com",
            roles=[],
            settings=settings,
        )

        claims = decode_token(token, settings)
        assert claims.roles == []

    def test_decode_malformed_token_raises_error(self, settings: Settings):
        with pytest.raises(AuthError):
            decode_token("not-a-jwt", settings)

    def test_decode_empty_token_raises_error(self, settings: Settings):
        with pytest.raises(AuthError):
            decode_token("", settings)
