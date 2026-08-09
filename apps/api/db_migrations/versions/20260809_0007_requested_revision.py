"""Add an immutable requested revision for reproducible repository indexing.

Revision ID: 20260809_0007
Revises: 20260809_0006
"""
from alembic import op
import sqlalchemy as sa

revision = "20260809_0007"
down_revision = "20260809_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("repositories", sa.Column("requested_revision", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("repositories", "requested_revision")
