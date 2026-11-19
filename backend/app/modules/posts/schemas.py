from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.core.schemas import PaginationMeta, PublicUserSummary, UtcDateTime


class PostBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    content: str
    cover_image: str | None = None
    tags: list[str] = Field(default_factory=list)


class CreatePostRequest(PostBase):
    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value):
        return value.strip() if isinstance(value, str) else value


class UpdatePostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default=None, min_length=5, max_length=255)
    content: str = Field(default=None)
    cover_image: str | None = None
    tags: list[str] = Field(default=None)
    status: str = Field(default=None, pattern="^(pending|active|rejected)$")

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one field is required.")
        for field in self.model_fields_set - {"cover_image"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        return self


PostCreate = CreatePostRequest
PostUpdate = UpdatePostRequest


class SharePostRequest(BaseModel):
    caption: str | None = Field(default=None, max_length=2000)


class SharePostResponse(BaseModel):
    post_id: int
    original_post_id: int


class LikeResponse(BaseModel):
    liked: bool


class BookmarkResponse(BaseModel):
    bookmarked: bool


class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    status: str | None
    original_post_id: int | None = None
    share_caption: str | None = None
    requested_new_tags: list[str] = Field(default_factory=list)
    created_at: UtcDateTime
    author: PublicUserSummary
    likes_count: int = 0
    comments_count: int = 0
    views_count: int = 0
    shares_count: int = 0
    trending_score: int = 0
    is_liked: bool = False
    is_bookmarked: bool = False


class PostListResponse(BaseModel):
    items: list[PostResponse]
    meta: PaginationMeta
