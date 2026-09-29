from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import UtcDateTime
from app.domain.horary import HoraryStatus

JSONType = JSON().with_variant(JSONB(), "postgresql")


class HoraryQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A question, and the moment it was asked.

    The instant and place are the chart: unlike every other chart in the
    product, a horary chart has nothing to do with the querent's birth data,
    and changing their birth profile must never change it. That is why the
    coordinates and the timezone are stored on the question itself rather than
    read from the user's profile at analysis time.
    """

    __tablename__ = "horary_questions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)

    # Normalised hash of the question text, for the duplicate *hint* only.
    # Re-asking is never blocked; traditionally a repeated question is judged
    # from the original chart, and that is the astrologer's call.
    question_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    house_override: Mapped[int | None] = mapped_column(Integer, nullable=True)

    asked_at_utc: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, index=True
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    chart_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("charts.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[HoraryStatus] = mapped_column(
        String(20), default=HoraryStatus.CREATED, nullable=False
    )
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    analysis: Mapped["HoraryAnalysisRecord | None"] = relationship(
        back_populates="question", uselist=False, cascade="all, delete-orphan"
    )


class HoraryAnalysisRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The structured analysis of one question.

    Stored whole: it is what an expert opens in their panel (phase B8) and
    what Astro AI reads in B6, and it must not drift when the engine or the
    rules change - hence the version columns.
    """

    __tablename__ = "horary_analyses"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("horary_questions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(40), nullable=False)
    dignity_version: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)

    question: Mapped[HoraryQuestion] = relationship(back_populates="analysis")
