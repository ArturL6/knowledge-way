# ADR 0001: Storage Backends Behind Replaceable Adapters

- **Status:** Accepted
- **Date:** 2026-08-10

## Context

Knowledge Way needs one consistent, commit-pinned view of repositories, files, symbols,
code relationships, code cards, and embeddings. PostgreSQL with pgvector is the current
operational store because it keeps relational scope filters, provenance, transactions, and
semantic retrieval metadata together.

Future workloads may benefit from specialist engines:

- Neo4j or another graph database for deeper graph traversal and visualization;
- FAISS or another ANN engine for very large, local, read-optimized vector snapshots;
- a managed graph/vector service for an explicitly approved deployment.

Making any one provider leak into domain logic would make those changes risky and create
multiple uncontrolled sources of truth.

## Decision

1. **PostgreSQL/pgvector is the initial source of truth.** It owns repository identity,
   pinned commits, file/symbol metadata, relationships, cards, embedding provenance, and
   deletion/update semantics.
2. **Domain and API services use storage contracts, not backend-specific calls.** Contracts
   cover the code graph, semantic-vector retrieval, and provenance/decision records.
3. **Alternative engines are adapters or derived projections.** A Neo4j graph or FAISS
   index is rebuilt from the authoritative, commit-pinned dataset and may be discarded and
   recreated safely.
4. **Every derived index is versioned and scoped.** Its identity includes repository/workspace
   scope, indexed commit (or explicit snapshot), embedding model/dimensions, and schema/index
   version.
5. **Queries retain identical correctness semantics across adapters.** Repository, workspace,
   commit, file, symbol, and authorization filters are applied before a result is returned.
   An approximate vector candidate is never sufficient evidence by itself.
6. **No backend migration is implied now.** A new adapter is introduced only after a measured
   workload demonstrates a concrete capability or performance need.

## Initial Contracts

```text
CodeGraphStore
  - get_snapshot(scope, commit)
  - get_symbol(symbol_id, scope, commit)
  - get_bounded_subgraph(root, scope, commit, limits)
  - find_impact(symbol_id, scope, commit, limits)

VectorSearchIndex
  - upsert(snapshot_id, chunk_id, embedding, metadata)
  - search(query_embedding, scope, commit, filters, limit)
  - remove_snapshot(snapshot_id)
  - status(snapshot_id)

ProvenanceStore
  - record(source, transformation, decision)
  - trace(evidence_id, scope, commit)
```

The contracts describe behavior and evidence, not Neo4j, FAISS, pgvector, Cypher, or SQL.

## Consequences

- Current implementation remains operationally simple and transactionally consistent.
- FAISS can later become a fast local read index without becoming a second master database.
- Neo4j can later be added for a graph-specific query or UI without rewriting the API
  semantics.
- Each additional adapter carries projection, freshness, testing, and operational cost; it
  must therefore earn its place with a benchmark and a rebuild/resume strategy.

## Validation Gate for Any Future Adapter

Before enabling an adapter for production queries, validate it against the same frozen,
commit-pinned fixture as PostgreSQL/pgvector:

1. identical scope and provenance filtering;
2. expected known-symbol and impact-query results;
3. stale-snapshot removal and reindex behavior;
4. rebuild from authoritative data after deliberate deletion;
5. measured latency/throughput benefit at a recorded corpus size.
