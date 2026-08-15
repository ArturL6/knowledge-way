"""Add a term-document-frequency table for rare-term lexical query digestion (ADR-008).

Revision ID: 20260815_0012
Revises: 20260815_0011

The table itself is a plain (term, document_frequency) pair -- dialect-portable, unlike
fts_tokens -- so it's created on every dialect via op.create_table. Only Postgres populates
and reads it: the backfill below uses ts_stat(), a Postgres-only function, and
app/search.py's digestion only runs on the Postgres branch. app/ingestion.py refreshes this
table after every successful index (see search.refresh_term_document_frequency); this
migration's INSERT is only the one-time backfill for chunks indexed before this migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260815_0012"
down_revision = "20260815_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "term_document_frequency",
        sa.Column("term", sa.String(255), primary_key=True),
        sa.Column("document_frequency", sa.Integer(), nullable=False),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            INSERT INTO term_document_frequency (term, document_frequency)
            SELECT word, ndoc FROM ts_stat('SELECT fts_tokens FROM code_chunks WHERE fts_tokens IS NOT NULL')
        """)


def downgrade() -> None:
    op.drop_table("term_document_frequency")
