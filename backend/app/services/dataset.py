"""Dataset upload use-case: immutable artifact storage + v1 metadata (ADR-009)."""

import asyncio
import io
from uuid import UUID

import pandas as pd

from app.core.config import Settings
from app.models.dataset import Dataset, DatasetVersion, ValidationStatus, VersionOrigin
from app.models.user import User, UserRole
from app.repositories.dataset import DatasetRepository, DatasetVersionRepository
from app.services.cleaning import clean
from app.services.validation import validate
from app.storage.object_store import ObjectStore, sha256_hex


class DatasetError(Exception):
    """Base class for dataset use-case failures."""


class InvalidCsvError(DatasetError):
    """The uploaded bytes could not be parsed as a CSV."""


class UploadTooLargeError(DatasetError):
    """The uploaded content exceeds the configured size cap."""


class DatasetNotFoundError(DatasetError):
    """No live dataset with this id."""


class DatasetForbiddenError(DatasetError):
    """The requester is neither the dataset's owner nor an admin."""


class DatasetService:
    """Dataset use-cases backed by the repository/store layers."""

    def __init__(
        self,
        datasets: DatasetRepository,
        versions: DatasetVersionRepository,
        store: ObjectStore,
        settings: Settings,
    ) -> None:
        self.datasets = datasets
        self.versions = versions
        self.store = store
        self.settings = settings

    async def create_from_upload(
        self,
        *,
        name: str,
        description: str | None,
        filename: str | None,
        content: bytes,
        owner: User,
    ) -> tuple[Dataset, DatasetVersion]:
        """Store the raw CSV immutably and create the dataset + v1 metadata row.

        The bytes are stored EXACTLY as uploaded — no normalisation, no cleaning.
        Anything derived comes later as a new version (ADR-009).
        """
        if len(content) > self.settings.max_upload_bytes:
            raise UploadTooLargeError(len(content))

        try:
            df = pd.read_csv(io.BytesIO(content))
        except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
            raise InvalidCsvError(str(exc)) from exc

        uri = self.store.put(content)
        checksum = sha256_hex(content)
        schema_hash = sha256_hex(
            ",".join(f"{c}:{df.dtypes[c]}" for c in df.columns).encode()
        )
        # CPU-bound sync validation dispatched off the event loop (ADR-014).
        passed, report = await asyncio.to_thread(validate, df)

        dataset = await self.datasets.add(
            Dataset(name=name, description=description, owner_id=owner.id)
        )
        version = await self.versions.add(
            DatasetVersion(
                dataset_id=dataset.id,
                version_number=1,
                origin=VersionOrigin.upload,
                storage_uri=uri,
                checksum=checksum,
                size_bytes=len(content),
                original_filename=filename,
                row_count=len(df),
                column_names=list(df.columns),
                schema_hash=schema_hash,
                validation_status=ValidationStatus.passed if passed else ValidationStatus.failed,
                validation_report=report,
                created_by_id=owner.id,
            )
        )
        return dataset, version

    async def revalidate_latest(self, dataset_id: UUID, *, requester: User) -> DatasetVersion:
        """Re-run validation against the latest version's stored bytes.

        The single sanctioned mutation of a persisted ``DatasetVersion``: it
        updates only the validation verdict, never the stored artifact or any
        other field (ADR-009 immutability applies to everything else).

        Owner-or-admin only: the response echoes ``validation_report``, which
        can carry raw row values (pandera's ``failure_cases``) from the
        dataset's own data — patient-level content per TRD §9, so a stranger
        must not be able to pull it via another user's dataset id.
        """
        dataset = await self.datasets.get_active(dataset_id)
        if dataset is None:
            raise DatasetNotFoundError(dataset_id)
        if dataset.owner_id != requester.id and requester.role != UserRole.admin:
            raise DatasetForbiddenError(dataset_id)

        versions = await self.versions.list_for_dataset(dataset_id)
        latest = versions[-1]

        content = self.store.get(latest.storage_uri)
        df = pd.read_csv(io.BytesIO(content))
        passed, report = await asyncio.to_thread(validate, df)

        latest.validation_status = ValidationStatus.passed if passed else ValidationStatus.failed
        latest.validation_report = report
        return await self.versions.add(latest)

    async def clean_latest(self, dataset_id: UUID, *, requester: User) -> DatasetVersion:
        """Derive a NEW version from the dataset's latest version (ADR-009, #34).

        The parent version's bytes and row are untouched — cleaning never
        mutates a version in place. The child records ``parent_version_id``,
        ``origin=cleaned`` and the ``transformation`` report, so the lineage
        from raw upload to trained model stays reconstructable.

        Owner-or-admin only, same rationale as ``revalidate_latest``: the
        response echoes derived content from the dataset's own data.
        """
        dataset = await self.datasets.get_active(dataset_id)
        if dataset is None:
            raise DatasetNotFoundError(dataset_id)
        if dataset.owner_id != requester.id and requester.role != UserRole.admin:
            raise DatasetForbiddenError(dataset_id)

        versions = await self.versions.list_for_dataset(dataset_id)
        parent = versions[-1]

        content = self.store.get(parent.storage_uri)
        df = pd.read_csv(io.BytesIO(content))
        cleaned_df, transformation = await asyncio.to_thread(clean, df)
        cleaned_bytes = cleaned_df.to_csv(index=False).encode()

        uri = self.store.put(cleaned_bytes)
        checksum = sha256_hex(cleaned_bytes)
        schema_hash = sha256_hex(
            ",".join(f"{c}:{cleaned_df.dtypes[c]}" for c in cleaned_df.columns).encode()
        )
        passed, report = await asyncio.to_thread(validate, cleaned_df)
        version_number = await self.versions.next_version_number(dataset_id)

        child = DatasetVersion(
            dataset_id=dataset_id,
            version_number=version_number,
            parent_version_id=parent.id,
            origin=VersionOrigin.cleaned,
            storage_uri=uri,
            checksum=checksum,
            size_bytes=len(cleaned_bytes),
            original_filename=parent.original_filename,
            row_count=len(cleaned_df),
            column_names=list(cleaned_df.columns),
            schema_hash=schema_hash,
            validation_status=ValidationStatus.passed if passed else ValidationStatus.failed,
            validation_report=report,
            transformation=transformation,
            created_by_id=requester.id,
        )
        return await self.versions.add(child)
