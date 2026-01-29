"""Tests for rate limiting."""

import time

import pytest

from dsar_query_generator.api.rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for the rate limiter."""

    def test_first_request_is_allowed(self):
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        result = limiter.check("agent-001")

        assert result.allowed is True
        assert result.remaining == 9
        assert result.limit == 10

    def test_requests_within_limit_are_allowed(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        for i in range(5):
            result = limiter.check("agent-001")
            assert result.allowed is True
            assert result.remaining == 4 - i

    def test_request_exceeding_limit_is_denied(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        # Make 3 requests (should all pass)
        for _ in range(3):
            result = limiter.check("agent-001")
            assert result.allowed is True

        # 4th request should be denied
        result = limiter.check("agent-001")
        assert result.allowed is False
        assert result.remaining == 0

    def test_different_agents_have_separate_limits(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # Agent 1 uses their limit
        limiter.check("agent-001")
        limiter.check("agent-001")
        result = limiter.check("agent-001")
        assert result.allowed is False

        # Agent 2 should still have their limit
        result = limiter.check("agent-002")
        assert result.allowed is True
        assert result.remaining == 1

    def test_window_expiration_resets_limit(self):
        # Use a very short window for testing
        limiter = RateLimiter(max_requests=2, window_seconds=1)

        # Use up the limit
        limiter.check("agent-001")
        limiter.check("agent-001")
        result = limiter.check("agent-001")
        assert result.allowed is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        result = limiter.check("agent-001")
        assert result.allowed is True

    def test_reset_clears_agent_limit(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # Use up the limit
        limiter.check("agent-001")
        limiter.check("agent-001")
        result = limiter.check("agent-001")
        assert result.allowed is False

        # Reset
        limiter.reset("agent-001")

        # Should be allowed again
        result = limiter.check("agent-001")
        assert result.allowed is True
        assert result.remaining == 1

    def test_reset_at_is_in_future(self):
        limiter = RateLimiter(max_requests=10, window_seconds=3600)

        result = limiter.check("agent-001")

        assert result.reset_at > time.time()
        assert result.reset_at <= time.time() + 3600

    def test_remaining_decrements_correctly(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        for expected_remaining in [4, 3, 2, 1, 0]:
            result = limiter.check("agent-001")
            assert result.remaining == expected_remaining

    def test_window_seconds_is_returned(self):
        limiter = RateLimiter(max_requests=10, window_seconds=7200)

        result = limiter.check("agent-001")

        assert result.window_seconds == 7200
