from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import ingestion
from app.db import Base
from app.models import File, Repository, Symbol, SymbolEdge


def _index_with_sqlite(monkeypatch, tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(ingestion, "SessionLocal", sessions)
    monkeypatch.setattr(ingestion.settings, "repository_storage_path", str(tmp_path))
    monkeypatch.setattr(
        ingestion,
        "run",
        lambda *args, **kwargs: "test-sha" if args[1:3] == ("rev-parse", "HEAD") else "main",
    )
    return sessions


def test_full_index_builds_parser_graph_with_safe_resolution_and_source_provenance(monkeypatch, tmp_path):
    sessions = _index_with_sqlite(monkeypatch, tmp_path)
    repo = Repository(name="example", clone_url="unused")
    other_repo = Repository(name="other", clone_url="unused")
    with sessions() as db:
        db.add_all([repo, other_repo])
        db.commit()
        # This same-named declaration must not be considered by resolution.
        foreign_file = File(repository_id=other_repo.id, path="other.py", language="python", content="", content_hash="x", size_bytes=0, indexed_commit_sha="old")
        db.add(foreign_file); db.flush()
        db.add(Symbol(repository_id=other_repo.id, file_id=foreign_file.id, name="shared", qualified_name="shared", symbol_type="function", language="python", start_line=1, end_line=1, start_byte=0, end_byte=0, source_text="", signature="def shared()"))
        db.commit()

    root = Path(tmp_path) / repo.id
    root.mkdir()
    (root / "source.py").write_text("from internal import shared\n\ndef caller():\n    shared()\n    missing()\n    duplicate()\n")
    (root / "target.py").write_text("def shared():\n    pass\n\ndef duplicate():\n    pass\n")
    (root / "second.py").write_text("def duplicate():\n    pass\n")

    ingestion.index_repository(repo.id, full=True)

    with sessions() as db:
        symbols = db.scalars(select(Symbol).where(Symbol.repository_id == repo.id)).all()
        assert {(s.qualified_name, s.symbol_type) for s in symbols} >= {
            ("caller", "function"), ("shared", "function"), ("duplicate", "function")
        }
        edges = db.scalars(select(SymbolEdge).where(SymbolEdge.repository_id == repo.id)).all()
        by_target = {edge.target_name: edge for edge in edges}
        assert set(by_target) == {"shared", "missing", "duplicate"}
        assert by_target["shared"].relationship_type == "import"
        assert by_target["shared"].target_symbol_id is not None
        assert by_target["shared"].confidence == ingestion.RESOLVED_CONFIDENCE
        assert by_target["missing"].target_symbol_id is None
        assert by_target["missing"].confidence == ingestion.UNRESOLVED_CONFIDENCE
        # Two same-repository declarations make this call ambiguous, not arbitrarily resolved.
        assert by_target["duplicate"].target_symbol_id is None
        call_edges = [edge for edge in edges if edge.relationship_type == "call"]
        assert all(edge.source_symbol_id for edge in call_edges)
        assert all(edge.source_file_id for edge in call_edges)
        assert {edge.line_number for edge in call_edges} == {4, 5, 6}


def test_full_reindex_clears_old_edges_before_rebuilding(monkeypatch, tmp_path):
    sessions = _index_with_sqlite(monkeypatch, tmp_path)
    repo = Repository(name="example", clone_url="unused")
    with sessions() as db:
        db.add(repo); db.commit()
        file = File(repository_id=repo.id, path="old.py", language="python", content="", content_hash="old", size_bytes=0, indexed_commit_sha="old")
        db.add(file); db.flush()
        symbol = Symbol(repository_id=repo.id, file_id=file.id, name="old", qualified_name="old", symbol_type="function", language="python", start_line=1, end_line=1, start_byte=0, end_byte=0, source_text="", signature="def old()")
        db.add(symbol); db.flush()
        db.add(SymbolEdge(repository_id=repo.id, source_symbol_id=symbol.id, target_symbol_id=None, target_name="stale", relationship_type="call", source_file_id=file.id, line_number=1, confidence=20))
        db.commit()

    root = Path(tmp_path) / repo.id
    root.mkdir()
    (root / "fresh.py").write_text("def fresh():\n    unknown()\n")
    ingestion.index_repository(repo.id, full=True)
    ingestion.index_repository(repo.id, full=True)

    with sessions() as db:
        edges = db.scalars(select(SymbolEdge).where(SymbolEdge.repository_id == repo.id)).all()
        assert [(edge.target_name, edge.relationship_type) for edge in edges] == [("unknown", "call")]
        assert edges[0].target_symbol_id is None
