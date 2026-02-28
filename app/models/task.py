from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.subtask import SubtaskResponse
from app.models.tag import TagResponse
from app.models.comment import CommentResponse


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: str = "normal"
    due_date: datetime | None = None
    start_date: datetime | None = None
    estimated_minutes: int | None = None
    bucket_id: UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    due_date: datetime | None = None
    start_date: datetime | None = None
    estimated_minutes: int | None = None
    bucket_id: UUID | None = None


class TaskMove(BaseModel):
    bucket_id: UUID
    position: float


class TaskReorder(BaseModel):
    position: float


class TaskResponse(BaseModel):
    id: UUID
    bucket_id: UUID | None
    project_id: UUID
    title: str
    description: str | None
    priority: str
    due_date: datetime | None
    start_date: datetime | None
    estimated_minutes: int | None
    position: float
    created_at: datetime
    updated_at: datetime


class TaskDetailResponse(TaskResponse):
    subtasks: list[SubtaskResponse] = []
    tags: list[TagResponse] = []
    comments: list[CommentResponse] = []
