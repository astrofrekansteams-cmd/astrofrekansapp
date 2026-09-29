"""Vocabulary for the service catalog, the expert marketplace and money.

Nothing here has tables yet (phases B8-B10), but the *names and states* are
fixed now, because they are what later tables, API payloads and the Flutter
client will speak. Changing an enum value after data exists is a migration;
agreeing on it early is free.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class FulfillmentMode(StrEnum):
    """Who actually performs the service."""

    AUTOMATED = "automated"  # engine + Astro AI, no human
    EXPERT = "expert"  # a real astrologer delivers it
    HYBRID = "hybrid"  # engine pre-analysis, expert consultation on top


class ServiceCategory(StrEnum):
    NATAL = "natal"
    FORECAST = "forecast"
    RELATIONSHIP = "relationship"
    HORARY = "horary"
    DIVINATION = "divination"
    AI = "ai"
    SPECIAL = "special"


class ServiceCode(StrEnum):
    """Stable identifiers for everything Astrofrekans can sell or generate.

    The client, the order rows, the expert's offerings and the report
    generators all key off these strings, so they never change once shipped.
    """

    # --- natal ---------------------------------------------------------
    NATAL_CHART_ANALYSIS = "natal_chart_analysis"
    KARMIC_ANALYSIS = "karmic_analysis"
    LUNAR_NODES_ANALYSIS = "lunar_nodes_analysis"
    CAREER_ANALYSIS = "career_analysis"
    LOVE_ANALYSIS = "love_analysis"
    FINANCIAL_ANALYSIS = "financial_analysis"

    # --- forecast ------------------------------------------------------
    DAILY_HOROSCOPE = "daily_horoscope"
    WEEKLY_HOROSCOPE = "weekly_horoscope"
    MONTHLY_FORECAST = "monthly_forecast"
    ANNUAL_FORECAST = "annual_forecast"
    TRANSIT_ANALYSIS = "transit_analysis"
    SOLAR_RETURN = "solar_return"
    LUNAR_RETURN = "lunar_return"

    # --- relationship --------------------------------------------------
    SYNASTRY = "synastry"
    RELATIONSHIP_ANALYSIS = "relationship_analysis"
    COMPOSITE_CHART = "composite_chart"
    DAVISON_CHART = "davison_chart"

    # --- horary --------------------------------------------------------
    HORARY_QUESTION = "horary_question"

    # --- divination ----------------------------------------------------
    TAROT_READING = "tarot_reading"
    RUNE_READING = "rune_reading"
    KATINA_READING = "katina_reading"

    # --- ai ------------------------------------------------------------
    ASTRO_AI_CONSULTATION = "astro_ai_consultation"

    # --- planned; catalogued now so codes stay stable ------------------
    SECONDARY_PROGRESSIONS = "secondary_progressions"
    SOLAR_ARC = "solar_arc"
    ANNUAL_PROFECTIONS = "annual_profections"
    ASTROCARTOGRAPHY = "astrocartography"
    RELOCATION_CHART = "relocation_chart"
    ELECTIONAL_ASTROLOGY = "electional_astrology"


class DeliveryType(StrEnum):
    """How an expert delivers their service."""

    CHAT = "chat"
    VOICE = "voice"
    VIDEO = "video"
    WRITTEN_REPORT = "written_report"


class ExpertSpecialty(StrEnum):
    """What an expert practises. A stable code, never free text.

    Free text would make search unusable within a month - "tarot", "Tarot",
    "tarot okuma" and "tarot reading" would be four different specialties.
    New entries are additive; existing values never change.
    """

    ASTROLOGY = "astrology"
    NATAL_CHART = "natal_chart"
    TRANSITS = "transits"
    SYNASTRY = "synastry"
    COMPOSITE = "composite"
    DAVISON = "davison"
    HORARY = "horary"
    MONTHLY_FORECAST = "monthly_forecast"
    ANNUAL_FORECAST = "annual_forecast"
    TAROT = "tarot"
    RUNE = "rune"
    KATINA = "katina"


class ExpertStatus(StrEnum):
    """Where an expert profile sits in its lifecycle.

    Only `ACTIVE` is discoverable in the marketplace. A user may move their
    own profile between DRAFT, PENDING_REVIEW and INACTIVE; ACTIVE and
    SUSPENDED are moderation decisions and are never self-assigned.
    """

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"

    @property
    def is_public(self) -> bool:
        return self is ExpertStatus.ACTIVE

    @property
    def is_self_assignable(self) -> bool:
        """States a user may put their own profile into."""
        return self in (
            ExpertStatus.DRAFT,
            ExpertStatus.PENDING_REVIEW,
            ExpertStatus.PAUSED,
            ExpertStatus.INACTIVE,
        )


class OrderStatus(StrEnum):
    """Lifecycle of a service order (automated, expert or hybrid).

    The automated stages (CALCULATING, GENERATING) and the expert stages
    (PENDING_PAYMENT, PAID, CONFIRMED, AWAITING_EXPERT) share one enum because
    a hybrid order passes through both kinds.
    """

    DRAFT = "draft"
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    CONFIRMED = "confirmed"

    PENDING = "pending"
    CALCULATING = "calculating"
    GENERATING = "generating"
    AWAITING_EXPERT = "awaiting_expert"
    IN_PROGRESS = "in_progress"

    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in (
            OrderStatus.COMPLETED,
            OrderStatus.CANCELLED,
            OrderStatus.REFUNDED,
            OrderStatus.FAILED,
        )


class PaymentStatus(StrEnum):
    """Payment state, kept separate from order state on purpose.

    An order can be CONFIRMED while payment is NOT_REQUIRED (a free service),
    or CANCELLED while payment is PAID (a refund is owed). Collapsing the two
    would lose exactly the cases that matter.

    No payment provider is integrated yet. Nothing in this codebase sets PAID
    on a priced order.
    """

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    AUTHORIZED = "authorized"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    # B11: a paid order was cancelled and the money is owed back. Not
    # "refunded" until a provider says it moved.
    REFUND_PENDING = "refund_pending"


class AppointmentStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class CancellationActor(StrEnum):
    """Who ended the appointment - refund policy depends on it."""

    USER = "user"
    EXPERT = "expert"
    ADMIN = "admin"
    SYSTEM = "system"
    TECHNICAL_FAILURE = "technical_failure"


# Calls have their own domain module since B10. Re-exported here because these
# names were placeholders in this module first.
from app.domain.calls import CallStatus, CallType  # noqa: E402,F401


class MessageType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    SYSTEM = "system"


# Payouts have their own domain module since B11 (with APPROVED and CANCELLED,
# and a transition table). Re-exported because the name started here.
from app.domain.payments import PayoutStatus  # noqa: E402,F401


class ConsentScope(StrEnum):
    """What an expert may see about the user, per order or appointment.

    An expert never gets access to the account: they get exactly the scopes
    the user granted, for exactly that engagement, and it is checked on every
    read.
    """

    BIRTH_PROFILE = "share_birth_profile"
    NATAL_CHART = "share_natal_chart"
    PARTNER_PROFILE = "share_partner_profile"
    SYNASTRY = "share_synastry"
    HORARY = "share_horary"
    FORECAST = "share_forecast"
    DIVINATION_READING = "share_divination_reading"
    PREVIOUS_READINGS = "share_previous_readings"


class NotificationEvent(StrEnum):
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_REMINDER = "appointment_reminder"
    APPOINTMENT_STARTING = "appointment_starting"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    NEW_CHAT_MESSAGE = "new_chat_message"
    INCOMING_VOICE_CALL = "incoming_voice_call"
    INCOMING_VIDEO_CALL = "incoming_video_call"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    AUTOMATED_REPORT_READY = "automated_report_ready"
    MONTHLY_FORECAST_READY = "monthly_forecast_ready"
    ANNUAL_FORECAST_READY = "annual_forecast_ready"
    IMPORTANT_TRANSIT = "important_transit"
    FULL_MOON = "full_moon"
    NEW_MOON = "new_moon"


class AvailabilityExceptionType(StrEnum):
    """An override on top of the weekly schedule.

    The first three remove time, the last adds it. Keeping them in one table
    means slot generation applies them in one pass rather than joining two
    differently-shaped sources.
    """

    VACATION = "vacation"
    BUSY = "busy"
    MANUAL_BLOCK = "manual_block"
    EXTRA_AVAILABILITY = "extra_availability"

    @property
    def adds_time(self) -> bool:
        return self is AvailabilityExceptionType.EXTRA_AVAILABILITY


class SlotHoldStatus(StrEnum):
    """A short-lived claim on a slot while an order is being placed.

    Without it, two people filling in a booking form at the same time both
    believe they have the slot and one of them finds out at the end. The hold
    expires on its own, so a user who walks away does not block the slot
    forever.
    """

    ACTIVE = "active"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class OrderSourceKind(StrEnum):
    """What an order is *about*, when it references existing work.

    A hybrid consultation is usually built on something the platform already
    produced - a chart, a synastry report, a horary question, a reading. One
    typed linkage table covers all of them rather than a nullable column per
    kind, which would need a migration every time a new source appears.
    """

    BIRTH_PROFILE = "birth_profile"
    SAVED_PERSON = "saved_person"
    CHART = "chart"
    COMPATIBILITY_REPORT = "compatibility_report"
    HORARY_QUESTION = "horary_question"
    DIVINATION_READING = "divination_reading"
    AI_REPORT = "ai_report"


# --------------------------------------------------------------------- money


@dataclass(slots=True, frozen=True, order=True)
class Money:
    """An amount in **minor units** (kuruş, cent) plus an ISO-4217 code.

    Floats never touch money: ``1000.00 TRY`` is ``Money(100000, "TRY")``.
    Database columns follow the same rule (``BigInteger`` + ``String(3)``),
    which is why the convention is pinned here before any payment table
    exists.
    """

    amount_minor: int
    currency: str = "TRY"

    def __post_init__(self) -> None:
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError(f"Not an ISO-4217 currency code: {self.currency!r}")
        object.__setattr__(self, "currency", self.currency.upper())

    @classmethod
    def from_decimal(cls, value: Decimal | str | int, currency: str = "TRY") -> "Money":
        minor = (Decimal(str(value)) * 100).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return cls(int(minor), currency)

    @property
    def as_decimal(self) -> Decimal:
        return Decimal(self.amount_minor) / 100

    def _check(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot combine {self.currency} and {other.currency} amounts."
            )

    def __add__(self, other: "Money") -> "Money":
        self._check(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._check(other)
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def split_commission(self, basis_points: int) -> tuple["Money", "Money"]:
        """Split into (platform fee, expert amount).

        The rate arrives in basis points (1% = 100 bp) from configuration, so
        no percentage is ever hard-coded in business logic. Rounding favours
        the expert: the fee is truncated, the remainder is theirs.
        """
        if not 0 <= basis_points <= 10_000:
            raise ValueError("Commission must be between 0 and 10000 basis points.")
        fee = self.amount_minor * basis_points // 10_000
        return Money(fee, self.currency), Money(self.amount_minor - fee, self.currency)

    def __str__(self) -> str:
        return f"{self.as_decimal:.2f} {self.currency}"
