from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.errors import ApiError
from app.models import Role
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    username: str
    role: Role
    student_no: str | None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """Read the Bearer token, validate it and return who is calling."""
    if credentials is None:
        raise ApiError(401, "MISSING_TOKEN", "Authorization header with a Bearer token is required.")

    claims = decode_access_token(credentials.credentials)
    return CurrentUser(
        username=claims["sub"],
        role=Role(claims["role"]),
        student_no=claims.get("student_no"),
    )


def require_roles(*allowed: Role):
    """Build a dependency that only lets the given roles through."""

    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise ApiError(403, "FORBIDDEN_ROLE", f"Role '{user.role.value}' is not allowed to perform this action.")
        return user

    return checker