"""Voice and video calls: sessions, participants and provider events.

The one-live-call rule is a **partial unique index** on
`call_sessions(order_id) WHERE status IN (live statuses)`. Ten simultaneous
"start call" taps all try to insert; the index lets exactly one through, which
an application-level SELECT-then-INSERT cannot promise.

The B8/B9 reserved pointers (`service_orders.call_session_id`,
`appointments.call_session_id`, `expert_conversations.call_session_id`) are
left untouched and unwritten. `call_sessions.order_id / appointment_id /
conversation_id` is the source of truth; a single pointer on the parent could
only ever hold one of several calls, and writing both would give two answers
to "which call belongs to this order".

Revision ID: 0010_livekit_calls
Revises: 0009_firebase_chat
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_livekit_calls"
down_revision = "0009_firebase_chat"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)

LIVE_STATUS_SQL = "status IN ('scheduled', 'waiting', 'ringing', 'active')"
ALL_STATUS_SQL = (
    "status IN ('scheduled', 'waiting', 'ringing', 'active', "
    "'ended', 'missed', 'cancelled', 'failed')"
)


def upgrade() -> None:
    op.create_table(
        "call_sessions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "order_id",
            UUID,
            sa.ForeignKey("service_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "appointment_id",
            UUID,
            sa.ForeignKey("appointments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "conversation_id",
            UUID,
            sa.ForeignKey("expert_conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "expert_id",
            UUID,
            sa.ForeignKey("experts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "expert_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("call_type", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_room_name", sa.String(64), nullable=False),
        sa.Column("room_provisioned_at", TS, nullable=True),
        sa.Column("provider_error_code", sa.String(60), nullable=True),
        sa.Column("scheduled_start_at", TS, nullable=True),
        sa.Column("scheduled_end_at", TS, nullable=True),
        sa.Column("ringing_at", TS, nullable=True),
        sa.Column("started_at", TS, nullable=True),
        sa.Column("ended_at", TS, nullable=True),
        sa.Column("ended_by", sa.String(20), nullable=True),
        sa.Column("end_reason", sa.String(40), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("last_reconciled_at", TS, nullable=True),
        sa.Column(
            "recording_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider_room_name", name="uq_call_sessions_room"),
        sa.CheckConstraint(ALL_STATUS_SQL, name="ck_call_sessions_status"),
        sa.CheckConstraint(
            "call_type IN ('audio', 'video')", name="ck_call_sessions_type"
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="ck_call_sessions_times",
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_call_sessions_duration",
        ),
        sa.CheckConstraint(
            "recording_enabled = false", name="ck_call_sessions_no_recording"
        ),
    )
    op.create_index(
        "uq_call_sessions_live_order",
        "call_sessions",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text(LIVE_STATUS_SQL),
        sqlite_where=sa.text(LIVE_STATUS_SQL),
    )
    op.create_index("ix_call_sessions_order", "call_sessions", ["order_id"])
    op.create_index(
        "ix_call_sessions_appointment", "call_sessions", ["appointment_id"]
    )
    op.create_index(
        "ix_call_sessions_conversation", "call_sessions", ["conversation_id"]
    )
    op.create_index("ix_call_sessions_status", "call_sessions", ["status"])
    op.create_index("ix_call_sessions_created_at", "call_sessions", ["created_at"])
    op.create_index(
        "ix_call_sessions_user", "call_sessions", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_call_sessions_expert", "call_sessions", ["expert_id", "created_at"]
    )

    op.create_table(
        "call_participants",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "call_session_id",
            UUID,
            sa.ForeignKey("call_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("provider_identity", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("first_joined_at", TS, nullable=True),
        sa.Column("last_joined_at", TS, nullable=True),
        sa.Column("last_left_at", TS, nullable=True),
        sa.Column(
            "connection_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_event_at", TS, nullable=True),
        sa.Column(
            "token_issued_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_token_issued_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "call_session_id", "role", name="uq_call_participants_role"
        ),
        sa.UniqueConstraint(
            "provider_identity", name="uq_call_participants_identity"
        ),
        sa.CheckConstraint(
            "role IN ('user', 'expert')", name="ck_call_participants_role"
        ),
        sa.CheckConstraint(
            "status IN ('invited', 'joining', 'joined', 'left', 'disconnected')",
            name="ck_call_participants_status",
        ),
        sa.CheckConstraint(
            "connection_count >= 0", name="ck_call_participants_connections"
        ),
    )
    op.create_index(
        "ix_call_participants_call_session_id",
        "call_participants",
        ["call_session_id"],
    )
    op.create_index(
        "ix_call_participants_user_id", "call_participants", ["user_id"]
    )

    op.create_table(
        "call_provider_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("event_id", sa.String(80), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column(
            "call_session_id",
            UUID,
            sa.ForeignKey("call_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("room_name", sa.String(64), nullable=True),
        sa.Column("participant_identity", sa.String(64), nullable=True),
        sa.Column("provider_created_at", TS, nullable=True),
        sa.Column("received_at", TS, nullable=False),
        sa.Column("processed_at", TS, nullable=True),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=True),
        sa.UniqueConstraint(
            "provider", "event_id", name="uq_call_provider_events_event"
        ),
    )
    op.create_index(
        "ix_call_provider_events_session",
        "call_provider_events",
        ["call_session_id"],
    )
    op.create_index(
        "ix_call_provider_events_received",
        "call_provider_events",
        ["received_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_call_provider_events_received", table_name="call_provider_events"
    )
    op.drop_index(
        "ix_call_provider_events_session", table_name="call_provider_events"
    )
    op.drop_table("call_provider_events")

    op.drop_index("ix_call_participants_user_id", table_name="call_participants")
    op.drop_index(
        "ix_call_participants_call_session_id", table_name="call_participants"
    )
    op.drop_table("call_participants")

    for name in (
        "ix_call_sessions_expert",
        "ix_call_sessions_user",
        "ix_call_sessions_created_at",
        "ix_call_sessions_status",
        "ix_call_sessions_conversation",
        "ix_call_sessions_appointment",
        "ix_call_sessions_order",
        "uq_call_sessions_live_order",
    ):
        op.drop_index(name, table_name="call_sessions")
    op.drop_table("call_sessions")
