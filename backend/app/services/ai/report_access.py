"""Who pays for an AI report, decided in one place.

The invariant: a report type that is sold as a credit is **never delivered**
without either a verified, reserved credit or - when the product says premium
includes it - a verified premium entitlement. Flutter's gating is a
convenience; this is the boundary.

Outcomes:

* ``FREE``             - not a paid report type. B6 behaviour, unchanged.
* ``PREMIUM_INCLUDED`` - a paid type, and the caller's verified premium
  subscription includes it (`PAID_REPORTS_INCLUDED_IN_PREMIUM`). No credit.
* ``CREDIT_REQUIRED``  - a paid type, paid for per delivery with a store
  credit, reserved together with the job under the client's `consumer_ref`.

What is sold is the store catalogue's decision (`payments.catalog`), which
report type each product delivers is this module's: `PAID_REPORT_PRODUCTS`.
Nothing else in the code names a paid report.

Premium comes from `user_entitlements` through `EntitlementPolicyService`
(expiry, grace, revocation) - never from `User.tier` and never from the client.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.domain.ai import ReportType
from app.domain.enums import SubscriptionTier
from app.services.coins.catalog import AI_DEEP_READING, SPECIAL_ANALYSIS
from app.services.features import Feature, has_feature
from app.services.payments.catalog import CATALOG, COSMIC_PLUS, PREMIUM
from app.services.payments.entitlements import EntitlementService

# Report type -> the store product (catalogue code) that sells it.
PAID_REPORT_PRODUCTS: dict[ReportType, str] = {
    ReportType.NATAL: "natal_report",
    ReportType.SYNASTRY: "synastry_report",
    ReportType.YEARLY: "annual_forecast_report",
}

# The prefix a report's credit reservation carries in
# `user_entitlements.consumed_ref`, so it can never collide with - or be
# satisfied by - a reference used on `POST /billing/credits/consume`.
RESERVATION_PREFIX = "ai_report:"


class ReportAccess(StrEnum):
    FREE = "free"
    PREMIUM_INCLUDED = "premium"
    CREDIT_REQUIRED = "credit"
    # Paid with AstroCoins: the spend is taken when the job is created and
    # refunded if the job ends without a report.
    COINS = "coins"


@dataclass(slots=True, frozen=True)
class ReportAccessDecision:
    access: ReportAccess
    product_code: str | None = None
    entitlement_code: str | None = None
    # The coin spend item that pays for it (COINS), or that may pay instead
    # of a credit (CREDIT_REQUIRED).
    coin_item: str | None = None


class ReportPaymentRequired(AppError):
    status_code = 402
    code = "report_payment_required"
    message = "This report needs a purchased credit."


class ReportConsumerRefRequired(AppError):
    status_code = 422
    code = "report_consumer_ref_required"
    message = "A paid report needs a consumer_ref that identifies this purchase attempt."


class ReportCreditConflict(AppError):
    status_code = 409
    code = "report_credit_conflict"
    message = "That consumer_ref was already used for a different report."


class ReportCreditUnavailable(AppError):
    status_code = 409
    code = "report_credit_unavailable"
    message = "The credit held for this report is no longer available."


def _entitlement_code(product_code: str) -> str:
    for definition in CATALOG:
        if definition.code == product_code:
            return definition.entitlement_code
    raise LookupError(product_code)  # pragma: no cover - checked at import


# Fail at import, not at request time, if the mapping names a product the
# catalogue does not sell.
for _product in PAID_REPORT_PRODUCTS.values():
    _entitlement_code(_product)


def report_entitlement_codes() -> frozenset[str]:
    """The credits only a report may spend."""
    return frozenset(_entitlement_code(code) for code in PAID_REPORT_PRODUCTS.values())


def reservation_ref(consumer_ref: str) -> str:
    return f"{RESERVATION_PREFIX}{consumer_ref}"


class ReportAccessPolicy:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def decide(
        self,
        user_id: uuid.UUID,
        report_type: ReportType,
        tier: SubscriptionTier | None = None,
    ) -> ReportAccessDecision:
        # "Astro AI ile Derinleştir" on a reading: Kozmik+ includes it, other
        # plans pay coins. Only enforced with plan gating on.
        if (
            report_type.is_divination
            and tier is not None
            and not has_feature(tier, Feature.ADVANCED_AI)
        ):
            return ReportAccessDecision(ReportAccess.COINS, coin_item=AI_DEEP_READING)
        product = PAID_REPORT_PRODUCTS.get(report_type)
        if product is None:
            return ReportAccessDecision(ReportAccess.FREE)
        entitlement_code = _entitlement_code(product)
        entitlements = EntitlementService(self.session)
        if (
            settings.paid_reports_included_in_cosmic_plus
            and await entitlements.has_access(user_id, COSMIC_PLUS)
        ) or (
            settings.paid_reports_included_in_premium
            and await entitlements.has_access(user_id, PREMIUM)
        ):
            return ReportAccessDecision(
                ReportAccess.PREMIUM_INCLUDED, product, entitlement_code
            )
        return ReportAccessDecision(
            ReportAccess.CREDIT_REQUIRED,
            product,
            entitlement_code,
            coin_item=SPECIAL_ANALYSIS,
        )
