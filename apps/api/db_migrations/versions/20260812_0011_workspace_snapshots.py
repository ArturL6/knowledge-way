"""add immutable workspace snapshot manifests

Revision ID: 20260812_0011
Revises: 20260810_0010
"""
from alembic import op
import sqlalchemy as sa

revision = '20260812_0011'
down_revision = '20260810_0010'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('workspace_snapshots',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('manifest_hash', sa.String(length=64), nullable=False),
        sa.Column('schema_version', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('workspace_id', 'manifest_hash', name='uq_workspace_snapshots_manifest'))
    op.create_index('ix_workspace_snapshots_workspace_id', 'workspace_snapshots', ['workspace_id'])
    op.create_index('ix_workspace_snapshots_manifest_hash', 'workspace_snapshots', ['manifest_hash'])
    op.create_table('workspace_snapshot_repositories',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('snapshot_id', sa.String(length=36), sa.ForeignKey('workspace_snapshots.id', ondelete='CASCADE'), nullable=False),
        sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('indexed_commit_sha', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('snapshot_id', 'repository_id', name='uq_workspace_snapshot_repositories_member'))
    op.create_index('ix_workspace_snapshot_repositories_snapshot_id', 'workspace_snapshot_repositories', ['snapshot_id'])
    op.create_index('ix_workspace_snapshot_repositories_repository_id', 'workspace_snapshot_repositories', ['repository_id'])


def downgrade():
    op.drop_table('workspace_snapshot_repositories')
    op.drop_table('workspace_snapshots')
