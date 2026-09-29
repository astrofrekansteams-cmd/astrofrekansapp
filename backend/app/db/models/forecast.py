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

JSONType = JSON().with_variant(JSONB(), "postgresql")


class ForecastSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Durable cache for the expensive forecasts.

    A month or a year of transits takes seconds of ephemeris work, and the
    answer only changes when the birth data, the engine or the scoring version
    changes - all of which are folded into ``input_hash``. Redis holds the hot
    copy; this table means a cold cache after a deploy does not recompute a
    year per user.

    It doubles as the record an expert reads in a hybrid consultation (phase
    B8), which is why the payload is stored whole rather than as loose columns.
    """

    __tablename__ = "forecast_snapshots"
    __table_args__ = (
        UniqueConstraint("input_hash", name="uq_forecast_snapshots_input_hash"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # "monthly", "annual", later "weekly" / report kinds.
    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # "2026-10" for a month, "2026" for a year.
    period_key: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)

    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)


class CosmicEventRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Global sky events, cached once for everyone.

    Moon phases, stations, eclipses and ingresses do not depend on a user, so
    they are computed once per window and shared. Personal relevance is layered
    on at read time - it is cheap - rather than stored per user.
    """

    __tablename__ = "cosmic_events"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_cosmic_events_event_key"),
    )

    event_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    exact_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, index=True
    )
    planet: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sign: Mapped[str | None] = mapped_column(String(20), nullable=True)
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
