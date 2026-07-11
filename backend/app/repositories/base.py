"""Generic async repository — the single choke point for ORM access.

Services and API handlers go through repositories rather than touching the
session directly, keeping persistence concerns out of the business/API layers
(see project-memory: repository/service pattern).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base


class BaseRepository[ModelT: Base]:
    """CRUD operations shared by all entity repositories.

    Subclasses set ``model`` to their mapped class::

        class UserRepository(BaseRepository[User]):
            model = User
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id_: UUID) -> ModelT | None:
        """Return the row with this primary key, or ``None``."""
        return await self.session.get(self.model, id_)

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        """Return a bounded page of rows (never unbounded)."""
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def add(self, obj: ModelT) -> ModelT:
        """Stage a new row and flush so server defaults populate."""
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def delete(self, obj: ModelT) -> None:
        """Delete a row (flushed with the surrounding unit of work)."""
        await self.session.delete(obj)
