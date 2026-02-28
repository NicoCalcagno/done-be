# done-be

Backend dell'app **Done**, un task manager personale AI-powered.

## Stack

- **Python 3.11** · FastAPI + Uvicorn (async)
- **PostgreSQL 15** · asyncpg (no ORM)
- **Alembic** per le migration
- **OpenAI** GPT-4o + Whisper
- **Docker + Docker Compose**

## Setup

```bash
cp .env.example .env
# Inserisci SECRET_KEY e OPENAI_API_KEY nel .env

docker compose up --build
docker compose exec backend alembic upgrade head
```

Il backend è disponibile su `http://localhost:8000`.
Documentazione interattiva: `http://localhost:8000/docs`

## Comandi utili

```bash
# Avvia stack completo con hot reload
docker compose up

# Esegui le migration
docker compose exec backend alembic upgrade head

# Crea una nuova migration
docker compose exec backend alembic revision --autogenerate -m "descrizione"

# Rollback dell'ultima migration
docker compose exec backend alembic downgrade -1
```

## Variabili d'ambiente

| Variabile | Descrizione |
|---|---|
| `DATABASE_URL` | URL di connessione PostgreSQL |
| `SECRET_KEY` | Chiave per la firma dei JWT |
| `OPENAI_API_KEY` | API key OpenAI (GPT-4o + Whisper) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Durata access token (default: 30) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Durata refresh token (default: 7) |

## API

Prefisso base: `/api/v1`
Tutte le route tranne `/health` e `/api/v1/auth/*` richiedono `Authorization: Bearer <token>`.
