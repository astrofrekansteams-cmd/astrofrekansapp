"""Configuration diagnostics for the AI layer.

This answers "why is AI off?" without asking the provider anything. Startup
must not depend on a third party being reachable: a boot that calls an
external API is a boot that fails when that API is having a bad morning, and
this one would fail *after* the load balancer has already been told the
process is coming up.

So the check is local and free - is a provider selected, is there a key, which
models would we ask for - and it is exposed on `/ai/status` so an operator can
see the answer without shell access.

Nothing here ever returns a key, a key prefix, or anything derived from one.
A boolean is enough to tell an operator what to fix.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.ai import ModelTier, UseCase
from app.services.ai.router import get_model_router

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class AIDiagnostic:
    configured: bool
    provider: str
    models: dict[str, str]
    fallback: dict[str, bool]
    reason: str | None = None


def describe() -> AIDiagnostic:
    """What this server is configured to do. No network calls."""
    router = get_model_router()
    models = {
        "low_cost": router.model_for_tier(ModelTier.LOW_COST),
        "standard": router.model_for_tier(ModelTier.STANDARD),
        "premium": router.model_for_tier(ModelTier.PREMIUM),
    }
    fallback = {
        "chat": router.fallback_allowed(UseCase.CHAT),
        "summary": router.fallback_allowed(UseCase.SUMMARY),
        "report": router.fallback_allowed(UseCase.REPORT),
    }

    reason: str | None = None
    if settings.ai_provider == "openai" and not settings.openai_api_key:
        reason = "OPENAI_API_KEY is not set on this server."

    return AIDiagnostic(
        configured=settings.ai_configured,
        provider=settings.ai_provider,
        models=models,
        fallback=fallback,
        reason=reason,
    )


def log_startup_diagnostic() -> AIDiagnostic:
    """Say once, at boot, what the AI layer will and will not do.

    Deliberately never raises. A missing key degrades a feature; it must not
    stop the application from serving everything else.
    """
    diagnostic = describe()
    if diagnostic.configured:
        logger.info(
            "ai_configured",
            provider=diagnostic.provider,
            **{f"model_{key}": value for key, value in diagnostic.models.items()},
            fallback_report=diagnostic.fallback["report"],
        )
    else:
        logger.warning(
            "ai_not_configured",
            provider=diagnostic.provider,
            reason=diagnostic.reason,
            impact="AI endpoints answer 503; the rest of the API is unaffected.",
        )
    return diagnostic
