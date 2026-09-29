"""The expert marketplace.

The part worth reading: two **exclusion constraints**.

Double booking cannot be prevented by "SELECT then INSERT". Two requests can
both run the SELECT before either runs the INSERT, and both find the slot
free. The window is small and it is exactly the window a popular expert's
10:00 slot lives in.

So Postgres enforces it:

    EXCLUDE USING gist (
        expert_id WITH =,
        tstzrange(starts_at_utc, ends_at_utc) WITH &&
    ) WHERE (status IN ('pending', 'confirmed'))

Two overlapping live appointments for one expert cannot exist, whatever the
application does. The same shape guards active slot holds. Both need
`btree_gist`, because `expert_id` is a uuid and gist does not handle equality
on uuid without it.

SQLite (the unit-test database) has neither extension nor exclusion
constraints, so they are created only on PostgreSQL. That is why the
concurrency test that actually matters runs against real Postgres
(`scripts/booking_concurrency_check.py`) - the SQLite tests prove the state
machine, not the locking.

Revision ID: 0008_marketplace
Revises: 0007_divination
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_marketplace"
down_revision = "0007_divination"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
JSONB = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")

LIVE_APPOINTMENTS = "('pending', 'confirmed')"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgres():
        # Needed for `expert_id WITH =` inside a gist exclusion constraint.
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # ----------------------------------------------------------- experts
    op.create_table(
        "experts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("avatar_key", sa.String(120), nullable=True),
        sa.Column("headline", sa.String(160), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("languages", JSONB, nullable=False),
        sa.Column("specialties", JSONB, nullable=False),
        sa.Column(
            "experience_years", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "rating_average",
            sa.Numeric(3, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "rating_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("deleted_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_experts_user"),
        sa.CheckConstraint(
            "rating_average >= 0 AND rating_average <= 5",
            name="ck_experts_rating_range",
        ),
        sa.CheckConstraint("rating_count >= 0", name="ck_experts_rating_count"),
    )
    op.create_index("ix_experts_user_id", "experts", ["user_id"])
    op.create_index("ix_experts_status", "experts", ["status"])
    op.create_index(
        "ix_experts_status_rating", "experts", ["status", "rating_average"]
    )
    op.create_index("ix_experts_created_at", "experts", ["created_at"])

    # --------------------------------------------------- expert services
    op.create_table(
        "expert_services",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "expert_id",
            UUID,
            sa.ForeignKey("experts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_definition_id",
            UUID,
            sa.ForeignKey("service_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("delivery_type", sa.String(20), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("deleted_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("price_minor >= 0", name="ck_expert_services_price"),
        sa.CheckConstraint(
            "duration_minutes > 0 AND duration_minutes <= 600",
            name="ck_expert_services_duration",
        ),
    )
    op.create_index("ix_expert_services_expert_id", "expert_services", ["expert_id"])
    op.create_index(
        "ix_expert_services_expert_active",
        "expert_services",
        ["expert_id", "active"],
    )
    op.create_index(
        "ix_expert_services_definition",
        "expert_services",
        ["service_definition_id"],
    )
    op.create_index(
        "ix_expert_services_price", "expert_services", ["currency", "price_minor"]
    )

    # ------------------------------------------------------ availability
    op.create_table(
        "expert_availability",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "expert_id",
            UUID,
            sa.ForeignKey("experts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_local_time", sa.Time(), nullable=False),
        sa.Column("end_local_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6", name="ck_availability_weekday"
        ),
        sa.CheckConstraint(
            "start_local_time < end_local_time", name="ck_availability_order"
        ),
    )
    op.create_index(
        "ix_expert_availability_expert_id", "expert_availability", ["expert_id"]
    )
    op.create_index(
        "ix_expert_availability_expert_day",
        "expert_availability",
        ["expert_id", "weekday"],
    )

    op.create_table(
        "expert_availability_exceptions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "expert_id",
            UUID,
            sa.ForeignKey("experts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("exception_type", sa.String(30), nullable=False),
        sa.Column("starts_at_utc", TS, nullable=False),
        sa.Column("ends_at_utc", TS, nullable=False),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("starts_at_utc < ends_at_utc", name="ck_exception_order"),
    )
    op.create_index(
        "ix_expert_availability_exceptions_expert_id",
        "expert_availability_exceptions",
        ["expert_id"],
    )
    op.create_index(
        "ix_availability_exceptions_window",
        "expert_availability_exceptions",
        ["expert_id", "starts_at_utc", "ends_at_utc"],
    )

    # -------------------------------------------------------- slot holds
    op.create_table(
        "slot_holds",
        sa.Column("id", UUID, primary_key=True),
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
            "expert_service_id",
            UUID,
            sa.ForeignKey("expert_services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("starts_at_utc", TS, nullable=False),
        sa.Column("ends_at_utc", TS, nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("starts_at_utc < ends_at_utc", name="ck_hold_order"),
    )
    op.create_index("ix_slot_holds_user_id", "slot_holds", ["user_id"])
    op.create_index("ix_slot_holds_expert_id", "slot_holds", ["expert_id"])
    op.create_index("ix_slot_holds_status", "slot_holds", ["status"])
    op.create_index(
        "ix_slot_holds_expert_window", "slot_holds", ["expert_id", "starts_at_utc"]
    )
    op.create_index("ix_slot_holds_expiry", "slot_holds", ["status", "expires_at"])

    # ------------------------------------------------------------ orders
    op.create_table(
        "service_orders",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_definition_id",
            UUID,
            sa.ForeignKey("service_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "expert_id",
            UUID,
            sa.ForeignKey("experts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "expert_service_id",
            UUID,
            sa.ForeignKey("expert_services.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("fulfillment_mode", sa.String(20), nullable=False),
        sa.Column("delivery_type", sa.String(20), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("payment_status", sa.String(30), nullable=False),
        sa.Column(
            "subtotal_minor", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "discount_minor", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_minor", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "commission_basis_points",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "platform_fee_minor",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "expert_net_minor", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("service_title", sa.String(120), nullable=True),
        sa.Column("service_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("conversation_id", UUID, nullable=True),
        sa.Column("call_session_id", UUID, nullable=True),
        sa.Column(
            "preconsultation_report_id",
            UUID,
            sa.ForeignKey("ai_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("meta", JSONB, nullable=True),
        sa.Column("completed_at", TS, nullable=True),
        sa.Column("cancelled_at", TS, nullable=True),
        sa.Column("cancellation_actor", sa.String(30), nullable=True),
        sa.Column("cancellation_reason", sa.String(300), nullable=True),
        sa.Column("deleted_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_service_orders_idempotency"
        ),
        sa.CheckConstraint("total_minor >= 0", name="ck_orders_total"),
        sa.CheckConstraint(
            "platform_fee_minor >= 0 AND expert_net_minor >= 0",
            name="ck_orders_split",
        ),
    )
    op.create_index("ix_service_orders_user_id", "service_orders", ["user_id"])
    op.create_index("ix_service_orders_expert_id", "service_orders", ["expert_id"])
    op.create_index("ix_service_orders_status", "service_orders", ["status"])
    op.create_index(
        "ix_service_orders_user_status", "service_orders", ["user_id", "status"]
    )
    op.create_index(
        "ix_service_orders_expert_status", "service_orders", ["expert_id", "status"]
    )
    op.create_index(
        "ix_service_orders_created_at", "service_orders", ["created_at"]
    )

    op.create_table(
        "service_order_sources",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "order_id",
            UUID,
            sa.ForeignKey("service_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(40), nullable=False),
        sa.Column("source_id", UUID, nullable=False),
        sa.Column("label", sa.String(120), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "order_id", "source_kind", "source_id", name="uq_order_source"
        ),
    )
    op.create_index("ix_order_sources_order", "service_order_sources", ["order_id"])

    # ------------------------------------------------------ appointments
    op.create_table(
        "appointments",
        sa.Column("id", UUID, primary_key=True),
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
            "expert_service_id",
            UUID,
            sa.ForeignKey("expert_services.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "service_order_id",
            UUID,
            sa.ForeignKey("service_orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("starts_at_utc", TS, nullable=False),
        sa.Column("ends_at_utc", TS, nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("conversation_id", UUID, nullable=True),
        sa.Column("call_session_id", UUID, nullable=True),
        sa.Column("cancelled_at", TS, nullable=True),
        sa.Column("cancellation_actor", sa.String(30), nullable=True),
        sa.Column("cancellation_reason", sa.String(300), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("starts_at_utc < ends_at_utc", name="ck_appointment_order"),
    )
    op.create_index("ix_appointments_user_id", "appointments", ["user_id"])
    op.create_index("ix_appointments_expert_id", "appointments", ["expert_id"])
    op.create_index(
        "ix_appointments_service_order_id", "appointments", ["service_order_id"]
    )
    op.create_index("ix_appointments_status", "appointments", ["status"])
    op.create_index(
        "ix_appointments_expert_start", "appointments", ["expert_id", "starts_at_utc"]
    )
    op.create_index(
        "ix_appointments_user_start", "appointments", ["user_id", "starts_at_utc"]
    )

    # ---------------------------------------------------------- consents
    op.create_table(
        "service_consents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "order_id",
            UUID,
            sa.ForeignKey("service_orders.id", ondelete="CASCADE"),
            nullable=False,
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
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("granted_at", TS, nullable=False),
        sa.Column("revoked_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("order_id", "scope", name="uq_consent_order_scope"),
    )
    op.create_index(
        "ix_consents_expert_scope", "service_consents", ["expert_id", "scope"]
    )
    op.create_index("ix_consents_user", "service_consents", ["user_id"])

    # ----------------------------------------------- reviews & favorites
    op.create_table(
        "expert_reviews",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "order_id",
            UUID,
            sa.ForeignKey("service_orders.id", ondelete="CASCADE"),
            nullable=False,
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
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("deleted_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("order_id", name="uq_review_order"),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating"),
    )
    op.create_index("ix_expert_reviews_user_id", "expert_reviews", ["user_id"])
    op.create_index("ix_reviews_expert", "expert_reviews", ["expert_id"])
    op.create_index("ix_reviews_created_at", "expert_reviews", ["created_at"])

    op.create_table(
        "expert_favorites",
        sa.Column("id", UUID, primary_key=True),
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
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "user_id", "expert_id", name="uq_favorite_user_expert"
        ),
    )
    op.create_index("ix_favorites_user", "expert_favorites", ["user_id"])

    # --------------------------------------------- the real booking guard
    if _is_postgres():
        op.execute(
            f"""
            ALTER TABLE appointments
            ADD CONSTRAINT ex_appointments_no_overlap
            EXCLUDE USING gist (
                expert_id WITH =,
                tstzrange(starts_at_utc, ends_at_utc, '[)') WITH &&
            )
            WHERE (status IN {LIVE_APPOINTMENTS})
            """
        )
        op.execute(
            """
            ALTER TABLE slot_holds
            ADD CONSTRAINT ex_slot_holds_no_overlap
            EXCLUDE USING gist (
                expert_id WITH =,
                tstzrange(starts_at_utc, ends_at_utc, '[)') WITH &&
            )
            WHERE (status = 'active')
            """
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute(
            "ALTER TABLE slot_holds DROP CONSTRAINT IF EXISTS "
            "ex_slot_holds_no_overlap"
        )
        op.execute(
            "ALTER TABLE appointments DROP CONSTRAINT IF EXISTS "
            "ex_appointments_no_overlap"
        )

    op.drop_table("expert_favorites")
    op.drop_table("expert_reviews")
    op.drop_table("service_consents")
    op.drop_table("appointments")
    op.drop_table("service_order_sources")
    op.drop_table("service_orders")
    op.drop_table("slot_holds")
    op.drop_table("expert_availability_exceptions")
    op.drop_table("expert_availability")
    op.drop_table("expert_services")
    op.drop_table("experts")
