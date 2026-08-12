"""add provider pilot audit ledger

Revision ID: 20260812_0013
Revises: 20260812_0012
"""
from alembic import op
import sqlalchemy as sa

revision = '20260812_0013'
down_revision = '20260812_0012'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('provider_audit_ledgers',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('provider', sa.String(64), nullable=False),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('workspace_snapshot_id', sa.String(36), sa.ForeignKey('workspace_snapshots.id', ondelete='RESTRICT')),
        sa.Column('configuration', sa.JSON(), nullable=False), sa.Column('caps', sa.JSON(), nullable=False), sa.Column('price_source', sa.JSON(), nullable=False), sa.Column('actual', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('updated_at', sa.DateTime(), nullable=False))
    op.create_index('ix_provider_audit_ledgers_status', 'provider_audit_ledgers', ['status'])
    op.create_index('ix_provider_audit_ledgers_workspace_snapshot_id', 'provider_audit_ledgers', ['workspace_snapshot_id'])
    op.create_table('provider_audit_events',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('ledger_id', sa.String(36), sa.ForeignKey('provider_audit_ledgers.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('operation', sa.String(32), nullable=False), sa.Column('model', sa.String(255), nullable=False), sa.Column('model_version', sa.String(255)), sa.Column('input_hash', sa.String(64), nullable=False),
        sa.Column('input_tokens', sa.Integer()), sa.Column('output_tokens', sa.Integer()), sa.Column('cost_usd_micros', sa.Integer()), sa.Column('status', sa.String(20), nullable=False), sa.Column('details', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_provider_audit_events_ledger_created', 'provider_audit_events', ['ledger_id', 'created_at'])
    op.create_index('ix_provider_audit_events_ledger_id', 'provider_audit_events', ['ledger_id'])


def downgrade():
    op.drop_table('provider_audit_events')
    op.drop_table('provider_audit_ledgers')
