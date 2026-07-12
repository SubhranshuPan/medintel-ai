"""Password hashing and JWT issue/verify.

Single home for credential crypto so no other module reaches for passlib or
jose directly. Never log the plaintext password, hash, or token from here.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

# bcrypt hashes at most the first 72 bytes of the secret (its documented
# behaviour; bcrypt 5.x raises rather than truncating). We truncate explicitly
# and consistently in both hash and verify so long passwords remain usable.
_BCRYPT_MAX_BYTES = 72


def _secret_bytes(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of ``plain``."""
    return bcrypt.hashpw(_secret_bytes(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Return whether ``plain`` matches the stored bcrypt ``hashed`` value."""
    return bcrypt.checkpw(_secret_bytes(plain), hashed.encode("ascii"))


def create_access_token(subject: str, role: str) -> str:
    """Mint a signed JWT for ``subject`` (user id) carrying its RBAC ``role``.

    The ``role`` claim is INFORMATIONAL ONLY. Authorization always re-reads the
    role from the database (see ``app.api.deps.require_role``) so that role
    changes and deactivations take effect immediately — never trust this claim
    for an access-control decision.
    """
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    """Return the token claims, or ``None`` if invalid/expired/tampered."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
