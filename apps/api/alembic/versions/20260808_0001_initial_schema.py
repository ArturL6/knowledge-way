"""Create the pre-Alembic Knowledge Way schema.

Revision ID: 20260808_0001
Revises:
Create Date: 2026-08-08

This baseline reproduces the schema formerly created by SQLAlchemy at API startup.
It is intentionally additive for a new database; existing deployments must stamp
this revision after verifying their schema before applying later revisions.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The container image ships pgvector. Keeping extension setup in a migration
    # makes a fresh database reproducible and permits later Vector columns.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table("repositories", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("clone_url", sa.Text(), nullable=False), sa.Column("local_path", sa.Text()), sa.Column("provider", sa.String(30), nullable=False), sa.Column("default_branch", sa.String(255)), sa.Column("indexed_branch", sa.String(255)), sa.Column("indexed_commit_sha", sa.String(64)), sa.Column("latest_detected_commit_sha", sa.String(64)), sa.Column("indexing_status", sa.String(20), nullable=False), sa.Column("indexing_progress", sa.JSON(), nullable=False), sa.Column("error_message", sa.Text()), sa.Column("last_indexed_at", sa.DateTime()), sa.Column("last_sync_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_repositories_name", "repositories", ["name"])
    op.create_index("ix_repositories_indexing_status", "repositories", ["indexing_status"])

    op.create_table("files", sa.Column("id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False), sa.Column("path", sa.Text(), nullable=False), sa.Column("language", sa.String(50)), sa.Column("content", sa.Text(), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False), sa.Column("indexed_commit_sha", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_files_repository_id", "files", ["repository_id"])
    op.create_index("ix_files_language", "files", ["language"])
    op.create_index("ix_files_content_hash", "files", ["content_hash"])
    op.create_index("ix_files_repo_path", "files", ["repository_id", "path"], unique=True)

    op.create_table("symbols", sa.Column("id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False), sa.Column("file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("qualified_name", sa.String(512), nullable=False), sa.Column("symbol_type", sa.String(40), nullable=False), sa.Column("language", sa.String(50)), sa.Column("start_line", sa.Integer(), nullable=False), sa.Column("end_line", sa.Integer(), nullable=False), sa.Column("start_byte", sa.Integer(), nullable=False), sa.Column("end_byte", sa.Integer(), nullable=False), sa.Column("parent_symbol_id", sa.String(36), sa.ForeignKey("symbols.id")), sa.Column("source_text", sa.Text(), nullable=False), sa.Column("signature", sa.Text()))
    for column in ("repository_id", "file_id", "name", "qualified_name"):
        op.create_index(f"ix_symbols_{column}", "symbols", [column])
    op.create_index("ix_symbols_repo_name", "symbols", ["repository_id", "name"])

    op.create_table("code_chunks", sa.Column("id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False), sa.Column("file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False), sa.Column("symbol_id", sa.String(36), sa.ForeignKey("symbols.id", ondelete="SET NULL")), sa.Column("language", sa.String(50)), sa.Column("chunk_type", sa.String(30), nullable=False), sa.Column("symbol_name", sa.String(255)), sa.Column("qualified_symbol_name", sa.String(512)), sa.Column("start_line", sa.Integer(), nullable=False), sa.Column("end_line", sa.Integer(), nullable=False), sa.Column("source_text", sa.Text(), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("indexed_commit_sha", sa.String(64), nullable=False))
    for column in ("repository_id", "file_id", "content_hash"):
        op.create_index(f"ix_code_chunks_{column}", "code_chunks", [column])
    op.create_index("ix_chunks_repo_file", "code_chunks", ["repository_id", "file_id"])

    op.create_table("symbol_edges", sa.Column("id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False), sa.Column("source_symbol_id", sa.String(36), sa.ForeignKey("symbols.id")), sa.Column("target_symbol_id", sa.String(36), sa.ForeignKey("symbols.id")), sa.Column("target_name", sa.String(512), nullable=False), sa.Column("relationship_type", sa.String(30), nullable=False), sa.Column("source_file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False), sa.Column("line_number", sa.Integer(), nullable=False), sa.Column("confidence", sa.Integer(), nullable=False))
    op.create_index("ix_symbol_edges_repository_id", "symbol_edges", ["repository_id"])
    op.create_index("ix_symbol_edges_target_name", "symbol_edges", ["target_name"])

    op.create_table("indexing_jobs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False), sa.Column("kind", sa.String(30), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("progress", sa.JSON(), nullable=False), sa.Column("error_message", sa.Text()), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("started_at", sa.DateTime()), sa.Column("finished_at", sa.DateTime()))
    op.create_index("ix_indexing_jobs_repository_id", "indexing_jobs", ["repository_id"])

    op.create_table("conversations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id")), sa.Column("title", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_table("messages", sa.Column("id", sa.String(36), primary_key=True), sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False), sa.Column("role", sa.String(20), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("citations", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    for table in ("messages", "conversations", "indexing_jobs", "symbol_edges", "code_chunks", "symbols", "files", "repositories"):
        op.drop_table(table)
    # Do not drop `vector`: extensions can be shared by application schemas.
