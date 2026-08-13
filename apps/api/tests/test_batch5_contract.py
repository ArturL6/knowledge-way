"""#33/#34 (batch5/contract): the /tree detoast + /callers/callees pagination fix is covered in
test_graph_api.py; this file covers the five #34 correctness defects that don't fit the
existing fixture files."""

from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.main import app
from app.models import Evidence, File, Repository, Symbol, SymbolEdge


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _client(db):
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_tree_like_escape_does_not_fabricate_matches():
    """path='%' used to be interpolated unescaped into a LIKE, so the '%' acted as a wildcard:
    prefix becomes '%/' and File.path LIKE '%/%' matches any path containing a '/' at all (e.g.
    'examples/a.py'), and the (unescaped) prefix-stripping then fabricated a bogus 'amples' entry
    -- exactly the '%/amples matched from examples' report. With the '%' escaped, no real
    directory is literally named '%', so browsing path='%' must come back empty."""
    db = _session()
    db.add(Repository(id="repo", name="demo", clone_url="https://example.test/demo.git"))
    db.commit()
    db.add(File(id="f", repository_id="repo", path="examples/a.py", language="python", content="x",
                content_hash="h", size_bytes=1, indexed_commit_sha="a" * 40))
    db.commit()
    api = _client(db)
    response = api.get("/api/repositories/repo/tree", params={"path": "%"})
    assert response.status_code == 200
    assert response.json() == []
    # A real top-level browse still works and does not select File.content.
    root = api.get("/api/repositories/repo/tree").json()
    assert root == [{"name": "examples", "type": "directory", "path": "examples"}]


def test_tree_like_escape_handles_underscore_too():
    """'_' is the other SQL LIKE wildcard (matches exactly one char); it must be escaped too."""
    db = _session()
    db.add(Repository(id="repo", name="demo", clone_url="https://example.test/demo.git"))
    db.commit()
    db.add(File(id="f", repository_id="repo", path="axb/y.py", language="python", content="x",
                content_hash="h", size_bytes=1, indexed_commit_sha="a" * 40))
    db.commit()
    api = _client(db)
    # 'a_b' would match 'axb' if '_' were left as a live wildcard.
    response = api.get("/api/repositories/repo/tree", params={"path": "a_b"})
    assert response.status_code == 200
    assert response.json() == []


def test_chat_404s_on_bad_repository_id_before_any_insert():
    db = _session()
    api = _client(db)
    response = api.post("/api/chat", json={"question": "hi", "repository_id": "missing-repo"})
    assert response.status_code == 404
    # Nothing was written -- no orphaned conversation/message rows from a failed FK insert.
    from app.models import Conversation
    assert db.query(Conversation).count() == 0


class _RaisesOnBadPk:
    """Wraps a real session but makes db.get(File, 'bad-id') raise a DBAPIError, the way a real
    Postgres backend does for a malformed PK value (e.g. an embedded NUL byte -- psycopg raises
    'DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes' from the lookup itself,
    rather than returning None). httpx/starlette refuse to even put a raw NUL byte in a test
    request URL, so this simulates the DB-level failure directly instead."""

    def __init__(self, real):
        self._real = real

    def get(self, model, value):
        if model is File and value == "bad-id":
            raise DBAPIError("SELECT 1", {}, Exception("simulated NUL byte"))
        return self._real.get(model, value)

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_files_bad_id_404s_instead_of_500():
    db = _session()
    db.add(Repository(id="repo", name="demo", clone_url="https://example.test/demo.git"))
    db.commit()
    api = _client(_RaisesOnBadPk(db))
    assert api.get("/api/files/missing-file").status_code == 404
    assert api.get("/api/files/missing-file/symbols").status_code == 404
    # A malformed id makes the PK lookup itself raise at the DB layer instead of returning None
    # -- must still come back as a clean 404, not a 500, and the session must stay usable
    # afterwards (the route rolls back before re-raising as HTTPException).
    assert api.get("/api/files/bad-id").status_code == 404
    assert api.get("/api/files/bad-id/symbols").status_code == 404
    # Session is still usable for a normal request after the simulated failure + rollback.
    assert api.get("/api/repositories/repo").status_code == 200


def test_delete_repository_while_indexing_returns_409():
    db = _session()
    db.add(Repository(id="repo", name="demo", clone_url="https://example.test/demo.git",
                       indexing_status="indexing"))
    db.commit()
    api = _client(db)
    assert api.delete("/api/repositories/repo").status_code == 409
    # Repository is still there afterwards.
    assert api.get("/api/repositories/repo").status_code == 200


def test_indexing_progress_is_cleared_once_ready():
    db = _session()
    db.add(Repository(id="repo", name="demo", clone_url="https://example.test/demo.git",
                       indexing_status="ready", indexing_progress={"phase": "finalizing", "files": 2284}))
    db.commit()
    api = _client(db)
    assert api.get("/api/repositories/repo").json()["indexing_progress"] == {}
    assert api.get("/api/repositories/repo/status").json()["progress"] == {}


def test_callers_report_total_and_truncated_when_paginated():
    """The paginated callers endpoint must signal that a page is not the whole set, so a client
    asking 'who calls X' on a hot symbol can't mistake a truncated page for all callers."""
    db = _session()
    db.add(Repository(id="repo", name="demo", clone_url="https://example.test/demo.git")); db.commit()
    db.add(File(id="f", repository_id="repo", path="a.py", language="python", content="x",
                content_hash="h", size_bytes=1, indexed_commit_sha="a" * 40)); db.commit()
    def sym(i): return Symbol(id=i, repository_id="repo", file_id="f", name=i, qualified_name=f"m.{i}",
                              symbol_type="function", start_line=1, end_line=1, start_byte=0, end_byte=1, source_text="x")
    db.add(sym("target")); [db.add(sym(f"c{i}")) for i in range(3)]; db.commit()
    db.add(Evidence(id="evidence", repository_id="repo", indexed_commit_sha="a" * 40, path="a.py", start_line=1,
                    end_line=1, extractor="test", extractor_version="v1", content_hash="e" * 64)); db.commit()
    for i in range(3):
        db.add(SymbolEdge(id=f"e{i}", repository_id="repo", source_symbol_id=f"c{i}", target_symbol_id="target",
                          target_name="target", relationship_type="calls", source_file_id="f", line_number=i + 1, evidence_id="evidence"))
    db.commit()
    api = _client(db)
    page = api.get("/api/repositories/repo/symbols/target/callers", params={"limit": 2}).json()
    assert len(page["callers"]) == 2 and page["total"] == 3 and page["truncated"] is True
    rest = api.get("/api/repositories/repo/symbols/target/callers", params={"limit": 2, "offset": 2}).json()
    assert len(rest["callers"]) == 1 and rest["total"] == 3 and rest["truncated"] is False


def test_search_mode_and_limit_are_validated():
    db = _session()
    api = _client(db)
    assert api.get("/api/search", params={"q": "foo", "mode": "bogus"}).status_code == 422
    assert api.get("/api/search", params={"q": "foo", "limit": 0}).status_code == 422
    assert api.get("/api/search", params={"q": "foo", "limit": 101}).status_code == 422
    assert api.get("/api/search", params={"q": "foo", "mode": "text", "limit": 10}).status_code == 200
