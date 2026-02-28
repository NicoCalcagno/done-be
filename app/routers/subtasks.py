import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import (
    get_db, get_current_user, require_task,
    compute_next_position, needs_rebalance, rebalance_positions,
)
from app.models.subtask import SubtaskCreate, SubtaskUpdate, SubtaskResponse

router = APIRouter()


async def _require_subtask(db, subtask_id, user_id):
    exists = await db.fetchval("SELECT 1 FROM subtasks WHERE id = $1", subtask_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Subtask not found")
    row = await db.fetchrow(
        """
        SELECT s.* FROM subtasks s
        JOIN tasks t ON t.id = s.task_id
        JOIN projects p ON p.id = t.project_id
        JOIN workspaces w ON w.id = p.workspace_id
        WHERE s.id = $1 AND w.user_id = $2
        """,
        subtask_id, user_id,
    )
    if not row:
        raise HTTPException(status_code=403, detail="Access forbidden")
    return dict(row)


@router.get("/tasks/{task_id}/subtasks", response_model=list[SubtaskResponse])
async def list_subtasks(
    task_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    rows = await db.fetch(
        "SELECT * FROM subtasks WHERE task_id = $1 ORDER BY position", task_id
    )
    return [dict(r) for r in rows]


@router.post("/tasks/{task_id}/subtasks", response_model=SubtaskResponse, status_code=201)
async def create_subtask(
    task_id: uuid.UUID,
    body: SubtaskCreate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    position = await compute_next_position(db, "subtasks", "task_id", task_id)
    row = await db.fetchrow(
        "INSERT INTO subtasks (task_id, title, position) VALUES ($1, $2, $3) RETURNING *",
        task_id, body.title, position,
    )
    return dict(row)


@router.patch("/subtasks/{subtask_id}", response_model=SubtaskResponse)
async def update_subtask(
    subtask_id: uuid.UUID,
    body: SubtaskUpdate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    subtask = await _require_subtask(db, subtask_id, current_user["id"])
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return subtask

    fields = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
    values = list(updates.values())
    row = await db.fetchrow(
        f"UPDATE subtasks SET {fields} WHERE id = $1 RETURNING *",
        subtask_id, *values,
    )
    if "position" in updates:
        task_id = subtask["task_id"]
        if await needs_rebalance(db, "subtasks", "task_id", task_id):
            await rebalance_positions(db, "subtasks", "task_id", task_id)
            row = await db.fetchrow("SELECT * FROM subtasks WHERE id = $1", subtask_id)
    return dict(row)


@router.delete("/subtasks/{subtask_id}", status_code=204)
async def delete_subtask(
    subtask_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _require_subtask(db, subtask_id, current_user["id"])
    await db.execute("DELETE FROM subtasks WHERE id = $1", subtask_id)
