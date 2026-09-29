"""Horary questions, their analyses, and compatibility reports.

Chart data stays in ``charts``: these tables reference it rather than copying
planet positions around.

Revision ID: 0004_horary_compat
Revises: 0003_forecast_tables
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_horary_compat"
down_revision: Union[str, None] = "0003_forecast_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "horary_questions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("question_hash", sa.String(64), nullable=False),
        sa.Column("category", sa.String(30), nullable=True),
        sa.Column("house_override", sa.Integer(), nullable=True),
        sa.Column("asked_at_utc", TS, nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("location_name", sa.String(255), nullable=True),
        sa.Column(
            "chart_id", UUID, sa.ForeignKey("charts.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        sa.Column("deleted_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_horary_questions_user_id", "horary_questions", ["user_id"])
    op.create_index(
        "ix_horary_questions_question_hash", "horary_questions", ["question_hash"]
    )
    op.create_index(
        "ix_horary_questions_asked_at_utc", "horary_questions", ["asked_at_utc"]
    )

    op.create_table(
        "horary_analyses",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "question_id",
            UUID,
            sa.ForeignKey("horary_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("rules_version", sa.String(40), nullable=False),
        sa.Column("dignity_version", sa.String(40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_horary_analyses_question_id", "horary_analyses", ["question_id"], unique=True
    )

    op.create_table(
        "compatibility_reports",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("person_a_ref", sa.String(60), nullable=False),
        sa.Column("person_b_ref", sa.String(60), nullable=False),
        sa.Column("person_a_label", sa.String(120), nullable=True),
        sa.Column("person_b_label", sa.String(120), nullable=True),
        sa.Column(
            "chart_a_id", UUID, sa.ForeignKey("charts.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "chart_b_id", UUID, sa.ForeignKey("charts.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "derived_chart_id",
            UUID,
            sa.ForeignKey("charts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("scoring_version", sa.String(40), nullable=False),
        sa.Column("structured_result", postgresql.JSONB(), nullable=False),
        sa.Column("deleted_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_compatibility_reports_user_id", "compatibility_reports", ["user_id"]
    )
    op.create_index("ix_compatibility_reports_kind", "compatibility_reports", ["kind"])
    op.create_index(
        "ix_compatibility_reports_input_fingerprint",
        "compatibility_reports",
        ["input_fingerprint"],
    )


def downgrade() -> None:
    op.drop_table("compatibility_reports")
    op.drop_table("horary_analyses")
    op.drop_table("horary_questions")
