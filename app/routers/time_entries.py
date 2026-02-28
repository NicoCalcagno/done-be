import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_db, get_current_user, require_task
from app.models.time_entry import TimeEntryCreate, TimeEntryUpdate, TimeEntryResponse

router = APIRouter()


async def _require_time_entry(db, entry_id, user_id):
    exists = await db.fetchval("SELECT 1 FROM time_entries WHERE id = $1", entry_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Time entry not found")
    row = await db.fetchrow(
        """
        SELECT te.* FROM time_entries te
        JOIN tasks t ON t.id = te.task_id
        JOIN projects p ON p.id = t.project_id
        JOIN workspaces w ON w.id = p.workspace_id
        WHERE te.id = $1 AND w.user_id = $2
        """,
        entry_id, user_id,
    )
    if not row:
        raise HTTPException(status_code=403, detail="Access forbidden")
    return dict(row)


@router.get("/tasks/{task_id}/time-entries", response_model=list[TimeEntryResponse])
async def list_time_entries(
    task_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    rows = await db.fetch(
        "SELECT * FROM time_entries WHERE task_id = $1 ORDER BY started_at", task_id
    )
    return [dict(r) for r in rows]


@router.post("/tasks/{task_id}/time-entries", response_model=TimeEntryResponse, status_code=201)
async def create_time_entry(
    task_id: uuid.UUID,
    body: TimeEntryCreate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    row = await db.fetchrow(
        """
        INSERT INTO time_entries (task_id, started_at, ended_at, minutes, note)
        VALUES ($1, $2, $3, $4, $5) RETURNING *
        """,
        task_id, body.started_at, body.ended_at, body.minutes, body.note,
    )
    return dict(row)


@router.patch("/time-entries/{entry_id}", response_model=TimeEntryResponse)
async def update_time_entry(
    entry_id: uuid.UUID,
    body: TimeEntryUpdate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _require_time_entry(db, entry_id, current_user["id"])
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return await _require_time_entry(db, entry_id, current_user["id"])

    fields = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
    values = list(updates.values())
    row = await db.fetchrow(
        f"UPDATE time_entries SET {fields} WHERE id = $1 RETURNING *",
        entry_id, *values,
    )
    return dict(row)


@router.delete("/time-entries/{entry_id}", status_code=204)
async def delete_time_entry(
    entry_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _require_time_entry(db, entry_id, current_user["id"])
    await db.execute("DELETE FROM time_entries WHERE id = $1", entry_id)
