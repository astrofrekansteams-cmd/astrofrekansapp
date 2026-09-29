from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import UtcDateTime
from app.domain.enums import ChartKind

# JSONB on Postgres, plain JSON on SQLite (test suite).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class ChartCache(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Durable cache of computed charts of every kind.

    A chart is a pure function of (moment, place, house system, engine
    version, kind), so ``input_hash`` covers all of them and a row never goes
    stale on its own. Natal charts dominate, but horary, solar/lunar return,
    composite and event charts land in the same table: they differ only in
    ``kind`` and in what ``subject_type``/``subject_id`` point at
    (``birth_profile``, ``saved_person``, ``horary_question``, ``ad_hoc``).
    """

    __tablename__ = "charts"
    __table_args__ = (UniqueConstraint("input_hash", name="uq_charts_input_hash"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    chart_kind: Mapped[ChartKind] = mapped_column(
        String(20), default=ChartKind.NATAL, nullable=False, index=True
    )
    subject_type: Mapped[str] = mapped_column(String(30), default="user", nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    # The instant the chart is cast for - a birth, a question, an event.
    moment_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    house_system: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
