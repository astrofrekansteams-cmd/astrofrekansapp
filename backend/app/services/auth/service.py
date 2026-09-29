"""Authentication service.

Security decisions in one place:

* Argon2id password hashing, transparent rehash when parameters change.
* Access tokens are short lived; refresh tokens are long lived, stored as
  SHA-256 digests and **rotated on every use**.
* Reusing an already-rotated refresh token revokes the whole session family -
  the standard stolen-token response.
* ``forgot-password`` never reveals whether an address exists.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CurrentPasswordIncorrect,
    AuthenticationError,
    EmailAlreadyRegistered,
    InvalidCredentials,
    TokenError,
)
from app.core.logging import get_logger
from app.core.security import (
    TOKEN_TYPE_REFRESH,
    TOKEN_TYPE_RESET,
    TokenPair,
    create_password_reset_token,
    create_token_pair,
    decode_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)
from app.db.models.user import User
from app.repositories.token_repository import (
    PasswordResetTokenRepository,
    RefreshTokenRepository,
)
from app.repositories.user_repository import UserRepository

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class AuthResult:
    user: User
    tokens: TokenPair


@dataclass(slots=True, frozen=True)
class RequestContext:
    user_agent: str | None = None
    ip_address: str | None = None


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.reset_tokens = PasswordResetTokenRepository(session)

    # ------------------------------------------------------------- register

    async def register(
        self,
        *,
        email: str,
        password: str,
        name: str,
        language: str = "tr",
        timezone: str = "Europe/Istanbul",
        context: RequestContext | None = None,
    ) -> AuthResult:
        if await self.users.email_exists(email):
            raise EmailAlreadyRegistered()

        user = await self.users.create(
            email=email,
            password_hash=hash_password(password),
            name=name,
            language=language,
            timezone=timezone,
        )
        tokens = await self._issue_tokens(user, context=context)
        await self.users.touch_login(user)
        logger.info("user_registered", user_id=str(user.id))
        return AuthResult(user=user, tokens=tokens)

    # ---------------------------------------------------------------- login

    async def login(
        self, *, email: str, password: str, context: RequestContext | None = None
    ) -> AuthResult:
        user = await self.users.get_by_email(email)
        if user is None or user.password_hash is None:
            # Same error and roughly the same work either way: no user
            # enumeration through timing or message.
            hash_password(password)
            raise InvalidCredentials()

        if not verify_password(password, user.password_hash):
            raise InvalidCredentials()
        if not user.is_active:
            raise AuthenticationError("This account is disabled.", code="account_disabled")

        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        tokens = await self._issue_tokens(user, context=context)
        await self.users.touch_login(user)
        logger.info("user_logged_in", user_id=str(user.id))
        return AuthResult(user=user, tokens=tokens)

    # -------------------------------------------------------------- refresh

    async def refresh(
        self, *, refresh_token: str, context: RequestContext | None = None
    ) -> AuthResult:
        payload = decode_token(refresh_token, token_type=TOKEN_TYPE_REFRESH)
        stored = await self.refresh_tokens.get_by_hash(hash_token(refresh_token))

        if stored is None:
            raise TokenError("Unknown refresh token.", code="token_unknown")

        if stored.revoked_at is not None:
            # A revoked token being presented means it leaked: drop the family.
            # Committed here on purpose - the caller will get an exception and
            # never reaches its own commit, and the revocation must survive.
            await self.refresh_tokens.revoke_session(stored.session_id)
            await self.session.commit()
            logger.warning(
                "refresh_token_reuse_detected",
                user_id=str(stored.user_id),
                session_id=str(stored.session_id),
            )
            raise TokenError("Refresh token was already used.", code="token_reused")

        if stored.expires_at <= datetime.now(UTC):
            raise TokenError("The token has expired.", code="token_expired")

        user = await self.users.get(uuid.UUID(payload["sub"]))
        if user is None or not user.is_active:
            raise TokenError()

        new_tokens = create_token_pair(user.id, session_id=stored.session_id)
        new_row = await self.refresh_tokens.create(
            user_id=user.id,
            token_hash=hash_token(new_tokens.refresh_token),
            session_id=stored.session_id,
            expires_at=new_tokens.refresh_expires_at,
            user_agent=context.user_agent if context else None,
            ip_address=context.ip_address if context else None,
        )
        stored.revoke(replaced_by=new_row.id)
        await self.session.flush()
        return AuthResult(user=user, tokens=new_tokens)

    # --------------------------------------------------------------- logout

    async def logout(self, *, refresh_token: str) -> None:
        """Idempotent: an invalid token still ends in 'logged out'."""
        try:
            decode_token(refresh_token, token_type=TOKEN_TYPE_REFRESH)
        except TokenError:
            return
        stored = await self.refresh_tokens.get_by_hash(hash_token(refresh_token))
        if stored is not None:
            await self.refresh_tokens.revoke_session(stored.session_id)

    async def logout_everywhere(self, user: User) -> None:
        await self.refresh_tokens.revoke_all_for_user(user.id)

    # ------------------------------------------------------- password reset

    async def request_password_reset(self, *, email: str) -> str | None:
        """Returns the token only so the caller can hand it to the mailer.

        The API response is identical whether or not the address exists.
        """
        user = await self.users.get_by_email(email)
        # Eligible: an active account that signs in with a password here. A
        # Firebase-only account resets through Firebase; a disabled one does
        # not come back through a reset link. The response is the same.
        if user is None or not user.is_active or not user.password_hash:
            return None
        # One live link at a time: asking again retires the previous one.
        await self.reset_tokens.retire_unused(user.id)
        token, expires_at = create_password_reset_token(user.id)
        await self.reset_tokens.create(
            user_id=user.id, token_hash=hash_token(token), expires_at=expires_at
        )
        return token

    async def language_for_email(self, email: str) -> str | None:
        user = await self.users.get_by_email(email)
        return user.profile.language if user is not None and user.profile else None

    async def check_reset_token(self, *, token: str) -> datetime:
        """Whether a reset link can still be used, before the form is filled.

        Raises the same errors `reset_password` would: `token_expired` for a
        link past its time, `token_used` for one already used or retired.
        """
        decode_token(token, token_type=TOKEN_TYPE_RESET)
        stored = await self.reset_tokens.get_by_hash(hash_token(token))
        if stored is None or not stored.is_usable:
            raise TokenError("This reset link is no longer valid.", code="token_used")
        return stored.expires_at

    async def reset_password(self, *, token: str, new_password: str) -> None:
        payload = decode_token(token, token_type=TOKEN_TYPE_RESET)
        stored = await self.reset_tokens.get_by_hash(hash_token(token))
        if stored is None or not stored.is_usable:
            raise TokenError("This reset link is no longer valid.", code="token_used")

        user = await self.users.get(uuid.UUID(payload["sub"]))
        if user is None:
            raise TokenError()

        user.password_hash = hash_password(new_password)
        await self.reset_tokens.mark_used(stored)
        # Changing the password invalidates every existing session.
        await self.refresh_tokens.revoke_all_for_user(user.id)
        await self.session.flush()
        logger.info("password_reset_completed", user_id=str(user.id))

    # ----------------------------------------------------------- sessions

    async def list_sessions(self, user: User) -> list[dict]:
        """Signed-in sessions (email/password logins), newest activity first.

        Built from refresh tokens: a session is every token sharing one
        `session_id`; the newest live token says when it was last used. The IP
        is shortened - enough to recognise a place, not to track one.
        """
        seen: dict[uuid.UUID, dict] = {}
        for token in await self.refresh_tokens.active_for_user(user.id):
            if token.session_id in seen:
                continue
            seen[token.session_id] = {
                "id": token.session_id,
                "last_used_at": token.created_at,
                "expires_at": token.expires_at,
                "user_agent": token.user_agent,
                "ip_hint": ip_hint(token.ip_address),
            }
        for session_id, row in seen.items():
            row["created_at"] = await self.refresh_tokens.first_seen(session_id) or row["last_used_at"]
        return list(seen.values())

    async def revoke_session(self, user: User, session_id: uuid.UUID) -> None:
        owned = any(
            token.session_id == session_id
            for token in await self.refresh_tokens.active_for_user(user.id)
        )
        if not owned:
            from app.core.exceptions import NotFound

            raise NotFound("Session not found.")
        await self.refresh_tokens.revoke_session(session_id)
        await self.session.flush()
        logger.info("session_revoked", user_id=str(user.id), session_id=str(session_id))

    async def change_password(
        self, *, user: User, current_password: str, new_password: str
    ) -> None:
        if user.password_hash is None or not verify_password(
            current_password, user.password_hash
        ):
            raise CurrentPasswordIncorrect()
        user.password_hash = hash_password(new_password)
        await self.refresh_tokens.revoke_all_for_user(user.id)
        await self.session.flush()

    # -------------------------------------------------------------- helpers

    async def _issue_tokens(
        self, user: User, *, context: RequestContext | None
    ) -> TokenPair:
        tokens = create_token_pair(user.id)
        await self.refresh_tokens.create(
            user_id=user.id,
            token_hash=hash_token(tokens.refresh_token),
            session_id=tokens.refresh_token_id,
            expires_at=tokens.refresh_expires_at,
            user_agent=context.user_agent if context else None,
            ip_address=context.ip_address if context else None,
        )
        return tokens


def ip_hint(ip: str | None) -> str | None:
    """`85.105.x.x` / `2a02:e0:…`: recognisable, not a precise address."""
    if not ip:
        return None
    if "." in ip:
        parts = ip.split(".")
        return ".".join(parts[:2] + ["x", "x"]) if len(parts) == 4 else None
    if ":" in ip:
        return ":".join(ip.split(":")[:2]) + ":…"
    return None
