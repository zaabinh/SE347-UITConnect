from datetime import datetime

from app.core.exceptions import ApplicationError
from app.core.security import decode_token, verify_password


def require_available_user(user, *, missing_status=404):
    if not user or user.status.lower() == "deleted":
        raise ApplicationError(missing_status, "User not found.")
    if user.status.lower() == "banned":
        raise ApplicationError(403, "User is banned")


def require_password(user, password):
    require_available_user(user)
    if not verify_password(password, user.password_hash):
        raise ApplicationError(401, "Invalid password.")


def should_reset_password(user):
    if not user or user.status.lower() == "deleted":
        return False
    require_available_user(user)
    return True


def require_public_user(user):
    if not user or user.status != "active":
        raise ApplicationError(404, "User not found.")


def require_refresh_session(session, token):
    if not session:
        raise ApplicationError(401, "Refresh token not found.")
    if session.expires_at < datetime.utcnow():
        raise ApplicationError(401, "Refresh token expired.")
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise ApplicationError(401, str(exc)) from exc
    if payload.get("type") != "refresh" or str(session.user_id) != str(payload.get("sub")):
        raise ApplicationError(401, "Refresh token is invalid.")


def require_reset_token(record):
    if not record or record.used_at is not None or record.expires_at < datetime.utcnow():
        raise ApplicationError(400, "Reset token is invalid or expired.")
