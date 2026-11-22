import secrets
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.modules.auth.models import EmailVerificationToken, PasswordResetToken
from app.modules.users.models import User
from app.modules.auth.email_service import build_password_reset_link, build_verification_link
from app.modules.auth.repository import AuthRepository
from app.db.outbox import enqueue_email
from app.core.security import hash_password


def is_profile_completed(user: User) -> bool:
    return bool(user.username and user.username.strip())


def create_email_verification_token(db: Session, user: User) -> EmailVerificationToken:
    repository = AuthRepository(db)
    repository.delete_verification_tokens(user.id)
    token = EmailVerificationToken(
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    repository.add(token)
    repository.flush()
    return token


def send_verification_email(db: Session, user: User, token: str) -> None:
    link = build_verification_link(token)
    enqueue_email(
        db,
        user.email,
        "Verify your Forum account",
        f"Hello {user.full_name},\n\nVerify your email here: {link}\n\nThis link expires in 24 hours.",
    )


def create_password_reset_token(db: Session, user: User) -> PasswordResetToken:
    repository = AuthRepository(db)
    repository.delete_unused_reset_tokens(user.id)
    token = PasswordResetToken(
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    repository.add(token)
    repository.flush()
    return token


def send_password_reset_email(db: Session, user: User, token: str) -> None:
    link = build_password_reset_link(token)
    enqueue_email(
        db,
        user.email,
        "Reset your Forum password",
        f"Hello {user.full_name},\n\nReset your password here: {link}\n\nThis link expires in 30 minutes.",
    )


def create_google_user(*, email: str, full_name: str, avatar_url: str | None) -> User:
    return User(
        username=None,
        email=email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        full_name=full_name or email.split("@", 1)[0],
        avatar_url=avatar_url,
        bio=None,
        role="Student",
        status="active",
        provider="google",
        is_verified=True,
    )
