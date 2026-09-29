"""Store doubles for tests. Refused in production.

Like the LiveKit fake in B10, the parts that matter are real:

* **Apple** - transactions and notifications are genuine ES256 JWS with an x5c
  chain, and they are verified by Apple's own `SignedDataVerifier` against a
  throwaway root certificate generated here. The chain carries Apple's two
  marker OIDs, because the library checks them. So a test that forges a
  signature, a bundle id or an environment is attacking Apple's real code.
* **Google** - responses are raw Developer API JSON, run through the same
  normalisation as the real provider. Pub/Sub push tokens are real RS256 JWTs
  from a throwaway key, checked with the same claim validation.

Nothing generated here is a credential for anything: the root certificate,
the keys and the service-account email exist only in this process.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID

from app.services.payments.providers.apple import LibraryBackedAppleVerifier, normalise_transaction
from app.services.payments.providers.base import (
    AppleNotification,
    InvalidProviderNotification,
    StoreUnavailable,
    StoreVerificationFailed,
    VerifiedPurchase,
)
from app.services.payments.providers.google import (
    normalise_product,
    normalise_subscription,
    validate_push_claims,
)

FAKE_BUNDLE_ID = "com.astrofrekans.app"
FAKE_APP_APPLE_ID = 1234567890
FAKE_PACKAGE = "com.astrofrekans.app"
FAKE_PUSH_AUDIENCE = "https://api.astrofrekans.invalid/api/v1/webhooks/google/play"
FAKE_PUSH_ACCOUNT = "rtdn-push@astrofrekans-test.iam.gserviceaccount.invalid"

APPLE_LEAF_OID = "1.2.840.113635.100.6.11.1"
APPLE_INTERMEDIATE_OID = "1.2.840.113635.100.6.2.1"


def _ms(moment: datetime | None) -> int | None:
    return int(moment.timestamp() * 1000) if moment else None


# ================================================================== Apple


class _TestChain:
    """Root -> intermediate -> leaf, shaped like Apple's."""

    def __init__(self) -> None:
        now = datetime.now(UTC) - timedelta(days=1)
        later = now + timedelta(days=3650)

        def name(common: str) -> x509.Name:
            return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common)])

        self.root_key = ec.generate_private_key(ec.SECP256R1())
        self.intermediate_key = ec.generate_private_key(ec.SECP256R1())
        self.leaf_key = ec.generate_private_key(ec.SECP256R1())

        def build(subject, issuer, public, signer, *, ca, pathlen=None, oid=None, issuer_public=None):  # noqa: ANN001,ANN202
            builder = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(public)
                .serial_number(x509.random_serial_number())
                .not_valid_before(now)
                .not_valid_after(later)
                .add_extension(x509.BasicConstraints(ca=ca, path_length=pathlen), critical=True)
                .add_extension(
                    x509.KeyUsage(
                        digital_signature=not ca,
                        content_commitment=False,
                        key_encipherment=False,
                        data_encipherment=False,
                        key_agreement=False,
                        key_cert_sign=ca,
                        crl_sign=ca,
                        encipher_only=False,
                        decipher_only=False,
                    ),
                    critical=True,
                )
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(public), critical=False)
            )
            if issuer_public is not None:
                builder = builder.add_extension(
                    x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_public),
                    critical=False,
                )
            if oid:
                builder = builder.add_extension(
                    x509.UnrecognizedExtension(x509.ObjectIdentifier(oid), b"\x05\x00"),
                    critical=False,
                )
            return builder.sign(signer, hashes.SHA256())

        self.root = build(
            name("Astrofrekans Test Root"), name("Astrofrekans Test Root"),
            self.root_key.public_key(), self.root_key, ca=True,
        )
        self.intermediate = build(
            name("Astrofrekans Test Intermediate"), self.root.subject,
            self.intermediate_key.public_key(), self.root_key, ca=True, pathlen=0,
            oid=APPLE_INTERMEDIATE_OID, issuer_public=self.root_key.public_key(),
        )
        self.leaf = build(
            name("Astrofrekans Test Signing"), self.intermediate.subject,
            self.leaf_key.public_key(), self.intermediate_key, ca=False,
            oid=APPLE_LEAF_OID, issuer_public=self.intermediate_key.public_key(),
        )

    def x5c(self) -> list[str]:
        return [
            base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode()
            for cert in (self.leaf, self.intermediate, self.root)
        ]

    def root_der(self) -> bytes:
        return self.root.public_bytes(serialization.Encoding.DER)


_CHAIN: _TestChain | None = None


def _chain() -> _TestChain:
    # Generating keys is the slow part; one chain per test process is plenty.
    global _CHAIN
    if _CHAIN is None:
        _CHAIN = _TestChain()
    return _CHAIN


class FakeAppleStoreProvider:
    name = "apple"
    configured = True

    def __init__(self, *, environment: str = "Production", accept_sandbox: bool = False) -> None:
        self.environment = environment
        self._verifier = LibraryBackedAppleVerifier(
            root_certificates=[_chain().root_der()],
            bundle_id=FAKE_BUNDLE_ID,
            app_apple_id=FAKE_APP_APPLE_ID,
            environment=environment,
            accept_sandbox=accept_sandbox,
            online_checks=False,
        )
        # What the App Store Server API would return: transaction id -> JWS.
        self.server_transactions: dict[str, str] = {}
        self.server_renewals: dict[str, str] = {}
        self.api_configured = True
        self.unavailable = False
        self.calls: list[str] = []

    # ---------------------------------------------------------- test helpers

    def sign(self, payload: dict[str, Any], *, forge: bool = False) -> str:
        key = ec.generate_private_key(ec.SECP256R1()) if forge else _chain().leaf_key
        return jwt.encode(payload, key, algorithm="ES256", headers={"x5c": _chain().x5c()})

    def transaction(
        self,
        *,
        product_id: str,
        type_: str = "Auto-Renewable Subscription",
        transaction_id: str | None = None,
        original_transaction_id: str | None = None,
        expires_in: timedelta | None = timedelta(days=30),
        revoked: bool = False,
        environment: str | None = None,
        bundle_id: str = FAKE_BUNDLE_ID,
        app_account_token: str | None = None,
        price_milli: int | None = 99_990,
        currency: str = "TRY",
        quantity: int = 1,
        forge: bool = False,
        register: bool = True,
    ) -> str:
        now = datetime.now(UTC)
        transaction_id = transaction_id or str(uuid.uuid4().int)[:16]
        payload = {
            "transactionId": transaction_id,
            "originalTransactionId": original_transaction_id or transaction_id,
            "bundleId": bundle_id,
            "productId": product_id,
            "purchaseDate": _ms(now - timedelta(minutes=1)),
            "originalPurchaseDate": _ms(now - timedelta(minutes=1)),
            "quantity": quantity,
            "type": type_,
            "inAppOwnershipType": "PURCHASED",
            "signedDate": _ms(now),
            "environment": environment or self.environment,
            "transactionReason": "PURCHASE",
            "storefront": "TUR",
            "storefrontId": "143480",
        }
        if type_ == "Auto-Renewable Subscription" and expires_in is not None:
            payload["expiresDate"] = _ms(now + expires_in)
        if revoked:
            payload["revocationDate"] = _ms(now)
            payload["revocationReason"] = 0
        if app_account_token:
            payload["appAccountToken"] = app_account_token
        if price_milli is not None:
            payload["price"] = price_milli
            payload["currency"] = currency
        signed = self.sign(payload, forge=forge)
        if register and not forge:
            self.server_transactions[transaction_id] = signed
        return signed

    def renewal(
        self,
        *,
        original_transaction_id: str,
        product_id: str,
        auto_renew: bool = True,
        in_billing_retry: bool = False,
        grace_until: datetime | None = None,
    ) -> str:
        payload = {
            "originalTransactionId": original_transaction_id,
            "autoRenewProductId": product_id,
            "productId": product_id,
            "autoRenewStatus": 1 if auto_renew else 0,
            "isInBillingRetryPeriod": in_billing_retry,
            "signedDate": _ms(datetime.now(UTC)),
            "environment": self.environment,
        }
        if grace_until:
            payload["gracePeriodExpiresDate"] = _ms(grace_until)
        signed = self.sign(payload)
        self.server_renewals[original_transaction_id] = signed
        return signed

    def notification(
        self,
        *,
        notification_type: str,
        signed_transaction: str | None,
        signed_renewal: str | None = None,
        subtype: str | None = None,
        notification_uuid: str | None = None,
        bundle_id: str = FAKE_BUNDLE_ID,
        forge: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "notificationType": notification_type,
            "notificationUUID": notification_uuid or str(uuid.uuid4()),
            "version": "2.0",
            "signedDate": _ms(datetime.now(UTC)),
            "data": {
                "environment": self.environment,
                "appAppleId": FAKE_APP_APPLE_ID,
                "bundleId": bundle_id,
                "bundleVersion": "1",
            },
        }
        if subtype:
            payload["subtype"] = subtype
        if signed_transaction:
            payload["data"]["signedTransactionInfo"] = signed_transaction
        if signed_renewal:
            payload["data"]["signedRenewalInfo"] = signed_renewal
        return self.sign(payload, forge=forge)

    # -------------------------------------------------------------- protocol

    def verify_signed_transaction(self, signed_transaction: str) -> VerifiedPurchase:
        return normalise_transaction(self._verifier.transaction(signed_transaction))

    def _check(self, operation: str) -> None:
        self.calls.append(operation)
        if self.unavailable:
            raise StoreUnavailable()

    async def fetch_transaction(self, transaction_id: str) -> VerifiedPurchase:
        self._check("get_transaction_info")
        signed = self.server_transactions.get(transaction_id)
        if signed is None:
            raise StoreVerificationFailed("The App Store does not know that transaction.")
        return self.verify_signed_transaction(signed)

    async def fetch_subscription(self, any_transaction_id: str) -> VerifiedPurchase:
        self._check("get_all_subscription_statuses")
        latest = None
        for signed in self.server_transactions.values():
            decoded = self._verifier.transaction(signed)
            if decoded.originalTransactionId == any_transaction_id:
                if latest is None or (decoded.purchaseDate or 0) >= (latest.purchaseDate or 0):
                    latest = decoded
        if latest is None:
            raise StoreVerificationFailed("No such subscription.")
        renewal_jws = self.server_renewals.get(any_transaction_id)
        renewal = self._verifier.renewal(renewal_jws) if renewal_jws else None
        return normalise_transaction(latest, renewal)

    def verify_notification(self, signed_payload: str) -> AppleNotification:
        return self._verifier.decode_notification(signed_payload)


# ================================================================= Google


class _PushKey:
    def __init__(self) -> None:
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public = self.private.public_key()


_PUSH_KEY: _PushKey | None = None


def _push_key() -> _PushKey:
    global _PUSH_KEY
    if _PUSH_KEY is None:
        _PUSH_KEY = _PushKey()
    return _PUSH_KEY


class FakeGooglePlayProvider:
    name = "google"
    configured = True

    def __init__(self) -> None:
        self.subscriptions: dict[str, dict[str, Any]] = {}
        self.products: dict[str, dict[str, Any]] = {}
        self.acknowledged: list[tuple[str, str]] = []
        self.consumed: list[tuple[str, str]] = []
        self.fetches: list[str] = []
        self.unavailable = False
        self.fail_acknowledge = False

    # ---------------------------------------------------------- test helpers

    def add_subscription(
        self,
        token: str,
        *,
        product_id: str,
        state: str = "SUBSCRIPTION_STATE_ACTIVE",
        expires_in: timedelta = timedelta(days=30),
        order_id: str | None = None,
        test: bool = False,
        acknowledged: bool = False,
        account: str | None = None,
        auto_renew: bool = True,
        linked_token: str | None = None,
    ) -> None:
        data: dict[str, Any] = {
            "kind": "androidpublisher#subscriptionPurchaseV2",
            "regionCode": "TR",
            "startTime": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "subscriptionState": state,
            "latestOrderId": order_id or f"GPA.{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}",
            "acknowledgementState": (
                "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED" if acknowledged else "ACKNOWLEDGEMENT_STATE_PENDING"
            ),
            "lineItems": [
                {
                    "productId": product_id,
                    "expiryTime": (datetime.now(UTC) + expires_in).isoformat().replace("+00:00", "Z"),
                    "autoRenewingPlan": {"autoRenewEnabled": auto_renew},
                }
            ],
        }
        if test:
            data["testPurchase"] = {}
        if account:
            data["externalAccountIdentifiers"] = {"obfuscatedExternalAccountId": account}
        if linked_token:
            data["linkedPurchaseToken"] = linked_token
        self.subscriptions[token] = data

    def add_product(
        self,
        token: str,
        *,
        product_id: str,
        state: str = "PURCHASED",
        order_id: str | None = None,
        quantity: int = 1,
        test: bool = False,
        acknowledged: bool = False,
        account: str | None = None,
    ) -> None:
        data: dict[str, Any] = {
            "kind": "androidpublisher#productPurchaseV2",
            "orderId": order_id or f"GPA.{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}",
            "purchaseStateContext": {"purchaseState": state},
            "purchaseCompletionTime": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "acknowledgementState": (
                "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED" if acknowledged else "ACKNOWLEDGEMENT_STATE_PENDING"
            ),
            "productLineItem": [
                {
                    "productId": product_id,
                    "productOfferDetails": {
                        "quantity": quantity,
                        "consumptionState": "CONSUMPTION_STATE_YET_TO_BE_CONSUMED",
                    },
                }
            ],
        }
        if test:
            data["testPurchaseContext"] = {"fopType": "TEST"}
        if account:
            data["obfuscatedExternalAccountId"] = account
        self.products[token] = data

    def push_authorization(
        self,
        *,
        audience: str = FAKE_PUSH_AUDIENCE,
        email: str = FAKE_PUSH_ACCOUNT,
        issuer: str = "https://accounts.google.com",
        email_verified: bool = True,
        forge: bool = False,
    ) -> str:
        now = datetime.now(UTC)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if forge else _push_key().private
        token = jwt.encode(
            {
                "aud": audience,
                "iss": issuer,
                "email": email,
                "email_verified": email_verified,
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=5)).timestamp()),
                "sub": "1234567890",
            },
            key,
            algorithm="RS256",
        )
        return f"Bearer {token}"

    @staticmethod
    def push_body(notification: dict[str, Any], *, message_id: str | None = None) -> bytes:
        payload = {"version": "1.0", "packageName": FAKE_PACKAGE,
                   "eventTimeMillis": str(int(datetime.now(UTC).timestamp() * 1000)), **notification}
        return json.dumps(
            {
                "message": {
                    "data": base64.b64encode(json.dumps(payload).encode()).decode(),
                    "messageId": message_id or uuid.uuid4().hex,
                },
                "subscription": "projects/test/subscriptions/rtdn",
            }
        ).encode()

    # -------------------------------------------------------------- protocol

    def _check(self) -> None:
        if self.unavailable:
            raise StoreUnavailable()

    async def get_subscription(self, token: str) -> VerifiedPurchase:
        self._check()
        self.fetches.append("subscriptionsv2.get")
        data = self.subscriptions.get(token)
        if data is None:
            raise StoreVerificationFailed()
        return normalise_subscription(token, data)

    async def get_product(self, token: str) -> VerifiedPurchase:
        self._check()
        self.fetches.append("productsv2.get")
        data = self.products.get(token)
        if data is None:
            raise StoreVerificationFailed()
        return normalise_product(token, data)

    async def acknowledge_subscription(self, product_id: str, token: str) -> None:
        self._check()
        if self.fail_acknowledge:
            raise StoreUnavailable()
        self.acknowledged.append((product_id, token))
        if token in self.subscriptions:
            self.subscriptions[token]["acknowledgementState"] = "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"

    async def acknowledge_product(self, product_id: str, token: str) -> None:
        self._check()
        if self.fail_acknowledge:
            raise StoreUnavailable()
        self.acknowledged.append((product_id, token))
        if token in self.products:
            self.products[token]["acknowledgementState"] = "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"

    async def consume_product(self, product_id: str, token: str) -> None:
        self._check()
        if self.fail_acknowledge:
            raise StoreUnavailable()
        self.consumed.append((product_id, token))
        if token in self.products:
            line = self.products[token]["productLineItem"][0]["productOfferDetails"]
            line["consumptionState"] = "CONSUMPTION_STATE_CONSUMED"

    async def verify_push(self, authorization: str | None) -> None:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise InvalidProviderNotification()
        try:
            claims = jwt.decode(
                authorization[7:].strip(),
                _push_key().public,
                algorithms=["RS256"],
                audience=FAKE_PUSH_AUDIENCE,
            )
        except jwt.PyJWTError as exc:
            raise InvalidProviderNotification() from exc
        validate_push_claims(claims, audience=FAKE_PUSH_AUDIENCE, service_account=FAKE_PUSH_ACCOUNT)
