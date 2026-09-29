"""Forecast snapshots and the global cosmic event cache.

A month or a year of transits costs seconds of ephemeris work per user, so the
expensive results are persisted: Redis holds the hot copy, these tables mean a
cold cache after a deploy does not recompute a year for everyone. Global sky
events do not depend on a user at all, so they are cached once for everybody.

Revision ID: 0003_forecast_tables
Revises: 0002_service_catalog
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_forecast_tables"
down_revision: Union[str, None] = "0002_service_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "forecast_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("period_key", sa.String(20), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("scoring_version", sa.String(40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("input_hash", name="uq_forecast_snapshots_input_hash"),
    )
    op.create_index("ix_forecast_snapshots_user_id", "forecast_snapshots", ["user_id"])
    op.create_index("ix_forecast_snapshots_kind", "forecast_snapshots", ["kind"])
    op.create_index(
        "ix_forecast_snapshots_period_key", "forecast_snapshots", ["period_key"]
    )
    op.create_index(
        "ix_forecast_snapshots_input_hash", "forecast_snapshots", ["input_hash"]
    )

    op.create_table(
        "cosmic_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("event_key", sa.String(64), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("exact_at", TS, nullable=False),
        sa.Column("planet", sa.String(20), nullable=True),
        sa.Column("sign", sa.String(20), nullable=True),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("event_key", name="uq_cosmic_events_event_key"),
    )
    op.create_index("ix_cosmic_events_event_key", "cosmic_events", ["event_key"])
    op.create_index("ix_cosmic_events_type", "cosmic_events", ["type"])
    op.create_index("ix_cosmic_events_exact_at", "cosmic_events", ["exact_at"])


def downgrade() -> None:
    op.drop_table("cosmic_events")
    op.drop_table("forecast_snapshots")
