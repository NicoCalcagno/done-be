from uuid import UUID

from pydantic import BaseModel


class TagCreate(BaseModel):
    name: str
    color: str | None = None


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class TagResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    color: str | None
