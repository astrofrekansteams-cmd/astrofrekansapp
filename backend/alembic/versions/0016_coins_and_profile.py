"""AstroCoin ledger and profile customisation.

Revision ID: 0016_coins_and_profile
Revises: 0015_divination_draw_sessions

* `coin_wallets`: one balance per user (never negative).
* `coin_transactions`: the append-only coin ledger; `(user_id,
  idempotency_key)` is unique so a retried grant or spend lands once.
* `user_profiles`: avatar preset, bio, cover theme, privacy and notification
  preferences.

The subscription tier column is a string: the new `cosmic_plus` plan needs no
schema change.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0016_coins_and_profile'
down_revision: Union[str, None] = '0015_divination_draw_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        'coin_wallets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('balance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('lifetime_earned', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('lifetime_spent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_coin_wallets_user'),
        sa.CheckConstraint('balance >= 0', name='ck_coin_wallets_balance'),
    )
    op.create_index('ix_coin_wallets_user_id', 'coin_wallets', ['user_id'])

    op.create_table(
        'coin_transactions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('reason', sa.String(length=80), nullable=False),
        sa.Column('idempotency_key', sa.String(length=160), nullable=False),
        sa.Column('reference_id', sa.String(length=80), nullable=True),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'idempotency_key', name='uq_coin_transactions_idempotency'),
        sa.CheckConstraint('amount <> 0', name='ck_coin_transactions_amount'),
    )
    op.create_index('ix_coin_transactions_user_id', 'coin_transactions', ['user_id'])
    op.create_index('ix_coin_transactions_kind', 'coin_transactions', ['kind'])

    op.add_column('user_profiles', sa.Column('avatar_preset', sa.String(length=40), nullable=True))
    op.add_column('user_profiles', sa.Column('bio', sa.String(length=280), nullable=True))
    op.add_column(
        'user_profiles',
        sa.Column('cover_theme', sa.String(length=30), nullable=False, server_default='cosmic_night'),
    )
    op.add_column('user_profiles', sa.Column('privacy', JSONB, nullable=True))
    op.add_column('user_profiles', sa.Column('notification_prefs', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('user_profiles', 'notification_prefs')
    op.drop_column('user_profiles', 'privacy')
    op.drop_column('user_profiles', 'cover_theme')
    op.drop_column('user_profiles', 'bio')
    op.drop_column('user_profiles', 'avatar_preset')
    op.drop_index('ix_coin_transactions_kind', table_name='coin_transactions')
    op.drop_index('ix_coin_transactions_user_id', table_name='coin_transactions')
    op.drop_table('coin_transactions')
    op.drop_index('ix_coin_wallets_user_id', table_name='coin_wallets')
    op.drop_table('coin_wallets')
