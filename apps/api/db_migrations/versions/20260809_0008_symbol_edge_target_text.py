"""Allow complete parser reference targets in graph edges.

Revision ID: 20260809_0008
Revises: 20260809_0007
"""
from alembic import op
import sqlalchemy as sa

revision = "20260809_0008"
down_revision = "20260809_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("symbol_edges", "target_name", type_=sa.Text(), existing_type=sa.String(512))


def downgrade() -> None:
    op.alter_column("symbol_edges", "target_name", type_=sa.String(512), existing_type=sa.Text())
