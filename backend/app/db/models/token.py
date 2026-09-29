from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.types import UtcDateTime
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class RefreshToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One row per issued refresh token.

    Only the SHA-256 digest is stored. Rotation replaces the row and links the
    old one through ``replaced_by_id``, so reuse of a revoked token can be
    detected and the whole session family revoked.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > datetime.now(UTC)

    def revoke(self, *, replaced_by: uuid.UUID | None = None) -> None:
        self.revoked_at = datetime.now(UTC)
        self.replaced_by_id = replaced_by


class PasswordResetToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single-use password reset tokens, stored hashed like refresh tokens."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )

    @property
    def is_usable(self) -> bool:
        return self.used_at is None and self.expires_at > datetime.now(UTC)
