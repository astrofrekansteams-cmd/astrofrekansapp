"""Marketplace API contracts.

Two things these schemas deliberately do not carry.

**No expert PII.** A search result and a public profile contain the shop front
- display name, bio, languages, specialties, ratings - and nothing from the
underlying account. No email, no real name, no birth data.

**No money as a float or a formatted string.** Amounts are integer minor units
plus an ISO-4217 code, and formatting is the client's job. `1999 TRY` means
19.99 lira; the backend never guesses how a locale wants that written.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import Field, field_validator

from app.domain.marketplace import (
    AppointmentStatus,
    AvailabilityExceptionType,
    CancellationActor,
    ConsentScope,
    DeliveryType,
    ExpertSpecialty,
    ExpertStatus,
    FulfillmentMode,
    OrderSourceKind,
    OrderStatus,
    PaymentStatus,
)
from app.schemas.common import APIModel


class MoneyResponse(APIModel):
    """An amount, the honest way."""

    amount_minor: int = Field(
        description="Integer minor units. 1999 with currency TRY is 19.99 TRY."
    )
    currency: str = Field(min_length=3, max_length=3)


# ------------------------------------------------------------------ experts


class ExpertApplicationRequest(APIModel):
    display_name: str = Field(min_length=2, max_length=80)
    headline: str | None = Field(default=None, max_length=160)
    bio: str | None = Field(default=None, max_length=4000)
    avatar_key: str | None = Field(default=None, max_length=120)
    languages: list[str] = Field(min_length=1, max_length=10)
    specialties: list[ExpertSpecialty] = Field(min_length=1, max_length=12)
    experience_years: int = Field(default=0, ge=0, le=80)
    timezone: str = Field(min_length=3, max_length=64)

    @field_validator("languages")
    @classmethod
    def _lowercase(cls, value: list[str]) -> list[str]:
        return [item.strip().lower() for item in value]


class ExpertUpdateRequest(APIModel):
    """Everything an expert may change about themselves.

    `verified` and `status: active` are absent on purpose: an applicant who can
    publish themselves is not an applicant.
    """

    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    headline: str | None = Field(default=None, max_length=160)
    bio: str | None = Field(default=None, max_length=4000)
    avatar_key: str | None = Field(default=None, max_length=120)
    languages: list[str] | None = Field(default=None, min_length=1, max_length=10)
    specialties: list[ExpertSpecialty] | None = Field(
        default=None, min_length=1, max_length=12
    )
    experience_years: int | None = Field(default=None, ge=0, le=80)
    timezone: str | None = Field(default=None, min_length=3, max_length=64)
    status: ExpertStatus | None = Field(
        default=None,
        description=(
            "Only draft, pending_review, paused or inactive. Activation and "
            "verification are moderation decisions."
        ),
    )


class ExpertSummary(APIModel):
    """A search result. Public information only."""

    id: uuid.UUID
    display_name: str
    headline: str | None = None
    avatar_key: str | None = None
    languages: list[str] = Field(default_factory=list)
    specialties: list[str] = Field(default_factory=list)
    experience_years: int
    verified: bool
    rating_average: float
    rating_count: int
    from_price: MoneyResponse | None = Field(
        default=None, description="The cheapest active offering, if any."
    )
    is_favorite: bool = False


class ExpertServiceResponse(APIModel):
    id: uuid.UUID
    expert_id: uuid.UUID
    service_code: str
    service_name: str
    title: str
    description: str | None = None
    delivery_type: DeliveryType
    duration_minutes: int
    price: MoneyResponse
    active: bool

    # The definition's capability AND the offering's channel, so the client can
    # show a video button only when both agree.
    supports_chat: bool = False
    supports_voice: bool = False
    supports_video: bool = False
    requires_birth_data: bool = False
    requires_partner_data: bool = False
    requires_question: bool = False
    supports_appointment: bool = False


class ExpertDetail(ExpertSummary):
    bio: str | None = None
    timezone: str
    status: ExpertStatus
    services: list[ExpertServiceResponse] = Field(default_factory=list)
    rating_distribution: dict[str, int] = Field(default_factory=dict)
    created_at: datetime


class ExpertSearchResponse(APIModel):
    items: list[ExpertSummary]
    total: int
    limit: int
    offset: int


class ExpertServiceCreateRequest(APIModel):
    service_definition_id: uuid.UUID
    title: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    delivery_type: DeliveryType
    duration_minutes: int = Field(ge=5, le=600)
    price_minor: int = Field(ge=0, description="Integer minor units.")
    currency: str = Field(default="TRY", min_length=3, max_length=3)


class ExpertServiceUpdateRequest(APIModel):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    delivery_type: DeliveryType | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=600)
    price_minor: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    active: bool | None = None


# ------------------------------------------------------------ availability


class AvailabilityWindowRequest(APIModel):
    weekday: int = Field(ge=0, le=6, description="0 = Monday.")
    start_local_time: time
    end_local_time: time
    timezone: str | None = Field(
        default=None,
        description="Defaults to the expert's own timezone.",
    )


class AvailabilityWindowResponse(APIModel):
    id: uuid.UUID
    weekday: int
    start_local_time: time
    end_local_time: time
    timezone: str
    active: bool


class AvailabilityExceptionRequest(APIModel):
    exception_type: AvailabilityExceptionType
    starts_at_utc: datetime
    ends_at_utc: datetime
    reason: str | None = Field(default=None, max_length=200)


class AvailabilityExceptionResponse(APIModel):
    id: uuid.UUID
    exception_type: AvailabilityExceptionType
    starts_at_utc: datetime
    ends_at_utc: datetime
    reason: str | None = None


class SlotResponse(APIModel):
    """UTC is canonical. The local times are for display only."""

    starts_at_utc: datetime
    ends_at_utc: datetime
    starts_at_local: datetime
    ends_at_local: datetime
    display_timezone: str


class SlotListResponse(APIModel):
    expert_id: uuid.UUID
    expert_service_id: uuid.UUID
    duration_minutes: int
    display_timezone: str
    slots: list[SlotResponse]
    generated_at: datetime


class SlotHoldRequest(APIModel):
    expert_service_id: uuid.UUID
    starts_at_utc: datetime


class SlotHoldResponse(APIModel):
    id: uuid.UUID
    expert_id: uuid.UUID
    expert_service_id: uuid.UUID
    starts_at_utc: datetime
    ends_at_utc: datetime
    expires_at: datetime
    status: str


# ------------------------------------------------------------------ orders


class OrderSourceRequest(APIModel):
    source_kind: OrderSourceKind
    source_id: uuid.UUID


class OrderSourceResponse(APIModel):
    source_kind: OrderSourceKind
    source_id: uuid.UUID
    label: str | None = None
    # For an expert view: whether consent actually allows reading this.
    readable: bool | None = None


class OrderCreateRequest(APIModel):
    expert_service_id: uuid.UUID | None = Field(
        default=None, description="For an expert or hybrid order."
    )
    service_definition_id: uuid.UUID | None = Field(
        default=None, description="For an automated order."
    )
    starts_at_utc: datetime | None = Field(
        default=None,
        description="Required when the service is delivered by appointment.",
    )
    display_timezone: str | None = None
    sources: list[OrderSourceRequest] = Field(default_factory=list, max_length=10)
    notes: str | None = Field(default=None, max_length=2000)
    # What the person saw when they chose the slot. When both are sent, the
    # server checks `starts_at_utc` falls on that local day - a slot picked on
    # one day and submitted after the calendar moved on is refused rather than
    # booked for the wrong day.
    selected_local_date: date | None = None
    selected_utc_offset_minutes: int | None = Field(default=None, ge=-14 * 60, le=14 * 60)


class CommissionResponse(APIModel):
    """The split, frozen at purchase. Integer arithmetic throughout."""

    gross_amount_minor: int
    platform_fee_minor: int
    expert_net_minor: int
    commission_basis_points: int = Field(
        description="10000 basis points = 100%."
    )


class AppointmentResponse(APIModel):
    id: uuid.UUID
    expert_id: uuid.UUID
    expert_service_id: uuid.UUID
    service_order_id: uuid.UUID | None = None
    starts_at_utc: datetime
    ends_at_utc: datetime
    starts_at_local: datetime
    timezone: str
    status: AppointmentStatus
    cancelled_at: datetime | None = None
    cancellation_actor: CancellationActor | None = None
    cancellation_reason: str | None = None
    created_at: datetime


OrderLifecycle = Literal[
    "pending",
    "paid",
    "scheduled",
    "awaiting_completion",
    "completed",
    "cancelled",
    "refund_review",
    "refunded",
]


class OrderActionsResponse(APIModel):
    """What the caller may do now. The server refuses anything not offered."""

    can_cancel: bool = False
    can_complete: bool = False
    can_deliver: bool = False
    review_eligible: bool = False


class OrderRefundResponse(APIModel):
    id: uuid.UUID
    status: str = Field(
        description="requested, manual_review, approved, processing, refunded, denied or failed."
    )
    amount_minor: int
    currency: str
    reason: str
    created_at: datetime | None = None
    processed_at: datetime | None = None


class CancellationPreviewResponse(APIModel):
    allowed: bool
    refund_outcome: Literal["refund_review", "not_paid", "free", "none"] = Field(
        description=(
            "`refund_review`: paid, a refund request opens for review. "
            "`not_paid`: nothing was collected. `free`: nothing to pay."
        )
    )
    refundable_minor: int = 0
    currency: str


class OrderDeliveryResponse(APIModel):
    note: str
    delivered_at: datetime | None = None


class OrderTimelineEvent(APIModel):
    event: str
    at: datetime
    actor: str | None = None


class OrderResponse(APIModel):
    id: uuid.UUID
    service_code: str
    fulfillment_mode: FulfillmentMode
    delivery_type: DeliveryType | None = None
    status: OrderStatus
    payment_status: PaymentStatus

    expert_id: uuid.UUID | None = None
    expert_display_name: str | None = None
    expert_service_id: uuid.UUID | None = None

    # The snapshot. These never change, whatever the expert does to their
    # offering afterwards.
    service_title: str | None = None
    service_duration_minutes: int | None = None
    subtotal: MoneyResponse
    discount_minor: int = 0
    total: MoneyResponse
    commission: CommissionResponse

    appointment: AppointmentResponse | None = None
    sources: list[OrderSourceResponse] = Field(default_factory=list)
    granted_consent_scopes: list[ConsentScope] = Field(default_factory=list)

    notes: str | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancellation_actor: CancellationActor | None = None
    cancellation_reason: str | None = None
    created_at: datetime

    # Derived for display, never stored (services/marketplace/lifecycle.py).
    lifecycle: OrderLifecycle = "pending"
    actions: OrderActionsResponse = Field(default_factory=lambda: OrderActionsResponse())
    completion_block: str | None = Field(
        default=None,
        description="Why completion is not available now, when it is not.",
    )
    refund: OrderRefundResponse | None = None
    cancellation: CancellationPreviewResponse | None = None
    delivery: OrderDeliveryResponse | None = None
    timeline: list[OrderTimelineEvent] = Field(default_factory=list)


class OrderSummary(APIModel):
    id: uuid.UUID
    service_code: str
    service_title: str | None = None
    status: OrderStatus
    payment_status: PaymentStatus
    total: MoneyResponse
    expert_id: uuid.UUID | None = None
    expert_display_name: str | None = None
    appointment_starts_at_utc: datetime | None = None
    created_at: datetime
    lifecycle: OrderLifecycle = "pending"


class CancelRequest(APIModel):
    reason: str | None = Field(default=None, max_length=300)


class DeliverRequest(APIModel):
    note: str = Field(min_length=1, max_length=20_000)


class AppointmentCreateRequest(APIModel):
    expert_service_id: uuid.UUID
    starts_at_utc: datetime
    display_timezone: str | None = None


# ----------------------------------------------------------------- consent


class ConsentResponse(APIModel):
    scope: ConsentScope
    granted_at: datetime
    revoked_at: datetime | None = None
    active: bool


class ConsentUpdateRequest(APIModel):
    """The complete set of scopes the user is comfortable sharing.

    A PUT, not a toggle: anything absent from the list is revoked, which makes
    "share less than before" one obvious action rather than several.
    """

    scopes: list[ConsentScope] = Field(default_factory=list, max_length=10)


# ----------------------------------------------------------------- reviews


class ReviewCreateRequest(APIModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewUpdateRequest(APIModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewResponse(APIModel):
    id: uuid.UUID
    expert_id: uuid.UUID
    order_id: uuid.UUID
    rating: int
    comment: str | None = None
    created_at: datetime
    updated_at: datetime


class ReviewListResponse(APIModel):
    items: list[ReviewResponse]
    total: int
    rating_average: float
    rating_count: int
    distribution: dict[str, int] = Field(default_factory=dict)
