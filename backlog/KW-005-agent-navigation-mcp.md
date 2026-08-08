# KW-005 — Read-only MCP and graph-navigation MVP

**Priority:** P0  
**Depends on:** KW-002, KW-003, KW-004

## Design
A coding agent receives a bounded, commit-pinned `CodeGraphContext`, not a raw graph dump. Use an MCP adapter over the FastAPI service layer; no direct DB, checkout, SQL/Cypher, shell, or Git access.

## Initial tools
- `knowledgeway_list_repositories`
- `knowledgeway_search_code(repository_id, query, mode, limit)`
- `knowledgeway_get_file_range(repository_id, file_id, start_line, end_line)`
- `knowledgeway_get_symbol(repository_id, symbol_id)`
- `knowledgeway_get_code_graph_context(repository_id, anchor, direction, relationship_types, max_depth=1, max_nodes, max_edges)`

## Required REST/service capabilities
- Symbol detail, bounded file-range read, relationships, graph-context endpoint.
- Explicit repository scope, commit pinning, cursor/limit/truncation metadata.
- Source citations and confidence metadata on all graph evidence.

## Acceptance criteria
- Tools are read-only, schema-tested, principal-scoped, and return structured errors for invalid/cross-repo IDs.
- Depth is initially 1; node/edge/source byte budgets are enforced and omissions reported.
- Integration fixture proves: search → symbol → graph hop → cited code range.
- MCP-facing process runs without checkout mount and with database read-only credentials.
