"""Password hashing and JWT handling.

- Passwords: Argon2id (argon2-cffi defaults), never stored or logged in clear.
- Access tokens: short lived, signed with ``JWT_SECRET``.
- Refresh tokens: opaque random strings signed into a JWT with a separate
  secret, stored **hashed** (SHA-256) so a database leak cannot be replayed,
  and rotated on every use.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings
from app.core.exceptions import TokenError

_hasher = PasswordHasher()

TOKEN_TYPE_ACCESS: Final = "access"
TOKEN_TYPE_REFRESH: Final = "refresh"
TOKEN_TYPE_RESET: Final = "password_reset"

TokenType = Literal["access", "refresh", "password_reset"]


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, ValueError):
        return True


def hash_token(raw_token: str) -> str:
    """Refresh tokens are stored as digests, never in clear."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@dataclass(slots=True, frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    refresh_token_id: uuid.UUID
    access_expires_at: datetime
    refresh_expires_at: datetime
    token_type: str = "Bearer"


def _encode(
    *,
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    secret: str,
    extra: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
        **(extra or {}),
    }
    token = jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(token: str, *, token_type: TokenType) -> dict[str, Any]:
    secret = (
        settings.jwt_refresh_secret
        if token_type == TOKEN_TYPE_REFRESH
        else settings.jwt_secret
    )
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("The token has expired.", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError() from exc

    if payload.get("type") != token_type:
        raise TokenError("Unexpected token type.", code="token_type_mismatch")
    if not payload.get("sub"):
        raise TokenError()
    return payload


def create_token_pair(user_id: uuid.UUID, *, session_id: uuid.UUID | None = None) -> TokenPair:
    refresh_id = session_id or uuid.uuid4()
    access_token, access_expires = _encode(
        subject=str(user_id),
        token_type=TOKEN_TYPE_ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_ttl_minutes),
        secret=settings.jwt_secret,
        # The login session this token belongs to: lets the account centre
        # mark "this device" and never offer to sign out the caller by mistake.
        extra={"sid": str(refresh_id)},
    )
    refresh_token, refresh_expires = _encode(
        subject=str(user_id),
        token_type=TOKEN_TYPE_REFRESH,
        expires_delta=timedelta(days=settings.refresh_token_ttl_days),
        secret=settings.jwt_refresh_secret,
        extra={"sid": str(refresh_id), "nonce": secrets.token_urlsafe(16)},
    )
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        refresh_token_id=refresh_id,
        access_expires_at=access_expires,
        refresh_expires_at=refresh_expires,
    )


def create_password_reset_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    return _encode(
        subject=str(user_id),
        token_type=TOKEN_TYPE_RESET,
        expires_delta=timedelta(minutes=settings.password_reset_ttl_minutes),
        secret=settings.jwt_secret,
        extra={"nonce": secrets.token_urlsafe(16)},
    )
