from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProfileResponse(BaseModel):
    id: str
    username: str
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


class CurrentProfileResponse(ProfileResponse):
    email: str
    role: str
    status: str
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    full_name: str
    bio: str | None = None
    avatar_url: str | None = None
    major: str | None = None
    academic_year: str | None = None
    career_goal: str | None = None
    interest_tags: list[str] = Field(default_factory=list)


class UserPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    cover_image: str | None
    status: str | None
    created_at: datetime


class UserCommentResponse(BaseModel):
    id: int
    post_id: int
    post_title: str | None
    content: str
    created_at: datetime


class FollowResponse(BaseModel):
    message: str
    following: bool
