"""Readings: dealing, storing and reading back.

The draw happens first and is committed on its own. That ordering is the
point of the phase: a user who pays for a reading gets their cards even if the
interpretation service is down, over quota, or slow. An AI failure costs an
explanation, never the deal.

Ownership is checked before anything is assembled, and another user's reading
is a 404 rather than a 403 - a wrong guess must not confirm that an id exists.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFound
from app.core.logging import get_logger
from app.db.models.divination import DivinationDrawItem, DivinationReading
from app.db.models.user import User
from app.domain.divination import (
    DeckType,
    DivinationDraw,
    Orientation,
    ReadingStatus,
)
from app.services.divination.decks import get_deck
from app.services.divination.engine import DrawEngine, get_draw_engine

logger = get_logger(__name__)

MAX_QUESTION_LENGTH = 500


def normalise_question(question: str) -> str:
    """Fold a question down to something two asks can be compared on.

    Turkish "İ".casefold() is "i" plus a combining dot above, so "İşim" and
    "işim" would otherwise hash differently and the same question asked twice
    would not be recognised as a repeat. Dropping that one combining mark
    fixes it without touching ş, ğ, ı and the rest.
    """
    folded = (
        unicodedata.normalize("NFKC", question)
        .casefold()
        .replace("̇", "")
        .strip()
    )
    return re.sub(r"\s+", " ", folded)


def question_hash(question: str | None) -> str | None:
    """A hash, never the text.

    Repeat asks can be spotted without storing or indexing the question in a
    comparable form - the question itself is private.
    """
    if not question or not question.strip():
        return None
    return hashlib.sha256(
        normalise_question(question).encode("utf-8")
    ).hexdigest()


def draw_fingerprint(draw: DivinationDraw) -> str:
    """Identify the deal itself.

    Covers the deck and spread versions as well as the items, so an
    interpretation produced against `tarot_v1` is not reused after the deck
    text is rewritten as `tarot_v2`.
    """
    parts = [
        draw.deck_type.value,
        draw.deck_version,
        draw.spread.spread_version,
        *(
            f"{item.position.index}:{item.item.item_id}:{item.orientation.value}"
            for item in draw.items
        ),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


class DivinationService:
    def __init__(
        self, session: AsyncSession, engine: DrawEngine | None = None
    ) -> None:
        self.session = session
        self.engine = engine or get_draw_engine()

    # -------------------------------------------------------------- draw

    async def create_reading(
        self,
        user: User,
        *,
        deck_type: DeckType,
        spread_code: str,
        locale: str,
        question: str | None = None,
        include_optional_items: bool = False,
    ) -> DivinationReading:
        """Deal, then store. Nothing about the question reaches the dealer.

        Deprecated path (server picks the cards). The app uses user-pick draw
        sessions; this stays for backward compatibility.
        """
        draw = self.engine.draw(
            deck_type,
            spread_code,
            include_optional_items=include_optional_items,
        )
        return await self.store_draw(
            user,
            draw,
            locale=locale,
            question=question,
            include_optional_items=include_optional_items,
        )

    async def store_draw(
        self,
        user: User,
        draw: DivinationDraw,
        *,
        locale: str,
        question: str | None,
        include_optional_items: bool,
        draw_session_id: uuid.UUID | None = None,
        extra_meta: dict | None = None,
    ) -> DivinationReading:
        """Persist a finished draw as an immutable reading snapshot."""
        deck_type = draw.deck_type
        cleaned = (question or "").strip()[:MAX_QUESTION_LENGTH] or None
        digest = question_hash(cleaned)
        previous = await self._recent_same_question(user, deck_type, digest)

        reading = DivinationReading(
            user_id=user.id,
            deck_type=deck_type.value,
            deck_version=draw.deck_version,
            spread_code=draw.spread.spread_code,
            spread_version=draw.spread.spread_version,
            locale=locale,
            question=cleaned,
            question_hash=digest,
            repeat_of_id=previous.id if previous else None,
            rng_source=draw.rng_source,
            drawn_at=draw.drawn_at,
            draw_fingerprint=draw_fingerprint(draw),
            status=ReadingStatus.DRAWN.value,
            draw_session_id=draw_session_id,
            meta={
                "repeat_reading": previous is not None,
                "reversed_count": draw.reversed_count,
                "position_count": len(draw.items),
                "includes_optional_items": include_optional_items,
                **(extra_meta or {}),
            },
        )
        self.session.add(reading)
        await self.session.flush()

        for drawn in draw.items:
            self.session.add(
                DivinationDrawItem(
                    reading_id=reading.id,
                    draw_order=drawn.draw_order,
                    position_index=drawn.position.index,
                    position_key=drawn.position.key,
                    item_id=drawn.item.item_id,
                    orientation=drawn.orientation.value,
                    image_asset_key=drawn.item.image_asset_key,
                    meaning_version=draw.deck_version,
                )
            )
        await self.session.flush()

        # The question text is deliberately absent from this line.
        logger.info(
            "divination_reading_created",
            reading_id=str(reading.id),
            deck_type=deck_type.value,
            spread=draw.spread.spread_code,
            count=len(draw.items),
            repeat_reading=previous is not None,
            rng_source=draw.rng_source,
            user_pick=draw_session_id is not None,
        )
        return reading

    async def _recent_same_question(
        self, user: User, deck_type: DeckType, digest: str | None
    ) -> DivinationReading | None:
        """The same question, same deck, recently.

        Never blocks: people are allowed to ask again, and refusing would be
        both paternalistic and easy to work around. It is recorded so the
        interpreter can be told, and told not to narrate a changed fate.
        """
        if digest is None:
            return None
        since = datetime.now(UTC) - timedelta(
            seconds=settings.divination_repeat_window_seconds
        )
        return await self.session.scalar(
            select(DivinationReading)
            .where(
                DivinationReading.user_id == user.id,
                DivinationReading.deck_type == deck_type.value,
                DivinationReading.question_hash == digest,
                DivinationReading.created_at >= since,
                DivinationReading.deleted_at.is_(None),
            )
            .order_by(DivinationReading.created_at.desc())
            .limit(1)
        )

    # ------------------------------------------------------------- read

    async def get(
        self, *, user: User, reading_id: uuid.UUID
    ) -> DivinationReading:
        reading = await self.session.scalar(
            select(DivinationReading).where(
                DivinationReading.id == reading_id,
                DivinationReading.user_id == user.id,
                DivinationReading.deleted_at.is_(None),
            )
        )
        if reading is None:
            raise NotFound("Reading not found.")
        return reading

    async def items(self, reading_id: uuid.UUID) -> list[DivinationDrawItem]:
        rows = await self.session.scalars(
            select(DivinationDrawItem)
            .where(DivinationDrawItem.reading_id == reading_id)
            .order_by(DivinationDrawItem.draw_order)
        )
        return list(rows)

    async def list(
        self,
        *,
        user: User,
        deck_type: DeckType | None = None,
        limit: int = 50,
    ) -> list[DivinationReading]:
        statement = (
            select(DivinationReading)
            .where(
                DivinationReading.user_id == user.id,
                DivinationReading.deleted_at.is_(None),
            )
            .order_by(DivinationReading.created_at.desc())
            .limit(limit)
        )
        if deck_type is not None:
            statement = statement.where(
                DivinationReading.deck_type == deck_type.value
            )
        return list(await self.session.scalars(statement))

    async def delete(self, *, user: User, reading_id: uuid.UUID) -> DivinationReading:
        """Soft delete, like every other user-owned record in the app."""
        reading = await self.get(user=user, reading_id=reading_id)
        reading.deleted_at = datetime.now(UTC)
        await self.session.flush()
        return reading

    # ----------------------------------------------------------- render

    async def hydrate(self, reading: DivinationReading) -> list[dict]:
        """Resolve stored ids back into deck text.

        The reading's own `deck_version` decides which text an id resolves to,
        which is what makes the snapshot hold.
        """
        deck = get_deck(DeckType(reading.deck_type), reading.deck_version)
        from app.services.divination.spreads import get_spread

        spread = get_spread(DeckType(reading.deck_type), reading.spread_code)
        positions = {position.index: position for position in spread.positions}

        hydrated: list[dict] = []
        for row in await self.items(reading.id):
            item = deck.item(row.item_id)
            meaning = item.meaning(reading.locale, fallback=deck.locales[0])
            position = positions.get(row.position_index)
            orientation = Orientation(row.orientation)

            hydrated.append(
                {
                    "draw_order": row.draw_order,
                    "position_index": row.position_index,
                    "position_key": row.position_key,
                    "position_title": (
                        position.title(reading.locale, fallback="tr")
                        if position
                        else row.position_key
                    ),
                    "position_role": (
                        position.interpretation_role if position else ""
                    ),
                    "position_description": (
                        position.description(reading.locale, fallback="tr")
                        if position
                        else ""
                    ),
                    "item_id": row.item_id,
                    "display_name": meaning.display_name,
                    "canonical_name": item.canonical_name,
                    "orientation": orientation.value,
                    "image_asset_key": row.image_asset_key,
                    "keywords": list(
                        meaning.reversed_keywords
                        if orientation is Orientation.REVERSED
                        and meaning.reversed_keywords
                        else meaning.keywords
                    ),
                    "meaning": (
                        meaning.reversed_meaning
                        if orientation is Orientation.REVERSED
                        else meaning.upright_meaning
                    ),
                    "shadow_meaning": (
                        meaning.reversed_meaning
                        if orientation is not Orientation.REVERSED
                        else ""
                    ),
                    "love_meaning": meaning.love_meaning,
                    "career_meaning": meaning.career_meaning,
                    "growth_meaning": meaning.growth_meaning,
                    "symbolism": meaning.symbolism,
                    "content_status": item.content_status.value,
                    "meaning_version": row.meaning_version,
                }
            )
        return hydrated
