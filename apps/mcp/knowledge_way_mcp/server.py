"""stdio MCP server exposing only read-only knowledge-way API operations."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .client import KnowledgeWayClient, configured_client_from_env

mcp = FastMCP("knowledge-way", instructions=(
    "Read-only code intelligence for an already indexed knowledge-way API. "
    "Use repository and symbol IDs returned by the tools; no mutation tools exist."
))


def client() -> KnowledgeWayClient:
    # Resolve configuration at invocation time so startup fails clearly if omitted.
    return configured_client_from_env()


@mcp.tool()
def list_repositories() -> list[dict]:
    """List indexed repositories visible to the configured knowledge-way API."""
    return client().list_repositories()


@mcp.tool()
def get_workspace_overview(workspace_id: str, snapshot_id: str) -> dict:
    """Get member repositories and declared dependencies for an immutable workspace snapshot.

    Edge evidence is explicitly labelled; no cross-repository resolution is inferred.
    """
    return client().get_workspace_overview(workspace_id, snapshot_id)


@mcp.tool()
def find_relevant_repositories(workspace_id: str, snapshot_id: str, query: str, limit: int = 8) -> dict:
    """Rank relevant repositories at immutable snapshot pins with citations and unknowns.

    Use this before repository drill-down. It never searches a repository outside
    the supplied snapshot and does not invoke semantic providers.
    """
    return client().find_relevant_repositories(workspace_id, snapshot_id, query, limit)


@mcp.tool()
def search_code(query: str, mode: str = "hybrid", limit: int = 20, repository_id: str | None = None, workspace_id: str | None = None) -> dict:
    """Search code globally, in one repository, or across declared workspace members.

    mode is hybrid, text, exact, symbols, or semantic. repository_id and
    workspace_id are mutually exclusive; workspace results remain grouped by
    repository because the API does not compute a combined rank.
    """
    return client().search_code(query, mode, limit, repository_id, workspace_id)


@mcp.tool()
def get_symbol(repository_id: str, symbol_id: str) -> dict:
    """Get one symbol and its source metadata using IDs (each capped at 256 chars)."""
    return client().get_symbol(repository_id, symbol_id)


@mcp.tool()
def get_callers(repository_id: str, symbol_id: str) -> dict:
    """Get direct callers of a symbol. Does not traverse beyond one hop."""
    return client().get_callers(repository_id, symbol_id)


@mcp.tool()
def get_callees(repository_id: str, symbol_id: str) -> dict:
    """Get direct callees of a symbol. Does not traverse beyond one hop."""
    return client().get_callees(repository_id, symbol_id)


@mcp.tool()
def get_subgraph(repository_id: str, symbol_id: str, depth: int = 1, max_nodes: int = 50) -> dict:
    """Get a bounded surrounding graph: depth 1..2 and max_nodes 1..100."""
    return client().get_subgraph(repository_id, symbol_id, depth, max_nodes)


if __name__ == "__main__":
    # FastMCP's default transport is stdio; explicitly state it to make local launch invariant.
    mcp.run(transport="stdio")
