"""Rate limiting for the API."""

import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock

from fastapi import Depends, HTTPException, status

from dsar_query_generator.api.auth import AgentClaims, get_current_agent
from dsar_query_generator.config.settings import Settings, get_settings


@dataclass
class RateLimitInfo:
    """Information about rate limit status."""

    allowed: bool
    remaining: int
    reset_at: float
    limit: int
    window_seconds: int


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, limit: int, retry_after: int):
        self.limit = limit
        self.retry_after = retry_after
        super().__init__(f"Rate limit of {limit} requests exceeded. Retry after {retry_after}s")


class RateLimiter:
    """In-memory rate limiter using sliding window."""

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 3600,
    ):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed per window.
            window_seconds: Window size in seconds.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> RateLimitInfo:
        """Check if a request is allowed and record it.

        Args:
            key: Identifier for the rate limit bucket (e.g., agent_id).

        Returns:
            RateLimitInfo with limit status.
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # Clean old entries
            self._requests[key] = [
                t for t in self._requests[key] if t > window_start
            ]

            current_count = len(self._requests[key])

            if current_count >= self.max_requests:
                # Calculate when the oldest request will expire
                oldest = min(self._requests[key]) if self._requests[key] else now
                reset_at = oldest + self.window_seconds
                return RateLimitInfo(
                    allowed=False,
                    remaining=0,
                    reset_at=reset_at,
                    limit=self.max_requests,
                    window_seconds=self.window_seconds,
                )

            # Record this request
            self._requests[key].append(now)

            return RateLimitInfo(
                allowed=True,
                remaining=self.max_requests - current_count - 1,
                reset_at=now + self.window_seconds,
                limit=self.max_requests,
                window_seconds=self.window_seconds,
            )

    def reset(self, key: str) -> None:
        """Reset rate limit for a key (for testing)."""
        with self._lock:
            if key in self._requests:
                del self._requests[key]


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter(settings: Settings | None = None) -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        if settings is None:
            settings = get_settings()
        _rate_limiter = RateLimiter(
            max_requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )
    return _rate_limiter


async def check_rate_limit(
    claims: AgentClaims = Depends(get_current_agent),
    settings: Settings = Depends(get_settings),
) -> RateLimitInfo:
    """FastAPI dependency to check rate limit for current agent.

    Args:
        claims: Current agent's claims from JWT.
        settings: Application settings.

    Returns:
        RateLimitInfo with limit status.

    Raises:
        HTTPException: If rate limit is exceeded.
    """
    limiter = get_rate_limiter(settings)
    info = limiter.check(claims.agent_id)

    if not info.allowed:
        retry_after = int(info.reset_at - time.time())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit of {info.limit} requests per hour exceeded",
            headers={"Retry-After": str(max(1, retry_after))},
        )

    return info
