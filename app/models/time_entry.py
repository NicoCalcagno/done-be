from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TimeEntryCreate(BaseModel):
    started_at: datetime
    ended_at: datetime | None = None
    minutes: int | None = None
    note: str | None = None


class TimeEntryUpdate(BaseModel):
    started_at: datetime | None = None
    ended_at: datetime | None = None
    minutes: int | None = None
    note: str | None = None


class TimeEntryResponse(BaseModel):
    id: UUID
    task_id: UUID
    started_at: datetime
    ended_at: datetime | None
    minutes: int | None
    note: str | None
