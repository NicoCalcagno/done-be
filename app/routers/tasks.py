import uuid
from datetime import datetime

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.core.dependencies import (
    get_db, get_current_user, require_project, require_task,
    compute_next_position, needs_rebalance, rebalance_positions,
)
from app.models.task import (
    TaskCreate, TaskUpdate, TaskMove, TaskReorder,
    TaskResponse, TaskDetailResponse,
)
from app.models.subtask import SubtaskResponse
from app.models.tag import TagResponse
from app.models.comment import CommentResponse

router = APIRouter()


@router.get("/projects/{project_id}/tasks", response_model=list[TaskResponse])
async def list_tasks(
    project_id: uuid.UUID,
    bucket_id: uuid.UUID | None = Query(None),
    priority: str | None = Query(None),
    tag_id: uuid.UUID | None = Query(None),
    due_before: datetime | None = Query(None),
    search: str | None = Query(None),
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_project(db, project_id, current_user["id"])

    conditions = ["t.project_id = $1"]
    params: list = [project_id]
    idx = 2

    if bucket_id is not None:
        conditions.append(f"t.bucket_id = ${idx}")
        params.append(bucket_id)
        idx += 1
    if priority is not None:
        conditions.append(f"t.priority = ${idx}")
        params.append(priority)
        idx += 1
    if due_before is not None:
        conditions.append(f"t.due_date <= ${idx}")
        params.append(due_before)
        idx += 1
    if search is not None:
        conditions.append(f"(t.title ILIKE ${idx} OR t.description ILIKE ${idx})")
        params.append(f"%{search}%")
        idx += 1
    if tag_id is not None:
        conditions.append(f"EXISTS (SELECT 1 FROM task_tags tt WHERE tt.task_id = t.id AND tt.tag_id = ${idx})")
        params.append(tag_id)
        idx += 1

    where = " AND ".join(conditions)
    rows = await db.fetch(f"SELECT t.* FROM tasks t WHERE {where} ORDER BY t.position", *params)
    return [dict(r) for r in rows]


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    project_id: uuid.UUID,
    body: TaskCreate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_project(db, project_id, current_user["id"])
    position = await compute_next_position(db, "tasks", "project_id", project_id)
    row = await db.fetchrow(
        """
        INSERT INTO tasks (project_id, bucket_id, title, description, priority,
                           due_date, start_date, estimated_minutes, position)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *
        """,
        project_id, body.bucket_id, body.title, body.description, body.priority,
        body.due_date, body.start_date, body.estimated_minutes, position,
    )
    return dict(row)


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    task = await require_task(db, task_id, current_user["id"])

    subtask_rows = await db.fetch(
        "SELECT * FROM subtasks WHERE task_id = $1 ORDER BY position", task_id
    )
    tag_rows = await db.fetch(
        "SELECT tg.* FROM tags tg JOIN task_tags tt ON tt.tag_id = tg.id WHERE tt.task_id = $1",
        task_id,
    )
    comment_rows = await db.fetch(
        "SELECT * FROM comments WHERE task_id = $1 ORDER BY created_at", task_id
    )

    return {
        **task,
        "subtasks": [dict(r) for r in subtask_rows],
        "tags": [dict(r) for r in tag_rows],
        "comments": [dict(r) for r in comment_rows],
    }


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return await require_task(db, task_id, current_user["id"])

    fields = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
    values = list(updates.values())
    row = await db.fetchrow(
        f"UPDATE tasks SET {fields} WHERE id = $1 RETURNING *",
        task_id, *values,
    )
    return dict(row)


@router.patch("/tasks/{task_id}/move", response_model=TaskResponse)
async def move_task(
    task_id: uuid.UUID,
    body: TaskMove,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    row = await db.fetchrow(
        "UPDATE tasks SET bucket_id = $1, position = $2 WHERE id = $3 RETURNING *",
        body.bucket_id, body.position, task_id,
    )
    return dict(row)


@router.patch("/tasks/{task_id}/reorder", response_model=TaskResponse)
async def reorder_task(
    task_id: uuid.UUID,
    body: TaskReorder,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    task = await require_task(db, task_id, current_user["id"])
    row = await db.fetchrow(
        "UPDATE tasks SET position = $1 WHERE id = $2 RETURNING *",
        body.position, task_id,
    )
    if await needs_rebalance(db, "tasks", "project_id", task["project_id"]):
        await rebalance_positions(db, "tasks", "project_id", task["project_id"])
        row = await db.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
    return dict(row)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, task_id, current_user["id"])
    await db.execute("DELETE FROM tasks WHERE id = $1", task_id)
