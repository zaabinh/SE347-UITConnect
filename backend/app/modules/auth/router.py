from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.schemas import PublicUserSummary
from app.modules.auth.application import AuthApplicationService
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    CompleteProfileRequest, CurrentUserIdentityResponse, ForgotPasswordRequest, LoginRequest,
    LogoutRequest, MessageResponse, RefreshTokenRequest, RegisterRequest,
    ResendVerificationRequest, ResetPasswordRequest, TokenResponse,
    VerificationResponse, VerifyEmailRequest,
)
from app.modules.auth.service import is_profile_completed
from app.modules.users.models import User


router = APIRouter(prefix="/auth", tags=["Authentication"])
public_user_router = APIRouter(tags=["Users"])
profile_completion_router = APIRouter(tags=["Users"])


def parse_interest_tags(raw_tags: str | None) -> list[str]:
    if not raw_tags:
        return []
    return [tag for tag in [item.strip() for item in raw_tags.split(",")] if tag]


def build_current_user_response(user: User) -> CurrentUserIdentityResponse:
    return CurrentUserIdentityResponse(
        id=user.id, username=user.username, email=user.email, full_name=user.full_name,
        avatar_url=user.avatar_url, bio=user.bio, major=user.major,
        academic_year=user.academic_year, career_goal=user.career_goal,
        interest_tags=parse_interest_tags(user.interest_tags), role=user.role,
        status=user.status, provider=user.provider, is_verified=user.is_verified,
        profile_completed=is_profile_completed(user),
    )


def request_metadata(request: Request):
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


def create_session_tokens(user: User, request: Request, db: Session) -> TokenResponse:
    return AuthApplicationService(db).create_session_tokens(user, **request_metadata(request))


@router.post("/register", response_model=VerificationResponse, status_code=status.HTTP_201_CREATED, operation_id="auth_register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    AuthApplicationService(db).register(payload)
    return VerificationResponse(message="Registration successful. You can now log in.")


@router.post("/login", response_model=TokenResponse, operation_id="auth_login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return AuthApplicationService(db).login(payload, **request_metadata(request))


@router.get("/google/login", status_code=307, response_class=RedirectResponse, operation_id="auth_google_login")
def google_login():
    return RedirectResponse(AuthApplicationService.google_login())


@router.get("/google/callback", status_code=307, response_class=RedirectResponse, operation_id="auth_google_callback")
def google_callback(code: str, request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(AuthApplicationService(db).google_callback(code, **request_metadata(request)))


@router.post("/refresh", response_model=TokenResponse, operation_id="auth_refresh")
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    return AuthApplicationService(db).refresh(payload.refresh_token)


@router.post("/logout", status_code=204, response_class=Response, operation_id="auth_logout")
def logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    AuthApplicationService(db).logout(payload.refresh_token)
    return Response(status_code=204)


@router.post("/verify-email", response_model=MessageResponse, operation_id="auth_verify_email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    return MessageResponse(message="Email verification is temporarily disabled.")


@router.post("/resend-verification", response_model=VerificationResponse, operation_id="auth_resend_verification")
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    return VerificationResponse(message="Email verification is temporarily disabled.")


@router.post("/forgot-password", response_model=MessageResponse, status_code=202, operation_id="auth_forgot_password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    AuthApplicationService(db).forgot_password(payload.email)
    return MessageResponse(message="If the email exists, a password reset email has been queued.")


@router.post("/reset-password", response_model=MessageResponse, operation_id="auth_reset_password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    AuthApplicationService(db).reset_password(payload)
    return MessageResponse(message="Password has been reset successfully.")


@profile_completion_router.put("/users/me/profile-completion", response_model=CurrentUserIdentityResponse, operation_id="users_complete_profile")
def complete_profile(
    payload: CompleteProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return build_current_user_response(AuthApplicationService(db).complete_profile(current_user, payload))


@router.get("/me", response_model=CurrentUserIdentityResponse, operation_id="auth_me")
def get_me(current_user: User = Depends(get_current_user)):
    return build_current_user_response(current_user)


@public_user_router.get("/users/{user_id}", response_model=PublicUserSummary, operation_id="users_get_by_id")
def get_user_by_id(user_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return PublicUserSummary.model_validate(AuthApplicationService(db).get_user(user_id))
