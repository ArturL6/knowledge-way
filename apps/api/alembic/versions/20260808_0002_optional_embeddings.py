"""Add optional embedding metadata to code chunks.

Revision ID: 20260808_0002
Revises: 20260808_0001
Create Date: 2026-08-08

Semantic retrieval remains disabled until an explicit embedding provider is configured.
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "20260808_0002"
down_revision = "20260808_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("code_chunks", sa.Column("embedding", Vector(), nullable=True))
    op.add_column("code_chunks", sa.Column("embedding_model", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("code_chunks", "embedding_model")
    op.drop_column("code_chunks", "embedding")
