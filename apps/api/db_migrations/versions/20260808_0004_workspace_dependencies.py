"""Add declared, workspace-scoped repository dependencies.

Revision ID: 20260808_0004
Revises: 20260808_0003
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0004"
down_revision = "20260808_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_dependencies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("package_name", sa.String(512), nullable=True),
        sa.Column("import_path", sa.String(1024), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "source_repository_id", "target_repository_id", "package_name", "import_path", name="uq_workspace_dependencies_declaration"),
    )
    op.create_index("ix_workspace_dependencies_workspace_id", "workspace_dependencies", ["workspace_id"])
    op.create_index("ix_workspace_dependencies_source_repository_id", "workspace_dependencies", ["source_repository_id"])
    op.create_index("ix_workspace_dependencies_target_repository_id", "workspace_dependencies", ["target_repository_id"])


def downgrade() -> None:
    op.drop_table("workspace_dependencies")