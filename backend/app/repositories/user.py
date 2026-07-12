"""User persistence — the only place auth flows load/store accounts."""

from sqlalchemy import select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """CRUD for :class:`User`, plus email lookup for login/registration."""

    model = User

    async def get_by_email(self, email: str) -> User | None:
        """Return the account for this email, or ``None``."""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
