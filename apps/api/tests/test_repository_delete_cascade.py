from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.main import app
from app.models import Repository, File, Symbol, SymbolEdge


def test_delete_repository_cascades_to_files_symbols_and_edges():
    """Repository.delete only removes workspace membership/dependency rows
    itself (app/main.py delete_repository); files/symbols/edges are expected
    to disappear via the `ondelete='CASCADE'` FKs declared on those models.
    SQLite ignores those declarations unless FK enforcement is turned on
    (see tests/conftest.py) -- this test is what actually exercises them."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    # No relationship() is declared between these models (see app/models.py), so the
    # ORM unit-of-work can't infer insert order from the raw FK columns alone -- commit
    # each parent before adding its child, in dependency order, rather than one big flush.
    db.add(Repository(id="repo-1", name="one", clone_url="https://example.test/one.git"))
    db.commit()
    db.add(File(
        id="file-1", repository_id="repo-1", path="a.py", language="python",
        content="x = 1", content_hash="h1", size_bytes=5, indexed_commit_sha="a" * 40,
    ))
    db.commit()
    db.add(Symbol(
        id="sym-1", repository_id="repo-1", file_id="file-1", name="x",
        qualified_name="a.x", symbol_type="variable", start_line=1, end_line=1,
        start_byte=0, end_byte=1, source_text="x = 1",
    ))
    db.add(SymbolEdge(
        id="edge-1", repository_id="repo-1", source_symbol_id="sym-1",
        target_name="y", relationship_type="references", source_file_id="file-1",
        line_number=1,
    ))
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        api = TestClient(app)
        assert api.delete("/api/repositories/repo-1").status_code == 204
        # The operative cleanup path is File.repository_id's cascade: removing it leaves the
        # file row, which under FK enforcement blocks the repository DELETE (FK violation ->
        # 500, not 204) -- so this assertion fails red exactly as the gate requires. The
        # symbol/edge repository_id cascades are not independently guarded here because they
        # are redundant with file_id -> files ON DELETE CASCADE (a symbol's file is always in
        # the same repo) and cannot be isolated without constructing invalid cross-repo data.
        assert db.scalars(select(File).where(File.repository_id == "repo-1")).all() == []
        assert db.scalars(select(Symbol).where(Symbol.repository_id == "repo-1")).all() == []
        assert db.scalars(select(SymbolEdge).where(SymbolEdge.repository_id == "repo-1")).all() == []
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
