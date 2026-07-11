# MedIntel AI — Backend

FastAPI service for the MedIntel AI clinical intelligence platform. Modular
monolith, repository/service pattern (see `docs/architecture/adr/` and
`docs/05_BACKEND_DESIGN.md`).

## Requirements
- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16 (for the database layer / migrations)

## Quickstart
```bash
uv sync                 # create venv + install deps
cp .env.example .env    # optional; sensible defaults exist
uv run uvicorn app.main:app --reload
```
API: http://localhost:8000 · Docs: http://localhost:8000/docs
Health: http://localhost:8000/api/v1/health

## Database & migrations
Models live in `app/models/` (SQLAlchemy 2.0, async — ADR-013). The async engine
and `get_db()` session dependency are in `app/core/db.py`. Data access goes
through repositories (`app/repositories/`), never raw ORM in the API layer.

```bash
# Point MEDINTEL_DATABASE_URL at a running Postgres, then:
uv run alembic upgrade head          # apply migrations
uv run alembic downgrade base        # revert
uv run alembic revision --autogenerate -m "describe change"
uv run alembic check                 # fail if models drift from migrations
```

A throwaway Postgres for local work:
```bash
docker run -d --name medintel-pg -e POSTGRES_USER=medintel \
  -e POSTGRES_PASSWORD=medintel -e POSTGRES_DB=medintel -p 5432:5432 postgres:16
```
(Compose wiring for api + postgres + qdrant lands in #8.)

## Dev
```bash
uv run ruff check app tests   # lint
uv run pytest                 # tests
```

## Layout
```
app/
  main.py            # create_app() factory + ASGI app
  core/config.py     # typed settings (pydantic-settings, MEDINTEL_ prefix)
  core/logging.py    # logging setup
  core/db.py         # async engine, session factory, get_db dependency
  api/router.py      # aggregates /api/v1
  api/v1/health.py   # GET /api/v1/health
  models/            # SQLAlchemy models: user, conversation, message,
                     #   document, embedding, citation (+ base mixins)
  repositories/      # BaseRepository[ModelT] — async data-access layer
alembic/             # migration environment (async) + versions/
tests/               # pytest + httpx TestClient
```

### Planned (subsequent Sprint 1 issues)
- `services/`, `api/v1/auth.py` — JWT + bcrypt + RBAC auth (#7)
- `Dockerfile`, `docker-compose.yml` — api + postgres + qdrant (#8)
