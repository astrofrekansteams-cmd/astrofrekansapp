"""Billing API contracts.

What never appears in any response here: an App Store JWS, a Google purchase
token, a provider's raw payload, a card detail, or a secret. Store prices do
not appear either - the client shows the store's own localised price.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.domain.payments import ClientPlatform, RefundReason
from app.schemas.common import APIModel


class BillingStatusResponse(APIModel):
    apple_configured: bool
    google_configured: bool
    external_marketplace_configured: bool


class StoreProductResponse(APIModel):
    code: str
    product_type: str
    entitlement_code: str
    store_product_id: str = Field(description="The id to pass to StoreKit / Play Billing.")


class ProductListResponse(APIModel):
    platform: ClientPlatform
    items: list[StoreProductResponse]


class AccountTokensResponse(APIModel):
    """Stamp these on purchases so the store vouches for whose they are."""

    apple_app_account_token: str = Field(description="StoreKit appAccountToken (a UUID).")
    google_obfuscated_account_id: str = Field(description="Play Billing obfuscatedAccountId.")


class AppleVerifyRequest(APIModel):
    product_code: str = Field(max_length=80)
    signed_transaction: str | None = Field(
        default=None,
        max_length=20000,
        description="StoreKit 2 `Transaction.jwsRepresentation`. Verified to Apple's root.",
    )
    transaction_id: str | None = Field(default=None, max_length=64)


class GoogleVerifyRequest(APIModel):
    product_code: str = Field(max_length=80)
    purchase_token: str = Field(min_length=10, max_length=4000)


class ReconcileAppleItem(AppleVerifyRequest):
    pass


class ReconcileGoogleItem(GoogleVerifyRequest):
    pass


class ReconcileRequest(APIModel):
    """Restore: what StoreKit / Play Billing says the device currently owns."""

    apple: list[ReconcileAppleItem] = Field(default_factory=list, max_length=20)
    google: list[ReconcileGoogleItem] = Field(default_factory=list, max_length=20)


class EntitlementResponse(APIModel):
    id: uuid.UUID
    entitlement_code: str
    kind: str
    source: str
    status: str
    active: bool = Field(description="Whether it grants access right now, per policy.")
    environment: str
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    grace_until: datetime | None = None
    auto_renewing: bool | None = None
    consumed_at: datetime | None = None


class EntitlementSummaryResponse(APIModel):
    tier: str
    premium: bool
    premium_expires_at: datetime | None = None
    credits: dict[str, int] = Field(description="Unused credits per entitlement code.")
    capabilities: dict[str, object]
    items: list[EntitlementResponse]


class PurchaseResultResponse(APIModel):
    purchase_id: uuid.UUID
    product_code: str
    status: str
    environment: str
    expires_at: datetime | None = None
    entitlements: EntitlementSummaryResponse


class ReconcileResponse(APIModel):
    verified: int
    failed: list[dict[str, str]]
    entitlements: EntitlementSummaryResponse


class ConsumeCreditRequest(APIModel):
    entitlement_code: str = Field(max_length=80)
    consumer_ref: str = Field(
        min_length=8,
        max_length=120,
        description="An idempotency key. Reuse it for the report it pays for.",
    )


class ConsumeCreditResponse(APIModel):
    entitlement_id: uuid.UUID
    entitlement_code: str
    consumer_ref: str
    consumed_at: datetime | None


# ------------------------------------------------------------------ orders


class LineItemResponse(APIModel):
    id: uuid.UUID
    item_type: str
    code: str
    description: str | None = None
    quantity: int
    total_minor: int | None = Field(description="Null when the store sets the price.")
    currency: str
    payment_classification: str
    provider_rail: str
    line_status: str
    store_product_code: str | None = None


class PaymentGroupResponse(APIModel):
    id: uuid.UUID
    classification: str
    rail: str
    amount_minor: int | None = None
    currency: str
    status: str


class OrderPaymentResponse(APIModel):
    order_id: uuid.UUID
    order_status: str
    payment_status: str
    lines: list[LineItemResponse]
    groups: list[PaymentGroupResponse]
    payable_externally: bool
    blocked_by_policy_review: bool


class OrderPaymentRequest(APIModel):
    method: str = Field(pattern="^(external|store_credit)$")
    idempotency_key: str = Field(min_length=8, max_length=80)


class OrderPaymentStartResponse(APIModel):
    """External checkout: open `client_handoff` with the provider. No card data
    ever comes back to this API."""

    payment_intent_id: uuid.UUID | None = None
    status: str
    client_handoff: str | None = None
    expires_at: datetime | None = None
    order: OrderPaymentResponse


class RefundRequestCreate(APIModel):
    reason: RefundReason
    amount_minor: int | None = Field(default=None, gt=0, description="Omit for everything refundable.")
    idempotency_key: str = Field(min_length=8, max_length=80)


class RefundRequestResponse(APIModel):
    id: uuid.UUID
    order_id: uuid.UUID | None
    amount_minor: int
    currency: str
    reason: str
    status: str
    decision: str | None = Field(description="The policy's advice. A person decides.")
    created_at: datetime


# ------------------------------------------------------------------ expert


class ExpertBalanceResponse(APIModel):
    currency: str
    pending_minor: int
    available_minor: int = Field(description="May be negative after a late refund.")
    paid_minor: int


class ExpertEarningsResponse(APIModel):
    settlement_hold_days: int | None
    balances: list[ExpertBalanceResponse]


class PayoutResponse(APIModel):
    id: uuid.UUID
    amount_minor: int
    currency: str
    status: str
    created_at: datetime
    paid_at: datetime | None = None
