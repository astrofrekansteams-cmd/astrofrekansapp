"""Payments: the vocabulary.

Three things are kept apart on purpose, because every payment bug in a
marketplace comes from blurring two of them:

* **Classification** - *what kind of thing* is being sold, in store-policy
  terms. Decides which rail may collect the money.
* **Rail** - *who collects* it: the App Store, Google Play, or an external
  marketplace provider.
* **Accounting** - *where the money goes* once collected: platform revenue,
  expert payable, a refund. Immutable, balanced, per currency.

Money is always integer minor units plus an ISO-4217 code. No floats.
"""

from __future__ import annotations

from enum import StrEnum

# ============================================================ classification


class PaymentClassification(StrEnum):
    """What a line item is, for store policy.

    Verified against Apple App Review Guideline 3.1.1 / 3.1.3(d) and Google
    Play's Payments policy (1:1 online paid services) on 2026-09-24. See
    docs/payment_architecture.md.
    """

    # Digital content or functionality used in the app: must use the store's
    # in-app purchase system.
    DIGITAL_STORE = "digital_store"
    # A real-time service between two people that is not available for replay:
    # both stores allow payment outside in-app purchase.
    LIVE_PERSON_TO_PERSON = "live_person_to_person"
    # Anything the rules do not clearly place. Fail closed: no rail takes it
    # until somebody decides.
    REVIEW_REQUIRED = "review_required"
    FREE = "free"


class PaymentRail(StrEnum):
    APPLE_STORE = "apple_store"
    GOOGLE_PLAY = "google_play"
    EXTERNAL_MARKETPLACE = "external_marketplace"
    NONE = "none"


class ClientPlatform(StrEnum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


# =================================================================== stores


class StoreProvider(StrEnum):
    APPLE = "apple"
    GOOGLE = "google"


class StoreProductType(StrEnum):
    CONSUMABLE = "consumable"
    NON_CONSUMABLE = "non_consumable"
    SUBSCRIPTION = "subscription"


class StoreEnvironment(StrEnum):
    PRODUCTION = "production"
    SANDBOX = "sandbox"  # Apple sandbox, or a Google test purchase


class PurchaseStatus(StrEnum):
    """A store purchase, normalised across Apple and Google.

    The mapping from each store's own states is in
    docs/store_billing.md#state-mapping.
    """

    PENDING = "pending"  # not completed; never entitles
    ACTIVE = "active"
    # Cancelled, but paid up to `expires_at`: access continues until then.
    CANCELLED_PENDING_EXPIRY = "cancelled_pending_expiry"
    GRACE_PERIOD = "grace_period"
    ON_HOLD = "on_hold"
    PAUSED = "paused"
    EXPIRED = "expired"
    REVOKED = "revoked"  # refunded, voided, family-sharing removed...
    CANCELLED = "cancelled"  # a one-time purchase that never completed


class EntitlementKind(StrEnum):
    SUBSCRIPTION = "subscription"
    CREDIT = "credit"  # consumable: used once
    PERMANENT = "permanent"  # non-consumable


class EntitlementStatus(StrEnum):
    ACTIVE = "active"
    GRACE_PERIOD = "grace_period"
    ON_HOLD = "on_hold"
    PAUSED = "paused"
    CANCELLED_PENDING_EXPIRY = "cancelled_pending_expiry"
    EXPIRED = "expired"
    REVOKED = "revoked"
    CONSUMED = "consumed"  # a credit that has been used
    # A credit held by a paid AI report job until the report is delivered.
    # Not available to anything else; becomes CONSUMED on delivery.
    RESERVED = "reserved"


class EntitlementSource(StrEnum):
    APPLE = "apple"
    GOOGLE = "google"
    GRANT = "grant"  # an administrative grant, for support


# ================================================================ providers


class ProviderEventStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"


# =================================================================== orders


class LineItemType(StrEnum):
    EXPERT_SESSION = "expert_session"
    AI_PRE_ANALYSIS = "ai_pre_analysis"
    AUTOMATED_REPORT = "automated_report"


class LineItemStatus(StrEnum):
    INCLUDED = "included"
    # Offered only through a store product that is not configured: not sold,
    # not delivered, not charged.
    EXCLUDED = "excluded"


class PaymentGroupStatus(StrEnum):
    REQUIRED = "required"
    SATISFIED = "satisfied"
    NOT_REQUIRED = "not_required"
    # A REVIEW_REQUIRED line with a price: nobody may collect it yet.
    BLOCKED_REVIEW = "blocked_review"
    REFUNDED = "refunded"


class PaymentIntentStatus(StrEnum):
    CREATED = "created"
    PENDING = "pending"
    AUTHORIZED = "authorized"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class TransactionType(StrEnum):
    CHARGE = "charge"
    REFUND = "refund"
    PARTIAL_REFUND = "partial_refund"
    REVERSAL = "reversal"
    CHARGEBACK = "chargeback"
    ADJUSTMENT = "adjustment"
    # Internal movements with no money crossing a provider.
    SETTLEMENT_RELEASE = "settlement_release"
    PAYOUT = "payout"


# =================================================================== ledger


class LedgerAccount(StrEnum):
    PLATFORM_RECEIVABLE = "platform_receivable"
    PLATFORM_REVENUE = "platform_revenue"
    # EXPERT_PAYABLE, in its two halves: earned but held, and releasable.
    EXPERT_PAYABLE_PENDING = "expert_payable_pending"
    EXPERT_PAYABLE_AVAILABLE = "expert_payable_available"
    REFUND_LIABILITY = "refund_liability"
    STORE_CLEARING = "store_clearing"
    EXTERNAL_PROVIDER_CLEARING = "external_provider_clearing"


class LedgerDirection(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


# ============================================================== settlement


class PayoutStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


PAYOUT_TRANSITIONS: dict[PayoutStatus, frozenset[PayoutStatus]] = {
    PayoutStatus.PENDING: frozenset({PayoutStatus.APPROVED, PayoutStatus.CANCELLED}),
    PayoutStatus.APPROVED: frozenset({PayoutStatus.PROCESSING, PayoutStatus.CANCELLED}),
    PayoutStatus.PROCESSING: frozenset({PayoutStatus.PAID, PayoutStatus.FAILED}),
    PayoutStatus.PAID: frozenset(),
    PayoutStatus.FAILED: frozenset({PayoutStatus.APPROVED, PayoutStatus.CANCELLED}),
    PayoutStatus.CANCELLED: frozenset(),
}


# ================================================================= refunds


class RefundReason(StrEnum):
    USER_CANCELLATION = "user_cancellation"
    EXPERT_CANCELLATION = "expert_cancellation"
    NO_SHOW = "no_show"
    TECHNICAL_FAILURE = "technical_failure"
    DUPLICATE = "duplicate"
    FRAUD = "fraud"
    GOODWILL = "goodwill"
    STORE_REVERSAL = "store_reversal"


class RefundStatus(StrEnum):
    REQUESTED = "requested"
    MANUAL_REVIEW = "manual_review"
    APPROVED = "approved"
    PROCESSING = "processing"
    REFUNDED = "refunded"
    DENIED = "denied"
    FAILED = "failed"


class RefundDecision(StrEnum):
    """What the policy says - an input to a person, not a verdict by default."""

    AUTO = "auto"
    MANUAL_REVIEW = "manual_review"
    NOT_ELIGIBLE = "not_eligible"


class RefundActor(StrEnum):
    USER = "user"
    EXPERT = "expert"
    ADMIN = "admin"
    SYSTEM = "system"
    STORE = "store"


# =================================================================== ISO-4217

# Minor-unit exponents that differ from 2. ISO-4217 facts, not policy.
_EXPONENTS: dict[str, int] = {
    **{code: 0 for code in ("JPY", "KRW", "CLP", "ISK", "VND", "UGX", "XAF", "XOF", "HUF")},
    **{code: 3 for code in ("BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND")},
}


def minor_exponent(currency: str) -> int:
    return _EXPONENTS.get(currency.upper(), 2)


def milliunits_to_minor(milliunits: int, currency: str) -> int:
    """Apple reports prices in milliunits (1/1000 of the major unit).

    Exact for exponents 0-3 when Apple's value is itself a whole number of
    minor units; otherwise rounded half-up, which cannot happen for prices a
    store actually charges.
    """
    exponent = minor_exponent(currency)
    scaled = milliunits * (10**exponent)
    return (scaled + 500) // 1000
