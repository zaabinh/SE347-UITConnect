from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.core.schemas import UtcDateTime


class CreateReportRequest(BaseModel):
    reason: Literal["spam", "harassment", "hate_speech", "violence", "misinformation", "other"]
    details: str | None = Field(default=None, max_length=2000)


class ModerateReportRequest(BaseModel):
    status: str = Field(..., pattern="^(pending|reviewed|dismissed|resolved)$")
    action: Literal[
        "none",
        "hide_post",
        "hide_comment",
        "ban_author",
        "hide_post_and_ban_author",
        "hide_comment_and_ban_author",
    ] = "none"
    notes: str | None = Field(default=None, max_length=1000)


class ModeratePostRequest(BaseModel):
    status: Literal["active", "rejected"]


class BanUserRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


ReportCreate = CreateReportRequest
ReportModerate = ModerateReportRequest


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reporter_id: str | None
    post_id: int | None
    comment_id: int | None
    reason: str
    details: str | None
    status: str
    reviewed_by: str | None
    reviewed_at: UtcDateTime | None
    created_at: UtcDateTime
