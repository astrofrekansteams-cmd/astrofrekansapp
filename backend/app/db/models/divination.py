"""Divination storage: readings and the items they dealt.

A reading is a **snapshot**, in the strict sense: once the cards are down,
nothing rewrites them. The row records the deck version, the spread version
and the meaning version that were in force at the moment of the draw, so
reopening a reading a year later shows the same cards in the same positions
with the same text - whatever has changed in the deck data since.

The AI interpretation is stored separately, through the B6 report system. A
failed or regenerated interpretation must never be able to disturb the draw.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import UtcDateTime

JSONType = JSON().with_variant(JSONB(), "postgresql")


class DivinationReading(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """One deal: a deck, a spread and the moment it happened."""

    __tablename__ = "divination_readings"
    __table_args__ = (
        Index("ix_divination_readings_user_deck", "user_id", "deck_type"),
        Index("ix_divination_readings_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    deck_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    deck_version: Mapped[str] = mapped_column(String(40), nullable=False)
    spread_code: Mapped[str] = mapped_column(String(40), nullable=False)
    spread_version: Mapped[str] = mapped_column(String(60), nullable=False)

    locale: Mapped[str] = mapped_column(String(8), nullable=False)

    # The question is optional and is untrusted input. It is stored because a
    # reading without its question is hard to make sense of later, but it is
    # never logged and never treated as an instruction.
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A hash of the normalised question, so repeat asks can be spotted without
    # comparing - or indexing - the text itself.
    question_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    repeat_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("divination_readings.id", ondelete="SET NULL"), nullable=True
    )

    # Which randomness dealt this. A seeded deal must never be mistaken for a
    # real one, so the source is part of the record.
    rng_source: Mapped[str] = mapped_column(String(30), nullable=False)
    drawn_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    # Hash of the immutable draw. This is what an AI report fingerprints
    # against, so the same draw and prompt version reuse the same report.
    draw_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="drawn")
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)

    # Set when the reading was revealed from a user-pick session. Unique, so
    # the database itself guarantees one session produces at most one reading
    # even when reveals race.
    draw_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("divination_draw_sessions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    items: Mapped[list["DivinationDrawItem"]] = relationship(
        back_populates="reading",
        cascade="all, delete-orphan",
        order_by="DivinationDrawItem.draw_order",
    )


class DivinationDrawItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One card or rune, where it landed and how.

    `item_id` points at the deck data rather than copying the text: the deck
    version on the parent reading pins which text that id resolves to, so the
    snapshot holds without duplicating 167 meanings into every row.
    """

    __tablename__ = "divination_draw_items"
    __table_args__ = (
        # A position is dealt exactly once per reading. The database says so
        # too, because a duplicate here would be a broken deal that looked
        # like a real one.
        UniqueConstraint(
            "reading_id", "position_index", name="uq_divination_item_position"
        ),
        UniqueConstraint("reading_id", "item_id", name="uq_divination_item_unique"),
        Index("ix_divination_draw_items_created_at", "created_at"),
    )

    reading_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("divination_readings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    draw_order: Mapped[int] = mapped_column(Integer, nullable=False)
    position_index: Mapped[int] = mapped_column(Integer, nullable=False)
    position_key: Mapped[str] = mapped_column(String(40), nullable=False)

    item_id: Mapped[str] = mapped_column(String(60), nullable=False)
    orientation: Mapped[str] = mapped_column(String(10), nullable=False)
    image_asset_key: Mapped[str] = mapped_column(String(60), nullable=False)

    # Which meaning text this item resolved to when it was dealt.
    meaning_version: Mapped[str] = mapped_column(String(40), nullable=False)

    reading: Mapped[DivinationReading] = relationship(back_populates="items")


class DivinationDrawSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A shuffled, face-down deck waiting for the user's picks.

    The deck is shuffled once, when the session is created, and every
    face-down slot's orientation is fixed at the same moment. The user then
    chooses slots; the reveal resolves exactly those slots. Nothing is
    re-randomised later, and `hidden_state` never leaves the server.
    """

    __tablename__ = "divination_draw_sessions"
    __table_args__ = (
        # Create is idempotent per user and client reference.
        UniqueConstraint("user_id", "consumer_ref", name="uq_divination_session_consumer_ref"),
        Index("ix_divination_draw_sessions_expires_at", "expires_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    consumer_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    # Hash of the semantic request (deck, spread, question, locale, optional
    # items): the same ref with a different request is a conflict, not a retry.
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    deck_type: Mapped[str] = mapped_column(String(20), nullable=False)
    deck_version: Mapped[str] = mapped_column(String(40), nullable=False)
    spread_code: Mapped[str] = mapped_column(String(40), nullable=False)
    spread_version: Mapped[str] = mapped_column(String(60), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    include_optional_items: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Server-only: {"order": [item_id, ...], "orientations": [..]} indexed by
    # face-down slot. Never serialised to a client.
    hidden_state: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    deck_size: Mapped[int] = mapped_column(Integer, nullable=False)
    rng_source: Mapped[str] = mapped_column(String(30), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    selected_positions: Mapped[list[int] | None] = mapped_column(
        JSONType, nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    reading_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "divination_readings.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_divination_session_reading",
        ),
        nullable=True,
        unique=True,
    )
