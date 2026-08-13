from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


API_DIR = Path(__file__).resolve().parents[1]


def test_migrations_have_expected_head():
    script = ScriptDirectory.from_config(Config(str(API_DIR / "alembic.ini")))
    assert script.get_heads() == ["20260813_0010"]


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


def test_normal_startup_has_no_create_all_ddl():
    source = (API_DIR / "app" / "main.py").read_text()
    assert "create_all" not in source
    assert "verify_migration_ready" in source
