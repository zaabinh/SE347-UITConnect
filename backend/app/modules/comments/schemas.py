from pydantic import BaseModel, ConfigDict, Field
from app.core.schemas import PublicUserSummary, UtcDateTime


class CommentBase(BaseModel):
    content: str = Field(..., min_length=1)


class CreateCommentRequest(CommentBase):
    parent_id: int | None = None


CommentCreate = CreateCommentRequest


class CommentResponse(CommentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    user_id: str
    parent_id: int | None
    status: str = "active"
    created_at: UtcDateTime
    author: PublicUserSummary
    replies: list["CommentResponse"] = Field(default_factory=list)


CommentResponse.model_rebuild()
