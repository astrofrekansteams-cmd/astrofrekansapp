"""Choosing payment providers.

Missing credentials are a degraded feature set, never a broken backend: the
app boots, `/health` stays green, and only the endpoints that need a store or
the external provider answer a controlled 503.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_apple: Any = None
_google: Any = None
_external: Any = None


def get_apple_provider():  # noqa: ANN201 - AppleStoreProvider
    global _apple
    if _apple is None:
        if settings.store_provider == "fake":
            from app.services.payments.providers.fakes import FakeAppleStoreProvider

            _apple = FakeAppleStoreProvider()
        else:
            from app.services.payments.providers.apple import AppStoreProvider

            _apple = AppStoreProvider()
    return _apple


def get_google_provider():  # noqa: ANN201 - GooglePlayProvider
    global _google
    if _google is None:
        if settings.store_provider == "fake":
            from app.services.payments.providers.fakes import FakeGooglePlayProvider

            _google = FakeGooglePlayProvider()
        else:
            from app.services.payments.providers.google import PlayDeveloperApiProvider

            _google = PlayDeveloperApiProvider()
    return _google


def get_external_provider():  # noqa: ANN201 - ExternalMarketplacePaymentProvider
    global _external
    if _external is None:
        from app.services.payments.providers import external

        if settings.external_payment_provider == "fake":
            _external = external.FakeExternalMarketplacePaymentProvider()
        else:
            _external = external.DisabledExternalPaymentProvider()
    return _external


def set_payment_providers(*, apple: Any = None, google: Any = None, external: Any = None) -> None:
    """Tests only. Passing nothing resets all three."""
    global _apple, _google, _external
    _apple, _google, _external = apple, google, external


def billing_status() -> dict[str, bool]:
    """What `GET /billing/status` may say. Booleans only - no ids, no keys."""
    return {
        "apple_configured": bool(get_apple_provider().configured),
        "google_configured": bool(get_google_provider().configured),
        "external_marketplace_configured": bool(get_external_provider().configured),
    }


def log_startup_diagnostic() -> dict[str, bool]:
    status = billing_status()
    missing: list[str] = []
    if not status["apple_configured"]:
        missing.append("APPLE_BUNDLE_ID + APPLE_ROOT_CERTIFICATES_PATH")
    if not status["google_configured"]:
        missing.append("GOOGLE_PLAY_PACKAGE_NAME + GOOGLE_PLAY_SERVICE_ACCOUNT_JSON/PATH")
    if missing or not status["external_marketplace_configured"]:
        logger.warning(
            "payments_partially_configured",
            missing=missing,
            external_payment_provider=settings.external_payment_provider,
            impact="Unconfigured rails answer 503; everything else is unaffected.",
            **status,
        )
    else:
        logger.info("payments_configured", **status)
    return status
