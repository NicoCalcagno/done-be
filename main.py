import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db.connection import create_pool, close_pool
from app.routers import (
    auth,
    users,
    workspaces,
    projects,
    buckets,
    tasks,
    subtasks,
    tags,
    comments,
    attachments,
    time_entries,
    notifications,
    ai,
)

logger = logging.getLogger(__name__)

PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()
    yield
    await close_pool(app.state.pool)


app = FastAPI(
    title="Done API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s: %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


# Auth & Users
app.include_router(auth.router, prefix=f"{PREFIX}/auth", tags=["auth"])
app.include_router(users.router, prefix=f"{PREFIX}/users", tags=["users"])

# Workspaces (simple prefix)
app.include_router(workspaces.router, prefix=f"{PREFIX}/workspaces", tags=["workspaces"])

# Resources with mixed paths (registered at root prefix)
app.include_router(projects.router, prefix=PREFIX, tags=["projects"])
app.include_router(buckets.router, prefix=PREFIX, tags=["buckets"])
app.include_router(tasks.router, prefix=PREFIX, tags=["tasks"])
app.include_router(subtasks.router, prefix=PREFIX, tags=["subtasks"])
app.include_router(tags.router, prefix=PREFIX, tags=["tags"])
app.include_router(comments.router, prefix=PREFIX, tags=["comments"])
app.include_router(attachments.router, prefix=PREFIX, tags=["attachments"])
app.include_router(time_entries.router, prefix=PREFIX, tags=["time-entries"])

# Notifications & AI
app.include_router(notifications.router, prefix=f"{PREFIX}/notifications", tags=["notifications"])
app.include_router(ai.router, prefix=f"{PREFIX}/ai", tags=["ai"])
