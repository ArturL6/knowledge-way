"""Add a code-aware full-text search column and pg_trgm exact-match index to code_chunks.

Revision ID: 20260815_0011
Revises: 20260813_0010

FTS objects are Postgres-only (mirrors the CREATE EXTENSION vector precedent in
20260808_0001): SQLite has no tsvector/GIN/pg_trgm, and the portable test suite
builds its schema via Base.metadata.create_all rather than running migrations, so
this migration is a no-op there.

`fts_tokens` is a STORED generated column so indexing needs no application code
change. The generating expression is IMMUTABLE (left/regexp_replace/to_tsvector with
a constant 'simple' config and a constant length), which Postgres requires for
generated columns. The identifier-splitting regex (camelCase boundary + `._/`
separators) must exactly mirror the Python-side splitting applied to query text in
app/search.py, or index and query tokens will disagree.

source_text is truncated to 100_000 chars before tokenizing: tsvector has a hard
1_048_575 byte limit, and at least one real chunk in this repo's own indexed data
exceeds it untruncated (a large generated/vendored file indexed as a single chunk).
100_000 chars is comfortably under that limit even at 4 bytes/char and is far more
text than lexical relevance needs.
"""
from alembic import op

revision = "20260815_0011"
down_revision = "20260813_0010"
branch_labels = None
depends_on = None

FTS_EXPR = (
    "to_tsvector('simple', regexp_replace(regexp_replace(left(coalesce(source_text, ''), 100000), "
    "'([a-z0-9])([A-Z])', '\\1 \\2', 'g'), '[._/]+', ' ', 'g'))"
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(f"ALTER TABLE code_chunks ADD COLUMN fts_tokens tsvector GENERATED ALWAYS AS ({FTS_EXPR}) STORED")
    op.execute("CREATE INDEX ix_chunks_fts_tokens ON code_chunks USING GIN (fts_tokens)")
    op.execute("CREATE INDEX ix_chunks_source_text_trgm ON code_chunks USING GIN (source_text gin_trgm_ops)")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_chunks_source_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_chunks_fts_tokens")
    op.execute("ALTER TABLE code_chunks DROP COLUMN IF EXISTS fts_tokens")
    # Do not drop pg_trgm: it may be shared by other application indexes/extensions.
