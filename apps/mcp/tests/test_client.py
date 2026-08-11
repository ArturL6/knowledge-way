import os

import pytest

from knowledge_way_mcp.client import (
    ConfigurationError,
    InputError,
    KnowledgeWayClient,
    configured_client_from_env,
)


def test_request_mapping_is_get_only_encoded_and_authorized():
    client = KnowledgeWayClient("https://kw.example/api-root/", "secret")

    request = client.request_for("/api/search", {"q": "a b&c", "limit": 20})

    assert request.method == "GET"
    assert request.url == "https://kw.example/api-root/api/search?q=a+b%26c&limit=20"
    assert request.headers == {"Accept": "application/json", "Authorization": "Bearer secret"}


def test_symbol_routes_quote_identifiers_and_map_to_public_endpoints(monkeypatch):
    client = KnowledgeWayClient("http://localhost:8000")
    captured = []
    monkeypatch.setattr(client, "_get", lambda path, params=None: captured.append((path, params)) or {})

    client.get_symbol("repo/a", "symbol b")
    client.get_callers("repo", "sym")
    client.get_callees("repo", "sym")
    client.get_subgraph("repo", "sym", depth=2, max_nodes=100)

    assert captured == [
        ("/api/repositories/repo%2Fa/symbols/symbol%20b", None),
        ("/api/repositories/repo/symbols/sym/callers", None),
        ("/api/repositories/repo/symbols/sym/callees", None),
        ("/api/repositories/repo/symbols/sym/subgraph", {"depth": 2, "max_nodes": 100}),
    ]


def test_search_modes_and_scopes_match_api_contract(monkeypatch):
    client = KnowledgeWayClient("http://localhost:8000")
    captured = []

    def get(path, params=None):
        captured.append((path, params))
        if path == "/api/workspaces/team%2Fa/repositories":
            return [{"id": "one"}, {"id": "two"}]
        return {"results": []}

    monkeypatch.setattr(client, "_get", get)
    client.search_code("needle", mode="text", limit=7, repository_id="repo/a")
    workspace = client.search_code("needle", mode="exact", workspace_id="team/a")

    assert workspace["scope"] == "declared_workspace_members"
    assert captured == [
        ("/api/search", {"q": "needle", "mode": "text", "limit": 7, "repository_id": "repo/a"}),
        ("/api/workspaces/team%2Fa/repositories", None),
        ("/api/search", {"q": "needle", "mode": "exact", "limit": 20, "repository_id": "one"}),
        ("/api/search", {"q": "needle", "mode": "exact", "limit": 20, "repository_id": "two"}),
    ]


@pytest.mark.parametrize("call", [
    lambda c: c.search_code("", limit=1),
    lambda c: c.search_code("x" * 1001),
    lambda c: c.search_code("ok", mode="lexical"),
    lambda c: c.search_code("ok", mode="anything"),
    lambda c: c.search_code("ok", limit=51),
    lambda c: c.search_code("ok", repository_id="r", workspace_id="w"),
    lambda c: c.get_symbol("r", "s" * 257),
    lambda c: c.get_subgraph("r", "s", depth=3),
    lambda c: c.get_subgraph("r", "s", max_nodes=101),
])
def test_tool_inputs_are_bounded(call):
    with pytest.raises(InputError):
        call(KnowledgeWayClient("https://kw.example"))


def test_client_requires_valid_configured_base_url(monkeypatch):
    monkeypatch.delenv("KW_API_BASE_URL", raising=False)
    with pytest.raises(ConfigurationError, match="KW_API_BASE_URL"):
        configured_client_from_env()
    with pytest.raises(ConfigurationError):
        KnowledgeWayClient("file:///tmp/api")
    monkeypatch.setenv("KW_API_BASE_URL", "https://kw.example")
    monkeypatch.setenv("KW_API_BEARER_TOKEN", "token")
    assert configured_client_from_env().bearer_token == "token"
