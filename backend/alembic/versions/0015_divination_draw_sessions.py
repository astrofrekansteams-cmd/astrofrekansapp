"""User-pick divination: face-down draw sessions.

Revision ID: 0015_divination_draw_sessions
Revises: 0014_call_delivery_lease

A session holds one shuffle of a deck (and every face-down slot's
orientation), created when the user presses "shuffle". The user then picks
slots and the reveal resolves exactly those slots into an ordinary reading.

* `(user_id, consumer_ref)` is unique: session create is idempotent.
* `divination_draw_sessions.reading_id` and
  `divination_readings.draw_session_id` are both unique: one session yields
  at most one reading, enforced by the database even under racing reveals.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0015_divination_draw_sessions'
down_revision: Union[str, None] = '0014_call_delivery_lease'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        'divination_draw_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('consumer_ref', sa.String(length=80), nullable=False),
        sa.Column('request_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('deck_type', sa.String(length=20), nullable=False),
        sa.Column('deck_version', sa.String(length=40), nullable=False),
        sa.Column('spread_code', sa.String(length=40), nullable=False),
        sa.Column('spread_version', sa.String(length=60), nullable=False),
        sa.Column('locale', sa.String(length=8), nullable=False),
        sa.Column('question', sa.Text(), nullable=True),
        sa.Column('include_optional_items', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('hidden_state', JSONB, nullable=False),
        sa.Column('deck_size', sa.Integer(), nullable=False),
        sa.Column('rng_source', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('selected_positions', JSONB, nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reading_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['reading_id'], ['divination_readings.id'],
            ondelete='SET NULL', name='fk_divination_session_reading',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'consumer_ref', name='uq_divination_session_consumer_ref'),
        sa.UniqueConstraint('reading_id', name='uq_divination_session_reading'),
    )
    op.create_index('ix_divination_draw_sessions_user_id', 'divination_draw_sessions', ['user_id'])
    op.create_index('ix_divination_draw_sessions_expires_at', 'divination_draw_sessions', ['expires_at'])

    op.add_column('divination_readings', sa.Column('draw_session_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_divination_reading_session', 'divination_readings', 'divination_draw_sessions',
        ['draw_session_id'], ['id'], ondelete='SET NULL',
    )
    op.create_unique_constraint(
        'uq_divination_reading_session', 'divination_readings', ['draw_session_id'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_divination_reading_session', 'divination_readings', type_='unique')
    op.drop_constraint('fk_divination_reading_session', 'divination_readings', type_='foreignkey')
    op.drop_column('divination_readings', 'draw_session_id')
    op.drop_index('ix_divination_draw_sessions_expires_at', table_name='divination_draw_sessions')
    op.drop_index('ix_divination_draw_sessions_user_id', table_name='divination_draw_sessions')
    op.drop_table('divination_draw_sessions')
