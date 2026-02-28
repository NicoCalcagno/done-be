import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_db, get_current_user
from app.models.notification import NotificationResponse

router = APIRouter()


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rows = await db.fetch(
        "SELECT * FROM notifications WHERE user_id = $1 ORDER BY created_at DESC",
        current_user["id"],
    )
    return [dict(r) for r in rows]


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    exists = await db.fetchval("SELECT 1 FROM notifications WHERE id = $1", notification_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Notification not found")
    row = await db.fetchrow(
        "UPDATE notifications SET read = TRUE WHERE id = $1 AND user_id = $2 RETURNING *",
        notification_id, current_user["id"],
    )
    if not row:
        raise HTTPException(status_code=403, detail="Access forbidden")
    return dict(row)


@router.patch("/read-all", status_code=204)
async def mark_all_read(
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await db.execute(
        "UPDATE notifications SET read = TRUE WHERE user_id = $1", current_user["id"]
    )
