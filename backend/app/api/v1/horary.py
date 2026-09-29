"""Horary astrology endpoints.

A horary chart is cast for the moment and place the **question** was asked.
It has nothing to do with the querent's birth data, and editing a birth
profile never changes one.

Nothing here answers the question. The response is the structured material a
judgement is made from; the judgement belongs to the astrologer or, in phase
B6, to Astro AI with proper framing.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import Charts, CurrentUser, DbSession
from app.core.exceptions import NotFound
from app.core.rate_limit import RateLimit
from app.domain.horary import HoraryStatus
from app.schemas.horary import (
    HoraryAnalysisResponse,
    HoraryQuestionRequest,
    HoraryQuestionResponse,
)
from app.services.horary.service import HoraryService

from fastapi import Depends

router = APIRouter(prefix="/horary", tags=["horary"])


def _question_to_schema(
    record, *, duplicate: bool = False
) -> HoraryQuestionResponse:
    from app.services.astrology.horary_rules import HoraryCategory

    return HoraryQuestionResponse(
        id=record.id,
        question=record.question,
        category=HoraryCategory(record.category) if record.category else None,
        status=HoraryStatus(record.status),
        asked_at_utc=record.asked_at_utc,
        timezone=record.timezone,
        latitude=record.latitude,
        longitude=record.longitude,
        location_name=record.location_name,
        house_override=record.house_override,
        chart_id=record.chart_id,
        duplicate_suspected=duplicate,
        created_at=record.created_at,
    )


@router.post(
    "/questions",
    response_model=HoraryQuestionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimit("30/hour", scope="horary_question"))],
    summary="Ask a horary question",
    description=(
        "Stores the question with the exact instant and place it was asked - "
        "that moment is the chart. Re-asking the same question is allowed; "
        "the response flags it so the astrologer can choose to judge from the "
        "original chart, as tradition prescribes."
    ),
)
async def create_question(
    payload: HoraryQuestionRequest,
    user: CurrentUser,
    session: DbSession,
) -> HoraryQuestionResponse:
    service = HoraryService(session)
    record, duplicate = await service.create_question(
        user_id=user.id,
        question=payload.question,
        category=payload.category,
        asked_at=payload.asked_at,
        timezone=payload.timezone,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_name=payload.location_name,
        house_override=payload.house_override,
        fallback_timezone=(user.profile.timezone if user.profile else "UTC"),
    )
    await session.commit()
    return _question_to_schema(record, duplicate=duplicate)


@router.get(
    "/questions",
    response_model=list[HoraryQuestionResponse],
    summary="Your horary questions",
)
async def list_questions(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[HoraryQuestionResponse]:
    records = await HoraryService(session).list_questions(
        user_id=user.id, limit=limit
    )
    return [_question_to_schema(record) for record in records]


@router.get(
    "/questions/{question_id}",
    response_model=HoraryQuestionResponse,
    summary="One question",
)
async def get_question(
    question_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> HoraryQuestionResponse:
    record = await HoraryService(session).get_question(
        user_id=user.id, question_id=question_id
    )
    return _question_to_schema(record)


@router.post(
    "/questions/{question_id}/calculate",
    response_model=HoraryQuestionResponse,
    summary="Cast the chart for a question",
)
async def calculate(
    question_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> HoraryQuestionResponse:
    service = HoraryService(session)
    record = await service.get_question(user_id=user.id, question_id=question_id)
    await service.chart_for(record)
    await session.commit()
    return _question_to_schema(record)


@router.get(
    "/questions/{question_id}/analysis",
    response_model=HoraryAnalysisResponse,
    summary="Structured horary analysis",
    description=(
        "Significators and their dignities, receptions, applying and "
        "separating aspects, perfection and obstruction factors, the Moon's "
        "condition, and the classical warnings. No verdict: techniques the "
        "engine does not implement are listed in `not_implemented` so silence "
        "is never read as absence."
    ),
)
async def analysis(
    question_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    refresh: bool = Query(default=False),
) -> HoraryAnalysisResponse:
    service = HoraryService(session)
    record = await service.get_question(user_id=user.id, question_id=question_id)
    _, payload, cached = await service.analyse(record, refresh=refresh)
    await session.commit()

    return HoraryAnalysisResponse.model_validate(
        {**payload, "question_id": record.id, "cached": cached}
    )
