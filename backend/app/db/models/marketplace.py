"""The expert marketplace: profiles, offerings, availability, orders.

Two invariants shape almost every table here.

**An expert never gets access to an account.** They get exactly the consent
scopes a user granted, for exactly one order, checked on every read. There is
no "experts can see birth data" shortcut anywhere in this schema - which is
why `service_consents` is a table rather than a boolean on the order.

**A slot belongs to one appointment.** Two people booking the same minute is
the failure that costs an expert their morning and a user their trust, so it
is prevented in Postgres with an exclusion constraint over a time range, not
by an application-level check that a race can walk straight through.

Money is integer minor units throughout (see `app/domain/marketplace.py`).
Nothing here stores a formatted string or a float.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import UtcDateTime

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Expert(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A practitioner's public profile.

    Deliberately separate from `User`: everything here is meant to be seen by
    strangers, and nothing private about the account is copied in. A user has
    at most one profile, enforced by a unique constraint rather than by
    application code.

    `status` and `verified` are moderation decisions. The service layer
    refuses to let a user set either on their own profile.
    """

    __tablename__ = "experts"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_experts_user"),
        # Marketplace search filters on status first, then sorts.
        Index("ix_experts_status_rating", "status", "rating_average"),
        Index("ix_experts_created_at", "created_at"),
        CheckConstraint(
            "rating_average >= 0 AND rating_average <= 5",
            name="ck_experts_rating_range",
        ),
        CheckConstraint("rating_count >= 0", name="ck_experts_rating_count"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    avatar_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(160), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stable codes, never free text: ["tr", "az", "en"], ["tarot", "horary"].
    languages: Mapped[list[str]] = mapped_column(JSONType, nullable=False)
    specialties: Mapped[list[str]] = mapped_column(JSONType, nullable=False)

    experience_years: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    # The expert's own zone. Availability is stored in local time against it,
    # so a schedule survives the expert moving countries.
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Cached aggregate. Reviews remain the source of truth; this is recomputed
    # from them rather than incremented, so a lost update cannot drift it.
    rating_average: Mapped[float] = mapped_column(
        Numeric(3, 2), default=0, nullable=False
    )
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    services: Mapped[list["ExpertService"]] = relationship(
        back_populates="expert", cascade="all, delete-orphan"
    )


class ExpertService(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """One priced offering: an expert's version of a catalogue service.

    The catalogue (`service_definitions`) stays the source of truth for what a
    service *is* - whether it needs birth data, a partner, a question, and
    which fulfilment modes and channels it supports. An offering sets the
    price, the duration and the channel, and may only narrow what the
    definition allows. It can never widen it.
    """

    __tablename__ = "expert_services"
    __table_args__ = (
        Index("ix_expert_services_expert_active", "expert_id", "active"),
        Index("ix_expert_services_definition", "service_definition_id"),
        Index("ix_expert_services_price", "currency", "price_minor"),
        CheckConstraint("price_minor >= 0", name="ck_expert_services_price"),
        CheckConstraint(
            "duration_minutes > 0 AND duration_minutes <= 600",
            name="ck_expert_services_duration",
        ),
    )

    expert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_definitions.id", ondelete="RESTRICT"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    delivery_type: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Minor units and an ISO-4217 code. Never a float, never a string amount.
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    expert: Mapped[Expert] = relationship(back_populates="services")


class ExpertAvailability(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One recurring weekly window, in the expert's local time.

    Stored as local time plus a zone rather than as UTC, because "Mondays
    09:00-12:00 in Istanbul" is what the expert means and it must stay true
    across a daylight-saving change. Converting to UTC at write time would
    silently move their morning by an hour twice a year.
    """

    __tablename__ = "expert_availability"
    __table_args__ = (
        Index("ix_expert_availability_expert_day", "expert_id", "weekday"),
        CheckConstraint(
            "weekday >= 0 AND weekday <= 6", name="ck_availability_weekday"
        ),
        CheckConstraint(
            "start_local_time < end_local_time", name="ck_availability_order"
        ),
    )

    expert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 0 = Monday, matching datetime.weekday().
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_local_time: Mapped[time] = mapped_column(nullable=False)
    end_local_time: Mapped[time] = mapped_column(nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ExpertAvailabilityException(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An override on the weekly schedule, stored in UTC.

    Exceptions are absolute instants - a holiday, a blocked afternoon, one
    extra evening - so unlike the recurring schedule they have no local-time
    ambiguity to preserve.
    """

    __tablename__ = "expert_availability_exceptions"
    __table_args__ = (
        Index(
            "ix_availability_exceptions_window",
            "expert_id",
            "starts_at_utc",
            "ends_at_utc",
        ),
        CheckConstraint(
            "starts_at_utc < ends_at_utc", name="ck_exception_order"
        ),
    )

    expert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exception_type: Mapped[str] = mapped_column(String(30), nullable=False)
    starts_at_utc: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    ends_at_utc: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)


class SlotHold(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A short-lived claim on a slot while an order is being placed.

    Two people filling in a booking form at the same moment both believe they
    have the slot; without a hold, one of them finds out at the very end. The
    hold expires on its own, so somebody who abandons the form does not block
    the slot indefinitely.

    Uniqueness is enforced in Postgres over the time range for active holds
    only - see the migration's exclusion constraint.
    """

    __tablename__ = "slot_holds"
    __table_args__ = (
        Index("ix_slot_holds_expert_window", "expert_id", "starts_at_utc"),
        Index("ix_slot_holds_expiry", "status", "expires_at"),
        CheckConstraint("starts_at_utc < ends_at_utc", name="ck_hold_order"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expert_service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("expert_services.id", ondelete="CASCADE"), nullable=False
    )

    starts_at_utc: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    ends_at_utc: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)


class ServiceOrder(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """What a user bought, and on what terms.

    The price is **snapshotted**. An expert raising their rate tomorrow must
    not change what somebody agreed to today, so the order carries its own
    amounts, its own commission split and its own copy of the service title,
    duration and channel. Reading the price back through `expert_services`
    would be a live number wearing a historical label.

    Payment state is a separate column from order state on purpose: an order
    can be confirmed with payment `not_required`, or cancelled while payment
    is `paid` and a refund is owed.
    """

    __tablename__ = "service_orders"
    __table_args__ = (
        Index("ix_service_orders_user_status", "user_id", "status"),
        Index("ix_service_orders_expert_status", "expert_id", "status"),
        Index("ix_service_orders_created_at", "created_at"),
        UniqueConstraint(
            "user_id", "idempotency_key", name="uq_service_orders_idempotency"
        ),
        CheckConstraint("total_minor >= 0", name="ck_orders_total"),
        CheckConstraint(
            "platform_fee_minor >= 0 AND expert_net_minor >= 0",
            name="ck_orders_split",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    expert_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    expert_service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("expert_services.id", ondelete="SET NULL"), nullable=True
    )

    fulfillment_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    delivery_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    payment_status: Mapped[str] = mapped_column(String(30), nullable=False)

    # --- the price snapshot ------------------------------------------------
    subtotal_minor: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    discount_minor: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    total_minor: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # The commission split, frozen at purchase. Recomputing it later from a
    # changed configuration would rewrite what the expert was owed.
    commission_basis_points: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    platform_fee_minor: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    expert_net_minor: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )

    # Copies of what was bought, so an edited offering cannot rewrite history.
    service_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    service_duration_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # --- future integrations; columns exist, nothing writes them yet -------
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    call_session_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    preconsultation_report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_reports.id", ondelete="SET NULL"), nullable=True
    )

    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    cancellation_actor: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        String(300), nullable=True
    )

    sources: Mapped[list["ServiceOrderSource"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    consents: Mapped[list["ServiceConsent"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class ServiceOrderSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """What an order is about, when it builds on existing work.

    One typed table rather than a nullable column per kind: a hybrid synastry
    consultation references a compatibility report, a horary consultation a
    question, a tarot follow-up a reading. Adding a new source kind is a new
    enum value, not a migration.

    A row here is a *reference*, not an access grant. Seeing it tells an
    expert that a source exists; reading the source still needs consent.
    """

    __tablename__ = "service_order_sources"
    __table_args__ = (
        UniqueConstraint(
            "order_id", "source_kind", "source_id", name="uq_order_source"
        ),
        Index("ix_order_sources_order", "order_id"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    order: Mapped[ServiceOrder] = relationship(back_populates="sources")


class Appointment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A booked slot.

    Times are UTC. The display timezone is stored alongside so a client can
    render what the user saw when they booked, but nothing schedules against
    it - which is why an expert moving countries does not shift appointments
    that already exist.

    Double booking is prevented by a Postgres exclusion constraint over
    `tstzrange(starts_at_utc, ends_at_utc)` for live appointments, added in
    the migration. An application-level check alone loses the race.
    """

    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_expert_start", "expert_id", "starts_at_utc"),
        Index("ix_appointments_user_start", "user_id", "starts_at_utc"),
        Index("ix_appointments_status", "status"),
        CheckConstraint(
            "starts_at_utc < ends_at_utc", name="ck_appointment_order"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expert_service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("expert_services.id", ondelete="RESTRICT"), nullable=False
    )
    service_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    starts_at_utc: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    ends_at_utc: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    # What the user saw when they booked.
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False)

    # Future integrations; nothing writes these yet.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    call_session_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    cancelled_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    cancellation_actor: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        String(300), nullable=True
    )


class ServiceConsent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One scope, granted by one user, to one expert, for one order.

    This table is the whole of expert data access. There is no path anywhere
    in the codebase that reads a user's chart for an expert without finding a
    live row here first - "they are an expert, so they can see it" is not a
    rule this system has.

    Revocation sets `revoked_at` rather than deleting: a user needs to be able
    to see what they once granted, and an auditor needs to see when it ended.
    """

    __tablename__ = "service_consents"
    __table_args__ = (
        UniqueConstraint("order_id", "scope", name="uq_consent_order_scope"),
        Index("ix_consents_expert_scope", "expert_id", "scope"),
        Index("ix_consents_user", "user_id"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experts.id", ondelete="CASCADE"), nullable=False
    )

    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )

    order: Mapped[ServiceOrder] = relationship(back_populates="consents")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class ExpertReview(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A rating, written after a completed order.

    One review per order, enforced by the database. Reviews that are not
    anchored to a transaction are the cheapest thing in the world to
    manufacture, so the service layer refuses any that is not.
    """

    __tablename__ = "expert_reviews"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_review_order"),
        Index("ix_reviews_expert", "expert_id"),
        Index("ix_reviews_created_at", "created_at"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experts.id", ondelete="CASCADE"), nullable=False
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExpertFavorite(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "expert_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "expert_id", name="uq_favorite_user_expert"),
        Index("ix_favorites_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experts.id", ondelete="CASCADE"), nullable=False
    )
