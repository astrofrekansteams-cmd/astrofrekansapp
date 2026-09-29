"""Divination: readings and the items they dealt.

A reading is a snapshot. The uniqueness constraints are part of that promise:
one item per position, and no item twice in the same reading. A duplicate here
would be a broken deal that looked like a real one, so the database refuses it
rather than trusting the engine to have got it right.

Revision ID: 0007_divination
Revises: 0006_ai_hardening
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_divination"
down_revision = "0006_ai_hardening"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
JSONB = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "divination_readings",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("deck_type", sa.String(20), nullable=False),
        sa.Column("deck_version", sa.String(40), nullable=False),
        sa.Column("spread_code", sa.String(40), nullable=False),
        sa.Column("spread_version", sa.String(60), nullable=False),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("question_hash", sa.String(64), nullable=True),
        sa.Column(
            "repeat_of_id",
            UUID,
            sa.ForeignKey("divination_readings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rng_source", sa.String(30), nullable=False),
        sa.Column("drawn_at", TS, nullable=False),
        sa.Column("draw_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("meta", JSONB, nullable=True),
        sa.Column("deleted_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_divination_readings_user_id", "divination_readings", ["user_id"]
    )
    op.create_index(
        "ix_divination_readings_deck_type", "divination_readings", ["deck_type"]
    )
    op.create_index(
        "ix_divination_readings_question_hash",
        "divination_readings",
        ["question_hash"],
    )
    op.create_index(
        "ix_divination_readings_draw_fingerprint",
        "divination_readings",
        ["draw_fingerprint"],
    )
    op.create_index(
        "ix_divination_readings_user_deck",
        "divination_readings",
        ["user_id", "deck_type"],
    )
    op.create_index(
        "ix_divination_readings_created_at", "divination_readings", ["created_at"]
    )

    op.create_table(
        "divination_draw_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "reading_id",
            UUID,
            sa.ForeignKey("divination_readings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("draw_order", sa.Integer(), nullable=False),
        sa.Column("position_index", sa.Integer(), nullable=False),
        sa.Column("position_key", sa.String(40), nullable=False),
        sa.Column("item_id", sa.String(60), nullable=False),
        sa.Column("orientation", sa.String(10), nullable=False),
        sa.Column("image_asset_key", sa.String(60), nullable=False),
        sa.Column("meaning_version", sa.String(40), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "reading_id", "position_index", name="uq_divination_item_position"
        ),
        sa.UniqueConstraint(
            "reading_id", "item_id", name="uq_divination_item_unique"
        ),
    )
    op.create_index(
        "ix_divination_draw_items_reading_id",
        "divination_draw_items",
        ["reading_id"],
    )
    op.create_index(
        "ix_divination_draw_items_created_at",
        "divination_draw_items",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("divination_draw_items")
    op.drop_table("divination_readings")
