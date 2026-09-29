"""Call delivery reliability: per-delivery lease, at-least-once.

Revision ID: 0014_call_delivery_lease
Revises: 0013_mobile_call_delivery

`notification_deliveries` gains `lease_until` and `last_attempt_at`, so a
delivery left `sending` by a worker that died is claimed again once its lease
lapses, instead of never being sent. Statuses move to
pending/sending/delivered/failed/skipped; existing rows are mapped (the
downgrade maps them back).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0014_call_delivery_lease'
down_revision: Union[str, None] = '0013_mobile_call_delivery'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('notification_deliveries', sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('notification_deliveries', sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE notification_deliveries SET status = 'delivered' WHERE status = 'sent'")
    op.execute("UPDATE notification_deliveries SET status = 'pending' WHERE status = 'retry'")
    op.execute(
        "UPDATE notification_deliveries SET status = 'failed', "
        "error_code = COALESCE(error_code, 'invalid_token') WHERE status = 'invalid_token'"
    )
    op.execute(
        "UPDATE notification_deliveries SET status = 'skipped', "
        "error_code = 'provider_not_configured' WHERE status = 'not_configured'"
    )


def downgrade() -> None:
    op.execute("UPDATE notification_deliveries SET status = 'sent' WHERE status = 'delivered'")
    op.execute("UPDATE notification_deliveries SET status = 'retry' WHERE status = 'pending'")
    op.execute(
        "UPDATE notification_deliveries SET status = 'not_configured' "
        "WHERE status = 'skipped' AND error_code = 'provider_not_configured'"
    )
    op.drop_column('notification_deliveries', 'last_attempt_at')
    op.drop_column('notification_deliveries', 'lease_until')
