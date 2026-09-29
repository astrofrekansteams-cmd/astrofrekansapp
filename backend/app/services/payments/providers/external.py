"""The external payment provider for live 1:1 expert sessions.

No provider has been chosen. That is a business decision (fees, payout
support in the expert's country, onboarding, the merchant-of-record question),
so this module does **not** hardcode Stripe, iyzico or anybody else. It
defines what any of them must do, and ships two implementations:

* `DisabledExternalPaymentProvider` - the default. Checkout answers
  `external_payment_provider_not_configured`.
* `FakeExternalMarketplacePaymentProvider` - for tests. Refused in production.

**PCI boundary.** Whatever is chosen, card data goes from the client straight
to the provider (hosted page or the provider's own SDK). FastAPI receives an
opaque reference and a signed webhook - never a card number, CVV or a card
form post. That keeps this backend out of PCI DSS scope beyond SAQ-A-style
redirection, and it is the contract below: `create_checkout` returns a
hand-off, not a place to send card details.

Only `LIVE_PERSON_TO_PERSON` line items may reach this rail; the checkout
service enforces that before a provider is ever called.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.services.payments.providers.base import (
    ExternalPaymentNotConfigured,
    ExternalPaymentUnavailable,
    InvalidProviderNotification,
)


@dataclass(slots=True, frozen=True)
class ExternalCheckout:
    external_reference: str
    # What the client does next: open a hosted page, or hand this to the
    # provider SDK. Opaque to us; never card data.
    client_handoff: str = field(repr=False)
    expires_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class ExternalPaymentEvent:
    event_id: str
    event_type: str  # payment_succeeded / payment_failed / refund_succeeded / chargeback
    external_reference: str
    amount_minor: int | None
    currency: str | None
    provider_fee_minor: int | None = None
    external_transaction_ref: str | None = None
    occurred_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class ExternalRefundResult:
    external_refund_ref: str
    succeeded: bool


class ExternalMarketplacePaymentProvider(Protocol):
    name: str

    @property
    def configured(self) -> bool: ...

    async def create_checkout(
        self,
        *,
        intent_id: uuid.UUID,
        amount_minor: int,
        currency: str,
        idempotency_key: str,
    ) -> ExternalCheckout: ...

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> ExternalPaymentEvent: ...

    async def refund(
        self,
        *,
        external_reference: str,
        amount_minor: int,
        currency: str,
        idempotency_key: str,
    ) -> ExternalRefundResult: ...


class DisabledExternalPaymentProvider:
    name = "disabled"
    configured = False

    async def create_checkout(self, **_: object) -> ExternalCheckout:
        raise ExternalPaymentNotConfigured()

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> ExternalPaymentEvent:
        raise ExternalPaymentNotConfigured()

    async def refund(self, **_: object) -> ExternalRefundResult:
        raise ExternalPaymentNotConfigured()


FAKE_WEBHOOK_SECRET = b"fake-external-provider-test-secret"
SIGNATURE_HEADER = "x-fake-signature"


class FakeExternalMarketplacePaymentProvider:
    """A provider that exists only in tests.

    Its webhooks are HMAC-SHA256 signed with a test secret, so the signature
    check is a real check. Knobs make it misbehave.
    """

    name = "fake_external"
    configured = True

    def __init__(self) -> None:
        self.checkouts: dict[str, ExternalCheckout] = {}
        self.refunds: list[tuple[str, int]] = []
        self.unavailable = False
        self.refund_fails = False

    async def create_checkout(
        self,
        *,
        intent_id: uuid.UUID,
        amount_minor: int,
        currency: str,
        idempotency_key: str,
    ) -> ExternalCheckout:
        if self.unavailable:
            raise ExternalPaymentUnavailable()
        # Idempotent on the key, as real providers are.
        reference = f"fx_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:20]}"
        checkout = self.checkouts.get(reference) or ExternalCheckout(
            external_reference=reference,
            client_handoff=f"https://checkout.invalid/{reference}",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        self.checkouts[reference] = checkout
        return checkout

    # ---------------------------------------------------------------- webhooks

    @staticmethod
    def sign(body: bytes) -> str:
        return hmac.new(FAKE_WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()

    def event_body(
        self,
        *,
        event_type: str,
        external_reference: str,
        amount_minor: int,
        currency: str,
        event_id: str | None = None,
        transaction_ref: str | None = None,
    ) -> bytes:
        return json.dumps(
            {
                "id": event_id or f"evt_{uuid.uuid4().hex}",
                "type": event_type,
                "reference": external_reference,
                "amount_minor": amount_minor,
                "currency": currency,
                "transaction": transaction_ref or f"tx_{uuid.uuid4().hex[:16]}",
                "occurred_at": int(datetime.now(UTC).timestamp()),
            }
        ).encode()

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> ExternalPaymentEvent:
        signature = headers.get(SIGNATURE_HEADER, "")
        if not signature or not hmac.compare_digest(signature, self.sign(body)):
            raise InvalidProviderNotification()
        try:
            data = json.loads(body)
            return ExternalPaymentEvent(
                event_id=str(data["id"]),
                event_type=str(data["type"]),
                external_reference=str(data["reference"]),
                amount_minor=int(data["amount_minor"]),
                currency=str(data["currency"]).upper(),
                external_transaction_ref=str(data.get("transaction") or data["id"]),
                occurred_at=datetime.fromtimestamp(int(data["occurred_at"]), tz=UTC),
            )
        except Exception as exc:  # noqa: BLE001
            raise InvalidProviderNotification("Malformed event.") from exc

    async def refund(
        self,
        *,
        external_reference: str,
        amount_minor: int,
        currency: str,
        idempotency_key: str,
    ) -> ExternalRefundResult:
        if self.unavailable:
            raise ExternalPaymentUnavailable()
        if self.refund_fails:
            return ExternalRefundResult(external_refund_ref=f"rf_{idempotency_key}", succeeded=False)
        self.refunds.append((external_reference, amount_minor))
        return ExternalRefundResult(external_refund_ref=f"rf_{idempotency_key}", succeeded=True)
