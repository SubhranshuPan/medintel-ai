"""AuditLogMiddleware: every request under an audited path prefix is recorded.

Only ``POST /api/v1/datasets`` exists until #35 adds the read/delete surface,
so a GET here 405s (path matches, method doesn't) rather than 404ing. That is
still enough to prove prefix-based interception: the middleware audits by
path, before routing decides whether the method is allowed.
"""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.audit import AuditLog
from app.models.user import User


def test_non_audited_path_is_not_recorded(
    client: TestClient, audit_rows: Callable[[], list[AuditLog]]
) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert audit_rows() == []


def test_unauthenticated_dataset_prefix_request_is_audited(
    client: TestClient, audit_rows: Callable[[], list[AuditLog]]
) -> None:
    resp = client.get("/api/v1/datasets")
    assert resp.status_code == 405  # GET not allowed on this path — still an audited path

    rows = audit_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row.status_code == 405
    assert row.actor_id is None
    assert row.action == "GET"
    assert row.resource_type == "dataset"
    assert row.path == "/api/v1/datasets"


def test_authenticated_dataset_prefix_request_records_actor(
    client: TestClient, seed_user: Callable[..., User], audit_rows: Callable[[], list[AuditLog]]
) -> None:
    seed_user("clin@nhs.uk", "s3cret-pass")
    token = client.post(
        "/api/v1/auth/login", data={"username": "clin@nhs.uk", "password": "s3cret-pass"}
    ).json()["access_token"]

    resp = client.get("/api/v1/datasets", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 405  # method not allowed — the actor capture is what's under test

    rows = audit_rows()
    assert len(rows) == 1
    assert rows[0].actor_id is not None
    assert rows[0].actor_role == "clinician"
