"""Dataset upload use-case: immutable artifact storage + v1 metadata (ADR-009)."""

import io

import pandas as pd

from app.core.config import Settings
from app.models.dataset import Dataset, DatasetVersion, ValidationStatus, VersionOrigin
from app.models.user import User
from app.repositories.dataset import DatasetRepository, DatasetVersionRepository
from app.storage.object_store import ObjectStore, sha256_hex


class DatasetError(Exception):
    """Base class for dataset use-case failures."""


class InvalidCsvError(DatasetError):
    """The uploaded bytes could not be parsed as a CSV."""


class UploadTooLargeError(DatasetError):
    """The uploaded content exceeds the configured size cap."""


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
                validation_status=ValidationStatus.pending,
                created_by_id=owner.id,
            )
        )
        return dataset, version
