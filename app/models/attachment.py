from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AttachmentCreate(BaseModel):
    file_url: str
    file_name: str | None = None
    file_type: str | None = None


class AttachmentResponse(BaseModel):
    id: UUID
    task_id: UUID
    file_url: str
    file_name: str | None
    file_type: str | None
    created_at: datetime
