from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.types import UtcDateTime
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import SubscriptionStatus, SubscriptionTier

if TYPE_CHECKING:
    from app.db.models.user import User


class Subscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Entitlement record.

    The client never decides what it is entitled to: the tier is written here
    only after a store receipt has been verified server side (phase B8).
    """

    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    tier: Mapped[SubscriptionTier] = mapped_column(
        String(20), default=SubscriptionTier.FREE, nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        String(20), default=SubscriptionStatus.ACTIVE, nullable=False
    )
    platform: Mapped[str | None] = mapped_column(String(20), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Store transaction identifier; the receipt itself is never stored.
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="subscription")

    @property
    def is_active(self) -> bool:
        if self.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.GRACE):
            return False
        if self.expires_at is None:
            return SubscriptionTier(self.tier).is_paid
        return self.expires_at > datetime.now(UTC)
