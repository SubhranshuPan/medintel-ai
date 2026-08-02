"""Settings guards: the placeholder JWT secret must not reach a deployment."""

import pytest

from app.core.config import PLACEHOLDER_JWT_SECRET, Settings


def test_placeholder_secret_allowed_in_development() -> None:
    assert Settings(environment="development").jwt_secret == PLACEHOLDER_JWT_SECRET


def test_placeholder_secret_rejected_in_production() -> None:
    with pytest.raises(ValueError, match="MEDINTEL_JWT_SECRET"):
        Settings(environment="production", jwt_secret=PLACEHOLDER_JWT_SECRET)


def test_weak_secret_rejected_in_production() -> None:
    with pytest.raises(ValueError, match="MEDINTEL_JWT_SECRET"):
        Settings(environment="production", jwt_secret="too-short")


def test_typo_environment_fails_closed() -> None:
    """A near-miss environment name is treated as non-local, not as dev."""
    with pytest.raises(ValueError, match="MEDINTEL_JWT_SECRET"):
        Settings(environment="develop", jwt_secret=PLACEHOLDER_JWT_SECRET)


def test_unset_environment_defaults_to_production(monkeypatch) -> None:
    monkeypatch.delenv("MEDINTEL_ENVIRONMENT", raising=False)
    monkeypatch.delenv("MEDINTEL_JWT_SECRET", raising=False)

    with pytest.raises(ValueError, match="MEDINTEL_JWT_SECRET"):
        Settings(_env_file=None)
