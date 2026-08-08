# knowledge-way delivery backlog

This backlog was harvested from three independent reviews of the current codebase and CodeGraphContext. Tickets are ordered by dependency and product risk.

## Delivery order
1. `KW-001` migrations and index-run snapshots
2. `KW-002` repository admission, authorization, and secret-safe content policy
3. `KW-003` Tree-sitter facts and explainable graph edges
4. `KW-004` incremental Git indexing and graph invalidation
5. `KW-005` MCP/navigation MVP
6. `KW-006` OpenRouter semantic indexing and hybrid reranking
7. `KW-007` repository-management UI and observability

## Product boundaries
- PostgreSQL remains the graph store for MVP; do not add Neo4j/FalkorDB yet.
- Repository content is untrusted data, never tool instructions.
- Graph links must be commit-pinned, evidence-bearing, and confidence-labelled.
- Agent navigation starts read-only and bounded; do not expose raw SQL/Cypher, shell, Git, or filesystem tools.
- Semantic retrieval is optional and disabled until an OpenRouter credential is configured.
