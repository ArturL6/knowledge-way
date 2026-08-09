"""add versioned code cards

Revision ID: 20260809_0005
Revises: 20260808_0004
"""
from alembic import op
import sqlalchemy as sa

revision = "20260809_0005"
down_revision = "20260808_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("code_cards",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("repository_id", sa.String(length=36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol_id", sa.String(length=36), sa.ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("indexed_commit_sha", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("symbol_id", name="uq_code_cards_symbol_id"),
    )
    op.create_index("ix_code_cards_repo_status", "code_cards", ["repository_id", "status"])
    op.create_index("ix_code_cards_source_hash", "code_cards", ["source_hash"])


def downgrade():
    op.drop_index("ix_code_cards_source_hash", table_name="code_cards")
    op.drop_index("ix_code_cards_repo_status", table_name="code_cards")
    op.drop_table("code_cards")
