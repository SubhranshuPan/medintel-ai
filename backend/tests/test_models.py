"""Model-layer sanity checks that require no database.

Guards the declarative registry: all entities register, mappers configure, and
key relationships/enums exist. DB round-trips are covered by the Alembic
migration verification and integration tests (added with Docker, #8).
"""

from sqlalchemy.orm import configure_mappers

from app.models import (
    Base,
    Conversation,
    MessageRole,
    User,
    UserRole,
)


def test_all_tables_registered() -> None:
    configure_mappers()
    assert set(Base.metadata.tables) == {
        "users",
        "conversations",
        "messages",
        "documents",
        "embeddings",
        "citations",
        "datasets",
        "dataset_versions",
    }


def test_user_conversation_relationship() -> None:
    assert "conversations" in User.__mapper__.relationships
    assert "user" in Conversation.__mapper__.relationships


def test_role_enums() -> None:
    assert {r.value for r in UserRole} == {"clinician", "analyst", "admin"}
    assert {r.value for r in MessageRole} == {"user", "assistant", "system"}
