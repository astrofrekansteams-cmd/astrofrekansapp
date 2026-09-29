from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.types import UtcDateTime
from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import AuthProvider, SubscriptionTier

JSONType = JSON().with_variant(JSONB(), "postgresql")

if TYPE_CHECKING:
    from app.db.models.birth_profile import BirthProfile, SavedPerson
    from app.db.models.subscription import Subscription
    from app.db.models.token import RefreshToken


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Account record. Credentials only - everything else lives on the profile."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("firebase_uid", name="uq_users_firebase_uid"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)

    # Null for accounts created through a social provider.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_provider: Mapped[AuthProvider] = mapped_column(
        String(20), default=AuthProvider.PASSWORD, nullable=False
    )
    provider_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # The Firebase identity, when the account has one. Nullable so every
    # existing email/password account keeps working untouched, and unique so
    # one Firebase identity cannot point at two accounts.
    #
    # No business table keys on this. Orders, appointments and consent all
    # reference the local user id, so rotating a Firebase project does not
    # orphan anything.
    firebase_uid: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )

    profile: Mapped["UserProfile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    birth_profiles: Mapped[list["BirthProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    saved_people: Mapped[list["SavedPerson"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def tier(self) -> SubscriptionTier:
        if self.subscription and self.subscription.is_active:
            try:
                return SubscriptionTier(self.subscription.tier)
            except ValueError:
                return SubscriptionTier.FREE
        return SubscriptionTier.FREE


class UserProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Display data and preferences."""

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # A bundled avatar (zodiac glyph) - used when there is no uploaded photo.
    avatar_preset: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(280), nullable=True)
    # Cover / theme style for the profile header, from a fixed list.
    cover_theme: Mapped[str] = mapped_column(
        String(30), default="cosmic_night", nullable=False
    )
    # {"show_sun_sign": bool, "show_rising_sign": bool, ...}
    privacy: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    # {"daily_horoscope": bool, "transits": bool, ...}
    notification_prefs: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True
    )
    language: Mapped[str] = mapped_column(String(8), default="tr", nullable=False)

    # IANA zone of where the user *lives* (birth timezone lives on BirthProfile).
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Istanbul", nullable=False)

    user: Mapped[User] = relationship(back_populates="profile")
