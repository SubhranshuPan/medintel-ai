"""Auth request/response contracts."""

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    """Registration payload.

    Deliberately has no ``role`` field: self-registration always yields a
    ``clinician``. Privileged roles are provisioned out-of-band (seed/admin
    action), never chosen by the registrant — otherwise anyone could self-grant
    ``admin``.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserRead(BaseModel):
    """Public user representation (never exposes the password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool


class Token(BaseModel):
    """OAuth2 bearer token response."""

    access_token: str
    token_type: str = "bearer"
