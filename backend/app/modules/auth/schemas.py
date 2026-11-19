from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class AuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("username", "full_name", mode="before", check_fields=False)
    @classmethod
    def strip_profile_names(cls, value):
        return value.strip() if isinstance(value, str) else value


class RegisterRequest(AuthRequest):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr = Field(max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)


class LoginRequest(AuthRequest):
    identifier: str
    password: str = Field(..., min_length=6, max_length=128)


class RefreshTokenRequest(AuthRequest):
    refresh_token: str = Field(..., min_length=10)


class LogoutRequest(AuthRequest):
    refresh_token: str = Field(..., min_length=10)


class ForgotPasswordRequest(AuthRequest):
    email: EmailStr = Field(max_length=255)


class ResetPasswordRequest(AuthRequest):
    token: str = Field(..., min_length=12)
    password: str = Field(..., min_length=6, max_length=128)


class CompleteProfileRequest(AuthRequest):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=255)
    avatar_url: str | None = None
    bio: str | None = None
    major: str | None = Field(default=None, max_length=120)
    academic_year: str | None = Field(default=None, max_length=30)
    career_goal: str | None = Field(default=None, max_length=200)
    interest_tags: list[str] = Field(default_factory=list, max_length=20)


class VerifyEmailRequest(AuthRequest):
    token: str = Field(..., min_length=12)


class ResendVerificationRequest(AuthRequest):
    email: EmailStr = Field(max_length=255)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
    expires_in: int


class MessageResponse(BaseModel):
    message: str


class ForgotPasswordResponse(MessageResponse):
    reset_token: str | None = None


class VerificationResponse(MessageResponse):
    verification_token: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str | None
    email: EmailStr
    full_name: str
    avatar_url: str | None = None
    bio: str | None = None
    major: str | None = None
    academic_year: str | None = None
    career_goal: str | None = None
    interest_tags: list[str] = Field(default_factory=list)
    role: str
    status: str
    provider: str
    is_verified: bool

    @field_validator("interest_tags", mode="before")
    @classmethod
    def normalize_interest_tags(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []


class CurrentUserIdentityResponse(UserResponse):
    profile_completed: bool


# Internal compatibility for callers predating the versioned API.
CurrentUserResponse = CurrentUserIdentityResponse
