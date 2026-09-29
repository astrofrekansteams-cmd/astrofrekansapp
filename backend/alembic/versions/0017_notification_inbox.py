"""In-app notification centre: read state on the outbox.

Revision ID: 0017_notification_inbox
Revises: 0016_coins_and_profile

The in-app inbox is the same event stream as push: every notification the
backend queues in `notification_outbox` is also what the notification centre
lists. Only the read state is new - `read_at` - plus an index for "this user's
notifications, newest first".
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0017_notification_inbox'
down_revision: Union[str, None] = '0016_coins_and_profile'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'notification_outbox',
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_notification_outbox_inbox',
        'notification_outbox',
        ['user_id', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_notification_outbox_inbox', table_name='notification_outbox')
    op.drop_column('notification_outbox', 'read_at')
