from __future__ import annotations

import uuid
from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Float, ForeignKey, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import HouseSystem, SavedPersonRelation

if TYPE_CHECKING:
    from app.db.models.user import User


class BirthProfileFields:
    """Columns shared by the user's own chart and by saved people.

    Birth data is stored as *local* date/time plus the IANA timezone of the
    birth place. The UTC instant is derived on demand so that historical DST
    rules stay correct even if a zone's rules are updated later.
    """

    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    birth_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    birth_time_known: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    birth_place: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    house_system: Mapped[HouseSystem] = mapped_column(
        String(20), default=HouseSystem.PLACIDUS, nullable=False
    )


class BirthProfile(
    Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, BirthProfileFields
):
    """The user's own birth data. Exactly one profile is marked primary."""

    __tablename__ = "birth_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="birth_profiles")


class SavedPerson(
    Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, BirthProfileFields
):
    """Partner / friend / family charts used for synastry and AI context."""

    __tablename__ = "saved_people"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    relation: Mapped[SavedPersonRelation] = mapped_column(
        String(20), default=SavedPersonRelation.OTHER, nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped["User"] = relationship(back_populates="saved_people")
