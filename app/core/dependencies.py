import uuid
from typing import AsyncGenerator

import asyncpg
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token

security = HTTPBearer()


async def get_db(request: Request) -> AsyncGenerator[asyncpg.Connection, None]:
    async with request.app.state.pool.acquire() as conn:
        yield conn


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: asyncpg.Connection = Depends(get_db),
) -> dict:
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = uuid.UUID(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return dict(user)


async def get_current_user_refresh(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: asyncpg.Connection = Depends(get_db),
) -> dict:
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = uuid.UUID(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return dict(user)


# --- Ownership helpers ---

async def require_workspace(
    db: asyncpg.Connection,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    exists = await db.fetchval("SELECT 1 FROM workspaces WHERE id = $1", workspace_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Workspace not found")
    row = await db.fetchrow(
        "SELECT * FROM workspaces WHERE id = $1 AND user_id = $2", workspace_id, user_id
    )
    if not row:
        raise HTTPException(status_code=403, detail="Access forbidden")
    return dict(row)


async def require_project(
    db: asyncpg.Connection,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    exists = await db.fetchval("SELECT 1 FROM projects WHERE id = $1", project_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Project not found")
    row = await db.fetchrow(
        """
        SELECT p.* FROM projects p
        JOIN workspaces w ON w.id = p.workspace_id
        WHERE p.id = $1 AND w.user_id = $2
        """,
        project_id, user_id,
    )
    if not row:
        raise HTTPException(status_code=403, detail="Access forbidden")
    return dict(row)


async def require_bucket(
    db: asyncpg.Connection,
    bucket_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    exists = await db.fetchval("SELECT 1 FROM buckets WHERE id = $1", bucket_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Bucket not found")
    row = await db.fetchrow(
        """
        SELECT b.* FROM buckets b
        JOIN projects p ON p.id = b.project_id
        JOIN workspaces w ON w.id = p.workspace_id
        WHERE b.id = $1 AND w.user_id = $2
        """,
        bucket_id, user_id,
    )
    if not row:
        raise HTTPException(status_code=403, detail="Access forbidden")
    return dict(row)


async def require_task(
    db: asyncpg.Connection,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    exists = await db.fetchval("SELECT 1 FROM tasks WHERE id = $1", task_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Task not found")
    row = await db.fetchrow(
        """
        SELECT t.* FROM tasks t
        JOIN projects p ON p.id = t.project_id
        JOIN workspaces w ON w.id = p.workspace_id
        WHERE t.id = $1 AND w.user_id = $2
        """,
        task_id, user_id,
    )
    if not row:
        raise HTTPException(status_code=403, detail="Access forbidden")
    return dict(row)


# --- Position helpers ---

async def compute_next_position(
    db: asyncpg.Connection,
    table: str,
    parent_col: str,
    parent_id: uuid.UUID,
) -> float:
    row = await db.fetchrow(
        f"SELECT MAX(position) AS max_pos FROM {table} WHERE {parent_col} = $1",
        parent_id,
    )
    max_pos = row["max_pos"] if row["max_pos"] is not None else 0.0
    return max_pos + 1000.0


async def rebalance_positions(
    db: asyncpg.Connection,
    table: str,
    parent_col: str,
    parent_id: uuid.UUID,
) -> None:
    rows = await db.fetch(
        f"SELECT id FROM {table} WHERE {parent_col} = $1 ORDER BY position",
        parent_id,
    )
    for i, row in enumerate(rows):
        await db.execute(
            f"UPDATE {table} SET position = $1 WHERE id = $2",
            (i + 1) * 1000.0,
            row["id"],
        )


async def needs_rebalance(
    db: asyncpg.Connection,
    table: str,
    parent_col: str,
    parent_id: uuid.UUID,
) -> bool:
    rows = await db.fetch(
        f"SELECT position FROM {table} WHERE {parent_col} = $1 ORDER BY position",
        parent_id,
    )
    positions = [r["position"] for r in rows]
    for i in range(len(positions) - 1):
        if positions[i + 1] - positions[i] < 0.01:
            return True
    return False
