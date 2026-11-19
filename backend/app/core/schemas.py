from datetime import UTC, datetime
from typing import Annotated
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


UtcDateTime = Annotated[datetime, AfterValidator(as_utc)]


class PublicUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str | None
    full_name: str
    avatar_url: str | None = None
    bio: str | None = None
    role: str


class ValidationIssue(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ProblemDetails(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    request_id: str
    errors: list[ValidationIssue] | None = None


class HealthResponse(BaseModel):
    status: str
    message: str


class RootResponse(BaseModel):
    message: str
    version: str
    docs: str
    openapi_schema: str


class PaginationMeta(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=0)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)

    @model_validator(mode='after')
    def normalize_empty_pages(self):
        if self.total == 0:
            self.total_pages = 0
        return self
