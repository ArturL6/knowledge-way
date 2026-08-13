from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import File, Repository, Symbol, SymbolEdge


class Result:
    def __init__(self, values): self.values = values
    def all(self): return self.values


def mk_symbol(id, qualified_name, file_id="f"):
    return SimpleNamespace(id=id, repository_id="repo", file_id=file_id, name=id, qualified_name=qualified_name,
                            symbol_type="function", language="python", start_line=1, end_line=2, start_byte=0,
                            end_byte=10, parent_symbol_id=None, signature=f"{id}()", source_text=f"SOURCE-{id}")


def mk_edge(id, source, target, line, confidence=100, relationship_type="calls", target_name=None, file_id="f"):
    return SimpleNamespace(id=id, repository_id="repo", source_symbol_id=source, target_symbol_id=target,
                            target_name=target_name or target, relationship_type=relationship_type,
                            source_file_id=file_id, line_number=line, confidence=confidence)


class GraphDb:
    def __init__(self, symbols, edges, files):
        self.repo = SimpleNamespace(id="repo")
        self.symbols = symbols
        self.edges = edges
        self.files = files

    def get(self, model, value): return self.repo if model is Repository and value == "repo" else None

    def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        return Result(self.symbols if entity is Symbol else self.edges if entity is SymbolEdge else self.files if entity is File else [])


def client(db):
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def teardown_function(): app.dependency_overrides.clear()


def chain_db():
    symbols = [mk_symbol(f"a{i}", f"pkg.a{i}") for i in range(5)]
    edges = [mk_edge(f"e{i}", f"a{i}", f"a{i+1}", i) for i in range(4)]
    files = [SimpleNamespace(id="f", repository_id="repo", path="pkg/chain.py")]
    return GraphDb(symbols, edges, files)


def parallel_db():
    symbols = [mk_symbol("p", "pkg.p"), mk_symbol("t", "pkg.t"), mk_symbol("d", "pkg.d"),
               mk_symbol("t1", "pkg.t1"), mk_symbol("t2", "pkg.t2")]
    edges = [mk_edge(f"c{i}", "p", "t", i) for i in range(5)]
    edges.append(mk_edge("d1", "d", "t1", 10))
    edges.append(mk_edge("d2", "d", "t2", 11))
    files = [SimpleNamespace(id="f", repository_id="repo", path="pkg/f.py")]
    return GraphDb(symbols, edges, files)


def edge_endpoints(edge):
    if "source" in edge: return edge["source"], edge["target"]
    return edge["source_symbol_id"], edge["target_symbol_id"]


def test_subgraph_node_cap_reports_truncation_cause_and_counts():
    api = client(chain_db())
    response = api.get("/api/repositories/repo/symbols/a0/subgraph?depth=2&max_nodes=2")
    assert response.status_code == 200
    graph = response.json()
    assert graph["truncated"] is True
    assert graph["reason"] == "node_cap"
    assert graph["total_nodes"] > graph["returned_nodes"]
    assert graph["returned_nodes"] == len(graph["nodes"])


def test_no_graph_node_carries_source_text():
    subgraph = client(chain_db()).get("/api/repositories/repo/symbols/a0/subgraph?depth=2").json()
    repo_graph = client(parallel_db()).get("/api/repositories/repo/graph?max_nodes=20").json()
    assert all("source_text" not in node for node in subgraph["nodes"])
    assert all("source_text" not in node for node in repo_graph["nodes"])


def test_parallel_edges_collapse_and_do_not_inflate_degree_ranking():
    graph = client(parallel_db()).get("/api/repositories/repo/graph?max_nodes=20").json()
    assert graph["total_edges"] == 3
    p_to_t = next(e for e in graph["edges"] if e.get("source_symbol_id") == "p" and e.get("target_symbol_id") == "t")
    assert p_to_t["count"] == 5
    d_to_t1 = next(e for e in graph["edges"] if e.get("source_symbol_id") == "d" and e.get("target_symbol_id") == "t1")
    d_to_t2 = next(e for e in graph["edges"] if e.get("source_symbol_id") == "d" and e.get("target_symbol_id") == "t2")
    assert d_to_t1["count"] == d_to_t2["count"] == 1
    function_order = [n["id"] for n in graph["nodes"] if n.get("kind") == "function"]
    assert function_order.index("d") < function_order.index("p")

    subgraph = client(parallel_db()).get("/api/repositories/repo/symbols/p/subgraph?depth=1").json()
    collapsed = next(e for e in subgraph["edges"] if e["source_symbol_id"] == "p" and e["target_symbol_id"] == "t")
    assert collapsed["count"] == 5
    assert len(subgraph["edges"]) == 1


def test_no_edge_endpoint_is_missing_from_returned_nodes():
    subgraph = client(chain_db()).get("/api/repositories/repo/symbols/a0/subgraph?depth=2&max_nodes=2").json()
    subgraph_ids = {n["id"] for n in subgraph["nodes"]}
    for edge in subgraph["edges"]:
        source, target = edge_endpoints(edge)
        assert source in subgraph_ids and target in subgraph_ids

    repo_graph = client(parallel_db()).get("/api/repositories/repo/graph?max_nodes=20").json()
    repo_ids = {n["id"] for n in repo_graph["nodes"]}
    for edge in repo_graph["edges"]:
        source, target = edge_endpoints(edge)
        assert source in repo_ids and target in repo_ids
