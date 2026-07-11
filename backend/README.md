# MedIntel AI — Backend

FastAPI service for the MedIntel AI clinical intelligence platform. Modular
monolith, repository/service pattern (see `docs/architecture/adr/` and
`docs/05_BACKEND_DESIGN.md`).

## Requirements
- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Quickstart
```bash
uv sync                 # create venv + install deps
cp .env.example .env    # optional; sensible defaults exist
uv run uvicorn app.main:app --reload
```
API: http://localhost:8000 · Docs: http://localhost:8000/docs
Health: http://localhost:8000/api/v1/health

## Dev
```bash
uv run ruff check .     # lint
uv run pytest           # tests
```

## Layout
```
app/
  main.py            # create_app() factory + ASGI app
  core/config.py     # typed settings (pydantic-settings, MEDINTEL_ prefix)
  core/logging.py    # logging setup
  api/router.py      # aggregates /api/v1
  api/v1/health.py   # GET /api/v1/health
tests/               # pytest + httpx TestClient
```

### Planned (subsequent Sprint 1 issues)
- `core/db.py`, `models/`, `repositories/` — SQLAlchemy 2.0 + Alembic (#6)
- `services/`, `api/v1/auth.py` — JWT + bcrypt + RBAC auth (#7)
- `Dockerfile`, `docker-compose.yml` — api + postgres + qdrant (#8)
