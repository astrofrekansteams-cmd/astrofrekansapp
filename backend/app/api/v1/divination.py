"""Divination endpoints: tarot, runes and Katina.

The shape of this router is the phase's main design decision: **drawing and
interpreting are separate calls.**

    POST /divination/readings              -> the cards, committed
    POST /divination/readings/{id}/interpret -> the AI reading of them

A user who asks for a spread gets their cards even when the interpretation
service is unconfigured, rate-limited or down. An AI failure costs an
explanation, never the deal - and because the reading is a snapshot, the
interpretation can be retried later against exactly the same cards.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, UserRateLimit
from app.core.config import settings
from app.db.models.divination import DivinationReading
from app.domain.ai import Locale, ReportType
from app.domain.divination import DeckType
from app.schemas.ai import ReportJobResponse, ReportResponse
from app.schemas.common import Message
from app.schemas.divination import (
    DeckItemResponse,
    DeckResponse,
    DrawnItemResponse,
    InterpretRequest,
    ReadingCreateRequest,
    ReadingResponse,
    ReadingSummary,
    SpreadPositionResponse,
    SpreadResponse,
    SynthesisResponse,
    DrawAllowanceResponse,
    DrawSessionCreateRequest,
    DrawSessionResponse,
    DrawSessionRevealRequest,
)
from app.services.ai.factory import ai_available, build_report_service
from app.services.ai.provider import AINotConfigured
from app.services.divination.decks import deck_content_note, get_deck
from app.services.coins.catalog import ADVANCED_SPREAD, EXTRA_DRAW, spend_item
from app.services.divination.allowance import (
    DailyDrawLimitReached,
    allowance,
    charge_for_draw,
)
from app.services.divination.service import DivinationService
from app.services.divination.spreads import spreads_for
from app.services.divination.synthesis import contextual_meaning, synthesize
from app.services.features import ensure_feature, spread_feature
from app.services.divination.sessions import (
    DrawSessionService,
    RevealRaceLost,
    SessionExpired,
    reveal_lock,
)

router = APIRouter(prefix="/divination", tags=["divination"])

# Drawing is cheap - a shuffle and a few rows - so it gets a generous quota.
# Interpreting costs a model call, so it gets its own, much smaller one.
_draw_limit = Depends(
    UserRateLimit(
        settings.divination_draw_rate_limit,
        scope="divination_draw",
        code="rate_limited",
    )
)
_interpret_limit = Depends(
    UserRateLimit(
        settings.divination_interpret_rate_limit,
        scope="divination_interpret",
        code="ai_rate_limited",
    )
)


def _locale(requested: Locale | None, user) -> Locale:  # noqa: ANN001
    if requested is not None:
        return requested
    preferred = (user.profile.language if user.profile else None) or "tr"
    try:
        return Locale(preferred)
    except ValueError:
        return Locale.TR


def _spread_to_schema(spread, locale: Locale) -> SpreadResponse:  # noqa: ANN001
    return SpreadResponse(
        deck_type=spread.deck_type,
        spread_code=spread.spread_code,
        spread_version=spread.spread_version,
        name=spread.name(locale.value, fallback="tr"),
        origin=spread.origin,
        card_count=spread.card_count,
        allow_reversed=spread.allow_reversed,
        theme=spread.theme,
        positions=[
            SpreadPositionResponse(
                index=position.index,
                key=position.key,
                title=position.title(locale.value, fallback="tr"),
                role=position.interpretation_role,
                description=position.description(locale.value, fallback="tr")
                or None,
            )
            for position in spread.positions
        ],
    )


async def _reading_to_schema(
    reading: DivinationReading,
    service: DivinationService,
    *,
    has_interpretation: bool = False,
) -> ReadingResponse:
    from app.services.divination.spreads import get_spread

    deck_type = DeckType(reading.deck_type)
    spread = get_spread(deck_type, reading.spread_code)
    hydrated = await service.hydrate(reading)
    for row in hydrated:
        row["contextual_meaning"] = contextual_meaning(spread.theme, row)
    deck = get_deck(deck_type, reading.deck_version)
    synthesis = synthesize(
        deck_type=deck_type,
        spread=spread,
        rows=hydrated,
        items={row["item_id"]: deck.item(row["item_id"]) for row in hydrated},
        locale=reading.locale,
    )

    return ReadingResponse(
        id=reading.id,
        deck_type=deck_type,
        deck_version=reading.deck_version,
        spread_code=reading.spread_code,
        spread_version=reading.spread_version,
        spread_name=spread.name(reading.locale, fallback="tr"),
        locale=Locale(reading.locale),
        question=reading.question,
        repeat_reading=bool((reading.meta or {}).get("repeat_reading", False)),
        repeat_of_id=reading.repeat_of_id,
        rng_source=reading.rng_source,
        drawn_at=reading.drawn_at,
        status=reading.status,
        items=[DrawnItemResponse(**row) for row in hydrated],
        spread_theme=spread.theme,
        synthesis=SynthesisResponse(
            headline=synthesis.headline,
            lines=synthesis.lines,
            flow=synthesis.flow,
            counts=synthesis.counts,
            version=synthesis.version,
        ),
        has_interpretation=has_interpretation,
        created_at=reading.created_at,
    )


# ---------------------------------------------------------------- catalogue


@router.get(
    "/decks",
    response_model=list[DeckResponse],
    summary="The decks this server can deal",
)
async def list_decks(user: CurrentUser) -> list[DeckResponse]:
    responses: list[DeckResponse] = []
    for deck_type in DeckType:
        deck = get_deck(deck_type)
        responses.append(
            DeckResponse(
                deck_type=deck_type,
                deck_version=deck.deck_version,
                item_count=len(deck.items),
                optional_item_count=len(deck.optional_items),
                reversal_supported=deck.reversal_supported,
                locales=list(deck.locales),
                back_asset_key=deck.back_asset_key,
                content_note=deck_content_note(deck_type),
                spread_codes=[
                    spread.spread_code for spread in spreads_for(deck_type)
                ],
            )
        )
    return responses


@router.get(
    "/decks/{deck_type}/spreads",
    response_model=list[SpreadResponse],
    summary="The spreads available for a deck",
)
async def list_spreads(
    deck_type: DeckType, user: CurrentUser, locale: Locale | None = None
) -> list[SpreadResponse]:
    resolved = _locale(locale, user)
    return [
        _spread_to_schema(spread, resolved) for spread in spreads_for(deck_type)
    ]


@router.get(
    "/decks/{deck_type}/items",
    response_model=list[DeckItemResponse],
    summary="Every item in a deck",
    description=(
        "The full deck for browsing. `image_asset_key` is a stem; the client "
        "resolves the file from its own asset manifest."
    ),
)
async def list_deck_items(
    deck_type: DeckType,
    user: CurrentUser,
    locale: Locale | None = None,
    include_optional: bool = Query(default=False),
) -> list[DeckItemResponse]:
    deck = get_deck(deck_type)
    resolved = _locale(locale, user)
    items = list(deck.items)
    if include_optional:
        items.extend(deck.optional_items)

    responses: list[DeckItemResponse] = []
    for item in items:
        meaning = item.meaning(resolved.value, fallback=deck.locales[0])
        responses.append(
            DeckItemResponse(
                item_id=item.item_id,
                display_name=meaning.display_name,
                canonical_name=item.canonical_name,
                image_asset_key=item.image_asset_key,
                keywords=list(meaning.keywords),
                reversible=item.reversible,
                content_status=item.content_status.value,
                arcana=item.arcana.value if item.arcana else None,
                suit=item.suit.value if item.suit else None,
                number=item.number,
                rank=item.rank,
                symbol=item.symbol,
                transliteration=item.transliteration,
                aett=item.aett.value if item.aett else None,
                element=item.element,
            )
        )
    return responses


# ----------------------------------------------------------------- readings


@router.post(
    "/readings",
    response_model=ReadingResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_draw_limit],
    deprecated=True,
    summary="Draw a reading (deprecated: server picks the cards)",
    description=(
        "DEPRECATED. Kept for backward compatibility only; the app uses "
        "user-pick draw sessions (`POST /divination/sessions` then "
        "`POST /divination/sessions/{id}/reveal`). Deals the spread and "
        "stores it. The question is never allowed to influence the draw."
    ),
)
async def create_reading(
    payload: ReadingCreateRequest, user: CurrentUser, session: DbSession
) -> ReadingResponse:
    ensure_feature(user.tier, spread_feature(payload.deck_type, payload.spread_code))
    current = await allowance(session, user)
    if current.enforced and current.remaining <= 0:
        raise DailyDrawLimitReached(details={"daily_limit": current.daily_limit})
    service = DivinationService(session)
    reading = await service.create_reading(
        user,
        deck_type=payload.deck_type,
        spread_code=payload.spread_code,
        locale=_locale(payload.locale, user).value,
        question=payload.question,
        include_optional_items=(
            payload.include_optional_items
            and payload.deck_type is DeckType.RUNE
        ),
    )
    await session.commit()
    return await _reading_to_schema(reading, service)


@router.get(
    "/readings",
    response_model=list[ReadingSummary],
    summary="Your readings",
)
async def list_readings(
    user: CurrentUser,
    session: DbSession,
    deck_type: DeckType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ReadingSummary]:
    from app.services.divination.spreads import get_spread

    service = DivinationService(session)
    rows = await service.list(user=user, deck_type=deck_type, limit=limit)

    summaries: list[ReadingSummary] = []
    for reading in rows:
        spread = get_spread(DeckType(reading.deck_type), reading.spread_code)
        summaries.append(
            ReadingSummary(
                id=reading.id,
                deck_type=DeckType(reading.deck_type),
                spread_code=reading.spread_code,
                spread_name=spread.name(reading.locale, fallback="tr"),
                locale=Locale(reading.locale),
                question=reading.question,
                item_count=len(spread.positions),
                drawn_at=reading.drawn_at,
                created_at=reading.created_at,
            )
        )
    return summaries


@router.get(
    "/readings/{reading_id}",
    response_model=ReadingResponse,
    summary="One reading",
    description=(
        "Immutable. The same cards, in the same positions, however long "
        "afterwards it is opened."
    ),
)
async def get_reading(
    reading_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ReadingResponse:
    service = DivinationService(session)
    reading = await service.get(user=user, reading_id=reading_id)
    report = await _existing_interpretation(session, user, reading)
    return await _reading_to_schema(
        reading, service, has_interpretation=report is not None
    )


@router.delete(
    "/readings/{reading_id}",
    response_model=Message,
    summary="Delete a reading",
)
async def delete_reading(
    reading_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> Message:
    await DivinationService(session).delete(user=user, reading_id=reading_id)
    await session.commit()
    return Message(message="Reading deleted.")


# ------------------------------------------------------------ interpretation


REPORT_TYPES = {
    DeckType.TAROT: ReportType.TAROT,
    DeckType.RUNE: ReportType.RUNE,
    DeckType.KATINA: ReportType.KATINA,
}


async def _existing_interpretation(session, user, reading):  # noqa: ANN001
    from sqlalchemy import select

    from app.db.models.ai import AIReport
    from app.domain.ai import ReportStatus

    return await session.scalar(
        select(AIReport)
        .where(
            AIReport.user_id == user.id,
            AIReport.source_type == "divination_reading",
            AIReport.source_id == reading.id,
            AIReport.status == ReportStatus.COMPLETED.value,
            AIReport.deleted_at.is_(None),
        )
        .order_by(AIReport.created_at.desc())
        .limit(1)
    )


@router.post(
    "/readings/{reading_id}/interpret",
    response_model=None,
    responses={
        200: {"model": ReportResponse},
        202: {"model": ReportJobResponse},
    },
    dependencies=[_interpret_limit],
    summary="Interpret a reading",
    description=(
        "Runs the drawn cards through the AI interpretation layer. The draw "
        "is never redealt: `refresh=true` produces a new reading of the same "
        "cards. Fails with `ai_not_configured` when no provider is set up, "
        "leaving the reading itself intact."
    ),
)
async def interpret_reading(
    reading_id: uuid.UUID,
    payload: InterpretRequest,
    user: CurrentUser,
    session: DbSession,
) -> ReportResponse | JSONResponse:
    if not ai_available():
        # The cards are already the user's; only the explanation is missing.
        raise AINotConfigured()

    service = DivinationService(session)
    reading = await service.get(user=user, reading_id=reading_id)
    report_type = REPORT_TYPES[DeckType(reading.deck_type)]
    locale = payload.locale or Locale(reading.locale)

    reports = build_report_service(session)
    # The same gate as `/ai/reports`: if interpretations are ever priced, this
    # route cannot be the way around it.
    outcome = await reports.request(
        user,
        report_type=report_type,
        source_id=reading.id,
        locale=locale,
        refresh=payload.refresh,
        background=payload.background,
        consumer_ref=payload.consumer_ref,
    )
    await session.commit()

    from app.api.v1.ai import deliver_report

    return await deliver_report(reports, session, user, outcome)


@router.get(
    "/readings/{reading_id}/interpretation",
    response_model=ReportResponse,
    summary="The stored interpretation of a reading",
)
async def get_interpretation(
    reading_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ReportResponse:
    from app.core.exceptions import NotFound

    service = DivinationService(session)
    reading = await service.get(user=user, reading_id=reading_id)
    report = await _existing_interpretation(session, user, reading)
    if report is None:
        raise NotFound("This reading has not been interpreted yet.")

    from app.api.v1.ai import _report_to_schema

    return _report_to_schema(report, cached=True)


# --------------------------------------------------------- user-pick sessions


def _session_to_schema(row, locale: str) -> DrawSessionResponse:  # noqa: ANN001
    """Deliberately built field by field: `hidden_state` must never leak."""
    from app.services.divination.spreads import get_spread

    deck_type = DeckType(row.deck_type)
    spread = get_spread(deck_type, row.spread_code)
    return DrawSessionResponse(
        session_id=row.id,
        deck_type=deck_type,
        deck_size=row.deck_size,
        spread_code=row.spread_code,
        spread_name=spread.name(locale, fallback="tr"),
        required_selections=spread.card_count,
        positions=[
            SpreadPositionResponse(
                index=position.index,
                key=position.key,
                title=position.title(locale, fallback="tr"),
                role=position.interpretation_role,
                description=position.description(locale, fallback="tr") or None,
            )
            for position in spread.positions
        ],
        expires_at=row.expires_at,
        status=row.status,
        reading_id=row.reading_id,
    )


@router.post(
    "/sessions",
    response_model=DrawSessionResponse,
    dependencies=[_draw_limit],
    summary="Shuffle a deck face down for the user to pick from",
    description=(
        "Shuffles the whole deck once and fixes every face-down slot's "
        "orientation. Returns only the deck size and the spread; which item "
        "sits in which slot never leaves the server. Idempotent per "
        "`consumer_ref`: a retry returns the same session, the same ref with a "
        "different request is `409 consumer_ref_conflict`. Expires after 15 "
        "minutes."
    ),
)
async def create_draw_session(
    payload: DrawSessionCreateRequest, user: CurrentUser, session: DbSession
) -> DrawSessionResponse:
    locale = _locale(payload.locale, user).value
    service = DrawSessionService(session)
    # A retry of an existing shuffle is never checked or charged again.
    replay = await service._by_ref(user, payload.consumer_ref)
    spent = 0
    if replay is None:
        spent = await charge_for_draw(
            session,
            user,
            deck_type=payload.deck_type,
            spread_code=payload.spread_code,
            consumer_ref=payload.consumer_ref,
            pay_with_coins=payload.pay_with_coins,
        )
    row = await service.create(
        user,
        consumer_ref=payload.consumer_ref,
        deck_type=payload.deck_type,
        spread_code=payload.spread_code,
        locale=locale,
        question=payload.question,
        include_optional_items=(
            payload.include_optional_items and payload.deck_type is DeckType.RUNE
        ),
    )
    await session.commit()
    return _session_to_schema(row, locale).model_copy(update={"coins_spent": spent})


@router.get(
    "/allowance",
    response_model=DrawAllowanceResponse,
    summary="Today's included draws, and what extra costs in coins",
)
async def draw_allowance(user: CurrentUser, session: DbSession) -> DrawAllowanceResponse:
    current = await allowance(session, user)
    return DrawAllowanceResponse(
        tier=current.tier.value,
        enforced=current.enforced,
        daily_limit=current.daily_limit,
        used_today=current.used_today,
        remaining=current.remaining,
        extra_draw_price=spend_item(EXTRA_DRAW).price,
        advanced_spread_price=spend_item(ADVANCED_SPREAD).price,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=DrawSessionResponse,
    summary="A draw session's public state",
)
async def get_draw_session(
    session_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> DrawSessionResponse:
    row = await DrawSessionService(session).get(user, session_id)
    await session.commit()  # persists a lazily detected expiry
    return _session_to_schema(row, row.locale)


@router.post(
    "/sessions/{session_id}/reveal",
    response_model=ReadingResponse,
    summary="Reveal the user's picks as a reading",
    description=(
        "`positions` are face-down slots in pick order; the i-th pick fills "
        "the spread's i-th position (never sorted). The count must equal the "
        "spread's size, picks must be distinct and in range. Atomic: one "
        "session yields at most one reading. Retrying with the same picks "
        "returns the same reading; different picks on a revealed session are "
        "`409 session_already_completed`; an expired session is "
        "`410 divination_session_expired`."
    ),
)
async def reveal_draw_session(
    session_id: uuid.UUID,
    payload: DrawSessionRevealRequest,
    user: CurrentUser,
    session: DbSession,
) -> ReadingResponse:
    sessions = DrawSessionService(session)
    # In-process serialisation (covers commit); across processes the row lock
    # and the unique constraints decide, and the loser replays the winner.
    async with reveal_lock(session_id):
        try:
            reading = await sessions.reveal(user, session_id, payload.positions)
            await session.commit()
        except (RevealRaceLost, IntegrityError):
            # Another reveal of this session committed first; answer with its
            # reading (same picks) or a conflict (different picks).
            await session.rollback()
            reading = await sessions.reveal(user, session_id, payload.positions)
        except SessionExpired:
            await session.commit()  # keep the expired status
            raise
    return await _reading_to_schema(reading, DivinationService(session))
