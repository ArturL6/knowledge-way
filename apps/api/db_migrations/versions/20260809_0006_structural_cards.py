"""add deterministic structural cards

Revision ID: 20260809_0006
Revises: 20260809_0005
"""
from alembic import op
import sqlalchemy as sa
revision="20260809_0006"
down_revision="20260809_0005"
branch_labels=None
depends_on=None
def upgrade():
 op.create_table("structural_cards",sa.Column("id",sa.String(36),primary_key=True),sa.Column("repository_id",sa.String(36),sa.ForeignKey("repositories.id",ondelete="CASCADE"),nullable=False),sa.Column("kind",sa.String(20),nullable=False),sa.Column("path",sa.Text(),nullable=False),sa.Column("facts",sa.JSON(),nullable=False),sa.Column("content_fingerprint",sa.String(64),nullable=False),sa.Column("provenance_fingerprint",sa.String(64),nullable=False),sa.Column("indexed_commit_sha",sa.String(64),nullable=False),sa.Column("schema_version",sa.String(64),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("updated_at",sa.DateTime(),nullable=False),sa.UniqueConstraint("repository_id","kind","path",name="uq_structural_cards_repo_kind_path"))
 op.create_index("ix_structural_cards_repo_path","structural_cards",["repository_id","path"])
 op.create_index("ix_structural_cards_content_fingerprint","structural_cards",["content_fingerprint"])
def downgrade():
 op.drop_index("ix_structural_cards_content_fingerprint",table_name="structural_cards");op.drop_index("ix_structural_cards_repo_path",table_name="structural_cards");op.drop_table("structural_cards")
