import asyncpg
from app.core.config import settings


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(settings.DATABASE_URL)


async def close_pool(pool: asyncpg.Pool) -> None:
    await pool.close()
