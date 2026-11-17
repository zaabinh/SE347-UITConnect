from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash password with argon2."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against argon2 hash."""
    return pwd_context.verify(password, hashed)


def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, email: str, role: str) -> str:
    return _create_token(
        {
            "sub": str(user_id),
            "email": email,
            "role": role,
            "type": "access",
        },
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    token = _create_token(
        {
            "sub": str(user_id),
            "type": "refresh",
        },
        timedelta(days=settings.refresh_token_expire_days),
    )
    return token, expires_at


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key.get_secret_value(), algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token.") from exc
