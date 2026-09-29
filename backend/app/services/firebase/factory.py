"""Choosing between the real Firebase SDK and the test doubles.

A missing service account is a degraded feature set, never a broken backend:
the app boots, `/health` and `/ready` stay green, astrology, the marketplace
and Astro AI all keep working, and only the Firebase-backed endpoints answer
`firebase_not_configured`.

The fake providers are selected by explicit configuration alone, and
`assert_production_ready` refuses them in production.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.services.firebase.fake_provider import (
    FakeFirebaseIdentityProvider,
    FakeFirestoreChatProvider,
    FakePresenceProvider,
    FakePushProvider,
    FakeStorageProvider,
)
from app.services.firebase.provider import FirebaseProviders

logger = get_logger(__name__)

_providers: FirebaseProviders | None = None


def _build() -> FirebaseProviders:
    if settings.firebase_provider == "fake":
        return FirebaseProviders(
            identity=FakeFirebaseIdentityProvider(),
            chat=FakeFirestoreChatProvider(),
            presence=FakePresenceProvider(),
            storage=FakeStorageProvider(),
            push=FakePushProvider(),
        )

    from app.services.firebase.firebase_provider import (
        FirebaseIdentityProviderImpl,
        FirebasePresenceProviderImpl,
        FirebasePushProviderImpl,
        FirebaseStorageProviderImpl,
        FirestoreChatProviderImpl,
    )

    return FirebaseProviders(
        identity=FirebaseIdentityProviderImpl(),
        chat=FirestoreChatProviderImpl(),
        presence=FirebasePresenceProviderImpl(),
        storage=FirebaseStorageProviderImpl(),
        push=FirebasePushProviderImpl(),
    )


def get_firebase() -> FirebaseProviders:
    global _providers
    if _providers is None:
        _providers = _build()
    return _providers


def set_firebase(providers: FirebaseProviders | None) -> None:
    """Swap the providers. Tests only; never request handling."""
    global _providers
    _providers = providers


def firebase_available() -> bool:
    return settings.firebase_configured and get_firebase().available


def fake_providers() -> FirebaseProviders:
    """A fresh set of doubles, for a test to configure and inspect."""
    return FirebaseProviders(
        identity=FakeFirebaseIdentityProvider(),
        chat=FakeFirestoreChatProvider(),
        presence=FakePresenceProvider(),
        storage=FakeStorageProvider(),
        push=FakePushProvider(),
    )


def log_startup_diagnostic() -> dict:
    """Say once, at boot, what the Firebase layer will and will not do.

    A local check only. A boot that calls a third-party service is a boot that
    fails when that service is having a bad morning - and it would fail after
    the load balancer has already been told the process is up.
    """
    configured = settings.firebase_configured
    detail = {
        "configured": configured,
        "provider": settings.firebase_provider,
        "auth_mode": settings.auth_mode,
        "has_storage_bucket": bool(settings.firebase_storage_bucket),
        "has_database_url": bool(settings.firebase_database_url),
    }

    if configured:
        logger.info("firebase_configured", **detail)
    else:
        missing = []
        if not settings.firebase_project_id:
            missing.append("FIREBASE_PROJECT_ID")
        if not (
            settings.firebase_credentials_json or settings.firebase_credentials_path
        ):
            missing.append("FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH")
        logger.warning(
            "firebase_not_configured",
            missing=missing,
            impact=(
                "Chat, presence, attachments and push answer 503; the rest of "
                "the API is unaffected."
            ),
            **detail,
        )
        detail["missing"] = missing

    return detail
