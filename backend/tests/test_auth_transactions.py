import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.db.base import Base
from app.db.outbox import OutboxEvent
from app.db.uow import UnitOfWork
from app.modules.auth import application, email_service
from app.modules.auth.application import AuthApplicationService
from app.modules.auth.models import AuthSession, PasswordResetToken
from app.modules.auth.schemas import CompleteProfileRequest, LoginRequest
from app.modules.users.models import User


@compiles(UNIQUEIDENTIFIER, "sqlite")
def sqlite_identifier(type_, compiler, **kwargs):
    return "VARCHAR(36)"


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[
        User.__table__, AuthSession.__table__, PasswordResetToken.__table__, OutboxEvent.__table__,
    ])
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def add_user(db, **values):
    user = User(
        username="student", email="student@example.com", full_name="Student",
        password_hash=hash_password("password123"), role="Student", status="active",
        provider="local", is_verified=True,
    )
    for key, value in values.items():
        setattr(user, key, value)
    with UnitOfWork(db):
        db.add(user)
    return user


def count_commits(db):
    commits = []
    event.listen(db, "after_commit", lambda session: commits.append(True))
    return commits


def test_password_reset_token_and_email_commit_together(db, monkeypatch):
    user = add_user(db)
    commits = count_commits(db)
    monkeypatch.setattr(email_service, "send_email_message", lambda *args, **kwargs: pytest.fail("email sent in request"))

    AuthApplicationService(db).forgot_password(user.email)

    token = db.query(PasswordResetToken).one()
    message = json.loads(db.query(OutboxEvent).one().payload)
    assert message["recipient"] == user.email
    assert token.token in message["body"]
    assert commits == [True]


def test_password_reset_enqueue_failure_restores_previous_token(db, monkeypatch):
    user = add_user(db)
    with UnitOfWork(db):
        db.add(PasswordResetToken(
            user_id=user.id, token="previous-token", expires_at=datetime.utcnow() + timedelta(minutes=10),
        ))

    def fail_enqueue(*args, **kwargs):
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(application, "send_password_reset_email", fail_enqueue)
    with pytest.raises(RuntimeError, match="outbox unavailable"):
        AuthApplicationService(db).forgot_password(user.email)

    assert [record.token for record in db.query(PasswordResetToken).all()] == ["previous-token"]
    assert db.query(OutboxEvent).count() == 0


def test_password_reset_commit_failure_rolls_back_token_and_outbox(db):
    user = add_user(db)

    def fail_commit(session):
        session.flush()
        raise RuntimeError("commit failed")

    event.listen(db, "before_commit", fail_commit, once=True)
    with pytest.raises(RuntimeError, match="commit failed"):
        AuthApplicationService(db).forgot_password(user.email)

    assert db.query(PasswordResetToken).count() == 0
    assert db.query(OutboxEvent).count() == 0


def test_google_user_and_session_roll_back_together(db, monkeypatch):
    monkeypatch.setattr(application, "exchange_google_code", lambda code: {"access_token": "google-access"})
    monkeypatch.setattr(application, "fetch_google_userinfo", lambda token: {"email": "new@example.com"})

    def fail_commit(session):
        session.flush()
        assert session.query(User).count() == 1
        assert session.query(AuthSession).count() == 1
        raise RuntimeError("commit failed")

    event.listen(db, "before_commit", fail_commit, once=True)
    with pytest.raises(RuntimeError, match="commit failed"):
        AuthApplicationService(db).google_callback("code")

    assert db.query(User).count() == 0
    assert db.query(AuthSession).count() == 0


def test_login_persists_session_once(db):
    user = add_user(db)
    commits = count_commits(db)
    tokens = AuthApplicationService(db).login(LoginRequest(identifier=user.email, password="password123"))
    assert db.query(AuthSession).one().refresh_token == tokens.refresh_token
    assert commits == [True]


@pytest.mark.parametrize("reason, status", [
    ("expired", 401), ("malformed", 401), ("wrong-type", 401),
    ("wrong-user", 401), ("missing-user", 401), ("deleted", 401), ("banned", 403),
])
def test_invalid_refresh_removes_session_before_rejection(db, reason, status):
    user = add_user(db, status=reason if reason in ("deleted", "banned") else "active")
    token, expires_at = create_refresh_token(user.id)
    if reason == "malformed":
        token = "malformed-refresh-token"
    elif reason == "wrong-type":
        token = create_access_token(user.id, user.email, user.role)
    elif reason == "wrong-user":
        token, expires_at = create_refresh_token("00000000-0000-0000-0000-000000000002")
    with UnitOfWork(db):
        db.add(AuthSession(
            user_id="00000000-0000-0000-0000-000000000003" if reason == "missing-user" else user.id,
            refresh_token=token,
            expires_at=datetime.utcnow() - timedelta(seconds=1) if reason == "expired" else expires_at.replace(tzinfo=None),
        ))
    # The JWT subject still needs to match the session for the missing-user branch.
    if reason == "missing-user":
        with UnitOfWork(db):
            record = db.query(AuthSession).one()
            token, _ = create_refresh_token(record.user_id)
            record.refresh_token = token
    commits = count_commits(db)

    with pytest.raises(ApplicationError) as caught:
        AuthApplicationService(db).refresh(token)

    assert caught.value.status_code == status
    assert db.query(AuthSession).count() == 0
    assert commits == [True]


def test_profile_update_accepts_authentication_read_transaction(db):
    user = add_user(db)
    db.expire_all()
    current_user = db.query(User).filter(User.id == user.id).one()
    assert db.in_transaction()
    commits = count_commits(db)

    AuthApplicationService(db).complete_profile(
        current_user, CompleteProfileRequest(username="updated", full_name="Updated Student"),
    )

    assert db.query(User).one().username == "updated"
    assert commits == [True]
