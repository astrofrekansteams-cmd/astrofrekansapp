"""Provider selection and service wiring.

A missing API key is a degraded AI feature, never a broken backend: the app
boots, `/health` and `/ready` stay green, and the AI endpoints answer
``ai_not_configured``.

The fake provider is a test double. It is selected only by explicit
configuration and is refused outright in production by
``assert_production_ready``.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.ai.chat import ChatService
from app.services.ai.context.builder import get_context_builder
from app.services.ai.conversations import ConversationService
from app.services.ai.fake_provider import FakeAIProvider
from app.services.ai.generation import GenerationService
from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.provider import AIProvider
from app.services.ai.reports import ReportService
from app.services.ai.sources import SourceResolver
from app.services.astrology.service import get_chart_service
from app.services.forecast.service import get_forecast_service

_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    global _provider
    if _provider is None:
        _provider = (
            FakeAIProvider() if settings.ai_provider == "fake" else OpenAIProvider()
        )
    return _provider


def set_ai_provider(provider: AIProvider | None) -> None:
    """Swap the provider. Used by tests; never by request handling."""
    global _provider
    _provider = provider


def ai_available() -> bool:
    return settings.ai_configured and get_ai_provider().available


def build_generation_service() -> GenerationService:
    return GenerationService(get_ai_provider())


def build_source_resolver(session: AsyncSession) -> SourceResolver:
    return SourceResolver(
        session=session,
        charts=get_chart_service(),
        builder=get_context_builder(),
        forecasts=get_forecast_service(),
    )


def build_chat_service(session: AsyncSession) -> ChatService:
    return ChatService(
        session=session,
        conversations=ConversationService(session),
        resolver=build_source_resolver(session),
        generation=build_generation_service(),
    )


def build_report_service(session: AsyncSession) -> ReportService:
    return ReportService(
        session=session,
        resolver=build_source_resolver(session),
        generation=build_generation_service(),
    )


async def close_ai_provider() -> None:
    global _provider
    if _provider is not None:
        await _provider.close()
        _provider = None
