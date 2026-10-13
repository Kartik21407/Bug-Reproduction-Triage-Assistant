"""Password hashing and session token creation and verification. The only
module that touches argon2 or JWT directly."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import get_settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Returns a salted argon2 hash of the given password (NFR-03,
    US-01 criterion 4)."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Returns True when password matches the stored hash, False otherwise.
    Never raises, so callers cannot leak a mismatch through an exception."""
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def create_session_token(user_id: UUID) -> str:
    """Returns a signed JWT carrying the user id, expiring after
    SESSION_EXPIRE_MINUTES (NFR-03)."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.session_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> UUID | None:
    """Returns the user id carried by a valid, unexpired token, or None if the
    token is missing, malformed, expired or wrongly signed."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
