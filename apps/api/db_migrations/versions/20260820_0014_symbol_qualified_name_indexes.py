"""Index the packet-1.2 qualified-name symbol search paths.

Exact and prefix lookup use the functional B-tree index. The remaining substring fallback
uses pg_trgm, which is already required by the chunk exact-match migration but is declared here
as well so this migration is independently safe on a restored database.
"""

from alembic import op


revision = "20260820_0014"
down_revision = "20260816_0013"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_symbols_qualified_name_lower_prefix "
        "ON symbols (lower(qualified_name) varchar_pattern_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_symbols_qualified_name_trgm "
        "ON symbols USING GIN (qualified_name gin_trgm_ops)"
    )


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_symbols_qualified_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_symbols_qualified_name_lower_prefix")
