"""Paid AI reports: bind report jobs and reports to the credit that pays.

Revision ID: 0012_paid_report_enforcement
Revises: 0011_payments_entitlements

`ai_report_jobs` gains the payment it was allowed under (`payment_basis`),
the client's idempotency reference (`consumer_ref`, unique per user), the
credit it holds (`entitlement_id`) and whether it regenerates (`refresh`).
`ai_reports.entitlement_id` records the credit a paid snapshot was delivered
against. Existing rows keep NULLs: jobs queued before this revision are
re-judged by the report policy when they run.

The new `user_entitlements.status` value `reserved` needs no schema change
(the column carries no check constraint).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0012_paid_report_enforcement'
down_revision: Union[str, None] = '0011_payments_entitlements'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ai_report_jobs', sa.Column('payment_basis', sa.String(length=20), nullable=True))
    op.add_column('ai_report_jobs', sa.Column('consumer_ref', sa.String(length=100), nullable=True))
    op.add_column('ai_report_jobs', sa.Column('entitlement_id', sa.Uuid(), nullable=True))
    op.add_column(
        'ai_report_jobs',
        sa.Column('refresh', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_foreign_key(
        'fk_ai_report_jobs_entitlement_id_user_entitlements',
        'ai_report_jobs', 'user_entitlements',
        ['entitlement_id'], ['id'], ondelete='SET NULL',
    )
    op.create_unique_constraint(
        'uq_ai_report_jobs_user_consumer_ref', 'ai_report_jobs', ['user_id', 'consumer_ref']
    )

    op.add_column('ai_reports', sa.Column('entitlement_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_ai_reports_entitlement_id_user_entitlements',
        'ai_reports', 'user_entitlements',
        ['entitlement_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index(op.f('ix_ai_reports_entitlement_id'), 'ai_reports', ['entitlement_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_reports_entitlement_id'), table_name='ai_reports')
    op.drop_constraint('fk_ai_reports_entitlement_id_user_entitlements', 'ai_reports', type_='foreignkey')
    op.drop_column('ai_reports', 'entitlement_id')

    op.drop_constraint('uq_ai_report_jobs_user_consumer_ref', 'ai_report_jobs', type_='unique')
    op.drop_constraint(
        'fk_ai_report_jobs_entitlement_id_user_entitlements', 'ai_report_jobs', type_='foreignkey'
    )
    op.drop_column('ai_report_jobs', 'refresh')
    op.drop_column('ai_report_jobs', 'entitlement_id')
    op.drop_column('ai_report_jobs', 'consumer_ref')
    op.drop_column('ai_report_jobs', 'payment_basis')
