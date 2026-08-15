from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app import ingestion
from app.db import Base
from app.models import CodeCard, CodeChunk, Evidence, File, IndexingJob, Repository, Symbol, SymbolEdge


class _FakeEmbeddingProvider:
    model = "test:embedding"

    async def embed_texts(self, texts):
        assert len(texts) == 1
        assert texts[0].endswith("Source code:\ndef useful(): pass")
        return [FAKE_VECTOR]


# The embedding column is a fixed vector(768) (migration 20260816_0013), matching the one
# supported production model (Vertex text-embedding-005 @768, ADR-004/005).
FAKE_VECTOR = [0.25, 0.75] + [0.0] * 766


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
    # These tests exercise parsing/graph/card behavior, not embeddings. A developer's real
    # repo-root .env (config.py searches upward for it) can set EMBEDDING_PROVIDER=openrouter
    # with a real API key; without this, every such test would silently make a live, billed
    # embedding request. Tests that specifically cover embedding behavior override this below.
    monkeypatch.setattr(ingestion, "embedding_provider", lambda: None)
    return sessions


def test_symbol_edge_requires_evidence_at_the_database_boundary(monkeypatch, tmp_path):
    sessions = _index_with_sqlite(monkeypatch, tmp_path)
    repo = Repository(name="example", clone_url="unused")
    with sessions() as db:
        db.add(repo); db.flush()
        file = File(repository_id=repo.id, path="source.py", language="python", content="call()\n", content_hash="x" * 64, size_bytes=7, indexed_commit_sha="test-sha")
        db.add(file); db.flush()
        db.add(SymbolEdge(repository_id=repo.id, source_symbol_id=None, target_symbol_id=None, target_name="call", relationship_type="call", source_file_id=file.id, line_number=1, confidence=20))
        with pytest.raises(IntegrityError):
            db.flush()


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
        assert all(edge.evidence_id for edge in edges)
        evidence = db.scalars(select(Evidence).where(Evidence.repository_id == repo.id)).all()
        assert {(row.path, row.start_line, row.end_line, row.extractor, row.extractor_version) for row in evidence} >= {
            ("source.py", 1, 1, "tree-sitter", ingestion.PARSER_VERSION),
            ("source.py", 4, 4, "tree-sitter", ingestion.PARSER_VERSION),
        }
        assert {edge.line_number for edge in call_edges} == {4, 5, 6}


def test_full_reindex_clears_old_edges_before_rebuilding(monkeypatch, tmp_path):
    sessions = _index_with_sqlite(monkeypatch, tmp_path)
    repo = Repository(name="example", clone_url="unused", error_message="previous indexing failure")
    with sessions() as db:
        db.add(repo); db.commit()
        file = File(repository_id=repo.id, path="old.py", language="python", content="", content_hash="old", size_bytes=0, indexed_commit_sha="old")
        db.add(file); db.flush()
        symbol = Symbol(repository_id=repo.id, file_id=file.id, name="old", qualified_name="old", symbol_type="function", language="python", start_line=1, end_line=1, start_byte=0, end_byte=0, source_text="", signature="def old()")
        db.add(symbol); db.flush()
        evidence = Evidence(repository_id=repo.id, indexed_commit_sha="old", path="old.py", start_line=1, end_line=1, extractor="test", extractor_version="v1", content_hash="x" * 64)
        db.add(evidence); db.flush()
        db.add(SymbolEdge(repository_id=repo.id, source_symbol_id=symbol.id, target_symbol_id=None, target_name="stale", relationship_type="call", source_file_id=file.id, line_number=1, evidence_id=evidence.id, confidence=20))
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
        assert db.get(Repository, repo.id).error_message is None


def test_full_reindex_preserves_unchanged_code_cards(monkeypatch, tmp_path):
    sessions = _index_with_sqlite(monkeypatch, tmp_path)
    repo = Repository(name="example", clone_url="unused")
    with sessions() as db:
        db.add(repo); db.commit()
    root = Path(tmp_path) / repo.id
    root.mkdir()
    (root / "source.py").write_text("def stable():\n    return 1\n")

    ingestion.index_repository(repo.id, full=False)
    with sessions() as db:
        symbol = db.scalars(select(Symbol).where(Symbol.repository_id == repo.id)).one()
        old_symbol_id = symbol.id
        db.add(CodeCard(repository_id=repo.id, symbol_id=symbol.id, source_hash=ingestion.hashlib.sha256(symbol.source_text.encode()).hexdigest(), indexed_commit_sha="old", model="test", prompt_version="v1", status="ready", summary="retained", details={"keywords": ["stable"]}, input_tokens=10, output_tokens=5))
        db.commit()

    ingestion.index_repository(repo.id, full=False)

    with sessions() as db:
        symbol = db.scalars(select(Symbol).where(Symbol.repository_id == repo.id)).one()
        cards = db.scalars(select(CodeCard).where(CodeCard.repository_id == repo.id)).all()
        # A byte-identical sync must retain the existing durable rows rather than
        # delete/recreate them (which would invalidate cards, edges and vectors).
        assert symbol.id == old_symbol_id
        assert len(cards) == 1
        assert cards[0].symbol_id == symbol.id
        assert cards[0].summary == "retained"
        assert cards[0].input_tokens == 10


def test_sync_preserves_or_rebuilds_embedding_coverage(monkeypatch, tmp_path):
    sessions = _index_with_sqlite(monkeypatch, tmp_path)

    class Provider:
        model = "test:embedding"
        calls = 0

        async def embed_texts(self, texts):
            self.calls += 1
            return [FAKE_VECTOR for _ in texts]

    provider = Provider()
    monkeypatch.setattr(ingestion, "embedding_provider", lambda: provider)
    repo = Repository(name="example", clone_url="unused")
    with sessions() as db:
        db.add(repo); db.commit()
    root = Path(tmp_path) / repo.id
    root.mkdir()
    (root / "source.py").write_text("def stable():\n    return 1\n")

    ingestion.index_repository(repo.id, full=True)
    first_provider_calls = provider.calls
    with sessions() as db:
        assert all(chunk.embedding is not None for chunk in db.scalars(select(CodeChunk).where(CodeChunk.repository_id == repo.id)).all())

    ingestion.index_repository(repo.id, full=False)

    with sessions() as db:
        chunks = db.scalars(select(CodeChunk).where(CodeChunk.repository_id == repo.id)).all()
        assert chunks
        assert all(chunk.embedding is not None for chunk in chunks)
        assert all(chunk.embedding_model == provider.model for chunk in chunks)
    # An unchanged sync reuses documents by their exact embedding input hash rather than billing
    # another provider call, while still leaving a complete vector index.
    assert provider.calls == first_provider_calls


def test_embedding_prunes_empty_structural_chunks(monkeypatch, tmp_path):
    sessions = _index_with_sqlite(monkeypatch, tmp_path)
    monkeypatch.setattr(ingestion, "embedding_provider", lambda: _FakeEmbeddingProvider())
    repo = Repository(name="example", clone_url="unused")
    with sessions() as db:
        db.add(repo); db.flush()
        file = File(repository_id=repo.id, path="source.py", language="python", content="", content_hash="a" * 64, size_bytes=0, indexed_commit_sha="test")
        db.add(file); db.flush()
        blank = CodeChunk(repository_id=repo.id, file_id=file.id, language="python", chunk_type="module", start_line=1, end_line=1, source_text="  \n", content_hash="b" * 64, indexed_commit_sha="test")
        useful = CodeChunk(repository_id=repo.id, file_id=file.id, language="python", chunk_type="function", start_line=2, end_line=2, source_text="def useful(): pass", content_hash="c" * 64, indexed_commit_sha="test")
        db.add_all([blank, useful]); db.flush()
        ingestion._embed_full_index_chunks(db, repo.id, {})
        db.flush()
        assert db.get(CodeChunk, blank.id) is None
        embedded = db.get(CodeChunk, useful.id)
        assert embedded.embedding == FAKE_VECTOR
        assert embedded.embedding_model == "test:embedding"


def test_full_index_checks_out_requested_immutable_revision(monkeypatch, tmp_path):
    sessions = _index_with_sqlite(monkeypatch, tmp_path)
    requested = "a" * 40
    repo = Repository(name="pinned", clone_url="https://example.test/pinned.git", requested_revision=requested)
    with sessions() as db:
        db.add(repo)
        db.commit()

    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args)
        if args[1:3] == ("rev-parse", "HEAD"):
            return requested
        if args[1:3] == ("branch", "--show-current"):
            return ""
        return ""

    monkeypatch.setattr(ingestion, "run", fake_run)
    root = Path(tmp_path) / repo.id
    root.mkdir()
    (root / "fixture.py").write_text("def stable():\n    pass\n")

    ingestion.index_repository(repo.id, full=True)

    assert ("git", "fetch", "--depth", "1", "origin", requested) in calls
    assert ("git", "checkout", "--detach", requested) in calls
    with sessions() as db:
        indexed = db.get(Repository, repo.id)
        assert indexed.indexed_commit_sha == requested
        assert indexed.indexed_branch is None


def _index_snapshot(db, repo_id):
    """Row identity, not just counts: re-created rows get fresh UUIDs, so equality here proves
    the previous index was preserved rather than rebuilt into something that merely looks alike."""
    return {
        "files": {f.id: f.content_hash for f in db.scalars(select(File).where(File.repository_id == repo_id)).all()},
        "symbols": {s.id: s.qualified_name for s in db.scalars(select(Symbol).where(Symbol.repository_id == repo_id)).all()},
        "chunks": {c.id: c.content_hash for c in db.scalars(select(CodeChunk).where(CodeChunk.repository_id == repo_id)).all()},
        "edges": {(e.source_symbol_id, e.target_name) for e in db.scalars(select(SymbolEdge).where(SymbolEdge.repository_id == repo_id)).all()},
    }


def test_failed_reindex_leaves_the_previous_index_intact(monkeypatch, tmp_path):
    sessions = _index_with_sqlite(monkeypatch, tmp_path)
    repo = Repository(name="example", clone_url="unused")
    with sessions() as db:
        db.add(repo); db.commit()

    root = Path(tmp_path) / repo.id
    root.mkdir()
    (root / "source.py").write_text("def kept():\n    helper()\n\ndef helper():\n    pass\n")
    ingestion.index_repository(repo.id, full=True)

    with sessions() as db:
        before = _index_snapshot(db, repo.id)
    assert before["files"] and before["symbols"] and before["chunks"] and before["edges"]

    # Raise after the destructive delete-and-rebuild has already run, but before the run is
    # published. This is the ordinary failure path: a provider error, a parse error, a lost
    # connection. SIGKILL is the one mode that skips the handler, which is why manual kill
    # testing wrongly suggested the data survives.
    monkeypatch.setattr(ingestion, "refresh_structural_cards", _raise_provider_failure)
    (root / "source.py").write_text("def replaced():\n    pass\n")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        ingestion.index_repository(repo.id, full=True)

    with sessions() as db:
        assert _index_snapshot(db, repo.id) == before
        failed_repo = db.get(Repository, repo.id)
        assert failed_repo.indexing_status == "failed"
        assert "provider unavailable" in failed_repo.error_message
        jobs = db.scalars(select(IndexingJob).where(IndexingJob.repository_id == repo.id)).all()
        assert jobs[-1].status == "failed"
        assert "provider unavailable" in jobs[-1].error_message
        assert jobs[-1].finished_at is not None


def _raise_provider_failure(*args, **kwargs):
    raise RuntimeError("provider unavailable")
