"""Auth flow: registration, login, token validation, and RBAC enforcement."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import get_settings
from app.models.user import User, UserRole


def _login(client: TestClient, email: str, password: str):
    return client.post("/api/v1/auth/login", data={"username": email, "password": password})


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_hashes_password_and_returns_user(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "doc@nhs.uk", "password": "s3cret-pass", "full_name": "Dr Who"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "doc@nhs.uk"
    assert body["role"] == "clinician"
    # The password (hash or plaintext) must never appear in the response.
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    payload = {"email": "dupe@nhs.uk", "password": "s3cret-pass"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_login_returns_valid_jwt(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json={"email": "a@nhs.uk", "password": "s3cret-pass"})
    resp = _login(client, "a@nhs.uk", "s3cret-pass")
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/api/v1/users/me", headers=_bearer(token))
    assert me.status_code == 200
    assert me.json()["email"] == "a@nhs.uk"


def test_login_wrong_password_is_401(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json={"email": "b@nhs.uk", "password": "s3cret-pass"})
    assert _login(client, "b@nhs.uk", "wrong-password").status_code == 401


def test_protected_route_rejects_missing_and_invalid_token(client: TestClient) -> None:
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.get("/api/v1/users/me", headers=_bearer("not-a-jwt")).status_code == 401


def test_expired_token_is_rejected(client: TestClient) -> None:
    settings = get_settings()
    expired = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000000", "role": "clinician",
         "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert client.get("/api/v1/users/me", headers=_bearer(expired)).status_code == 401


def test_rbac_denies_insufficient_role(
    client: TestClient, seed_user: Callable[..., User]
) -> None:
    seed_user("clin@nhs.uk", "s3cret-pass", UserRole.clinician)
    token = _login(client, "clin@nhs.uk", "s3cret-pass").json()["access_token"]
    # Admin-only route: a clinician must be forbidden.
    assert client.get("/api/v1/users", headers=_bearer(token)).status_code == 403


def test_email_is_case_insensitive(client: TestClient) -> None:
    # Register with mixed case; the account is stored normalized (lowercased).
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "Doc@NHS.uk", "password": "s3cret-pass"},
    )
    assert reg.status_code == 201
    assert reg.json()["email"] == "doc@nhs.uk"
    # Login with a different case must resolve to the same account.
    assert _login(client, "DOC@nhs.UK", "s3cret-pass").status_code == 200
    # A case variant must not be treated as a new account.
    dupe = client.post(
        "/api/v1/auth/register",
        json={"email": "doc@nhs.uk", "password": "s3cret-pass"},
    )
    assert dupe.status_code == 409


def test_rbac_allows_admin(client: TestClient, seed_user: Callable[..., User]) -> None:
    seed_user("boss@nhs.uk", "s3cret-pass", UserRole.admin)
    token = _login(client, "boss@nhs.uk", "s3cret-pass").json()["access_token"]
    resp = client.get("/api/v1/users", headers=_bearer(token))
    assert resp.status_code == 200
    assert any(u["email"] == "boss@nhs.uk" for u in resp.json())
