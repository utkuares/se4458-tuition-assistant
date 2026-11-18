
from datetime import datetime, timedelta, timezone

import bcrypt 

from jose import JWTError, jwt

from app.config import get_settings
from app.errors import ApiError
from app.models import User

ALGORITHM = "RS256"

def verify_password(plain_password: str, password_hash: str) -> bool:
    # Does the entered password match the hash in the database?
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())

def create_access_token(user: User) -> str:
    # Generates a JWT signed with a secret key for the user.
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": user.username,
        "role": user.role.value,
        "student_no": user.student_no,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    return jwt.encode(claims, settings.jwt_private_key, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    # It checks the token's signature, expiration, 'iss' (issuer), and 'aud' (audience) fields, and returns its content.
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=[ALGORITHM],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except JWTError:
        raise ApiError(401, "INVALID_TOKEN", "Token is invalid or expired.")