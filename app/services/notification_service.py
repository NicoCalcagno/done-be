import uuid

import asyncpg


async def create_notification(
    db: asyncpg.Connection,
    user_id: uuid.UUID,
    notification_type: str,
    message: str,
    task_id: uuid.UUID | None = None,
) -> dict:
    row = await db.fetchrow(
        """
        INSERT INTO notifications (user_id, task_id, type, message)
        VALUES ($1, $2, $3, $4) RETURNING *
        """,
        user_id, task_id, notification_type, message,
    )
    return dict(row)
