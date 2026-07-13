"""Dataset / DatasetVersion model constraints (models-only; no endpoints yet, #30)."""

import asyncio
from collections.abc import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.dataset import Dataset, DatasetVersion, ValidationStatus, VersionOrigin
from app.models.user import User


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
