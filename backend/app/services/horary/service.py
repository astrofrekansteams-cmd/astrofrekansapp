"""Horary use cases: store the question, cast its chart, analyse it.

The question's instant and place *are* the chart. They are captured when the
question is created and never re-read from the user's profile afterwards, so
editing a birth profile cannot change a horary chart - which would be both
astrologically wrong and a silent rewrite of something the user already read.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AstrologyError, NotFound, ValidationFailed
from app.core.logging import get_logger
from app.db.models.chart import ChartCache
from app.db.models.horary import HoraryAnalysisRecord, HoraryQuestion
from app.domain.astrology import Chart, ChartSubject
from app.domain.enums import ChartKind, HouseSystem
from app.domain.horary import HoraryAnalysis, HoraryStatus
from app.services.astrology.horary import HoraryAnalysisEngine, get_horary_engine
from app.services.astrology.horary_rules import (
    DUPLICATE_QUESTION_HOURS,
    HoraryCategory,
)
from app.services.astrology.serializers import chart_to_payload
from app.services.astrology.service import chart_fingerprint
from app.services.astrology.skyfield_engine import SkyfieldEngine, get_engine
from app.services.timezone.service import is_valid_timezone, timezone_for_coordinates

logger = get_logger(__name__)


def normalise_question(question: str) -> str:
    """Lowercased, punctuation-stripped form used only for the duplicate hint."""
    return re.sub(r"[^\w\s]", "", question.lower()).strip()


def question_hash(question: str) -> str:
    return hashlib.sha256(normalise_question(question).encode("utf-8")).hexdigest()


class HoraryService:
    def __init__(
        self,
        session: AsyncSession,
        engine: SkyfieldEngine | None = None,
        analysis_engine: HoraryAnalysisEngine | None = None,
    ) -> None:
        self.session = session
        self._engine = engine or get_engine()
        self._analysis = analysis_engine or get_horary_engine()

    # ------------------------------------------------------------- create

    async def create_question(
        self,
        *,
        user_id: uuid.UUID,
        question: str,
        category: HoraryCategory | None,
        asked_at: datetime | None,
        timezone: str | None,
        latitude: float | None,
        longitude: float | None,
        location_name: str | None,
        house_override: int | None,
        fallback_timezone: str,
    ) -> tuple[HoraryQuestion, bool]:
        if latitude is None or longitude is None:
            raise ValidationFailed(
                "A horary question needs the place it was asked from.",
                details={"fields": ["latitude", "longitude"]},
            )

        zone = timezone or timezone_for_coordinates(latitude, longitude) or fallback_timezone
        if not is_valid_timezone(zone):
            raise ValidationFailed("Unknown timezone.", details={"timezone": zone})

        moment = (asked_at or datetime.now(UTC)).astimezone(UTC)
        digest = question_hash(question)
        duplicate = await self._recent_duplicate(user_id, digest, moment)

        record = HoraryQuestion(
            user_id=user_id,
            question=question.strip(),
            question_hash=digest,
            category=category.value if category else None,
            house_override=house_override,
            asked_at_utc=moment,
            timezone=zone,
            latitude=latitude,
            longitude=longitude,
            location_name=location_name,
            status=HoraryStatus.CREATED,
        )
        self.session.add(record)
        await self.session.flush()

        # Re-asking is never blocked. The hint is reported so the astrologer
        # can decide whether to judge from the original chart, which is the
        # traditional rule.
        logger.info("horary_question_created", question_id=str(record.id))
        return record, duplicate

    async def _recent_duplicate(
        self,
        user_id: uuid.UUID,
        digest: str,
        moment: datetime,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        window = moment - timedelta(hours=DUPLICATE_QUESTION_HOURS)
        statement = select(HoraryQuestion).where(
            HoraryQuestion.user_id == user_id,
            HoraryQuestion.question_hash == digest,
            HoraryQuestion.asked_at_utc >= window,
            HoraryQuestion.deleted_at.is_(None),
        )
        # A question must not detect itself: by analysis time it is already
        # stored, and flagging every first question as a repeat would make the
        # warning meaningless.
        if exclude_id is not None:
            statement = statement.where(HoraryQuestion.id != exclude_id)
        return await self.session.scalar(statement) is not None

    # -------------------------------------------------------------- fetch

    async def get_question(
        self, *, user_id: uuid.UUID, question_id: uuid.UUID
    ) -> HoraryQuestion:
        record = await self.session.scalar(
            select(HoraryQuestion).where(
                HoraryQuestion.id == question_id,
                HoraryQuestion.user_id == user_id,
                HoraryQuestion.deleted_at.is_(None),
            )
        )
        if record is None:
            raise NotFound("Question not found.")
        return record

    async def list_questions(
        self, *, user_id: uuid.UUID, limit: int = 50
    ) -> list[HoraryQuestion]:
        result = await self.session.scalars(
            select(HoraryQuestion)
            .where(
                HoraryQuestion.user_id == user_id,
                HoraryQuestion.deleted_at.is_(None),
            )
            .order_by(HoraryQuestion.asked_at_utc.desc())
            .limit(limit)
        )
        return list(result)

    # ------------------------------------------------------------- charts

    def subject_for(self, record: HoraryQuestion) -> ChartSubject:
        return ChartSubject(
            kind=ChartKind.HORARY,
            moment_utc=record.asked_at_utc,
            latitude=record.latitude,
            longitude=record.longitude,
            timezone=record.timezone,
            house_system=HouseSystem.PLACIDUS,
            location_name=record.location_name,
            label="horary",
        )

    async def chart_for(self, record: HoraryQuestion) -> Chart:
        """Cast (or reuse) the chart for a question."""
        subject = self.subject_for(record)
        fingerprint = chart_fingerprint(subject, self._engine.version)

        row = await self.session.scalar(
            select(ChartCache).where(ChartCache.input_hash == fingerprint)
        )
        chart = self._engine.chart_for(subject)

        if row is None:
            row = ChartCache(
                user_id=record.user_id,
                chart_kind=ChartKind.HORARY,
                subject_type="horary_question",
                subject_id=record.id,
                moment_utc=subject.moment_utc,
                input_hash=fingerprint,
                engine_version=self._engine.version,
                house_system=chart.house_system.value,
                payload=chart_to_payload(chart),
            )
            self.session.add(row)
            await self.session.flush()

        record.chart_id = row.id
        record.status = HoraryStatus.CALCULATED
        await self.session.flush()
        return chart

    # ----------------------------------------------------------- analysis

    async def analyse(
        self, record: HoraryQuestion, *, refresh: bool = False
    ) -> tuple[HoraryAnalysis | None, dict, bool]:
        """Returns (analysis, payload, cached).

        Stored analyses are returned as payloads: they are snapshots of what
        the engine said at the time, and re-running a newer engine over an old
        question would change an answer the user has already seen.
        """
        if not refresh:
            existing = await self.session.scalar(
                select(HoraryAnalysisRecord).where(
                    HoraryAnalysisRecord.question_id == record.id
                )
            )
            if existing is not None:
                return None, existing.payload, True

        chart = await self.chart_for(record)
        duplicate = await self._recent_duplicate(
            record.user_id,
            record.question_hash,
            record.asked_at_utc,
            exclude_id=record.id,
        )

        try:
            analysis = self._analysis.analyse(
                chart,
                question=record.question,
                category=(
                    HoraryCategory(record.category) if record.category else None
                ),
                house_override=record.house_override,
                duplicate_suspected=duplicate,
            )
        except ValueError as exc:
            record.status = HoraryStatus.FAILED
            record.failure_reason = str(exc)[:255]
            await self.session.flush()
            raise AstrologyError(str(exc), code="horary_analysis_failed") from exc

        payload = analysis_to_payload(analysis)

        stored = await self.session.scalar(
            select(HoraryAnalysisRecord).where(
                HoraryAnalysisRecord.question_id == record.id
            )
        )
        if stored is None:
            stored = HoraryAnalysisRecord(question_id=record.id)
            self.session.add(stored)
        stored.engine_version = analysis.engine_version
        stored.rules_version = analysis.rules_version
        stored.dignity_version = analysis.dignity_version
        stored.payload = payload

        record.status = HoraryStatus.READY
        await self.session.flush()
        return analysis, payload, False


def analysis_to_payload(analysis: HoraryAnalysis) -> dict:
    """Dataclass tree -> JSON, with enums and datetimes flattened."""
    return _jsonify(asdict(analysis))


def _jsonify(value):  # noqa: ANN001, ANN202 - recursive JSON coercion
    from enum import Enum

    if isinstance(value, dict):
        return {str(_jsonify(key)): _jsonify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return value
