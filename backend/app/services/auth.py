"""Registration and credential verification.

Keeps password hashing and the duplicate-email rule out of the API layer.
"""

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import UserCreate

# Precomputed hash used to spend the same bcrypt time on the "no such user"
# path as on a real verify, so login latency doesn't leak which emails exist.
_DUMMY_HASH = hash_password("dummy-password-for-constant-time-login")


def normalize_email(email: str) -> str:
    """Canonicalize an email for storage and lookup (case/space-insensitive)."""
    return email.strip().lower()


class EmailAlreadyRegisteredError(Exception):
    """Raised when registering an email that already has an account."""


class AuthService:
    """Auth use-cases backed by :class:`UserRepository`."""

    def __init__(self, users: UserRepository) -> None:
        self.users = users

    async def register(self, data: UserCreate) -> User:
        """Create a new account, hashing the password. Rejects duplicate email."""
        email = normalize_email(data.email)
        if await self.users.get_by_email(email):
            raise EmailAlreadyRegisteredError(email)
        # No role from the payload — registrants are always clinicians (see
        # UserCreate); the model default enforces this.
        user = User(
            email=email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )
        return await self.users.add(user)

    async def authenticate(self, email: str, password: str) -> User | None:
        """Return the user if credentials are valid and the account is active."""
        user = await self.users.get_by_email(normalize_email(email))
        if user is None or not user.is_active:
            # Spend equivalent bcrypt time so a missing/inactive account isn't
            # distinguishable from a wrong password by response latency.
            verify_password(password, _DUMMY_HASH)
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
