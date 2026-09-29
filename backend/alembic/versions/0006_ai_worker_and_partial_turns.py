"""Astro AI hardening: worker claim fields and turn completion status.

Two additions:

* ``ai_report_jobs`` gains the bookkeeping a real queue consumer needs -
  ``max_attempts``, ``worker_id`` and ``lease_expires_at``. A worker claims a
  job by writing its own id and a lease; the lease is what lets another worker
  recover a job whose owner died without finishing it.
* ``ai_messages`` gains ``completion_status``. A stream the client dropped
  leaves real text behind, but it is not a finished answer and must not be
  shown - or replayed to the model - as though it were.

Revision ID: 0006_ai_hardening
Revises: 0005_ai_tables
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_ai_hardening"
down_revision = "0005_ai_tables"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column(
        "ai_messages",
        sa.Column(
            "completion_status",
            sa.String(20),
            nullable=False,
            server_default="completed",
        ),
    )

    op.add_column(
        "ai_report_jobs",
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "ai_report_jobs", sa.Column("worker_id", sa.String(80), nullable=True)
    )
    op.add_column(
        "ai_report_jobs", sa.Column("lease_expires_at", TS, nullable=True)
    )

    # The claim query orders queued work by age; the index keeps that cheap
    # once a backlog exists.
    op.create_index(
        "ix_ai_report_jobs_claim", "ai_report_jobs", ["status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_report_jobs_claim", table_name="ai_report_jobs")
    op.drop_column("ai_report_jobs", "lease_expires_at")
    op.drop_column("ai_report_jobs", "worker_id")
    op.drop_column("ai_report_jobs", "max_attempts")
    op.drop_column("ai_messages", "completion_status")
