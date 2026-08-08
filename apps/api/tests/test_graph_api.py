from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Repository, Symbol, SymbolEdge


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
    def get(self, model, value): return self.repo if model is Repository and value == "repo" else None
    def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        return Result(self.symbols if entity is Symbol else self.edges if entity is SymbolEdge else [])


def client():
    db = GraphDb()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def teardown_function(): app.dependency_overrides.clear()


def test_symbol_detail_and_direct_navigation_include_evidence_and_are_scoped():
    api = client()
    detail = api.get("/api/repositories/repo/symbols/a")
    callers = api.get("/api/repositories/repo/symbols/a/callers")
    callees = api.get("/api/repositories/repo/symbols/a/callees")
    assert detail.status_code == 200
    assert detail.json()["qualified_name"] == "pkg.root"
    assert callers.json()["callers"] == [{"symbol": callers.json()["callers"][0]["symbol"], "edge": {"id": "e1", "source_symbol_id": "b", "target_symbol_id": "a", "target_name": "pkg.root", "type": "calls", "confidence": 95, "line": 11, "source_file_id": "fb"}}]
    assert callers.json()["callers"][0]["symbol"]["id"] == "b"
    assert callees.json()["callees"][0]["symbol"]["id"] == "c"
    assert api.get("/api/repositories/repo/symbols/foreign").status_code == 404


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
