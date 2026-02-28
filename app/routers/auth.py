import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_db, get_current_user_refresh
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models.auth import LoginRequest, TokenResponse
from app.models.user import UserCreate

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: UserCreate, db: asyncpg.Connection = Depends(get_db)):
    existing = await db.fetchval("SELECT 1 FROM users WHERE email = $1", body.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = hash_password(body.password)
    user = await db.fetchrow(
        "INSERT INTO users (email, hashed_password, full_name) VALUES ($1, $2, $3) RETURNING *",
        body.email, hashed, body.full_name,
    )

    await db.execute(
        "INSERT INTO workspaces (user_id, name) VALUES ($1, $2)",
        user["id"], "My Workspace",
    )

    user_id = str(user["id"])
    return TokenResponse(
        access_token=create_access_token({"sub": user_id}),
        refresh_token=create_refresh_token({"sub": user_id}),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: asyncpg.Connection = Depends(get_db)):
    user = await db.fetchrow("SELECT * FROM users WHERE email = $1", body.email)
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id = str(user["id"])
    return TokenResponse(
        access_token=create_access_token({"sub": user_id}),
        refresh_token=create_refresh_token({"sub": user_id}),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(current_user: dict = Depends(get_current_user_refresh)):
    user_id = str(current_user["id"])
    return TokenResponse(
        access_token=create_access_token({"sub": user_id}),
        refresh_token=create_refresh_token({"sub": user_id}),
    )
