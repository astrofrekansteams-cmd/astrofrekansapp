"""Choosing the realtime provider.

A missing LiveKit credential is a degraded feature set, never a broken backend:
the app boots, `/health` and `/ready` stay green, and only the call endpoints
answer `call_provider_not_configured`.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.services.calls.provider import RealtimeCommunicationProvider

logger = get_logger(__name__)

_provider: RealtimeCommunicationProvider | None = None


def _build() -> RealtimeCommunicationProvider:
    if settings.realtime_provider == "fake":
        from app.services.calls.fake_provider import FakeRealtimeCommunicationProvider

        return FakeRealtimeCommunicationProvider()

    from app.services.calls.livekit_provider import LiveKitProvider

    return LiveKitProvider()


def get_call_provider() -> RealtimeCommunicationProvider:
    global _provider
    if _provider is None:
        _provider = _build()
    return _provider


def set_call_provider(provider: RealtimeCommunicationProvider | None) -> None:
    """Swap the provider. Tests only; never request handling."""
    global _provider
    _provider = provider


def calls_available() -> bool:
    return settings.calls_configured and get_call_provider().available


async def close_call_provider() -> None:
    global _provider
    if _provider is not None:
        await _provider.close()
        _provider = None


def log_startup_diagnostic() -> dict:
    """Say once, at boot, whether calls will work. A local check only.

    Reports which variables are missing by *name*. Never a value, never a
    prefix of one.
    """
    detail = {
        "configured": settings.calls_configured,
        "provider": settings.realtime_provider,
    }
    if settings.calls_configured:
        logger.info("calls_configured", **detail)
    else:
        missing = [
            name
            for name, value in (
                ("LIVEKIT_URL", settings.livekit_url),
                ("LIVEKIT_API_KEY", settings.livekit_api_key),
                ("LIVEKIT_API_SECRET", settings.livekit_api_secret),
            )
            if not value
        ]
        logger.warning(
            "calls_not_configured",
            missing=missing,
            impact=(
                "Voice and video calls answer 503; the rest of the API is "
                "unaffected."
            ),
            **detail,
        )
        detail["missing"] = missing
    return detail
