import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_db, get_current_user, require_workspace
from app.models.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse

router = APIRouter()


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rows = await db.fetch(
        "SELECT * FROM workspaces WHERE user_id = $1 ORDER BY created_at",
        current_user["id"],
    )
    return [dict(r) for r in rows]


@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = await db.fetchrow(
        "INSERT INTO workspaces (user_id, name, description) VALUES ($1, $2, $3) RETURNING *",
        current_user["id"], body.name, body.description,
    )
    return dict(row)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await require_workspace(db, workspace_id, current_user["id"])


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: uuid.UUID,
    body: WorkspaceUpdate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_workspace(db, workspace_id, current_user["id"])
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return await require_workspace(db, workspace_id, current_user["id"])

    fields = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
    values = list(updates.values())
    row = await db.fetchrow(
        f"UPDATE workspaces SET {fields} WHERE id = $1 RETURNING *",
        workspace_id, *values,
    )
    return dict(row)


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_workspace(db, workspace_id, current_user["id"])
    await db.execute("DELETE FROM workspaces WHERE id = $1", workspace_id)
