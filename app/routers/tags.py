import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_db, get_current_user, require_workspace, require_task
from app.models.tag import TagCreate, TagUpdate, TagResponse

router = APIRouter()


async def _require_tag(db, tag_id, user_id):
    exists = await db.fetchval("SELECT 1 FROM tags WHERE id = $1", tag_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Tag not found")
    row = await db.fetchrow(
        """
        SELECT tg.* FROM tags tg
        JOIN workspaces w ON w.id = tg.workspace_id
        WHERE tg.id = $1 AND w.user_id = $2
        """,
        tag_id, user_id,
    )
    if not row:
        raise HTTPException(status_code=403, detail="Access forbidden")
    return dict(row)


@router.get("/workspaces/{workspace_id}/tags", response_model=list[TagResponse])
async def list_tags(
    workspace_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_workspace(db, workspace_id, current_user["id"])
    rows = await db.fetch("SELECT * FROM tags WHERE workspace_id = $1", workspace_id)
    return [dict(r) for r in rows]


@router.post("/workspaces/{workspace_id}/tags", response_model=TagResponse, status_code=201)
async def create_tag(
    workspace_id: uuid.UUID,
    body: TagCreate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_workspace(db, workspace_id, current_user["id"])
    row = await db.fetchrow(
        "INSERT INTO tags (workspace_id, name, color) VALUES ($1, $2, $3) RETURNING *",
        workspace_id, body.name, body.color,
    )
    return dict(row)


@router.patch("/tags/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: uuid.UUID,
    body: TagUpdate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _require_tag(db, tag_id, current_user["id"])
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return await _require_tag(db, tag_id, current_user["id"])

    fields = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
    values = list(updates.values())
    row = await db.fetchrow(
        f"UPDATE tags SET {fields} WHERE id = $1 RETURNING *",
        tag_id, *values,
    )
    return dict(row)


@router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _require_tag(db, tag_id, current_user["id"])
    await db.execute("DELETE FROM tags WHERE id = $1", tag_id)


@router.post("/tasks/{task_id}/tags/{tag_id}", status_code=201)
async def add_tag_to_task(
    task_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    await _require_tag(db, tag_id, current_user["id"])
    await db.execute(
        "INSERT INTO task_tags (task_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        task_id, tag_id,
    )
    return {"task_id": task_id, "tag_id": tag_id}


@router.delete("/tasks/{task_id}/tags/{tag_id}", status_code=204)
async def remove_tag_from_task(
    task_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    await db.execute(
        "DELETE FROM task_tags WHERE task_id = $1 AND tag_id = $2", task_id, tag_id
    )
