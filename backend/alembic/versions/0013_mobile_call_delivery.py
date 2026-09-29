"""Mobile call delivery: VoIP credentials, call push expiry, per-device ledger.

Revision ID: 0013_mobile_call_delivery
Revises: 0012_paid_report_enforcement

* `push_devices.credential_type` (`fcm` | `apns_voip`) keeps an iPhone's
  PushKit VoIP token apart from its FCM token; existing rows are FCM.
  `apns_environment` records which APNs environment a VoIP token belongs to.
* `notification_outbox.expires_at`: an incoming call past its ring is skipped,
  never sent late.
* `notification_deliveries`: one row per (outbox row, device) for call events,
  so retries resend only what failed and each device rings at most once.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0013_mobile_call_delivery'
down_revision: Union[str, None] = '0012_paid_report_enforcement'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'push_devices',
        sa.Column('credential_type', sa.String(length=20), server_default='fcm', nullable=False),
    )
    op.add_column('push_devices', sa.Column('apns_environment', sa.String(length=12), nullable=True))
    op.add_column(
        'notification_outbox', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True)
    )

    op.create_table(
        'notification_deliveries',
        sa.Column('outbox_id', sa.Uuid(), nullable=False),
        sa.Column('device_id', sa.Uuid(), nullable=False),
        sa.Column('transport', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('error_code', sa.String(length=60), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['push_devices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['outbox_id'], ['notification_outbox.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('outbox_id', 'device_id', name='uq_notification_deliveries_target'),
    )
    op.create_index(
        op.f('ix_notification_deliveries_device_id'), 'notification_deliveries', ['device_id'], unique=False
    )
    op.create_index(
        op.f('ix_notification_deliveries_outbox_id'), 'notification_deliveries', ['outbox_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_notification_deliveries_outbox_id'), table_name='notification_deliveries')
    op.drop_index(op.f('ix_notification_deliveries_device_id'), table_name='notification_deliveries')
    op.drop_table('notification_deliveries')
    op.drop_column('notification_outbox', 'expires_at')
    op.drop_column('push_devices', 'apns_environment')
    op.drop_column('push_devices', 'credential_type')
