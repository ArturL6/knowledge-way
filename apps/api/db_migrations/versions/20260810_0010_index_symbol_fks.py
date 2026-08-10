"""Index the four unindexed FKs that reference symbols.id.

symbols.parent_symbol_id, code_chunks.symbol_id, symbol_edges.source_symbol_id and
symbol_edges.target_symbol_id all declare a ForeignKey('symbols.id') but were never
indexed. Postgres has no built-in index on the referencing side of a FK, so every
symbol delete makes Postgres verify no row in these four columns still points at the
deleted id — and without an index that verification is a sequential scan. On
symbol_edges alone (hundreds of thousands of rows on a real repo) that's ~66ms per
symbol deleted versus ~0.095ms with an index, so a repository re-index that deletes
and recreates symbols turns into a seq-scan storm. code_cards.symbol_id is already
covered by its own UNIQUE constraint and does not need a second index.

Revision ID: 20260810_0010
Revises: 20260810_0009
"""
from alembic import op

revision = "20260810_0010"
down_revision = "20260810_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET lock_timeout = '3s'")
    op.create_index("ix_symbols_parent_symbol_id", "symbols", ["parent_symbol_id"])
    op.create_index("ix_code_chunks_symbol_id", "code_chunks", ["symbol_id"])
    op.create_index("ix_symbol_edges_source_symbol_id", "symbol_edges", ["source_symbol_id"])
    op.create_index("ix_symbol_edges_target_symbol_id", "symbol_edges", ["target_symbol_id"])


def downgrade() -> None:
    op.drop_index("ix_symbol_edges_target_symbol_id", table_name="symbol_edges")
    op.drop_index("ix_symbol_edges_source_symbol_id", table_name="symbol_edges")
    op.drop_index("ix_code_chunks_symbol_id", table_name="code_chunks")
    op.drop_index("ix_symbols_parent_symbol_id", table_name="symbols")
