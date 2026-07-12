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

## Docker Compose (full stack)
From the **repo root**, bring up api + PostgreSQL + Qdrant:
```bash
docker compose up --build
```
- API: http://localhost:8000 · Docs: `/docs` · Postgres: `5432` · Qdrant: `6333`
- The `api` container waits for a healthy Postgres, runs `alembic upgrade head`,
  then serves. Postgres data persists in the named volume `pgdata`.
- Image is multi-stage (`uv`) and runs as a **non-root** user.

```bash
docker compose up -d --build      # detached
docker compose logs -f api        # tail api logs
docker compose down               # stop (keep volumes)
docker compose down -v            # stop + wipe data volumes
```

Health probes: `GET /api/v1/health` (liveness) · `GET /api/v1/health/ready`
(readiness — 200 when the DB is reachable, else 503).

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
  api/v1/health.py   # GET /api/v1/health (+ /health/ready)
  api/v1/auth.py     # POST /auth/register, /auth/login (JWT)
  api/v1/users.py    # GET /users/me, admin-only GET /users
  api/deps.py        # get_current_user, require_role RBAC
  core/security.py   # bcrypt hashing + JWT issue/verify
  schemas/           # Pydantic request/response contracts
  services/          # AuthService (business logic over repositories)
  models/            # SQLAlchemy models: user, conversation, message,
                     #   document, embedding, citation (+ base mixins)
  repositories/      # BaseRepository[ModelT] — async data-access layer
alembic/             # migration environment (async) + versions/
tests/               # pytest + httpx TestClient
```

### Planned (subsequent sprints)
- Frontend (React/Vite) initialization (#10)
- ML risk engine, RAG decision support, reporting pillars
