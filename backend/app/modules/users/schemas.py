from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.core.schemas import UtcDateTime


class PublicUserProfileResponse(BaseModel):
    id: str
    username: str | None
    full_name: str
    avatar_url: str | None
    bio: str | None
    major: str | None
    academic_year: str | None
    career_goal: str | None
    interest_tags: list[str]
    followers_count: int
    following_count: int
    posts_count: int
    is_following: bool
    is_current_user: bool


class CurrentUserProfileResponse(PublicUserProfileResponse):
    email: str
    role: str
    status: str
    created_at: UtcDateTime


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(default=None, min_length=2, max_length=255)
    bio: str | None = None
    avatar_url: str | None = None
    major: str | None = Field(default=None, max_length=120)
    academic_year: str | None = Field(default=None, max_length=30)
    career_goal: str | None = Field(default=None, max_length=200)
    interest_tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("At least one profile field must be provided.")
        return self


class UserPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    cover_image: str | None
    status: str | None
    created_at: UtcDateTime


class UserCommentResponse(BaseModel):
    id: int
    post_id: int
    post_title: str | None
    content: str
    created_at: UtcDateTime


class FollowResponse(BaseModel):
    message: str
    following: bool
