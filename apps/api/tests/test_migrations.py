from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


API_DIR = Path(__file__).resolve().parents[1]


def test_migrations_have_expected_head():
    script = ScriptDirectory.from_config(Config(str(API_DIR / "alembic.ini")))
    assert script.get_heads() == ["20260812_0013"]


def test_initial_migration_creates_pgvector_extension_and_all_model_tables():
    revision = API_DIR / "db_migrations" / "versions" / "20260808_0001_initial_schema.py"
    source = revision.read_text()
    assert "CREATE EXTENSION IF NOT EXISTS vector" in source
    for table in (
        "repositories", "files", "symbols", "code_chunks", "symbol_edges",
        "indexing_jobs", "conversations", "messages",
    ):
        assert f'op.create_table("{table}"' in source


def test_normal_startup_has_no_create_all_ddl():
    source = (API_DIR / "app" / "main.py").read_text()
    assert "create_all" not in source
    assert "verify_migration_ready" in source


def test_index_symbol_fks_migration_indexes_and_drops_all_four_columns():
    revision = API_DIR / "db_migrations" / "versions" / "20260810_0010_index_symbol_fks.py"
    source = revision.read_text()
    for index_name in (
        "ix_symbols_parent_symbol_id",
        "ix_code_chunks_symbol_id",
        "ix_symbol_edges_source_symbol_id",
        "ix_symbol_edges_target_symbol_id",
    ):
        assert f'op.create_index("{index_name}"' in source
        assert f'op.drop_index("{index_name}"' in source