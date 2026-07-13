"""Shared pytest fixtures.

Auth/endpoint tests need a real database, but we don't want to require a
running Postgres for the unit suite. Each test gets an isolated file-backed
SQLite database (``NullPool`` so connections are loop-agnostic across the
TestClient worker thread and the seeding helpers), with ``get_db`` overridden
to use it.
"""

import asyncio
from collections.abc import AsyncGenerator, Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

import app.core.audit as audit_module
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models import Base
from app.models.audit import AuditLog
from app.models.user import User, UserRole


@pytest.fixture
def _engine(tmp_path) -> Iterator[AsyncEngine]:
    """Isolated SQLite engine with the schema created."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(
        url, poolclass=NullPool, connect_args={"check_same_thread": False}
    )

    # WAL + busy_timeout: with NullPool each checkout is a fresh sqlite
    # connection, and the request's own session plus AuditLogMiddleware's
    # separate session can otherwise hit "database is locked" (SQLite's
    # default journal mode takes an exclusive lock on commit, and the default
    # busy timeout is 0). WAL lets a writer and the not-yet-closed reader
    # coexist; busy_timeout makes SQLite retry briefly instead of erroring.
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    async def _create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
def client(_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """TestClient bound to a fresh app using the isolated database."""
    session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_test_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # AuditLogMiddleware imports AsyncSessionLocal directly (middleware can't
    # use FastAPI DI), so dependency_overrides never reaches it — without this,
    # audited requests in tests would write to the developer's real Postgres.
    monkeypatch.setattr(audit_module, "AsyncSessionLocal", session_factory)

    app = create_app()
    app.dependency_overrides[get_db] = _get_test_db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seed_user(_engine: AsyncEngine) -> Callable[..., User]:
    """Insert a user directly (simulates out-of-band provisioning, e.g. an admin)."""
    factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    def _seed(email: str, password: str, role: UserRole = UserRole.clinician) -> User:
        async def _insert() -> User:
            async with factory() as session:
                user = User(
                    email=email, hashed_password=hash_password(password), role=role
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return user

        return asyncio.run(_insert())

    return _seed


@pytest.fixture
def audit_rows(_engine: AsyncEngine) -> Callable[[], list[AuditLog]]:
    """Read back every ``AuditLog`` row written during the test."""
    factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    def _rows() -> list[AuditLog]:
        async def _select() -> list[AuditLog]:
            async with factory() as session:
                result = await session.execute(select(AuditLog))
                return list(result.scalars().all())

        return asyncio.run(_select())

    return _rows
