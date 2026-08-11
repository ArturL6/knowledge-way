from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.main import app
from app.models import Repository, File, Symbol, SymbolEdge


class Result:
    def __init__(self, values): self.values = values
    def all(self): return self.values


class GraphDb:
    def __init__(self):
        self.repo = SimpleNamespace(id="repo")
        self.symbols = [
            SimpleNamespace(id="a", repository_id="repo", file_id="fa", name="root", qualified_name="pkg.root", symbol_type="function", language="python", start_line=1, end_line=3, start_byte=0, end_byte=20, parent_symbol_id=None, signature="root()", source_text="def root(): pass"),
            SimpleNamespace(id="b", repository_id="repo", file_id="fb", name="beta", qualified_name="pkg.beta", symbol_type="function", language="python", start_line=10, end_line=12, start_byte=0, end_byte=20, parent_symbol_id=None, signature=None, source_text="def beta(): pass"),
            SimpleNamespace(id="c", repository_id="repo", file_id="fc", name="charlie", qualified_name="pkg.charlie", symbol_type="function", language="python", start_line=20, end_line=22, start_byte=0, end_byte=20, parent_symbol_id=None, signature=None, source_text="def charlie(): pass"),
            SimpleNamespace(id="foreign", repository_id="other", file_id="fx", name="foreign", qualified_name="foreign", symbol_type="function", language="python", start_line=1, end_line=1, start_byte=0, end_byte=0, parent_symbol_id=None, signature=None, source_text=""),
        ]
        self.edges = [
            SimpleNamespace(id="e2", repository_id="repo", source_symbol_id="a", target_symbol_id="c", target_name="pkg.charlie", relationship_type="calls", source_file_id="fa", line_number=3, confidence=80),
            SimpleNamespace(id="e1", repository_id="repo", source_symbol_id="b", target_symbol_id="a", target_name="pkg.root", relationship_type="calls", source_file_id="fb", line_number=11, confidence=95),
            SimpleNamespace(id="x", repository_id="other", source_symbol_id="foreign", target_symbol_id="a", target_name="pkg.root", relationship_type="calls", source_file_id="fx", line_number=1, confidence=1),
        ]
        self.files = [
            SimpleNamespace(id="fa", repository_id="repo", path="pkg/root.py"),
            SimpleNamespace(id="fb", repository_id="repo", path="pkg/beta.py"),
            SimpleNamespace(id="fc", repository_id="repo", path="pkg/charlie.py"),
        ]
    def get(self, model, value): return self.repo if model is Repository and value == "repo" else None
    def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        return Result(self.symbols if entity is Symbol else self.edges if entity is SymbolEdge else self.files if entity is File else [])


def client():
    db = GraphDb()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def teardown_function(): app.dependency_overrides.clear()


def test_symbol_detail_is_scoped_and_404s_on_a_foreign_symbol():
    api = client()
    detail = api.get("/api/repositories/repo/symbols/a")
    assert detail.status_code == 200
    assert detail.json()["qualified_name"] == "pkg.root"
    assert api.get("/api/repositories/repo/symbols/foreign").status_code == 404


# --- #33: callers/callees push the direction predicate + pagination into SQL --------------

def _sql_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _sql_client(db):
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_callers_and_callees_are_direction_filtered_and_paginated():
    db = _sql_session()
    db.add(Repository(id="repo", name="demo", clone_url="https://example.test/demo.git"))
    db.commit()
    db.add(File(id="f", repository_id="repo", path="a.py", language="python", content="x",
                content_hash="h", size_bytes=1, indexed_commit_sha="a" * 40))
    db.commit()
    db.add(Symbol(id="root", repository_id="repo", file_id="f", name="root", qualified_name="pkg.root",
                   symbol_type="function", start_line=1, end_line=1, start_byte=0, end_byte=1, source_text="x"))
    # 3 real callers of "root" (b0, b1, b2) plus a decoy callee edge (root -> c) and an edge
    # belonging to another symbol entirely -- these must not leak into either direction's result.
    for name in ["b0", "b1", "b2", "c"]:
        db.add(Symbol(id=name, repository_id="repo", file_id="f", name=name, qualified_name=f"pkg.{name}",
                       symbol_type="function", start_line=1, end_line=1, start_byte=0, end_byte=1, source_text="x"))
    db.commit()
    for i, name in enumerate(["b0", "b1", "b2"]):
        db.add(SymbolEdge(id=f"caller-{name}", repository_id="repo", source_symbol_id=name, target_symbol_id="root",
                           target_name="pkg.root", relationship_type="calls", source_file_id="f", line_number=i + 1))
    db.add(SymbolEdge(id="callee-c", repository_id="repo", source_symbol_id="root", target_symbol_id="c",
                       target_name="pkg.c", relationship_type="calls", source_file_id="f", line_number=1))
    # An edge with no resolved symbol on the related side must not surface as a caller.
    db.add(SymbolEdge(id="unresolved", repository_id="repo", source_symbol_id=None, target_symbol_id="root",
                       target_name="pkg.ghost", relationship_type="calls", source_file_id="f", line_number=9))
    db.commit()

    api = _sql_client(db)
    try:
        callers = api.get("/api/repositories/repo/symbols/root/callers")
        callees = api.get("/api/repositories/repo/symbols/root/callees")
        assert callers.status_code == callees.status_code == 200
        assert [c["symbol"]["id"] for c in callers.json()["callers"]] == ["b0", "b1", "b2"]
        assert [c["symbol"]["id"] for c in callees.json()["callees"]] == ["c"]

        first_page = api.get("/api/repositories/repo/symbols/root/callers?limit=2&offset=0")
        second_page = api.get("/api/repositories/repo/symbols/root/callers?limit=2&offset=2")
        assert [c["symbol"]["id"] for c in first_page.json()["callers"]] == ["b0", "b1"]
        assert [c["symbol"]["id"] for c in second_page.json()["callers"]] == ["b2"]

        assert api.get("/api/repositories/repo/symbols/root/callers?limit=0").status_code == 422
        assert api.get("/api/repositories/repo/symbols/root/callers?limit=201").status_code == 422
        assert api.get("/api/repositories/repo/symbols/root/callers?offset=-1").status_code == 422
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_change_impact_uses_scoped_resolved_call_edges_and_a_bounded_sql_frontier():
    db = _sql_session()
    db.add_all([
        Repository(id="repo", name="demo", clone_url="https://example.test/demo.git", indexed_commit_sha="a" * 40),
        Repository(id="other", name="other", clone_url="https://example.test/other.git"),
    ])
    db.commit()
    db.add_all([
        File(id="f-root", repository_id="repo", path="root.py", language="python", content="x", content_hash="hr", size_bytes=1, indexed_commit_sha="a" * 40),
        File(id="f-b", repository_id="repo", path="b.py", language="python", content="x", content_hash="hb", size_bytes=1, indexed_commit_sha="a" * 40),
        File(id="f-d", repository_id="repo", path="d.py", language="python", content="x", content_hash="hd", size_bytes=1, indexed_commit_sha="a" * 40),
        File(id="f-other", repository_id="other", path="other.py", language="python", content="x", content_hash="ho", size_bytes=1, indexed_commit_sha="b" * 40),
    ])
    db.commit()
    for symbol_id, repo_id, file_id in [("root", "repo", "f-root"), ("b", "repo", "f-b"), ("d", "repo", "f-d"), ("foreign", "other", "f-other")]:
        db.add(Symbol(id=symbol_id, repository_id=repo_id, file_id=file_id, name=symbol_id, qualified_name=f"pkg.{symbol_id}", symbol_type="function", start_line=1, end_line=1, start_byte=0, end_byte=1, source_text="x"))
    db.commit()
    db.add_all([
        SymbolEdge(id="b-calls-root", repository_id="repo", source_symbol_id="b", target_symbol_id="root", target_name="root", relationship_type="call", source_file_id="f-b", line_number=7, confidence=100),
        SymbolEdge(id="d-calls-b", repository_id="repo", source_symbol_id="d", target_symbol_id="b", target_name="b", relationship_type="call", source_file_id="f-d", line_number=9, confidence=100),
        SymbolEdge(id="b-reference-root", repository_id="repo", source_symbol_id="b", target_symbol_id="root", target_name="root", relationship_type="reference", source_file_id="f-b", line_number=8, confidence=100),
        SymbolEdge(id="unresolved", repository_id="repo", source_symbol_id=None, target_symbol_id="root", target_name="ghost", relationship_type="call", source_file_id="f-b", line_number=10, confidence=20),
        SymbolEdge(id="foreign-calls-root", repository_id="other", source_symbol_id="foreign", target_symbol_id="root", target_name="root", relationship_type="call", source_file_id="f-other", line_number=1, confidence=100),
    ])
    db.commit()
    api = _sql_client(db)
    try:
        response = api.get("/api/repositories/repo/symbols/root/impact?depth=2&max_nodes=2")
        capped = api.get("/api/repositories/repo/symbols/root/impact?depth=2&max_nodes=1")
        assert response.status_code == capped.status_code == 200
        impact = response.json()
        assert [(item["symbol"]["id"], item["distance"]) for item in impact["impact"]] == [("b", 1), ("d", 2)]
        assert impact["truncated"] is False
        assert [item["symbol"]["id"] for item in capped.json()["impact"]] == ["b"]
        assert capped.json()["truncated"] is True
        evidence = impact["impact"][0]["evidence"]
        assert (evidence["id"], evidence["path"], evidence["line"], evidence["type"]) == ("b-calls-root", "b.py", 7, "call")
        assert impact["limitations"]["resolved_call_edges_only"] is True
        assert api.get("/api/repositories/repo/symbols/foreign/impact").status_code == 404
        assert api.get("/api/repositories/repo/symbols/root/impact?depth=0").status_code == 422
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_subgraph_is_bounded_deterministic_and_validates_depth():
    api = client()
    response = api.get("/api/repositories/repo/symbols/a/subgraph?depth=2&max_nodes=2")
    invalid_low = api.get("/api/repositories/repo/symbols/a/subgraph?depth=0")
    invalid_high = api.get("/api/repositories/repo/symbols/a/subgraph?depth=3")
    assert response.status_code == 200
    graph = response.json()
    assert [node["id"] for node in graph["nodes"]] == ["b", "a"]
    assert [edge["id"] for edge in graph["edges"]] == ["e1"]
    assert graph["truncated"] is True
    assert invalid_low.status_code == invalid_high.status_code == 422


def test_repository_graph_includes_bounded_structure_and_symbol_relationships():
    api = client()
    response = api.get("/api/repositories/repo/graph?max_nodes=10")
    assert response.status_code == 200
    graph = response.json()
    assert {node["kind"] for node in graph["nodes"]} >= {"repository", "directory", "file", "function"}
    assert any(edge["relationship"] == "contains" for edge in graph["edges"])
    assert any(edge["relationship"] == "defines" for edge in graph["edges"])
    assert any(edge.get("type") == "calls" for edge in graph["edges"])
