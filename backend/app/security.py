"""Password hashing, session token creation and verification, and
encryption of stored third-party secrets. The only module that touches
argon2, JWT or the encryption library directly."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

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


class SecretStoreUnavailableError(RuntimeError):
    """No encryption key is configured, so no secret can be stored or read."""


class SecretUnreadableError(RuntimeError):
    """A stored secret cannot be decrypted, most likely because the key
    changed since it was stored."""


def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        raise SecretStoreUnavailableError("TOKEN_ENCRYPTION_KEY is not set")
    try:
        return Fernet(key.encode())
    except ValueError as error:
        raise SecretStoreUnavailableError("TOKEN_ENCRYPTION_KEY is not a valid key") from error


def encrypt_secret(secret: str) -> str:
    """Ciphertext for a third-party secret such as a GitHub token, so it is
    never stored in plain text (US-26 criterion 3)."""
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as error:
        raise SecretUnreadableError("The stored secret cannot be decrypted") from error
