from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

JSONType = JSON().with_variant(JSONB(), "postgresql")


class CompatibilityReport(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A synastry, composite or Davison result, frozen at the moment it was run.

    ``input_fingerprint`` covers both people's birth data plus the engine and
    scoring versions. If a saved person is edited later, the old report keeps
    saying what it said - a new calculation produces a new report rather than
    silently rewriting history, which matters when the report has been read,
    paid for, or shown to an expert.
    """

    __tablename__ = "compatibility_reports"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # "me" | "saved_person" | "inline" plus the id when there is one.
    person_a_ref: Mapped[str] = mapped_column(String(60), nullable=False)
    person_b_ref: Mapped[str] = mapped_column(String(60), nullable=False)
    person_a_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    person_b_label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    chart_a_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("charts.id", ondelete="SET NULL"), nullable=True
    )
    chart_b_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("charts.id", ondelete="SET NULL"), nullable=True
    )
    derived_chart_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("charts.id", ondelete="SET NULL"), nullable=True
    )

    input_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(40), nullable=False)
    structured_result: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
