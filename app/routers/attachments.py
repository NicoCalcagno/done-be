import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_db, get_current_user, require_task
from app.models.attachment import AttachmentCreate, AttachmentResponse

router = APIRouter()


async def _require_attachment(db, attachment_id, user_id):
    exists = await db.fetchval("SELECT 1 FROM attachments WHERE id = $1", attachment_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Attachment not found")
    row = await db.fetchrow(
        """
        SELECT a.* FROM attachments a
        JOIN tasks t ON t.id = a.task_id
        JOIN projects p ON p.id = t.project_id
        JOIN workspaces w ON w.id = p.workspace_id
        WHERE a.id = $1 AND w.user_id = $2
        """,
        attachment_id, user_id,
    )
    if not row:
        raise HTTPException(status_code=403, detail="Access forbidden")
    return dict(row)


@router.get("/tasks/{task_id}/attachments", response_model=list[AttachmentResponse])
async def list_attachments(
    task_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    rows = await db.fetch(
        "SELECT * FROM attachments WHERE task_id = $1 ORDER BY created_at", task_id
    )
    return [dict(r) for r in rows]


@router.post("/tasks/{task_id}/attachments", response_model=AttachmentResponse, status_code=201)
async def create_attachment(
    task_id: uuid.UUID,
    body: AttachmentCreate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    row = await db.fetchrow(
        "INSERT INTO attachments (task_id, file_url, file_name, file_type) VALUES ($1, $2, $3, $4) RETURNING *",
        task_id, body.file_url, body.file_name, body.file_type,
    )
    return dict(row)


@router.delete("/attachments/{attachment_id}", status_code=204)
async def delete_attachment(
    attachment_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _require_attachment(db, attachment_id, current_user["id"])
    await db.execute("DELETE FROM attachments WHERE id = $1", attachment_id)
