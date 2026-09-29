"""The shapes every payment provider speaks, and the errors it may raise.

Stores (Apple, Google) and the future external marketplace provider are very
different systems. The rest of the payment domain sees only what is below: a
`VerifiedPurchase` normalised from whatever the store said, and a small set of
stable errors. A provider's own error text never crosses this boundary - it
can carry transaction ids, account hints or internal hosts.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from app.core.exceptions import AppError
from app.domain.payments import PurchaseStatus, StoreEnvironment, StoreProvider

# =================================================================== errors


class StoreNotConfigured(AppError):
    status_code = 503
    code = "store_provider_not_configured"
    message = "Purchases from this store are not configured on this server."


class StoreUnavailable(AppError):
    """Timeouts, 429s and 5xx: the store may answer later."""

    status_code = 503
    code = "store_provider_unavailable"
    message = "The store did not answer. Please try again."


class StoreVerificationFailed(AppError):
    """The signature, bundle, package or token did not verify."""

    status_code = 422
    code = "store_verification_failed"
    message = "The purchase could not be verified with the store."


class StoreEnvironmentRejected(AppError):
    status_code = 422
    code = "store_environment_rejected"
    message = "This purchase was made in a test environment and is not accepted here."


class UnknownStoreProduct(AppError):
    status_code = 422
    code = "unknown_store_product"
    message = "That product is not sold here."


class ProductMismatch(AppError):
    status_code = 422
    code = "product_mismatch"
    message = "The purchase is for a different product than requested."


class PurchaseOwnedByAnotherAccount(AppError):
    """The same store purchase is already attached to a different account.

    Deliberately not resolved by moving it: that would be entitlement theft by
    anybody who learns a transaction id.
    """

    status_code = 409
    code = "purchase_owned_by_another_account"
    message = "This purchase belongs to another account."


class PurchaseAccountMismatch(AppError):
    """The app stamped the purchase with a different account's token."""

    status_code = 409
    code = "purchase_account_mismatch"
    message = "This purchase was made for another account."


class InvalidProviderNotification(AppError):
    status_code = 401
    code = "invalid_provider_notification"
    message = "Notification could not be verified."


class ExternalPaymentNotConfigured(AppError):
    status_code = 503
    code = "external_payment_provider_not_configured"
    message = "Payment for live consultations is not available yet."


class ExternalPaymentUnavailable(AppError):
    status_code = 503
    code = "external_payment_provider_unavailable"
    message = "The payment provider did not answer. Please try again."


# ============================================================ normalisation


def hash_token(token: str) -> str:
    """A Google purchase token is secret-like; we keep only this."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class VerifiedPurchase:
    """A store purchase after the store vouched for it.

    Every field here came from the store (a verified JWS, or the Developer
    API) - never from the client's request body.
    """

    provider: StoreProvider
    purchase_key: str
    store_product_ref: str
    product_kind: str  # subscription / consumable / non_consumable
    status: PurchaseStatus
    environment: StoreEnvironment
    external_transaction_id: str | None = None
    original_transaction_id: str | None = None
    purchase_token_hash: str | None = None
    quantity: int = 1
    purchased_at: datetime | None = None
    expires_at: datetime | None = None
    grace_until: datetime | None = None
    auto_renewing: bool | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    refunded: bool = False
    # Known only when the store reports it (Apple does, Google's purchase APIs
    # do not).
    amount_minor: int | None = None
    currency: str | None = None
    # appAccountToken (Apple) / obfuscatedExternalAccountId (Google): what the
    # app stamped on the purchase for this account.
    account_hint: str | None = None
    # Google: whether the store still expects an acknowledgement / whether a
    # consumable has been consumed there.
    acknowledged: bool = True
    store_consumed: bool = False
    # A Google upgrade/downgrade names the purchase it replaces.
    replaces_purchase_token_hash: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass(slots=True)
class AppleNotification:
    notification_uuid: str
    notification_type: str
    subtype: str | None
    environment: StoreEnvironment
    purchase: VerifiedPurchase | None
    signed_at: datetime | None


@dataclass(slots=True)
class GoogleNotification:
    message_id: str
    package_name: str
    kind: str  # subscription / one_time / voided / test
    notification_type: int | None
    purchase_token: str | None = field(default=None, repr=False)
    product_id: str | None = None
    voided_refund: bool = False
    event_time: datetime | None = None
