import uuid

import asyncpg
from fastapi import APIRouter, Depends

from app.core.dependencies import (
    get_db, get_current_user, require_project, require_bucket,
    compute_next_position, needs_rebalance, rebalance_positions,
)
from app.models.bucket import BucketCreate, BucketUpdate, BucketReorder, BucketResponse

router = APIRouter()


@router.get("/projects/{project_id}/buckets", response_model=list[BucketResponse])
async def list_buckets(
    project_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_project(db, project_id, current_user["id"])
    rows = await db.fetch(
        "SELECT * FROM buckets WHERE project_id = $1 ORDER BY position",
        project_id,
    )
    return [dict(r) for r in rows]


@router.post("/projects/{project_id}/buckets", response_model=BucketResponse, status_code=201)
async def create_bucket(
    project_id: uuid.UUID,
    body: BucketCreate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_project(db, project_id, current_user["id"])
    position = await compute_next_position(db, "buckets", "project_id", project_id)
    row = await db.fetchrow(
        "INSERT INTO buckets (project_id, name, color, position) VALUES ($1, $2, $3, $4) RETURNING *",
        project_id, body.name, body.color, position,
    )
    return dict(row)


@router.patch("/buckets/{bucket_id}", response_model=BucketResponse)
async def update_bucket(
    bucket_id: uuid.UUID,
    body: BucketUpdate,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_bucket(db, bucket_id, current_user["id"])
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return await require_bucket(db, bucket_id, current_user["id"])

    fields = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
    values = list(updates.values())
    row = await db.fetchrow(
        f"UPDATE buckets SET {fields} WHERE id = $1 RETURNING *",
        bucket_id, *values,
    )
    return dict(row)


@router.patch("/buckets/{bucket_id}/reorder", response_model=BucketResponse)
async def reorder_bucket(
    bucket_id: uuid.UUID,
    body: BucketReorder,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    bucket = await require_bucket(db, bucket_id, current_user["id"])
    row = await db.fetchrow(
        "UPDATE buckets SET position = $1 WHERE id = $2 RETURNING *",
        body.position, bucket_id,
    )
    project_id = bucket["project_id"]
    if await needs_rebalance(db, "buckets", "project_id", project_id):
        await rebalance_positions(db, "buckets", "project_id", project_id)
        row = await db.fetchrow("SELECT * FROM buckets WHERE id = $1", bucket_id)
    return dict(row)


@router.delete("/buckets/{bucket_id}", status_code=204)
async def delete_bucket(
    bucket_id: uuid.UUID,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_bucket(db, bucket_id, current_user["id"])
    await db.execute("DELETE FROM buckets WHERE id = $1", bucket_id)
