"""Declarative base plus the mixins every table shares."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.types import UtcDateTime


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, sort_order=-100
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=100,
    )
    # ``onupdate`` is Python-side on purpose: a SQL-side default would expire
    # the attribute on flush and force a lazy refresh, which is illegal inside
    # the async session (MissingGreenlet). The server default stays for rows
    # written outside the ORM.
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        default=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=101,
    )


class SoftDeleteMixin:
    """Rows users can 'delete' without losing referential history."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True, sort_order=102
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(UTC)
