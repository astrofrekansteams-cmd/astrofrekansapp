from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.token import PasswordResetToken, RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        session_id: uuid.UUID,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            session_id=session_id,
            expires_at=expires_at,
            user_agent=(user_agent or "")[:255] or None,
            ip_address=(ip_address or "")[:64] or None,
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )

    async def revoke_session(self, session_id: uuid.UUID) -> None:
        """Revoke every token of one login session (used on logout and on
        detected refresh-token reuse)."""
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.session_id == session_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )

    async def active_for_user(self, user_id: uuid.UUID) -> list[RefreshToken]:
        """Live refresh tokens, newest first. One login session rotates
        through many tokens; the caller groups them by `session_id`."""
        return list(
            await self.session.scalars(
                select(RefreshToken)
                .where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None),
                    RefreshToken.expires_at > datetime.now(UTC),
                )
                .order_by(RefreshToken.created_at.desc())
            )
        )

    async def first_seen(self, session_id: uuid.UUID) -> datetime | None:
        from sqlalchemy import func

        return await self.session.scalar(
            select(func.min(RefreshToken.created_at)).where(
                RefreshToken.session_id == session_id
            )
        )

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )


class PasswordResetTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> PasswordResetToken:
        token = PasswordResetToken(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        return await self.session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )

    async def mark_used(self, token: PasswordResetToken) -> None:
        token.used_at = datetime.now(UTC)
        await self.session.flush()

    async def retire_unused(self, user_id: uuid.UUID) -> None:
        """Retire every outstanding link, so only the newest one works."""
        await self.session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=datetime.now(UTC))
        )
