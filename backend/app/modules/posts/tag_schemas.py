from pydantic import BaseModel, ConfigDict, Field
from app.core.schemas import UtcDateTime


class CreateTagRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class UpdateTagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)


class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    created_at: UtcDateTime


TagCreate = CreateTagRequest
TagUpdate = UpdateTagRequest
