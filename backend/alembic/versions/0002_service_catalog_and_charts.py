"""Generalise the chart cache and add the service catalogue.

Two forward-compatibility moves made before any production data exists:

* ``natal_charts`` becomes ``charts`` with a ``chart_kind`` and the instant the
  chart is cast for. Horary (cast for the moment a question was asked), solar
  and lunar returns, composite and event charts then need no new table.
* ``service_definitions`` is the catalogue the marketplace, the automated
  report generators and the order rows all reference.

Revision ID: 0002_service_catalog
Revises: 0001_initial
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_service_catalog"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    # --- charts --------------------------------------------------------
    op.drop_index("ix_natal_charts_user_id", table_name="natal_charts")
    op.drop_index("ix_natal_charts_input_hash", table_name="natal_charts")
    op.drop_index("ix_natal_charts_subject_id", table_name="natal_charts")
    op.drop_constraint("uq_natal_charts_input_hash", "natal_charts", type_="unique")
    op.rename_table("natal_charts", "charts")

    op.add_column(
        "charts",
        sa.Column(
            "chart_kind", sa.String(20), nullable=False, server_default="natal"
        ),
    )
    op.add_column("charts", sa.Column("moment_utc", TS, nullable=True))
    op.alter_column(
        "charts",
        "subject_type",
        existing_type=sa.String(20),
        type_=sa.String(30),
        existing_nullable=False,
    )
    op.create_unique_constraint("uq_charts_input_hash", "charts", ["input_hash"])
    op.create_index("ix_charts_user_id", "charts", ["user_id"])
    op.create_index("ix_charts_input_hash", "charts", ["input_hash"])
    op.create_index("ix_charts_subject_id", "charts", ["subject_id"])
    op.create_index("ix_charts_chart_kind", "charts", ["chart_kind"])

    # --- service catalogue ---------------------------------------------
    op.create_table(
        "service_definitions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("fulfillment_modes", postgresql.JSONB(), nullable=False),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "requires_birth_data", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "requires_partner_data",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "requires_question", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "supports_chat", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "supports_voice", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "supports_video", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "supports_appointment",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "supports_automated_report",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "requires_premium", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_service_definitions_code"),
    )
    op.create_index("ix_service_definitions_code", "service_definitions", ["code"])


def downgrade() -> None:
    op.drop_table("service_definitions")

    op.drop_index("ix_charts_chart_kind", table_name="charts")
    op.drop_index("ix_charts_subject_id", table_name="charts")
    op.drop_index("ix_charts_input_hash", table_name="charts")
    op.drop_index("ix_charts_user_id", table_name="charts")
    op.drop_constraint("uq_charts_input_hash", "charts", type_="unique")
    op.alter_column(
        "charts",
        "subject_type",
        existing_type=sa.String(30),
        type_=sa.String(20),
        existing_nullable=False,
    )
    op.drop_column("charts", "moment_utc")
    op.drop_column("charts", "chart_kind")
    op.rename_table("charts", "natal_charts")

    op.create_unique_constraint(
        "uq_natal_charts_input_hash", "natal_charts", ["input_hash"]
    )
    op.create_index("ix_natal_charts_user_id", "natal_charts", ["user_id"])
    op.create_index("ix_natal_charts_input_hash", "natal_charts", ["input_hash"])
    op.create_index("ix_natal_charts_subject_id", "natal_charts", ["subject_id"])
