from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.marketplace import ServiceCategory

JSONType = JSON().with_variant(JSONB(), "postgresql")


class ServiceDefinition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The catalogue of everything Astrofrekans can deliver.

    One row per service (natal analysis, horary question, synastry, tarot...),
    independent of *who* delivers it. It is the join point for the rest of the
    platform: automated report generators dispatch on ``code``, experts offer
    their own priced variants of a definition, and orders reference it.

    ``fulfillment_modes`` lists which of automated / expert / hybrid apply, and
    the ``requires_*`` flags tell the client what to collect before an order
    can even be created.
    """

    __tablename__ = "service_definitions"
    __table_args__ = (
        UniqueConstraint("code", name="uq_service_definitions_code"),
    )

    code: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[ServiceCategory] = mapped_column(String(30), nullable=False)

    # ["automated", "expert", "hybrid"]
    fulfillment_modes: Mapped[list[str]] = mapped_column(JSONType, nullable=False)

    # Typical expert session length, and how long an automated run takes.
    estimated_duration_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    requires_birth_data: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    requires_partner_data: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    requires_question: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    supports_chat: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_voice: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_video: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_appointment: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    supports_automated_report: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Free tier gets a subset; the rest needs an entitlement or a purchase.
    requires_premium: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
