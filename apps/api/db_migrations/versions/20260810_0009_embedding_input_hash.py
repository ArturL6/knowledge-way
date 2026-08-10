"""Record which text an embedding was actually computed from.

The re-index reuse cache stored keys as (chunk.content_hash, embedding_model) — a hash of raw
source — but looked them up by the hash of the *header-prefixed* retrieval document. The two key
spaces never intersected, so every full re-index re-embedded every chunk at full price. Keying on
the embedded input itself makes reuse exact: a vector is reused only when the text that produced
it is byte-identical, so a chunk whose code is unchanged but whose code card or resolved calls
moved is correctly re-embedded rather than silently served a stale vector.

Revision ID: 20260810_0009
Revises: 20260809_0008
"""
from alembic import op
import sqlalchemy as sa

revision = "20260810_0009"
down_revision = "20260809_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("code_chunks", sa.Column("embedding_input_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("code_chunks", "embedding_input_hash")
