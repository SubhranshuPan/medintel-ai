"""Dataset / DatasetVersion persistence."""

from uuid import UUID

from sqlalchemy import func, select

from app.models.dataset import Dataset, DatasetVersion
from app.repositories.base import BaseRepository


class DatasetRepository(BaseRepository[Dataset]):
    """CRUD for :class:`Dataset`, plus soft-delete-aware queries."""

    model = Dataset

    async def list_active(
        self, *, owner_id: UUID | None = None, limit: int = 100, offset: int = 0
    ) -> list[Dataset]:
        """Live (not soft-deleted) datasets, newest first.

        ``owner_id=None`` returns across all owners (admin view); callers
        enforcing per-user isolation must pass the requester's id.
        """
        stmt = select(Dataset).where(Dataset.deleted_at.is_(None))
        if owner_id is not None:
            stmt = stmt.where(Dataset.owner_id == owner_id)
        result = await self.session.execute(
            stmt.order_by(Dataset.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def get_active(self, id_: UUID) -> Dataset | None:
        """Live (not soft-deleted) dataset by id, or ``None``."""
        result = await self.session.execute(
            select(Dataset).where(Dataset.id == id_, Dataset.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()


class DatasetVersionRepository(BaseRepository[DatasetVersion]):
    """CRUD for :class:`DatasetVersion`, plus lineage-ordered queries."""

    model = DatasetVersion

    async def list_for_dataset(self, dataset_id: UUID) -> list[DatasetVersion]:
        """Version history, oldest -> newest (lineage order)."""
        result = await self.session.execute(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number)
        )
        return list(result.scalars().all())

    async def get_latest_for_dataset(self, dataset_id: UUID) -> DatasetVersion | None:
        """Most recent version by ``version_number``, or ``None`` if none exist."""
        result = await self.session.execute(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def next_version_number(self, dataset_id: UUID) -> int:
        """``max(version_number) + 1`` for this dataset (1 if none exist)."""
        result = await self.session.execute(
            select(func.coalesce(func.max(DatasetVersion.version_number), 0)).where(
                DatasetVersion.dataset_id == dataset_id
            )
        )
        return int(result.scalar_one()) + 1
