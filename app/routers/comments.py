import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_db, get_current_user, require_task
from app.models.comment import CommentCreate, CommentUpdate, CommentResponse

router = APIRouter()


async def _require_comment(db, comment_id, user_id):
    exists = await db.fetchval("SELECT 1 FROM comments WHERE id = $1", comment_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Comment not found")
    row = await db.fetchrow(
        "SELECT * FROM comments WHERE id = $1 AND user_id = $2", comment_id, user_id
    )
    if not row:
        raise HTTPException(status_code=403, detail="Access forbidden")
    return dict(row)


@router.get("/tasks/{task_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    task_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    rows = await db.fetch(
        "SELECT * FROM comments WHERE task_id = $1 ORDER BY created_at", task_id
    )
    return [dict(r) for r in rows]


@router.post("/tasks/{task_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    task_id: uuid.UUID,
    body: CommentCreate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    row = await db.fetchrow(
        "INSERT INTO comments (task_id, user_id, content) VALUES ($1, $2, $3) RETURNING *",
        task_id, current_user["id"], body.content,
    )
    return dict(row)


@router.patch("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: uuid.UUID,
    body: CommentUpdate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _require_comment(db, comment_id, current_user["id"])
    row = await db.fetchrow(
        "UPDATE comments SET content = $1 WHERE id = $2 RETURNING *",
        body.content, comment_id,
    )
    return dict(row)


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _require_comment(db, comment_id, current_user["id"])
    await db.execute("DELETE FROM comments WHERE id = $1", comment_id)
