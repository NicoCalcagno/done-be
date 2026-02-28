from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AIChatRequest(BaseModel):
    message: str
    workspace_id: UUID


class AISuggestSubtasksRequest(BaseModel):
    task_id: UUID


class AISummaryResponse(BaseModel):
    summary: str
    tasks_completed: int
    tasks_overdue: int
    tasks_due_soon: int
    total_minutes_tracked: int


class AIConversationResponse(BaseModel):
    id: UUID
    user_id: UUID
    workspace_id: UUID
    role: str
    content: str
    audio_url: str | None
    created_at: datetime
