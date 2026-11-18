
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import User
from app.schemas import LoginRequest, TokenResponse
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Log in with username and password, receive a JWT access token."""
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid username or password.")

    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=get_settings().jwt_expire_minutes * 60,
        role=user.role.value,
    )