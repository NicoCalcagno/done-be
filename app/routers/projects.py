import uuid

import asyncpg
from fastapi import APIRouter, Depends

from app.core.dependencies import get_db, get_current_user, require_workspace, require_project
from app.models.project import ProjectCreate, ProjectUpdate, ProjectResponse

router = APIRouter()


@router.get("/workspaces/{workspace_id}/projects", response_model=list[ProjectResponse])
async def list_projects(
    workspace_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_workspace(db, workspace_id, current_user["id"])
    rows = await db.fetch(
        "SELECT * FROM projects WHERE workspace_id = $1 ORDER BY created_at",
        workspace_id,
    )
    return [dict(r) for r in rows]


@router.post("/workspaces/{workspace_id}/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    workspace_id: uuid.UUID,
    body: ProjectCreate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_workspace(db, workspace_id, current_user["id"])
    row = await db.fetchrow(
        """
        INSERT INTO projects (workspace_id, name, description, color, icon)
        VALUES ($1, $2, $3, $4, $5) RETURNING *
        """,
        workspace_id, body.name, body.description, body.color, body.icon,
    )
    return dict(row)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await require_project(db, project_id, current_user["id"])


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_project(db, project_id, current_user["id"])
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return await require_project(db, project_id, current_user["id"])

    fields = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
    values = list(updates.values())
    row = await db.fetchrow(
        f"UPDATE projects SET {fields} WHERE id = $1 RETURNING *",
        project_id, *values,
    )
    return dict(row)


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_project(db, project_id, current_user["id"])
    await db.execute("DELETE FROM projects WHERE id = $1", project_id)
