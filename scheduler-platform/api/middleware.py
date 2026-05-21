"""
RBAC middleware for role-based access control.
"""
from typing import Optional, List
from fastapi import HTTPException, Request
import jwt
from functools import wraps

from common.config import settings
from common.models import UserRole


class RBACMiddleware:
    """Role-based access control middleware."""

    @staticmethod
    def extract_user_info(request: Request) -> dict:
        """
        Extract user information from JWT token in Authorization header.

        Returns:
            Dict with user_id, email, teams, roles
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Invalid authorization scheme")

            # Decode JWT
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm]
            )

            return {
                "user_id": payload.get("user_id"),
                "email": payload.get("email"),
                "teams": payload.get("teams", []),  # List of team_ids
                "roles": payload.get("roles", {}),  # Dict: {team_id: role}
            }
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid authorization header")

    @staticmethod
    def require_role(required_role: UserRole):
        """
        Decorator to require a specific role in a team.

        Usage:
            @require_role(UserRole.EDITOR)
            def create_job(team_id: str, user_info: dict):
                ...
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                user_info = kwargs.get("user_info")
                team_id = kwargs.get("team_id")

                if not user_info or not team_id:
                    raise HTTPException(status_code=400, detail="Missing user_info or team_id")

                user_role = user_info.get("roles", {}).get(team_id)

                if not user_role:
                    raise HTTPException(
                        status_code=403,
                        detail=f"User not a member of team {team_id}"
                    )

                # Check role hierarchy: admin > editor > viewer
                role_hierarchy = {
                    UserRole.VIEWER: 0,
                    UserRole.EDITOR: 1,
                    UserRole.ADMIN: 2,
                }

                required_level = role_hierarchy.get(required_role, 0)
                user_level = role_hierarchy.get(UserRole(user_role), 0)

                if user_level < required_level:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Insufficient permissions. Required: {required_role.value}"
                    )

                return await func(*args, **kwargs)

            return wrapper
        return decorator


def get_user_info(request: Request) -> dict:
    """Dependency to extract user info from request."""
    return RBACMiddleware.extract_user_info(request)
