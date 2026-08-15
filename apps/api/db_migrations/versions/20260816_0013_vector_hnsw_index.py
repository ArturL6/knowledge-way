"""Fix the embedding column to a concrete dimension and add an HNSW ANN index (packet 1.3).

Revision ID: 20260816_0013
Revises: 20260815_0012

pgvector cannot build an ivfflat/hnsw index over a dimension-less `vector` column
("column does not have dimensions") -- verified empirically against pgvector/pg16.
ADR-004/005 already mandate exactly one production embedding provider+model
(Vertex text-embedding-005 @768), so pinning the column to vector(768) does not
narrow anything that was actually in use; it only makes that existing constraint
enforceable by the column type instead of by convention.

Any pre-existing row whose embedding is not 768-dimensional (e.g. leftover
OpenRouter/text-embedding-3-small vectors from local experimentation, which are
1536-dim) cannot survive an ALTER COLUMN TYPE vector(768) and would abort the
migration. Null those out first -- along with their model/hash tags, so the next
index run re-embeds them under the one supported model -- rather than fail the
migration on data that was never a supported production configuration.

Postgres-only (mirrors the CREATE EXTENSION vector precedent in 20260808_0001 and
the FTS-object precedent in 20260815_0011): SQLite has no vector/HNSW support, and
the portable test suite builds its schema via Base.metadata.create_all rather than
running migrations, so this migration is a no-op there.
"""
from alembic import op

revision = "20260816_0013"
down_revision = "20260815_0012"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = 768


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f"""
        UPDATE code_chunks SET embedding = NULL, embedding_model = NULL, embedding_input_hash = NULL
        WHERE embedding IS NOT NULL AND vector_dims(embedding) <> {EMBEDDING_DIMENSIONS}
    """)
    op.execute(f"ALTER TABLE code_chunks ALTER COLUMN embedding TYPE vector({EMBEDDING_DIMENSIONS})")
    # vector_cosine_ops matches the `<=>` cosine-distance operator used by the ANN query in
    # app/search.py; the index is otherwise unused if the query's distance operator disagrees.
    op.execute("CREATE INDEX ix_chunks_embedding_hnsw_cosine ON code_chunks USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw_cosine")
    op.execute("ALTER TABLE code_chunks ALTER COLUMN embedding TYPE vector")
