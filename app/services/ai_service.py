import json
import uuid
from datetime import datetime, timezone

import asyncpg
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.dependencies import compute_next_position

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """Sei l'assistente AI di Done, un task manager personale.
L'utente ha i seguenti progetti e bucket disponibili: {context}

Quando l'utente descrive task, estraili in formato JSON strutturato.
Rispondi SEMPRE con un oggetto JSON con due chiavi:
- "tasks": array di task estratti (può essere vuoto se non ci sono task da creare)
- "reply": stringa con risposta naturale in italiano

Ogni task ha i seguenti campi:
- title (string, obbligatorio)
- description (string o null)
- priority: "urgent" | "high" | "normal" | "low" (default "normal")
- due_date: ISO8601 UTC string o null
- project_id: UUID stringa del progetto scelto o null se non chiaro
- bucket_id: UUID stringa del bucket scelto o null
- suggested_bucket_name: stringa con nome bucket suggerito se bucket_id è null

La data/ora corrente è: {now}"""


async def _get_workspace_context(db: asyncpg.Connection, workspace_id: uuid.UUID) -> str:
    projects = await db.fetch(
        "SELECT id, name FROM projects WHERE workspace_id = $1", workspace_id
    )
    context_parts = []
    for project in projects:
        buckets = await db.fetch(
            "SELECT id, name FROM buckets WHERE project_id = $1 ORDER BY position",
            project["id"],
        )
        bucket_list = ", ".join(
            f'{{"id": "{b["id"]}", "name": "{b["name"]}"}}'
            for b in buckets
        )
        context_parts.append(
            f'Progetto "{project["name"]}" (id: {project["id"]}) — bucket: [{bucket_list}]'
        )
    return "\n".join(context_parts) if context_parts else "Nessun progetto disponibile."


async def _save_conversation(
    db: asyncpg.Connection,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    role: str,
    content: str,
) -> None:
    await db.execute(
        "INSERT INTO ai_conversations (user_id, workspace_id, role, content) VALUES ($1, $2, $3, $4)",
        user_id, workspace_id, role, content,
    )


async def _create_tasks_from_ai(
    db: asyncpg.Connection,
    ai_tasks: list[dict],
    user_id: uuid.UUID,
) -> list[dict]:
    created = []
    for task_data in ai_tasks:
        project_id_str = task_data.get("project_id")
        if not project_id_str:
            continue

        try:
            project_id = uuid.UUID(project_id_str)
        except ValueError:
            continue

        # Verify project ownership
        project = await db.fetchrow(
            """
            SELECT p.id FROM projects p
            JOIN workspaces w ON w.id = p.workspace_id
            WHERE p.id = $1 AND w.user_id = $2
            """,
            project_id, user_id,
        )
        if not project:
            continue

        bucket_id = None
        bucket_id_str = task_data.get("bucket_id")
        if bucket_id_str:
            try:
                bucket_id = uuid.UUID(bucket_id_str)
            except ValueError:
                pass

        due_date = None
        due_date_str = task_data.get("due_date")
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        position = await compute_next_position(db, "tasks", "project_id", project_id)

        row = await db.fetchrow(
            """
            INSERT INTO tasks (project_id, bucket_id, title, description, priority, due_date, position)
            VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *
            """,
            project_id,
            bucket_id,
            task_data.get("title", "Task senza titolo"),
            task_data.get("description"),
            task_data.get("priority", "normal"),
            due_date,
            position,
        )
        created.append(dict(row))
    return created


async def process_chat(
    db: asyncpg.Connection,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    message: str,
) -> dict:
    context = await _get_workspace_context(db, workspace_id)
    now = datetime.now(timezone.utc).isoformat()

    system_prompt = SYSTEM_PROMPT.format(context=context, now=now)

    await _save_conversation(db, user_id, workspace_id, "user", message)

    response = await _client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    )

    raw = response.choices[0].message.content
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"tasks": [], "reply": raw}

    reply = parsed.get("reply", "")
    ai_tasks = parsed.get("tasks", [])

    await _save_conversation(db, user_id, workspace_id, "assistant", reply)

    created_tasks = await _create_tasks_from_ai(db, ai_tasks, user_id)

    return {"reply": reply, "tasks_created": created_tasks}


async def generate_summary(
    db: asyncpg.Connection,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    summary_type: str,
) -> dict:
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    if summary_type == "weekly":
        since = now - timedelta(days=7)
        period_label = "questa settimana"
    else:
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_label = "oggi"

    completed = await db.fetchval(
        """
        SELECT COUNT(*) FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE p.workspace_id = $1 AND t.updated_at >= $2
        """,
        workspace_id, since,
    )
    overdue = await db.fetchval(
        """
        SELECT COUNT(*) FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE p.workspace_id = $1 AND t.due_date < $2
        """,
        workspace_id, now,
    )
    due_soon = await db.fetchval(
        """
        SELECT COUNT(*) FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE p.workspace_id = $1 AND t.due_date BETWEEN $2 AND $3
        """,
        workspace_id, now, now + timedelta(days=2),
    )
    total_minutes = await db.fetchval(
        """
        SELECT COALESCE(SUM(te.minutes), 0) FROM time_entries te
        JOIN tasks t ON t.id = te.task_id
        JOIN projects p ON p.id = t.project_id
        WHERE p.workspace_id = $1 AND te.started_at >= $2
        """,
        workspace_id, since,
    )

    stats = (
        f"Task completati {period_label}: {completed}. "
        f"Task in scadenza a breve: {due_soon}. "
        f"Task scaduti: {overdue}. "
        f"Minuti tracciati: {total_minutes}."
    )

    response = await _client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "Sei l'assistente AI di Done. Genera un riepilogo narrativo in italiano basato sulle statistiche fornite.",
            },
            {"role": "user", "content": stats},
        ],
    )

    summary_text = response.choices[0].message.content

    return {
        "summary": summary_text,
        "tasks_completed": completed,
        "tasks_overdue": overdue,
        "tasks_due_soon": due_soon,
        "total_minutes_tracked": total_minutes,
    }


async def suggest_subtasks(
    db: asyncpg.Connection,
    task_id: uuid.UUID,
) -> list[str]:
    task = await db.fetchrow("SELECT title, description FROM tasks WHERE id = $1", task_id)
    if not task:
        return []

    prompt = f'Task: "{task["title"]}"'
    if task["description"]:
        prompt += f'\nDescrizione: {task["description"]}'
    prompt += "\n\nSuggerisci 3-7 subtask realistici e specifici per completare questo task. Rispondi con un oggetto JSON: {\"subtasks\": [\"subtask1\", \"subtask2\", ...]}"

    response = await _client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Sei l'assistente AI di Done. Suggerisci subtask pratici in italiano.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    raw = response.choices[0].message.content
    try:
        parsed = json.loads(raw)
        return parsed.get("subtasks", [])
    except json.JSONDecodeError:
        return []
