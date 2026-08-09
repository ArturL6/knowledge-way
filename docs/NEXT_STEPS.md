# Next Steps — Knowledge Way

This is the prioritized implementation sequence after the validated indexing, hybrid retrieval, local graph, Vertex embeddings, and Gemini Code-Card pilot.

## Verified baseline

- Repository indexing persists commit-pinned files, Tree-sitter symbols, chunks, imports, and call evidence.
- Hybrid search combines lexical, symbol, and optional semantic retrieval.
- Vertex AI is live for embeddings (`text-embedding-005`) and optional Gemini Code Cards (`gemini-3.5-flash`).
- The local, read-only MCP bridge exposes repository search and bounded symbol/graph navigation over the API.
- Workspace membership and explicit repository-to-repository dependency declarations are available.

## 1. Finish the agent-ready retrieval path

**Why first:** the MCP surface exists, but its value is proven only when a real MCP client uses it successfully on indexed repositories.

1. Connect the MCP bridge to one real coding client (Claude Code, Cursor, Codex-compatible client, or Hermes).
2. Run an end-to-end agent exercise: repository discovery → natural-language search → open symbol → callers/callees → bounded subgraph.
3. Record a compact benchmark of 10–15 realistic developer questions with expected cited symbols/files.
4. Add any missing read-only tool only if the exercise exposes a real gap. Likely candidates are `get_file_range`, `find_references`, and workspace-scoped search.

**Definition of done:** an agent can answer a repository question with source path, lines, commit and confidence, without direct filesystem/database access.

## 2. Add an optional reranker

**Why now:** hybrid retrieval works; reranking is the smallest next quality improvement for natural-language queries.

1. Retrieve 30–50 candidates through lexical, symbol, semantic, and optional graph-neighbor retrieval.
2. Call a configured reranker only on those candidates.
3. Keep direct symbol lookup deterministic and skip reranking there.
4. Compare the 10–15 benchmark questions with reranking disabled/enabled; retain it only if it gives a measurable ranking improvement.
5. Return source citations unchanged; a reranker may reorder results but must never create relationships or claims.

**Definition of done:** a configuration switch enables a provider-backed reranker and benchmark results show its effect.

## 3. Make providers intentionally pluggable

### What is modular now

- The embedding layer has an `EmbeddingProvider` protocol.
- Implemented embedding adapters: **Vertex AI** and **OpenRouter**.
- The active embedding provider/model is selected through configuration.
- Stored chunks retain their embedding model identity, so results are filtered to the matching model.

### What is not generic yet

- The Gemini Code-Card generator currently calls Vertex directly.
- The future reranker is configuration-shaped but has no live provider adapter.
- General chat/explanation is not yet a complete provider abstraction.

### Required implementation

1. Introduce a `CodeCardProvider` protocol with adapters for Vertex Gemini and an OpenAI-compatible endpoint (for example OpenRouter or another compatible service).
2. Introduce a `RerankProvider` protocol with the same explicit provider/model configuration.
3. Make model identity, dimensions, prompt version, and source hash part of every persisted generated/vector record.
4. On changing embedding provider/model/dimensions, create a new embedding generation and reindex/re-embed; never compare vectors from incompatible models.
5. Keep all external providers opt-in, secret-backed, and disabled by default.

**Definition of done:** changing an environment configuration selects a supported provider without changing application code, and each provider has a live integration test using a small fixture.

## 4. Build cross-repository resolution incrementally

1. Parse package manifests/workspace configurations and persist repository-level relations with an evidence origin and confidence.
2. Add workspace-scoped search while preserving repository and commit identity on every result.
3. Build package/export inventories and resolve cross-repository imports only when a package/export match is unambiguous.
4. Add API-contract/schema relations (OpenAPI, protobuf, GraphQL, event schemas) after package resolution works.

**Definition of done:** an agent can follow one verified relationship from a symbol in Repository A to a concrete export/contract in Repository B, and ambiguous imports remain unresolved.

## 5. Add Repository Cards and Knowledge Clouds

1. Produce deterministic repository/module facts: entry points, manifests, exports, important tests, internal modules, and known dependencies.
2. Generate versioned Repository Cards from those facts plus bounded Code-Card evidence.
3. Add a knowledge-map view at workspace → repository → module → symbol granularity.
4. Build clusters from graph topology and embedding similarity; use an LLM only to label clusters.
5. Display evidence/confidence, source links, and an explicit generated/verified distinction.

**Definition of done:** users can visually navigate a workspace without losing source/commit evidence.

## 6. Production guardrails before wider use

- Authentication/authorization before exposing the API beyond a trusted local network.
- Secret-store based credentials, not API keys in repository URLs/config files.
- Indexing-job retries, cancellation, quotas, audit logs, metrics, backups, and retention policy.
- Commit-aware incremental reindexing and explicit cost controls for embeddings, Code Cards, reranking, and explanations.

## Decision requested before implementation

The immediate product decision is whether to prioritize:

1. **MCP E2E first** — prove the agent workflow with existing indexed repositories;
2. **Reranker first** — improve natural-language retrieval quality;
3. **Provider abstraction first** — enable non-Google enrichment/reranking providers before expanding features.

Recommendation: **MCP E2E → Reranker → Provider abstraction → Cross-repo resolution.** This proves user value before increasing architecture surface.
