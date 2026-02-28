from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SubtaskCreate(BaseModel):
    title: str


class SubtaskUpdate(BaseModel):
    title: str | None = None
    completed: bool | None = None
    position: float | None = None


class SubtaskResponse(BaseModel):
    id: UUID
    task_id: UUID
    title: str
    completed: bool
    position: float
    created_at: datetime
