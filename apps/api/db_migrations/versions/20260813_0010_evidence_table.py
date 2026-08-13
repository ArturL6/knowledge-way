"""Add immutable source evidence and require it for every symbol edge.

Revision ID: 20260813_0010
Revises: 20260810_0009
"""
from alembic import op
import sqlalchemy as sa

revision = "20260813_0010"
down_revision = "20260810_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("indexed_commit_sha", sa.String(64), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("extractor", sa.String(64), nullable=False),
        sa.Column("extractor_version", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_evidence_repository_id", "evidence", ["repository_id"])
    op.create_index("ix_evidence_content_hash", "evidence", ["content_hash"])
    op.create_index("ix_evidence_repo_commit_path", "evidence", ["repository_id", "indexed_commit_sha", "path"])
    op.add_column("symbol_edges", sa.Column("evidence_id", sa.String(36), nullable=True))
    op.execute("""
        INSERT INTO evidence (id, repository_id, indexed_commit_sha, path, start_line, end_line, extractor, extractor_version, content_hash)
        SELECT md5('evidence:' || e.id), e.repository_id, f.indexed_commit_sha, f.path,
               e.line_number, e.line_number, 'legacy-backfill', 'R.7', f.content_hash
        FROM symbol_edges e JOIN files f ON f.id = e.source_file_id
    """)
    op.execute("""
        UPDATE symbol_edges
        SET evidence_id = md5('evidence:' || symbol_edges.id)
        WHERE evidence_id IS NULL
    """)
    op.alter_column("symbol_edges", "evidence_id", nullable=False)
    op.create_foreign_key("fk_symbol_edges_evidence_id", "symbol_edges", "evidence", ["evidence_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_symbol_edges_evidence_id", "symbol_edges", ["evidence_id"])


def downgrade() -> None:
    op.drop_index("ix_symbol_edges_evidence_id", table_name="symbol_edges")
    op.drop_constraint("fk_symbol_edges_evidence_id", "symbol_edges", type_="foreignkey")
    op.drop_column("symbol_edges", "evidence_id")
    op.drop_table("evidence")
