"""Resolving what a request is *about*, with authorisation first.

Every path here checks ownership **before** any data is assembled and long
before anything is sent to a model. A source id belonging to another user
resolves to 404 - never a 403 that confirms it exists, and never a context
built from data the caller is not entitled to.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import MissingBirthData, NotFound
from app.db.models.ai import AIReport
from app.db.models.compatibility import CompatibilityReport
from app.db.models.horary import HoraryQuestion
from app.db.models.user import User
from app.domain.ai import AstroContext, ContextType, Locale, ReportType
from app.services.ai.context.builder import AstroAIContextBuilder
from app.services.astrology.service import ChartService
from app.services.forecast.service import ForecastService
from app.services.horary.service import HoraryService
from app.services.users.service import UserService


@dataclass(slots=True)
class ResolvedSource:
    """The verified material a generation will run on."""

    context: AstroContext
    source_type: str
    source_id: uuid.UUID | None
    engine_version: str
    label: str | None = None
    extra_fingerprint: dict[str, Any] | None = None


class SourceResolver:
    def __init__(
        self,
        session: AsyncSession,
        charts: ChartService,
        builder: AstroAIContextBuilder,
        forecasts: ForecastService,
    ) -> None:
        self.session = session
        self.charts = charts
        self.builder = builder
        self.forecasts = forecasts

    # ------------------------------------------------------------ natal

    async def _chart_for_user(self, user: User):
        service = UserService(self.session)
        profile = await service.birth_profiles.get_primary(user.id)
        if profile is None:
            raise MissingBirthData(
                "Add your birth data before requesting an interpretation.",
                code="birth_profile_missing",
            )
        birth = await service.get_primary_birth_data(user)
        chart = await self.charts.natal_chart(
            birth,
            session=self.session,
            user_id=user.id,
            subject_type="birth_profile",
            subject_id=profile.id,
        )
        return chart, profile

    def _subject(self, user: User) -> dict:
        """What the model is told about the person: no name, no birth data.

        The chart facts are in the factors; identity is not needed to
        interpret them, so it is not sent.
        """
        return {
            "kind": "app_user",
            "locale": user.profile.language if user.profile else "tr",
            "timezone": user.profile.timezone if user.profile else "UTC",
        }

    async def natal(
        self, user: User, *, locale: Locale, budget: int, focus: str | None = None
    ) -> ResolvedSource:
        chart, profile = await self._chart_for_user(user)
        context = self.builder.natal(
            chart,
            locale=locale,
            subject=self._subject(user),
            focus=focus,
            token_budget=budget,
        )
        return ResolvedSource(
            context=context,
            source_type="birth_profile",
            source_id=profile.id,
            engine_version=chart.engine_version,
        )

    # --------------------------------------------------------- forecast

    async def transits(
        self,
        user: User,
        *,
        locale: Locale,
        budget: int,
        range_key: str = "week",
    ) -> ResolvedSource:
        chart, profile = await self._chart_for_user(user)
        from app.services.astrology.service import chart_fingerprint

        fingerprint = chart_fingerprint(chart.subject, chart.engine_version)
        timezone = (user.profile.timezone if user.profile else None) or "UTC"

        payload = await self.forecasts.transits(
            chart,
            fingerprint=fingerprint,
            range_key=range_key,
            timezone=timezone,
        )
        context = self.builder.transits(
            payload.model_dump(mode="json"),
            locale=locale,
            subject=self._subject(user),
            token_budget=budget,
        )
        return ResolvedSource(
            context=context,
            source_type="birth_profile",
            source_id=profile.id,
            engine_version=chart.engine_version,
            extra_fingerprint={"range": range_key},
        )

    async def forecast(
        self,
        user: User,
        *,
        report_type: ReportType,
        locale: Locale,
        budget: int,
    ) -> ResolvedSource:
        chart, profile = await self._chart_for_user(user)
        from app.domain.horoscope import HoroscopePeriod
        from app.services.astrology.service import chart_fingerprint

        fingerprint = chart_fingerprint(chart.subject, chart.engine_version)
        timezone = (user.profile.timezone if user.profile else None) or "UTC"
        now = datetime.now(UTC)

        if report_type is ReportType.DAILY:
            payload = await self.forecasts.daily_frequency(
                chart, fingerprint=fingerprint, day=now, timezone=timezone
            )
            context = self.builder.daily(
                payload.model_dump(mode="json"),
                locale=locale,
                subject=self._subject(user),
                token_budget=budget,
            )
        elif report_type is ReportType.WEEKLY:
            payload = await self.forecasts.horoscope(
                chart,
                fingerprint=fingerprint,
                period=HoroscopePeriod.WEEKLY,
                day=now,
                timezone=timezone,
            )
            context = self.builder.horoscope(
                payload.model_dump(mode="json"),
                context_type=ContextType.WEEKLY,
                locale=locale,
                subject=self._subject(user),
                token_budget=budget,
            )
        elif report_type is ReportType.MONTHLY:
            payload = await self.forecasts.monthly(
                chart,
                fingerprint=fingerprint,
                year=now.year,
                month=now.month,
                timezone=timezone,
                session=self.session,
                user_id=user.id,
            )
            context = self.builder.horoscope(
                payload.model_dump(mode="json"),
                context_type=ContextType.MONTHLY,
                locale=locale,
                subject=self._subject(user),
                token_budget=budget,
            )
        else:
            payload = await self.forecasts.annual(
                chart,
                fingerprint=fingerprint,
                year=now.year,
                timezone=timezone,
                session=self.session,
                user_id=user.id,
            )
            context = self.builder.horoscope(
                payload.model_dump(mode="json"),
                context_type=ContextType.YEARLY,
                locale=locale,
                subject=self._subject(user),
                token_budget=budget,
            )

        return ResolvedSource(
            context=context,
            source_type="forecast",
            source_id=profile.id,
            engine_version=chart.engine_version,
            extra_fingerprint={"period": report_type.value, "at": now.date().isoformat()},
        )

    # ----------------------------------------------------------- horary

    async def horary(
        self,
        user: User,
        *,
        question_id: uuid.UUID,
        locale: Locale,
        budget: int,
    ) -> ResolvedSource:
        service = HoraryService(self.session)
        # Ownership is checked here, before any context is built.
        record = await service.get_question(
            user_id=user.id, question_id=question_id
        )
        _, payload, _ = await service.analyse(record)

        context = self.builder.horary(
            payload,
            locale=locale,
            subject=self._subject(user),
            token_budget=budget,
        )
        return ResolvedSource(
            context=context,
            source_type="horary_question",
            source_id=record.id,
            engine_version=payload.get("engine_version", ""),
        )

    # ---------------------------------------------------- compatibility

    async def compatibility(
        self,
        user: User,
        *,
        report_id: uuid.UUID,
        report_type: ReportType,
        locale: Locale,
        budget: int,
    ) -> ResolvedSource:
        report = await self.session.scalar(
            select(CompatibilityReport).where(
                CompatibilityReport.id == report_id,
                CompatibilityReport.user_id == user.id,
                CompatibilityReport.deleted_at.is_(None),
            )
        )
        if report is None:
            raise NotFound("Compatibility report not found.")

        expected = report_type.compatibility_kind
        if expected is None or report.kind != expected:
            raise NotFound("Compatibility report not found.")

        payload = dict(report.structured_result)
        subject = self._subject(user)

        if expected == "synastry":
            context = self.builder.synastry(
                payload, locale=locale, subject=subject, token_budget=budget
            )
        else:
            context = self.builder.composite(
                payload,
                kind=report_type.context_type,
                locale=locale,
                subject=subject,
                token_budget=budget,
            )

        return ResolvedSource(
            context=context,
            source_type="compatibility_report",
            source_id=report.id,
            engine_version=report.engine_version,
            label=f"{report.person_a_label or 'A'} & {report.person_b_label or 'B'}",
        )

    # -------------------------------------------------------- divination

    async def divination(
        self,
        user: User,
        *,
        reading_id: uuid.UUID,
        locale: Locale,
        budget: int,
        report_type: ReportType | None = None,
    ) -> ResolvedSource:
        """From a stored reading. The draw already happened; nothing is redealt.

        Ownership is checked first, as everywhere else: another user's reading
        is a 404, and no context is built from it.
        """
        from app.services.divination.context import (
            get_divination_context_builder,
        )
        from app.services.divination.service import DivinationService

        service = DivinationService(self.session)
        reading = await service.get(user=user, reading_id=reading_id)

        # A tarot interpretation of a rune reading is not "close enough": the
        # prompt, the vocabulary and the reversal rules all differ.
        if report_type is not None and reading.deck_type != report_type.value:
            raise NotFound("Reading not found.")

        hydrated = await service.hydrate(reading)

        context = get_divination_context_builder().build(
            reading,
            hydrated,
            locale=locale,
            subject=self._subject(user),
            token_budget=budget,
        )
        return ResolvedSource(
            context=context,
            source_type="divination_reading",
            source_id=reading.id,
            engine_version=reading.deck_version,
            extra_fingerprint={
                "draw": reading.draw_fingerprint,
                "spread_version": reading.spread_version,
            },
        )

    # -------------------------------------------------------------- chat

    async def for_context_type(
        self,
        user: User,
        *,
        context_type: ContextType,
        locale: Locale,
        budget: int,
        focus: str | None = None,
    ) -> ResolvedSource:
        """Chat: pick the material the routed intent needs."""
        if context_type is ContextType.NATAL:
            return await self.natal(user, locale=locale, budget=budget, focus=focus)
        if context_type is ContextType.TRANSIT:
            return await self.transits(
                user, locale=locale, budget=budget, range_key="week"
            )
        if context_type in (
            ContextType.DAILY,
            ContextType.WEEKLY,
            ContextType.MONTHLY,
            ContextType.YEARLY,
        ):
            return await self.forecast(
                user,
                report_type=ReportType(context_type.value),
                locale=locale,
                budget=budget,
            )
        if context_type in (
            ContextType.SYNASTRY,
            ContextType.COMPOSITE,
            ContextType.DAVISON,
            ContextType.HORARY,
        ):
            # These need a specific source the user must name; without one the
            # answer stays general rather than guessing which report is meant.
            return ResolvedSource(
                context=self.builder.general_chat(
                    locale=locale, subject=self._subject(user), token_budget=budget
                ),
                source_type="general",
                source_id=None,
                engine_version="",
            )

        return ResolvedSource(
            context=self.builder.general_chat(
                locale=locale, subject=self._subject(user), token_budget=budget
            ),
            source_type="general",
            source_id=None,
            engine_version="",
        )


async def existing_report(
    session: AsyncSession, *, user_id: uuid.UUID, fingerprint: str
) -> AIReport | None:
    return await session.scalar(
        select(AIReport).where(
            AIReport.input_fingerprint == fingerprint,
            AIReport.user_id == user_id,
            AIReport.deleted_at.is_(None),
        )
    )
