"""Shared FastAPI dependencies: current-user resolution and RBAC guards."""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.storage.object_store import LocalObjectStore, ObjectStore

# tokenUrl drives the Swagger "Authorize" button; must match the login route.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the bearer token to an active user, or raise 401."""
    claims = decode_access_token(token)
    if claims is None or "sub" not in claims:
        raise _credentials_error
    try:
        user_id = UUID(claims["sub"])
    except (ValueError, TypeError):
        raise _credentials_error from None
    user = await UserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise _credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(
    *allowed: UserRole,
) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Dependency factory: allow only users whose role is in ``allowed`` (else 403)."""

    async def _guard(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this resource",
            )
        return user

    return _guard


def get_object_store() -> ObjectStore:
    """Dataset artifact storage (ADR-009). Local disk in dev."""
    return LocalObjectStore(get_settings().storage_dir)
