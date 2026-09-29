"""Initial schema: users, profiles, birth data, tokens, subscriptions, chart cache.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("auth_provider", sa.String(20), nullable=False, server_default="password"),
        sa.Column("provider_subject", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "is_email_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("last_login_at", TS, nullable=True),
        sa.Column("deleted_at", TS, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "user_profiles",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("language", sa.String(8), nullable=False, server_default="tr"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Istanbul"),
        *_timestamps(),
    )
    op.create_index(
        "ix_user_profiles_user_id", "user_profiles", ["user_id"], unique=True
    )

    birth_columns = [
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("birth_time", sa.Time(), nullable=True),
        sa.Column(
            "birth_time_known", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("birth_place", sa.String(255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("house_system", sa.String(20), nullable=False, server_default="placidus"),
    ]

    op.create_table(
        "birth_profiles",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        *birth_columns,
        sa.Column("label", sa.String(80), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", TS, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_birth_profiles_user_id", "birth_profiles", ["user_id"])

    op.create_table(
        "saved_people",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("relation", sa.String(20), nullable=False, server_default="other"),
        *[column.copy() for column in birth_columns],
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("deleted_at", TS, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_saved_people_user_id", "saved_people", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("session_id", UUID, nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("revoked_at", TS, nullable=True),
        sa.Column("replaced_by_id", UUID, nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("used_at", TS, nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"]
    )
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tier", sa.String(20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("platform", sa.String(20), nullable=True),
        sa.Column("product_id", sa.String(120), nullable=True),
        sa.Column("transaction_id", sa.String(255), nullable=True),
        sa.Column("started_at", TS, nullable=True),
        sa.Column("expires_at", TS, nullable=True),
        sa.Column("cancelled_at", TS, nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=True
    )

    op.create_table(
        "natal_charts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("subject_type", sa.String(20), nullable=False, server_default="user"),
        sa.Column("subject_id", UUID, nullable=True),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("house_system", sa.String(20), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("input_hash", name="uq_natal_charts_input_hash"),
    )
    op.create_index("ix_natal_charts_user_id", "natal_charts", ["user_id"])
    op.create_index("ix_natal_charts_input_hash", "natal_charts", ["input_hash"])
    op.create_index("ix_natal_charts_subject_id", "natal_charts", ["subject_id"])


def downgrade() -> None:
    for table in (
        "natal_charts",
        "subscriptions",
        "password_reset_tokens",
        "refresh_tokens",
        "saved_people",
        "birth_profiles",
        "user_profiles",
        "users",
    ):
        op.drop_table(table)
