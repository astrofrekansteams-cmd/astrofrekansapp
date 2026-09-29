"""The App Store: verification and the App Store Server API.

Written against Apple's own `app-store-server-library==3.1.2`, read from the
installed source. What that source says, and what it means here:

* `SignedDataVerifier` verifies every JWS: the x5c chain up to an Apple root
  certificate, Apple's two marker OIDs on the leaf and intermediate, ES256,
  the bundle id and the environment. Optionally OCSP (on by default here).
* In `Environment.XCODE` and `Environment.LOCAL_TESTING` the library **skips
  signature verification entirely**. Those environments are therefore not
  selectable: configuration accepts only Production and Sandbox.
* Production verification requires the numeric App Apple ID.
* Transactions are StoreKit 2 JWS (`signedTransactionInfo`). The legacy
  `verifyReceipt` flow is not used anywhere.
* Server notifications are V2: a `signedPayload` JWS, whose `data` carries a
  signed transaction and signed renewal info - each verified again.

Nothing here decides entitlement. It returns a `VerifiedPurchase`; the
purchase service decides what it means.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.payments import (
    PurchaseStatus,
    StoreEnvironment,
    StoreProvider,
    milliunits_to_minor,
)
from app.services.payments.providers.base import (
    AppleNotification,
    StoreEnvironmentRejected,
    StoreNotConfigured,
    StoreUnavailable,
    StoreVerificationFailed,
    VerifiedPurchase,
)

logger = get_logger(__name__)

_APPLE_TYPES = {
    "Auto-Renewable Subscription": "subscription",
    "Non-Renewing Subscription": "subscription",
    "Consumable": "consumable",
    "Non-Consumable": "non_consumable",
}

# App Store Server API subscription status codes.
_STATUS = {1: "active", 2: "expired", 3: "billing_retry", 4: "grace", 5: "revoked"}


class AppleStoreProvider(Protocol):
    name: str

    @property
    def configured(self) -> bool: ...

    @property
    def api_configured(self) -> bool: ...

    def verify_signed_transaction(self, signed_transaction: str) -> VerifiedPurchase: ...

    async def fetch_transaction(self, transaction_id: str) -> VerifiedPurchase: ...

    async def fetch_subscription(self, any_transaction_id: str) -> VerifiedPurchase: ...

    def verify_notification(self, signed_payload: str) -> AppleNotification: ...


def _ms(value: Any) -> datetime | None:
    if value in (None, 0):
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


def _environment(value: Any) -> StoreEnvironment:
    text = getattr(value, "value", value)
    return StoreEnvironment.PRODUCTION if text == "Production" else StoreEnvironment.SANDBOX


def normalise_transaction(
    transaction: Any, renewal: Any | None = None, *, status_code: int | None = None
) -> VerifiedPurchase:
    """A decoded JWSTransaction (+ renewal info / API status) -> VerifiedPurchase.

    The mapping, which docs/store_billing.md repeats:

    * `revocationDate` set -> REVOKED (a refund, or Family Sharing removed).
    * subscription, status 4 or in billing retry with a grace date in the
      future -> GRACE_PERIOD; billing retry without grace -> ON_HOLD.
    * subscription past `expiresDate` -> EXPIRED.
    * auto-renew switched off but not yet expired -> CANCELLED_PENDING_EXPIRY.
    * otherwise ACTIVE. One-time purchases are ACTIVE unless revoked.
    """
    now = datetime.now(UTC)
    kind = _APPLE_TYPES.get(getattr(transaction.type, "value", transaction.type), "non_consumable")
    expires = _ms(transaction.expiresDate)
    revoked = _ms(transaction.revocationDate)
    grace_until = _ms(getattr(renewal, "gracePeriodExpiresDate", None)) if renewal else None
    auto_renew = None
    if renewal is not None and renewal.autoRenewStatus is not None:
        auto_renew = int(getattr(renewal.autoRenewStatus, "value", renewal.autoRenewStatus)) == 1
    in_retry = bool(renewal and renewal.isInBillingRetryPeriod)
    code = _STATUS.get(status_code) if status_code else None

    if revoked is not None or code == "revoked":
        status = PurchaseStatus.REVOKED
    elif kind != "subscription":
        status = PurchaseStatus.ACTIVE
    elif code == "grace" or (in_retry and grace_until is not None and grace_until > now):
        status = PurchaseStatus.GRACE_PERIOD
    elif code == "billing_retry" or in_retry:
        status = PurchaseStatus.ON_HOLD
    elif code == "expired" or (expires is not None and expires <= now):
        status = PurchaseStatus.EXPIRED
    elif auto_renew is False:
        status = PurchaseStatus.CANCELLED_PENDING_EXPIRY
    else:
        status = PurchaseStatus.ACTIVE

    currency = transaction.currency
    amount = None
    if transaction.price is not None and currency:
        amount = milliunits_to_minor(int(transaction.price), currency)

    original = transaction.originalTransactionId
    return VerifiedPurchase(
        provider=StoreProvider.APPLE,
        purchase_key=(original if kind == "subscription" and original else transaction.transactionId),
        store_product_ref=transaction.productId,
        product_kind=kind,
        status=status,
        environment=_environment(transaction.environment),
        external_transaction_id=transaction.transactionId,
        original_transaction_id=original,
        quantity=int(transaction.quantity or 1),
        purchased_at=_ms(transaction.purchaseDate),
        expires_at=expires,
        grace_until=grace_until,
        auto_renewing=auto_renew,
        revoked_at=revoked,
        revocation_reason=(
            str(getattr(transaction.revocationReason, "value", transaction.revocationReason))
            if transaction.revocationReason is not None
            else None
        ),
        refunded=revoked is not None,
        amount_minor=amount,
        currency=currency,
        account_hint=str(transaction.appAccountToken) if transaction.appAccountToken else None,
    )


def translate_verification_error(exc: Exception) -> Exception:
    """Apple's VerificationException -> our stable errors."""
    from appstoreserverlibrary.signed_data_verifier import VerificationStatus

    status = getattr(exc, "status", None)
    if status == VerificationStatus.INVALID_ENVIRONMENT:
        return StoreEnvironmentRejected()
    return StoreVerificationFailed()


class LibraryBackedAppleVerifier:
    """Verification with Apple's library, for a given root set.

    Shared by the real provider and the fake: the fake passes a test root, so
    tests run Apple's real chain and signature checks.
    """

    def __init__(
        self,
        *,
        root_certificates: list[bytes],
        bundle_id: str,
        app_apple_id: int | None,
        environment: str,
        accept_sandbox: bool,
        online_checks: bool,
    ) -> None:
        from appstoreserverlibrary.models.Environment import Environment
        from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier

        if environment not in ("Production", "Sandbox"):
            # Xcode / LocalTesting skip signature checks inside the library.
            raise ValueError("Only Production and Sandbox App Store environments are allowed.")
        self._primary = SignedDataVerifier(
            root_certificates,
            online_checks,
            Environment(environment),
            bundle_id,
            app_apple_id,
        )
        self._sandbox = None
        if environment == "Production" and accept_sandbox:
            self._sandbox = SignedDataVerifier(
                root_certificates, online_checks, Environment.SANDBOX, bundle_id, app_apple_id
            )

    def _each(self):
        yield self._primary
        if self._sandbox is not None:
            yield self._sandbox

    def transaction(self, signed: str) -> Any:
        from appstoreserverlibrary.signed_data_verifier import VerificationException

        last: Exception | None = None
        for verifier in self._each():
            try:
                return verifier.verify_and_decode_signed_transaction(signed)
            except VerificationException as exc:
                last = exc
        raise translate_verification_error(last) from last

    def renewal(self, signed: str) -> Any:
        from appstoreserverlibrary.signed_data_verifier import VerificationException

        last: Exception | None = None
        for verifier in self._each():
            try:
                return verifier.verify_and_decode_renewal_info(signed)
            except VerificationException as exc:
                last = exc
        raise translate_verification_error(last) from last

    def notification(self, signed: str) -> Any:
        from appstoreserverlibrary.signed_data_verifier import VerificationException

        last: Exception | None = None
        for verifier in self._each():
            try:
                return verifier.verify_and_decode_notification(signed)
            except VerificationException as exc:
                last = exc
        raise translate_verification_error(last) from last

    def decode_notification(self, signed_payload: str) -> AppleNotification:
        decoded = self.notification(signed_payload)
        purchase = None
        data = decoded.data
        environment = StoreEnvironment.PRODUCTION
        if data is not None:
            environment = _environment(data.environment)
            if data.signedTransactionInfo:
                transaction = self.transaction(data.signedTransactionInfo)
                renewal = self.renewal(data.signedRenewalInfo) if data.signedRenewalInfo else None
                purchase = normalise_transaction(transaction, renewal)
        return AppleNotification(
            notification_uuid=decoded.notificationUUID,
            notification_type=getattr(decoded.notificationType, "value", decoded.notificationType),
            subtype=getattr(decoded.subtype, "value", decoded.subtype) if decoded.subtype else None,
            environment=environment,
            purchase=purchase,
            signed_at=_ms(decoded.signedDate),
        )


def _load_roots(path: Path) -> list[bytes]:
    files = sorted(path.glob("*.cer")) + sorted(path.glob("*.der"))
    return [file.read_bytes() for file in files]


class AppStoreProvider:
    """The real App Store. Unverified live: no credentials exist yet."""

    name = "apple"

    def __init__(self) -> None:
        self._verifier: LibraryBackedAppleVerifier | None = None
        self._clients: dict[str, Any] = {}

    @property
    def configured(self) -> bool:
        return settings.apple_configured

    @property
    def api_configured(self) -> bool:
        return settings.apple_api_configured

    def _get_verifier(self) -> LibraryBackedAppleVerifier:
        if not self.configured:
            raise StoreNotConfigured()
        if self._verifier is None:
            roots = _load_roots(Path(settings.apple_root_certificates_path))
            if not roots:
                raise StoreNotConfigured("No Apple root certificates were found.")
            self._verifier = LibraryBackedAppleVerifier(
                root_certificates=roots,
                bundle_id=settings.apple_bundle_id or "",
                app_apple_id=settings.apple_app_apple_id,
                environment=settings.apple_environment,
                accept_sandbox=settings.apple_accept_sandbox_in_production,
                online_checks=settings.apple_enable_online_checks,
            )
        return self._verifier

    def _client(self, environment: str):  # noqa: ANN202 - library type
        if not self.api_configured:
            raise StoreNotConfigured("The App Store Server API is not configured.")
        if environment not in self._clients:
            from appstoreserverlibrary.api_client import AsyncAppStoreServerAPIClient
            from appstoreserverlibrary.models.Environment import Environment

            key = settings.apple_private_key
            if not key and settings.apple_private_key_path:
                key = Path(settings.apple_private_key_path).read_text(encoding="utf-8")
            self._clients[environment] = AsyncAppStoreServerAPIClient(
                (key or "").encode("utf-8"),
                settings.apple_key_id or "",
                settings.apple_issuer_id or "",
                settings.apple_bundle_id or "",
                Environment(environment),
            )
        return self._clients[environment]

    def verify_signed_transaction(self, signed_transaction: str) -> VerifiedPurchase:
        return normalise_transaction(self._get_verifier().transaction(signed_transaction))

    async def _call(self, operation: str, coroutine):  # noqa: ANN001,ANN202
        from appstoreserverlibrary.api_client import APIException

        try:
            return await asyncio.wait_for(coroutine, timeout=10)
        except APIException as exc:
            status = getattr(exc, "http_status_code", None)
            logger.warning("apple_api_error", operation=operation, http_status=status)
            if status in (404,):
                raise StoreVerificationFailed("The App Store does not know that transaction.") from exc
            raise StoreUnavailable() from exc
        except (TimeoutError, asyncio.TimeoutError) as exc:
            logger.warning("apple_api_timeout", operation=operation)
            raise StoreUnavailable() from exc

    async def fetch_transaction(self, transaction_id: str) -> VerifiedPurchase:
        response = await self._call(
            "get_transaction_info",
            self._client(settings.apple_environment).get_transaction_info(transaction_id),
        )
        return self.verify_signed_transaction(response.signedTransactionInfo)

    async def fetch_subscription(self, any_transaction_id: str) -> VerifiedPurchase:
        response = await self._call(
            "get_all_subscription_statuses",
            self._client(settings.apple_environment).get_all_subscription_statuses(
                any_transaction_id
            ),
        )
        verifier = self._get_verifier()
        for group in response.data or []:
            for item in group.lastTransactions or []:
                if not item.signedTransactionInfo:
                    continue
                # Verified before it is even compared: nothing unsigned is
                # allowed to choose which subscription we look at.
                transaction = verifier.transaction(item.signedTransactionInfo)
                if transaction.originalTransactionId != any_transaction_id:
                    continue
                renewal = (
                    verifier.renewal(item.signedRenewalInfo) if item.signedRenewalInfo else None
                )
                status = getattr(item.status, "value", item.status)
                return normalise_transaction(transaction, renewal, status_code=status)
        raise StoreVerificationFailed("The App Store returned no status for that subscription.")

    def verify_notification(self, signed_payload: str) -> AppleNotification:
        return self._get_verifier().decode_notification(signed_payload)
