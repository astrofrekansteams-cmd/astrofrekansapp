"""Astro AI: conversations, messages, generations, reports and report jobs.

Two deliberate absences in this schema:

* generations record cost and configuration but never the prompt, the context
  or the answer - the table has to stay safe to read,
* messages hold only user-visible turns; system and developer instructions are
  not stored as messages.

Revision ID: 0005_ai_tables
Revises: 0004_horary_compat
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_ai_tables"
down_revision: Union[str, None] = "0004_horary_compat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(160), nullable=True),
        sa.Column("locale", sa.String(8), nullable=False, server_default="tr"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "summarised_message_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("archived_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])
    op.create_index("ix_ai_conversations_created_at", "ai_conversations", ["created_at"])

    op.create_table(
        "ai_messages",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "conversation_id",
            UUID,
            sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("generation_id", UUID, nullable=True),
        sa.Column("context_type", sa.String(30), nullable=True),
        sa.Column("source_factor_ids", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"]
    )
    op.create_index("ix_ai_messages_created_at", "ai_messages", ["created_at"])

    op.create_table(
        "ai_generations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "conversation_id",
            UUID,
            sa.ForeignKey("ai_conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("use_case", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model_requested", sa.String(60), nullable=False),
        sa.Column("model_actual", sa.String(60), nullable=False),
        sa.Column("fallback_reason", sa.String(80), nullable=True),
        sa.Column("prompt_version", sa.String(60), nullable=False),
        sa.Column("context_version", sa.String(60), nullable=False),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "cached_input_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_response_id", sa.String(80), nullable=True),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_generations_user_id", "ai_generations", ["user_id"])
    op.create_index(
        "ix_ai_generations_conversation_id", "ai_generations", ["conversation_id"]
    )
    op.create_index("ix_ai_generations_use_case", "ai_generations", ["use_case"])
    op.create_index("ix_ai_generations_status", "ai_generations", ["status"])
    op.create_index("ix_ai_generations_created_at", "ai_generations", ["created_at"])

    op.create_table(
        "ai_reports",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_type", sa.String(20), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", UUID, nullable=True),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("sections", postgresql.JSONB(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=True),
        sa.Column("interpretation_scope", sa.Text(), nullable=True),
        sa.Column("safety_note", sa.Text(), nullable=True),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(60), nullable=False),
        sa.Column("context_version", sa.String(60), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(60), nullable=False),
        sa.Column("generation_id", UUID, nullable=True),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column("deleted_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_reports_user_id", "ai_reports", ["user_id"])
    op.create_index("ix_ai_reports_report_type", "ai_reports", ["report_type"])
    op.create_index("ix_ai_reports_source_id", "ai_reports", ["source_id"])
    op.create_index("ix_ai_reports_status", "ai_reports", ["status"])
    op.create_index(
        "ix_ai_reports_input_fingerprint", "ai_reports", ["input_fingerprint"]
    )
    op.create_index("ix_ai_reports_created_at", "ai_reports", ["created_at"])

    op.create_table(
        "ai_report_jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_type", sa.String(20), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", UUID, nullable=True),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column(
            "report_id",
            UUID,
            sa.ForeignKey("ai_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("started_at", TS, nullable=True),
        sa.Column("finished_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_report_jobs_user_id", "ai_report_jobs", ["user_id"])
    op.create_index("ix_ai_report_jobs_status", "ai_report_jobs", ["status"])
    op.create_index(
        "ix_ai_report_jobs_input_fingerprint", "ai_report_jobs", ["input_fingerprint"]
    )


def downgrade() -> None:
    op.drop_table("ai_report_jobs")
    op.drop_table("ai_reports")
    op.drop_table("ai_generations")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
