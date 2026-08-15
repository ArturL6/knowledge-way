from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


API_DIR = Path(__file__).resolve().parents[1]


def test_migrations_have_expected_head():
    script = ScriptDirectory.from_config(Config(str(API_DIR / "alembic.ini")))
    assert script.get_heads() == ["20260815_0012"]


def test_initial_migration_creates_pgvector_extension_and_all_model_tables():
    revision = API_DIR / "db_migrations" / "versions" / "20260808_0001_initial_schema.py"
    source = revision.read_text()
    assert "CREATE EXTENSION IF NOT EXISTS vector" in source
    for table in (
        "repositories", "files", "symbols", "code_chunks", "symbol_edges",
        "indexing_jobs", "conversations", "messages",
    ):
        assert f'op.create_table("{table}"' in source


def test_evidence_migration_backfills_edges_and_enforces_evidence_reference():
    revision = API_DIR / "db_migrations" / "versions" / "20260813_0010_evidence_table.py"
    source = revision.read_text()
    assert '"evidence"' in source
    assert "INSERT INTO evidence" in source
    assert "md5('evidence:' || e.id)" in source
    assert "random()" not in source
    assert 'op.alter_column("symbol_edges", "evidence_id", nullable=False)' in source
    assert 'op.create_foreign_key("fk_symbol_edges_evidence_id"' in source


def test_chunk_fts_migration_is_postgres_only_and_matches_search_tokenizer():
    revision = API_DIR / "db_migrations" / "versions" / "20260815_0011_chunk_fts.py"
    source = revision.read_text()
    assert 'dialect.name != "postgresql"' in source
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in source
    assert "GENERATED ALWAYS AS" in source
    assert "USING GIN (fts_tokens)" in source
    assert "gin_trgm_ops" in source


def test_term_document_frequency_migration_is_created_everywhere_backfilled_on_postgres():
    revision = API_DIR / "db_migrations" / "versions" / "20260815_0012_term_document_frequency.py"
    source = revision.read_text()
    assert 'down_revision = "20260815_0011"' in source
    assert 'op.create_table(\n        "term_document_frequency"' in source
    assert 'dialect.name == "postgresql"' in source
    assert "ts_stat(" in source


def test_normal_startup_has_no_create_all_ddl():
    source = (API_DIR / "app" / "main.py").read_text()
    assert "create_all" not in source
    assert "verify_migration_ready" in source
