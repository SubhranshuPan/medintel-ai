"""Dataset / DatasetVersion model constraints (#30) and upload endpoint (#32)."""

import asyncio
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.deps import get_object_store
from app.models.audit import AuditLog
from app.models.dataset import Dataset, DatasetVersion, ValidationStatus, VersionOrigin
from app.models.user import User
from app.storage.object_store import LocalObjectStore

_CSV = b"patient_id,age\np1,40\np2,55\n"


def _make_version(dataset_id, created_by_id, version_number: int) -> DatasetVersion:
    return DatasetVersion(
        dataset_id=dataset_id,
        version_number=version_number,
        storage_uri="file://deadbeef",
        checksum="deadbeef" * 8,
        size_bytes=123,
        created_by_id=created_by_id,
    )


def test_version_number_unique_per_dataset(
    _engine: AsyncEngine, seed_user: Callable[..., User]
) -> None:
    owner = seed_user("owner@nhs.uk", "s3cret-pass")
    factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    async def _run() -> tuple[bool, bool]:
        async with factory() as session:
            dataset_a = Dataset(name="Cohort A", owner_id=owner.id)
            dataset_b = Dataset(name="Cohort B", owner_id=owner.id)
            session.add_all([dataset_a, dataset_b])
            await session.flush()
            # Capture ids before any rollback expires the ORM attributes —
            # async lazy-refresh of an expired attribute raises MissingGreenlet.
            dataset_a_id, dataset_b_id = dataset_a.id, dataset_b.id

            session.add(_make_version(dataset_a_id, owner.id, 1))
            await session.commit()

            # Same dataset, same version_number -> IntegrityError.
            session.add(_make_version(dataset_a_id, owner.id, 1))
            dupe_raised = False
            try:
                await session.commit()
            except IntegrityError:
                dupe_raised = True
                await session.rollback()

            # Same version_number under a DIFFERENT dataset is fine.
            session.add(_make_version(dataset_b_id, owner.id, 1))
            await session.commit()
            cross_dataset_ok = True
            return dupe_raised, cross_dataset_ok

    dupe_raised, cross_dataset_ok = asyncio.run(_run())
    assert dupe_raised
    assert cross_dataset_ok


def test_version_defaults(_engine: AsyncEngine, seed_user: Callable[..., User]) -> None:
    owner = seed_user("owner2@nhs.uk", "s3cret-pass")
    factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    async def _run() -> DatasetVersion:
        async with factory() as session:
            dataset = Dataset(name="Cohort", owner_id=owner.id)
            session.add(dataset)
            await session.flush()
            version = _make_version(dataset.id, owner.id, 1)
            session.add(version)
            await session.commit()
            await session.refresh(version)
            return version

    version = asyncio.run(_run())
    assert version.validation_status == ValidationStatus.pending
    assert version.origin == VersionOrigin.upload


def test_dataset_version_enums() -> None:
    assert {s.value for s in ValidationStatus} == {"pending", "passed", "failed"}
    assert {o.value for o in VersionOrigin} == {"upload", "cleaned"}


def _override_store(client: TestClient, tmp_path) -> None:
    client.app.dependency_overrides[get_object_store] = lambda: LocalObjectStore(
        tmp_path / "store"
    )


def _register_and_login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-pass"})
    resp = client.post(
        "/api/v1/auth/login", data={"username": email, "password": "s3cret-pass"}
    )
    return resp.json()["access_token"]


def _upload(
    client: TestClient,
    token: str,
    *,
    name: str = "Cohort",
    filename: str = "cohort.csv",
    content: bytes = _CSV,
    content_type: str = "text/csv",
):
    return client.post(
        "/api/v1/datasets",
        data={"name": name},
        files={"file": (filename, content, content_type)},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_upload_creates_dataset_and_v1(client: TestClient, tmp_path) -> None:
    _override_store(client, tmp_path)
    token = _register_and_login(client, "up@nhs.uk")

    resp = _upload(client, token)

    assert resp.status_code == 201
    body = resp.json()
    assert body["latest_version"]["version_number"] == 1
    assert body["latest_version"]["row_count"] == 2
    assert body["latest_version"]["validation_status"] == "passed"


def test_upload_requires_auth(client: TestClient, tmp_path) -> None:
    _override_store(client, tmp_path)

    resp = client.post(
        "/api/v1/datasets", data={"name": "Cohort"}, files={"file": ("c.csv", _CSV, "text/csv")}
    )

    assert resp.status_code == 401


def test_upload_rejects_non_csv(client: TestClient, tmp_path) -> None:
    _override_store(client, tmp_path)
    token = _register_and_login(client, "nc@nhs.uk")

    resp = _upload(client, token, filename="cohort.txt", content_type="text/plain")

    assert resp.status_code == 415


def test_upload_rejects_malformed_csv(client: TestClient, tmp_path) -> None:
    _override_store(client, tmp_path)
    token = _register_and_login(client, "bad@nhs.uk")

    resp = _upload(client, token, content=b"")

    assert resp.status_code == 422


def test_identical_content_is_stored_once(client: TestClient, tmp_path) -> None:
    _override_store(client, tmp_path)
    token = _register_and_login(client, "dup@nhs.uk")

    first = _upload(client, token, name="Cohort A")
    second = _upload(client, token, name="Cohort B")

    assert (
        first.json()["latest_version"]["checksum"] == second.json()["latest_version"]["checksum"]
    )


def test_upload_is_audited(
    client: TestClient, tmp_path, audit_rows: Callable[[], list[AuditLog]]
) -> None:
    _override_store(client, tmp_path)
    token = _register_and_login(client, "aud@nhs.uk")

    resp = _upload(client, token)
    dataset_id = resp.json()["id"]

    rows = [r for r in audit_rows() if r.status_code == 201]
    assert len(rows) == 1
    assert rows[0].resource_id == dataset_id


def test_upload_with_duplicate_rows_is_stored_and_marked_failed(
    client: TestClient, tmp_path
) -> None:
    _override_store(client, tmp_path)
    token = _register_and_login(client, "invalid@nhs.uk")

    resp = _upload(client, token, content=b"patient_id,age\np1,40\np1,40\n")

    # ADR-009: a failed validation never rejects the upload.
    assert resp.status_code == 201
    body = resp.json()["latest_version"]
    assert body["validation_status"] == "failed"
    assert body["validation_report"]["failure_count"] > 0


def test_revalidate_returns_current_verdict(client: TestClient, tmp_path) -> None:
    _override_store(client, tmp_path)
    token = _register_and_login(client, "reval@nhs.uk")
    dataset_id = _upload(client, token).json()["id"]

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/validate", headers={"Authorization": f"Bearer {token}"}
    )

    assert resp.status_code == 200
    assert resp.json()["validation_status"] == "passed"


def test_revalidate_requires_auth(client: TestClient, tmp_path) -> None:
    _override_store(client, tmp_path)
    token = _register_and_login(client, "reval2@nhs.uk")
    dataset_id = _upload(client, token).json()["id"]

    resp = client.post(f"/api/v1/datasets/{dataset_id}/validate")

    assert resp.status_code == 401


def test_revalidate_non_owner_is_forbidden(client: TestClient, tmp_path) -> None:
    _override_store(client, tmp_path)
    owner_token = _register_and_login(client, "owner-reval@nhs.uk")
    dataset_id = _upload(client, owner_token).json()["id"]
    stranger_token = _register_and_login(client, "stranger-reval@nhs.uk")

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/validate",
        headers={"Authorization": f"Bearer {stranger_token}"},
    )

    assert resp.status_code == 403


def test_revalidate_unknown_dataset_404s(client: TestClient, tmp_path) -> None:
    _override_store(client, tmp_path)
    token = _register_and_login(client, "reval3@nhs.uk")

    resp = client.post(
        "/api/v1/datasets/00000000-0000-0000-0000-000000000000/validate",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 404
