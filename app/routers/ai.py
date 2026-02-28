import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form

from app.core.dependencies import get_db, get_current_user, require_workspace, require_task
from app.models.ai_conversation import (
    AIChatRequest,
    AISuggestSubtasksRequest,
    AIConversationResponse,
)
from app.services import ai_service, whisper_service

router = APIRouter()


@router.post("/chat")
async def chat(
    body: AIChatRequest,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_workspace(db, body.workspace_id, current_user["id"])
    result = await ai_service.process_chat(
        db=db,
        user_id=current_user["id"],
        workspace_id=body.workspace_id,
        message=body.message,
    )
    return result


@router.post("/voice")
async def voice(
    workspace_id: uuid.UUID = Form(...),
    audio: UploadFile = File(...),
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_workspace(db, workspace_id, current_user["id"])

    content_type = audio.content_type or "audio/mpeg"
    if content_type not in whisper_service.ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Formato audio non supportato: {content_type}",
        )

    file_content = await audio.read()
    transcript = await whisper_service.transcribe_audio(file_content, content_type)

    result = await ai_service.process_chat(
        db=db,
        user_id=current_user["id"],
        workspace_id=workspace_id,
        message=transcript,
    )
    result["transcript"] = transcript
    return result


@router.get("/summary")
async def summary(
    workspace_id: uuid.UUID = Query(...),
    type: str = Query("daily", pattern="^(daily|weekly)$"),
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_workspace(db, workspace_id, current_user["id"])
    return await ai_service.generate_summary(
        db=db,
        user_id=current_user["id"],
        workspace_id=workspace_id,
        summary_type=type,
    )


@router.post("/suggest-subtasks")
async def suggest_subtasks(
    body: AISuggestSubtasksRequest,
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_task(db, body.task_id, current_user["id"])
    subtasks = await ai_service.suggest_subtasks(db=db, task_id=body.task_id)
    return {"suggested_subtasks": subtasks}


@router.get("/conversations", response_model=list[AIConversationResponse])
async def list_conversations(
    workspace_id: uuid.UUID = Query(...),
    db: asyncpg.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await require_workspace(db, workspace_id, current_user["id"])
    rows = await db.fetch(
        """
        SELECT * FROM ai_conversations
        WHERE user_id = $1 AND workspace_id = $2
        ORDER BY created_at
        """,
        current_user["id"], workspace_id,
    )
    return [dict(r) for r in rows]
