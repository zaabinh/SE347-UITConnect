from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.application import AuthApplicationService
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    CompleteProfileRequest, CurrentUserResponse, ForgotPasswordRequest, LoginRequest,
    LogoutRequest, MessageResponse, RefreshTokenRequest, RegisterRequest,
    ResendVerificationRequest, ResetPasswordRequest, TokenResponse, UserResponse,
    VerificationResponse, VerifyEmailRequest,
)
from app.modules.auth.service import is_profile_completed
from app.modules.users.models import User


router = APIRouter(tags=["Authentication"])


def parse_interest_tags(raw_tags: str | None) -> list[str]:
    if not raw_tags:
        return []
    return [tag for tag in [item.strip() for item in raw_tags.split(",")] if tag]


def build_current_user_response(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
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


@router.post("/register", response_model=VerificationResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    AuthApplicationService(db).register(payload)
    return VerificationResponse(message="Registration successful. You can now log in.")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return AuthApplicationService(db).login(payload, **request_metadata(request))


@router.get("/google/login")
def google_login():
    return RedirectResponse(AuthApplicationService.google_login())


@router.get("/google/callback")
def google_callback(code: str, request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(AuthApplicationService(db).google_callback(code, **request_metadata(request)))


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    return AuthApplicationService(db).refresh(payload.refresh_token)


@router.post("/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    AuthApplicationService(db).logout(payload.refresh_token)
    return MessageResponse(message="Logged out successfully.")


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    return MessageResponse(message="Email verification is temporarily disabled.")


@router.post("/resend-verification", response_model=VerificationResponse)
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    return VerificationResponse(message="Email verification is temporarily disabled.")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    AuthApplicationService(db).forgot_password(payload.email)
    return MessageResponse(message="If the email exists, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    AuthApplicationService(db).reset_password(payload)
    return MessageResponse(message="Password has been reset successfully.")


@router.post("/complete-profile", response_model=CurrentUserResponse)
def complete_profile(
    payload: CompleteProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return build_current_user_response(AuthApplicationService(db).complete_profile(current_user, payload))


@router.get("/me", response_model=CurrentUserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return build_current_user_response(current_user)


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user_by_id(user_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response = build_current_user_response(AuthApplicationService(db).get_user(user_id))
    payload = response.model_dump()
    payload.pop("profile_completed", None)
    return UserResponse(**payload)
