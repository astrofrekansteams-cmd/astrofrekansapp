"""User-pick draw sessions: shuffle face down, let the user choose, reveal.

The flow that replaces "the server picks your cards":

1. ``create``  - shuffle the whole deck once and fix every face-down slot's
   orientation. Only the slot count leaves the server.
2. The user picks slots in the app (local state until the reveal).
3. ``reveal`` - resolve exactly the picked slots, in the picked order, into
   an ordinary reading. Nothing is re-randomised.

Guarantees:

* ``create`` is idempotent per ``(user, consumer_ref)``; the same ref with a
  different request is a conflict.
* One session yields at most one reading: the session row is locked for the
  reveal (Postgres), and two unique constraints (session.reading_id,
  reading.draw_session_id) make a lost race fail at the database, after
  which the winner's reading is returned.
* The hidden deck (item ids, orientations) is never serialised to a client.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
import weakref
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.db.models.divination import DivinationDrawSession, DivinationReading
from app.db.models.user import User
from app.domain.divination import DeckType
from app.services.divination.engine import DrawEngine, ShuffledDeck, get_draw_engine
from app.services.divination.service import MAX_QUESTION_LENGTH, DivinationService

logger = get_logger(__name__)

STATUS_OPEN = "open"
STATUS_COMPLETED = "completed"
STATUS_EXPIRED = "expired"


class ConsumerRefConflict(AppError):
    status_code = 409
    code = "consumer_ref_conflict"
    message = "This session reference was already used for a different request."


class SessionExpired(AppError):
    status_code = 410
    code = "divination_session_expired"
    message = "This shuffle has expired. Shuffle again to start a new reading."


class SessionAlreadyCompleted(AppError):
    status_code = 409
    code = "session_already_completed"
    message = "This session was already revealed with a different selection."


class InvalidSelection(AppError):
    status_code = 422
    code = "invalid_selection"
    message = "The selection does not match this spread."


class RevealRaceLost(Exception):
    """Another reveal of the same session committed first."""


_reveal_locks: "weakref.WeakValueDictionary[uuid.UUID, asyncio.Lock]" = (
    weakref.WeakValueDictionary()
)


@asynccontextmanager
async def reveal_lock(session_id: uuid.UUID):
    """Serialise reveals of one session inside this process.

    Only an optimisation for the common double-tap: correctness across
    processes rests on the row lock and the two unique constraints.
    """
    lock = _reveal_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _reveal_locks[session_id] = lock
    async with lock:
        yield


def request_fingerprint(
    *,
    deck_type: DeckType,
    spread_code: str,
    locale: str,
    question: str | None,
    include_optional_items: bool,
) -> str:
    payload = json.dumps(
        {
            "deck": deck_type.value,
            "spread": spread_code,
            "locale": locale,
            "question": (question or "").strip()[:MAX_QUESTION_LENGTH] or None,
            "optional": include_optional_items,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class DrawSessionService:
    def __init__(self, session: AsyncSession, engine: DrawEngine | None = None) -> None:
        self.session = session
        self.engine = engine or get_draw_engine()

    # ------------------------------------------------------------ create

    async def create(
        self,
        user: User,
        *,
        consumer_ref: str,
        deck_type: DeckType,
        spread_code: str,
        locale: str,
        question: str | None,
        include_optional_items: bool,
    ) -> DivinationDrawSession:
        fingerprint = request_fingerprint(
            deck_type=deck_type,
            spread_code=spread_code,
            locale=locale,
            question=question,
            include_optional_items=include_optional_items,
        )
        existing = await self._by_ref(user, consumer_ref)
        if existing is not None:
            return self._replay(existing, fingerprint)

        shuffled = self.engine.shuffle(
            deck_type, spread_code, include_optional_items=include_optional_items
        )
        row = DivinationDrawSession(
            user_id=user.id,
            consumer_ref=consumer_ref,
            request_fingerprint=fingerprint,
            deck_type=deck_type.value,
            deck_version=shuffled.deck_version,
            spread_code=shuffled.spread.spread_code,
            spread_version=shuffled.spread.spread_version,
            locale=locale,
            question=(question or "").strip()[:MAX_QUESTION_LENGTH] or None,
            include_optional_items=include_optional_items,
            hidden_state=shuffled.to_hidden_state(),
            deck_size=shuffled.size,
            rng_source=shuffled.rng_source,
            status=STATUS_OPEN,
            expires_at=datetime.now(UTC)
            + timedelta(seconds=settings.divination_session_ttl_seconds),
        )
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError:
            # A concurrent create with the same ref won: replay it.
            await self.session.rollback()
            existing = await self._by_ref(user, consumer_ref)
            if existing is None:  # pragma: no cover - constraint implies a row
                raise
            return self._replay(existing, fingerprint)

        logger.info(
            "divination_session_created",
            session_id=str(row.id),
            deck_type=deck_type.value,
            spread=spread_code,
            deck_size=row.deck_size,
        )
        return row

    def _replay(self, row: DivinationDrawSession, fingerprint: str) -> DivinationDrawSession:
        if row.request_fingerprint != fingerprint:
            raise ConsumerRefConflict()
        self._refresh_expiry(row)
        return row

    async def _by_ref(self, user: User, consumer_ref: str) -> DivinationDrawSession | None:
        return await self.session.scalar(
            select(DivinationDrawSession)
            .where(
                DivinationDrawSession.user_id == user.id,
                DivinationDrawSession.consumer_ref == consumer_ref,
            )
            .execution_options(populate_existing=True)
        )

    # --------------------------------------------------------------- get

    async def get(self, user: User, session_id: uuid.UUID, *, lock: bool = False) -> DivinationDrawSession:
        query = select(DivinationDrawSession).where(
            DivinationDrawSession.id == session_id,
            DivinationDrawSession.user_id == user.id,
        ).execution_options(populate_existing=True)
        if lock:
            query = query.with_for_update()
        row = await self.session.scalar(query)
        if row is None:
            # Another user's session is indistinguishable from a missing one.
            raise NotFound("Draw session not found.", code="divination_session_not_found")
        self._refresh_expiry(row)
        return row

    def _refresh_expiry(self, row: DivinationDrawSession) -> None:
        if row.status == STATUS_OPEN and _aware(row.expires_at) <= datetime.now(UTC):
            row.status = STATUS_EXPIRED

    # ------------------------------------------------------------ reveal

    async def reveal(
        self, user: User, session_id: uuid.UUID, positions: list[int]
    ) -> DivinationReading:
        row = await self.get(user, session_id, lock=True)

        if row.status == STATUS_COMPLETED:
            return await self._completed_result(row, positions)
        if row.status == STATUS_EXPIRED:
            raise SessionExpired()

        deck_type = DeckType(row.deck_type)
        spread = self.engine.resolve_spread(deck_type, row.spread_code)
        self._validate(positions, required=spread.card_count, deck_size=row.deck_size)

        shuffled = ShuffledDeck.from_hidden_state(
            deck_type=deck_type,
            deck_version=row.deck_version,
            spread=spread,
            state=row.hidden_state,
            rng_source=row.rng_source,
        )
        draw = self.engine.resolve_picks(shuffled, positions)
        readings = DivinationService(self.session, self.engine)
        try:
            reading = await readings.store_draw(
                user,
                draw,
                locale=row.locale,
                question=row.question,
                include_optional_items=row.include_optional_items,
                draw_session_id=row.id,
                extra_meta={
                    "draw_session_id": str(row.id),
                    "selected_positions": list(positions),
                    "user_pick": True,
                },
            )
            row.status = STATUS_COMPLETED
            row.selected_positions = list(positions)
            row.completed_at = datetime.now(UTC)
            row.reading_id = reading.id
            await self.session.flush()
        except IntegrityError as exc:
            raise RevealRaceLost() from exc

        logger.info(
            "divination_session_revealed",
            session_id=str(row.id),
            reading_id=str(reading.id),
            count=len(positions),
        )
        return reading

    async def _completed_result(
        self, row: DivinationDrawSession, positions: list[int]
    ) -> DivinationReading:
        if list(row.selected_positions or []) != list(positions):
            raise SessionAlreadyCompleted()
        reading = await self.session.get(DivinationReading, row.reading_id)
        if reading is None:  # pragma: no cover - FK keeps it
            raise NotFound("Reading not found.")
        return reading

    @staticmethod
    def _validate(positions: list[int], *, required: int, deck_size: int) -> None:
        # The count comes from the spread definition, never from the client.
        if len(positions) != required:
            raise InvalidSelection(
                f"This spread needs exactly {required} selections.",
                code="selection_count_mismatch",
                details={"required": required, "received": len(positions)},
            )
        if len(set(positions)) != len(positions):
            raise InvalidSelection(
                "The same face-down position cannot be picked twice.",
                code="duplicate_selection",
            )
        if any(p < 0 or p >= deck_size for p in positions):
            raise InvalidSelection(
                "A selection is outside this deck.",
                code="selection_out_of_range",
                details={"deck_size": deck_size},
            )
