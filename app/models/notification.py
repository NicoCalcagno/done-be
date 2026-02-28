from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    task_id: UUID | None
    type: str
    message: str
    read: bool
    created_at: datetime
