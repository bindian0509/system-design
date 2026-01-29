"""Authentication middleware for the API."""

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from dsar_query_generator.config.settings import Settings, get_settings

security = HTTPBearer()


@dataclass
class AgentClaims:
    """Claims extracted from JWT token."""

    agent_id: str
    email: str
    roles: list[str]
    exp: datetime


class AuthError(Exception):
    """Authentication error."""

    pass


def decode_token(
    token: str,
    settings: Settings | None = None,
) -> AgentClaims:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token string.
        settings: Application settings. If None, loads from environment.

    Returns:
        AgentClaims extracted from the token.

    Raises:
        AuthError: If token is invalid or expired.
    """
    if settings is None:
        settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        return AgentClaims(
            agent_id=payload.get("sub", ""),
            email=payload.get("email", ""),
            roles=payload.get("roles", []),
            exp=datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc),
        )
    except JWTError as e:
        raise AuthError(f"Invalid token: {e}")


async def get_current_agent(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> AgentClaims:
    """FastAPI dependency to get current authenticated agent.

    Args:
        credentials: Bearer token from Authorization header.
        settings: Application settings.

    Returns:
        AgentClaims for the authenticated agent.

    Raises:
        HTTPException: If authentication fails.
    """
    try:
        claims = decode_token(credentials.credentials, settings)

        # Check expiration
        if claims.exp < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return claims

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(required_role: str):
    """Dependency factory for role-based authorization.

    Args:
        required_role: The role required to access the endpoint.

    Returns:
        A dependency function that checks for the required role.
    """

    async def check_role(
        claims: AgentClaims = Depends(get_current_agent),
    ) -> AgentClaims:
        if required_role not in claims.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' is required",
            )
        return claims

    return check_role


def create_token(
    agent_id: str,
    email: str,
    roles: list[str],
    settings: Settings | None = None,
    expires_delta_minutes: int | None = None,
) -> str:
    """Create a JWT token for an agent.

    This is primarily used for testing and development.

    Args:
        agent_id: Unique identifier for the agent.
        email: Agent's email address.
        roles: List of roles assigned to the agent.
        settings: Application settings.
        expires_delta_minutes: Token expiration time in minutes.

    Returns:
        Encoded JWT token string.
    """
    from datetime import timedelta

    if settings is None:
        settings = get_settings()

    if expires_delta_minutes is None:
        expires_delta_minutes = settings.jwt_expire_minutes

    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_delta_minutes)

    payload = {
        "sub": agent_id,
        "email": email,
        "roles": roles,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
