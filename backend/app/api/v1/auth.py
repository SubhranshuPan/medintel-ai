"""Authentication endpoints: register and login."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import create_access_token
from app.repositories.user import UserRepository
from app.schemas.auth import Token, UserCreate, UserRead
from app.services.auth import AuthService, EmailAlreadyRegisteredError

router = APIRouter(prefix="/auth", tags=["auth"])


def _service(db: AsyncSession) -> AuthService:
    return AuthService(UserRepository(db))


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    """Create an account and return its public representation."""
    try:
        user = await _service(db).register(data)
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from None
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Verify credentials (OAuth2 form: ``username`` = email) and issue a JWT."""
    user = await _service(db).authenticate(form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=str(user.id), role=user.role.value)
    return Token(access_token=token)
