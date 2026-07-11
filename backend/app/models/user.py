"""User account model and RBAC roles."""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class UserRole(enum.StrEnum):
    """Role-based access control roles (enforced by the auth layer, #7)."""

    clinician = "clinician"
    analyst = "analyst"
    admin = "admin"


class User(UUIDMixin, TimestampMixin, Base):
    """An authenticated platform user."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.clinician
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
