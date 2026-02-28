from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BucketCreate(BaseModel):
    name: str
    color: str | None = None


class BucketUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class BucketReorder(BaseModel):
    position: float


class BucketResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    position: float
    color: str | None
    created_at: datetime
