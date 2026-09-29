"""Firebase identities, expert chat, attachments, devices and the outbox.

`users.firebase_uid` is added **nullable** on purpose. Every existing
email/password account keeps working with no value in it, which is what makes
the hybrid auth mode a migration rather than a flag day. Unique, so one
Firebase identity cannot point at two accounts.

No business foreign key moves to a Firebase uid. Orders, appointments and
consent still reference the local user id, so rotating or losing a Firebase
project orphans nothing.

Revision ID: 0009_firebase_chat
Revises: 0008_marketplace
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_firebase_chat"
down_revision = "0008_marketplace"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
JSONB = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    # --- existing accounts keep working -----------------------------------
    op.add_column(
        "users", sa.Column("firebase_uid", sa.String(128), nullable=True)
    )
    op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"])
    op.create_unique_constraint("uq_users_firebase_uid", "users", ["firebase_uid"])

    op.create_table(
        "firebase_identities",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("firebase_uid", sa.String(128), nullable=False),
        sa.Column("provider_id", sa.String(40), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column(
            "email_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("link_method", sa.String(30), nullable=False),
        sa.Column("last_firebase_login_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("firebase_uid", name="uq_firebase_identities_uid"),
    )
    op.create_index("ix_firebase_identities_user", "firebase_identities", ["user_id"])

    # --- chat --------------------------------------------------------------
    op.create_table(
        "expert_conversations",
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
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provisioning_status", sa.String(20), nullable=False),
        sa.Column("provisioning_error", sa.String(120), nullable=True),
        sa.Column("firebase_conversation_id", sa.String(64), nullable=True),
        sa.Column(
            "projection_version", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("last_message_at", TS, nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("call_session_id", UUID, nullable=True),
        sa.Column("closed_at", TS, nullable=True),
        sa.Column("close_reason", sa.String(120), nullable=True),
        sa.Column("deleted_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        # One conversation per order: a retry under a flaky connection must not
        # open a second thread.
        sa.UniqueConstraint("order_id", name="uq_expert_conversations_order"),
    )
    op.create_index("ix_expert_conversations_user_id", "expert_conversations", ["user_id"])
    op.create_index(
        "ix_expert_conversations_expert_id", "expert_conversations", ["expert_id"]
    )
    op.create_index("ix_expert_conversations_status", "expert_conversations", ["status"])
    op.create_index(
        "ix_expert_conversations_user", "expert_conversations", ["user_id", "status"]
    )
    op.create_index(
        "ix_expert_conversations_expert", "expert_conversations", ["expert_id", "status"]
    )
    op.create_index(
        "ix_expert_conversations_provisioning",
        "expert_conversations",
        ["provisioning_status"],
    )
    op.create_index(
        "ix_expert_conversations_created_at", "expert_conversations", ["created_at"]
    )

    op.create_table(
        "media_attachments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "conversation_id",
            UUID,
            sa.ForeignKey("expert_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploader_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "storage_provider",
            sa.String(20),
            nullable=False,
            server_default="firebase",
        ),
        sa.Column("storage_key", sa.String(300), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("mime_type", sa.String(80), nullable=False),
        sa.Column("verified_mime_type", sa.String(80), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("rejection_reason", sa.String(120), nullable=True),
        sa.Column("message_id", sa.String(64), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("storage_key", name="uq_media_attachments_key"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_media_attachments_size"),
    )
    op.create_index(
        "ix_media_attachments_uploader_user_id", "media_attachments", ["uploader_user_id"]
    )
    op.create_index(
        "ix_media_attachments_conversation",
        "media_attachments",
        ["conversation_id", "status"],
    )
    op.create_index(
        "ix_media_attachments_pending", "media_attachments", ["status", "created_at"]
    )

    # --- push --------------------------------------------------------------
    op.create_table(
        "push_devices",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("firebase_uid", sa.String(128), nullable=True),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("token", sa.String(300), nullable=False),
        sa.Column("device_id_hash", sa.String(64), nullable=True),
        sa.Column("app_version", sa.String(40), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("disabled_reason", sa.String(60), nullable=True),
        sa.Column("last_seen_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        # A token addresses exactly one device. Signing in as somebody else
        # moves it rather than duplicating it.
        sa.UniqueConstraint("token", name="uq_push_devices_token"),
    )
    op.create_index("ix_push_devices_user_id", "push_devices", ["user_id"])
    op.create_index(
        "ix_push_devices_user_enabled", "push_devices", ["user_id", "enabled"]
    )

    op.create_table(
        "notification_outbox",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("conversation_id", UUID, nullable=True),
        sa.Column("order_id", UUID, nullable=True),
        sa.Column("appointment_id", UUID, nullable=True),
        sa.Column("dedupe_key", sa.String(160), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column("worker_id", sa.String(80), nullable=True),
        sa.Column("lease_expires_at", TS, nullable=True),
        sa.Column("scheduled_for", TS, nullable=True),
        sa.Column("processed_at", TS, nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        # One event, one notification, however many times it is enqueued.
        sa.UniqueConstraint("dedupe_key", name="uq_notification_outbox_dedupe"),
    )
    op.create_index("ix_notification_outbox_status", "notification_outbox", ["status"])
    op.create_index(
        "ix_notification_outbox_claim", "notification_outbox", ["status", "created_at"]
    )
    op.create_index("ix_notification_outbox_user", "notification_outbox", ["user_id"])
    op.create_index(
        "ix_notification_outbox_scheduled_for",
        "notification_outbox",
        ["scheduled_for"],
    )


def downgrade() -> None:
    op.drop_table("notification_outbox")
    op.drop_table("push_devices")
    op.drop_table("media_attachments")
    op.drop_table("expert_conversations")
    op.drop_table("firebase_identities")

    op.drop_constraint("uq_users_firebase_uid", "users", type_="unique")
    op.drop_index("ix_users_firebase_uid", table_name="users")
    op.drop_column("users", "firebase_uid")
