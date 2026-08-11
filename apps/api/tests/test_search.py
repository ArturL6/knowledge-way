from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Repository, File, CodeChunk
from app import search as search_module
from app.search import parse_query, query_terms, result, search_with_capability, _fuse


def test_sourcegraph_filter_parser():
    query = parse_query('repo:backend lang:python path:src/auth "refresh token"')
    assert (query.repo, query.language, query.path, query.text) == (
        "backend", "python", "src/auth", "refresh token"
    )


def test_query_terms_keep_code_identifiers_and_drop_question_words():
    assert query_terms("Where is get_dependant defined?") == ["get_dependant"]


def test_result_exposes_symbol_and_indexed_commit_metadata():
    repo = SimpleNamespace(id="repo", name="demo")
    file = SimpleNamespace(id="file", path="demo.py", indexed_commit_sha="commit")
    symbol = SimpleNamespace(id="symbol", language="python", start_line=1, end_line=2, source_text="def f(): pass", qualified_name="demo.f")
    chunk = SimpleNamespace(id="chunk-row", symbol_id="symbol", language="python", start_line=1, end_line=2, source_text="def f(): pass", qualified_symbol_name="demo.f", indexed_commit_sha="chunk-commit")
    symbol_result = result("symbol", 1, repo, file, symbol)
    assert (symbol_result["symbol_id"], symbol_result["result_id"]) == ("symbol", "symbol")
    chunk_result = result("chunk", 1, repo, file, chunk)
    assert (chunk_result["symbol_id"], chunk_result["indexed_commit_sha"], chunk_result["result_id"]) == ("symbol", "chunk-commit", "chunk-row")


# --- #29/#30: SQLite-backed search_with_capability tests ------------------

def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _repo(db, id, name):
    repo = Repository(id=id, name=name, clone_url=f"https://example.test/{id}.git")
    db.add(repo); db.commit()
    return repo


def _file(db, id, repo_id, path):
    file = File(id=id, repository_id=repo_id, path=path, language="python", content="x",
                content_hash=f"hash-{id}", size_bytes=1, indexed_commit_sha="a" * 40)
    db.add(file); db.commit()
    return file


def _chunk(db, id, repo_id, file_id, start_line, text="needle in a haystack of code"):
    chunk = CodeChunk(id=id, repository_id=repo_id, file_id=file_id, language="python", chunk_type="block",
                       start_line=start_line, end_line=start_line, source_text=text,
                       content_hash=f"chash-{id}", indexed_commit_sha="a" * 40)
    db.add(chunk); db.commit()
    return chunk


def test_repository_scope_is_applied_before_the_sql_limit():
    """Repo A has more matching rows than the pre-limit window and its file path sorts
    ahead of repo B's -- so at a small limit, an unscoped-then-Python-filtered query would
    fill the whole window with repo A's rows and starve a repo-B-scoped search to zero. The
    fix pushes the repository_id scope into SQL before LIMIT, so it must not starve."""
    db = _session()
    repo_a = _repo(db, "repo-a", "alpha")
    repo_b = _repo(db, "repo-b", "beta")
    file_a = _file(db, "file-a", "repo-a", "aaa/file.py")  # sorts before repo B's path
    file_b = _file(db, "file-b", "repo-b", "zzz/file.py")
    for i in range(5):
        _chunk(db, f"chunk-a-{i}", "repo-a", "file-a", start_line=i + 1)
    _chunk(db, "chunk-b-0", "repo-b", "file-b", start_line=1)

    # limit=1 -> pre-limit window is limit*2=2 rows; both would be repo A's under the old
    # post-limit Python filter, since file_a's path sorts first.
    scoped, _ = search_with_capability(db, "needle", mode="text", limit=1, repository_id="repo-b")
    assert len(scoped) == 1
    assert scoped[0]["repository_id"] == "repo-b"
    assert all(r["repository_id"] == "repo-b" for r in scoped)  # no leakage from repo A

    unscoped, _ = search_with_capability(db, "needle", mode="text", limit=10)
    assert {r["repository_id"] for r in unscoped} == {"repo-a", "repo-b"}


def test_hybrid_exact_lexical_hit_skips_embedding_request(monkeypatch):
    """#54: an exact source match is already precise; hybrid must not pay a provider RTT."""
    db = _session()
    _repo(db, "repo", "demo")
    file = _file(db, "file", "repo", "source.py")
    _chunk(db, "chunk", "repo", "file", 1, "def exact_handler():\n    return 'ok'")

    class Provider:
        model = "test:embedding"
        calls = 0
        async def embed_texts(self, texts):
            self.calls += 1
            return [[0.0, 1.0]]

    provider = Provider()
    monkeypatch.setattr(search_module, "embedding_provider", lambda: provider)
    # The mock provider is intentionally independent of process environment; make the
    # returned capability describe that configured test double rather than CI settings.
    monkeypatch.setattr(
        search_module,
        "semantic_capability",
        lambda: {"state": "enabled", "enabled": True, "reranking": {"state": "disabled"}},
    )
    results, capability = search_with_capability(db, "exact_handler", mode="hybrid", limit=10)

    assert [item["result_id"] for item in results] == ["chunk"]
    assert provider.calls == 0
    assert capability["state"] == "enabled"


def test_hybrid_partial_term_match_still_uses_semantic_retrieval(monkeypatch):
    """The fast path is deliberately limited to exact phrase matches, not broad token hits."""
    db = _session()
    _repo(db, "repo", "demo")
    file = _file(db, "file", "repo", "source.py")
    _chunk(db, "chunk", "repo", "file", 1, "def exact_handler():\n    return 'ok'")

    class Provider:
        model = "test:embedding"
        calls = 0
        async def embed_texts(self, texts):
            self.calls += 1
            return [[0.0, 1.0]]

    provider = Provider()
    monkeypatch.setattr(search_module, "embedding_provider", lambda: provider)
    search_with_capability(db, "handler missing context", mode="hybrid", limit=10)
    assert provider.calls == 1


def test_scope_to_nonexistent_repository_returns_empty_not_everything():
    db = _session()
    _repo(db, "repo-a", "alpha")
    file_a = _file(db, "file-a", "repo-a", "aaa/file.py")
    _chunk(db, "chunk-a-0", "repo-a", "file-a", start_line=1)
    results, _ = search_with_capability(db, "needle", mode="text", limit=10, repository_id="does-not-exist")
    assert results == []


def test_search_ordering_is_deterministic_across_repeated_calls():
    """limit=3 -> pre-limit window is limit*2=6, but 8 rows match, so the window TRUNCATES
    and which rows survive depends entirely on the SQL ORDER BY. Rows are inserted in
    DESCENDING start_line, so SQLite's rowid (insertion) order differs from the start_line
    order the ORDER BY imposes: without ORDER BY the window would surface c8..c3 (top-3 c3,c4,c5),
    with it the window surfaces c1..c6 (top-3 c1,c2,c3). Asserting the exact top-3 therefore
    fails if the ORDER BY is dropped -- it is load-bearing, not just self-consistent."""
    db = _session()
    _repo(db, "repo-a", "alpha")
    file_a = _file(db, "file-a", "repo-a", "aaa/file.py")
    for start_line in range(8, 0, -1):  # insert c8, c7, ... c1 (rowid order != start_line order)
        _chunk(db, f"c{start_line}", "repo-a", "file-a", start_line=start_line)

    runs = [
        [r["result_id"] for r in search_with_capability(db, "needle", mode="text", limit=3)[0]]
        for _ in range(6)
    ]
    assert all(run == runs[0] for run in runs)  # deterministic across calls
    assert runs[0] == ["c1", "c2", "c3"]  # ordered by start_line before truncation, not insertion


# --- #31: identity-based dedup in _fuse ------------------------------------

def test_fuse_keeps_distinct_rows_at_the_same_location_separate():
    first = {"type": "chunk", "result_id": "row-a", "file_id": "f", "start_line": 1, "end_line": 2, "score": .9}
    second = {"type": "chunk", "result_id": "row-b", "file_id": "f", "start_line": 1, "end_line": 2, "score": .5}
    third = {"type": "chunk", "result_id": "row-c", "file_id": "f", "start_line": 1, "end_line": 2, "score": .1}
    fused = _fuse([[first, second, third]], 5)
    assert {item["result_id"] for item in fused} == {"row-a", "row-b", "row-c"}


def test_fuse_merges_same_row_identity_found_via_multiple_result_sets():
    lexical_hit = {"type": "chunk", "result_id": "row-a", "file_id": "f", "start_line": 1, "end_line": 2, "score": 1.0}
    semantic_hit = {"type": "chunk", "result_id": "row-a", "file_id": "f", "start_line": 1, "end_line": 2, "score": 0.6}
    fused = _fuse([[lexical_hit], [semantic_hit]], 5)
    assert len(fused) == 1
    assert fused[0]["result_id"] == "row-a"
    assert fused[0]["score"] == 1.0 / (60 + 1) + 1.0 / (60 + 1)
