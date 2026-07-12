"""User endpoints — demonstrates authenticated and role-gated access."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.core.db import get_db
from app.models.user import UserRole
from app.repositories.user import UserRepository
from app.schemas.auth import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_me(current_user: CurrentUser) -> UserRead:
    """Return the authenticated user's own profile."""
    return UserRead.model_validate(current_user)


@router.get(
    "",
    response_model=list[UserRead],
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserRead]:
    """List accounts — admin only (returns 403 for other roles)."""
    users = await UserRepository(db).list()
    return [UserRead.model_validate(u) for u in users]
