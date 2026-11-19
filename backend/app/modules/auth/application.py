from datetime import datetime
from urllib.parse import urlencode

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config import settings
from app.core.exceptions import ApplicationError
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.db.uow import UnitOfWork
from app.modules.auth.domain import (
    require_available_user, require_password, require_public_user, require_refresh_session,
    require_reset_token, should_reset_password,
)
from app.modules.auth.google_oauth_service import (
    build_google_auth_url, exchange_google_code, fetch_google_userinfo,
)
from app.modules.auth.models import AuthSession
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import TokenResponse
from app.modules.auth.service import (
    create_google_user, create_password_reset_token, is_profile_completed, send_password_reset_email,
)
from app.modules.users.models import User


class AuthApplicationService:
    def __init__(self, db):
        self.db = db
        self.repository = AuthRepository(db)

    def _session_tokens(self, user, ip_address, user_agent):
        access_token = create_access_token(user.id, user.email, user.role)
        refresh_token, expires_at = create_refresh_token(user.id)
        self.repository.add(AuthSession(
            user_id=user.id, refresh_token=refresh_token, ip_address=ip_address,
            user_agent=user_agent, expires_at=expires_at.replace(tzinfo=None),
        ))
        return self._token_response(access_token, refresh_token)

    @staticmethod
    def _token_response(access_token, refresh_token):
        return TokenResponse(
            access_token=access_token, refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    def create_session_tokens(self, user, ip_address=None, user_agent=None):
        with UnitOfWork(self.db):
            tokens = self._session_tokens(user, ip_address, user_agent)
        return tokens

    def register(self, payload):
        email = payload.email.lower().strip()
        username = payload.username.strip().lower()
        try:
            with UnitOfWork(self.db):
                existing = self.repository.registration_conflict(email, username)
                if existing:
                    detail = "Email already exists." if existing.email == email else "Username already exists."
                    raise ApplicationError(400, detail)
                self.repository.add(User(
                    username=username, email=email, password_hash=hash_password(payload.password),
                    full_name=payload.full_name.strip(), role="Student", status="active",
                    provider="local", is_verified=True,
                ))
                self.repository.flush()
        except IntegrityError as exc:
            raise ApplicationError(400, "Registration conflicts with an existing user.") from exc
        except SQLAlchemyError as exc:
            raise ApplicationError(500, "Database error during registration.") from exc

    def login(self, payload, ip_address=None, user_agent=None):
        with UnitOfWork(self.db):
            user = self.repository.find_identifier(payload.identifier.lower().strip())
            require_password(user, payload.password)
            tokens = self._session_tokens(user, ip_address, user_agent)
        return tokens

    @staticmethod
    def google_login():
        return build_google_auth_url()

    def google_callback(self, code, ip_address=None, user_agent=None):
        google_tokens = exchange_google_code(code)
        google_user = fetch_google_userinfo(google_tokens["access_token"])
        email = google_user.get("email", "").lower().strip()
        if not email:
            raise ApplicationError(400, "Google account did not provide an email.")
        with UnitOfWork(self.db):
            user = self.repository.find_email(email)
            if not user:
                user = create_google_user(
                    email=email,
                    full_name=(google_user.get("name") or email.split("@", 1)[0]).strip(),
                    avatar_url=google_user.get("picture"),
                )
                self.repository.add(user)
                self.repository.flush()
            require_available_user(user)
            tokens = self._session_tokens(user, ip_address, user_agent)
            completed = is_profile_completed(user)
            query = urlencode({
                "access_token": tokens.access_token, "refresh_token": tokens.refresh_token,
                "next": "/feed" if completed else "/complete-profile", "email": user.email,
                "verified": str(user.is_verified).lower(), "profile_completed": str(completed).lower(),
            })
        return f"{str(settings.frontend_url).rstrip('/')}/auth/callback?{query}"

    def refresh(self, token):
        rejection = None
        with UnitOfWork(self.db):
            session = self.repository.find_session(token)
            try:
                require_refresh_session(session, token)
                user = self.repository.find_user(session.user_id)
                require_available_user(user, missing_status=401)
            except ApplicationError as exc:
                rejection = exc
                if session:
                    self.repository.delete(session)
            else:
                tokens = self._token_response(create_access_token(user.id, user.email, user.role), token)
        # Invalid sessions must be durably removed before the HTTP rejection is raised.
        if rejection:
            raise rejection
        return tokens

    def logout(self, token):
        with UnitOfWork(self.db):
            session = self.repository.find_session(token)
            if session:
                self.repository.delete(session)

    def forgot_password(self, email):
        with UnitOfWork(self.db):
            user = self.repository.find_email(email.lower().strip())
            if not should_reset_password(user):
                return
            token = create_password_reset_token(self.db, user)
            send_password_reset_email(self.db, user, token.token)

    def reset_password(self, payload):
        with UnitOfWork(self.db):
            record = self.repository.find_reset_token(payload.token)
            require_reset_token(record)
            user = self.repository.find_user(record.user_id)
            require_available_user(user)
            user.password_hash = hash_password(payload.password)
            record.used_at = datetime.utcnow()
            self.repository.delete_user_sessions(user.id)

    def complete_profile(self, user, payload):
        with UnitOfWork(self.db):
            require_available_user(user)
            username = payload.username.strip().lower()
            if self.repository.username_taken(username, user.id):
                raise ApplicationError(400, "Username already exists.")
            user.username = username
            user.full_name = payload.full_name.strip()
            for field in ("avatar_url", "bio", "major", "academic_year", "career_goal"):
                value = getattr(payload, field)
                if value:
                    setattr(user, field, value.strip())
            user.interest_tags = ",".join(dict.fromkeys(
                tag.strip().lower() for tag in payload.interest_tags if tag.strip()
            )) or user.interest_tags
            self.repository.flush()
            self.repository.refresh(user)
        return user

    def get_user(self, user_id):
        user = self.repository.find_user(user_id)
        require_public_user(user)
        return user
