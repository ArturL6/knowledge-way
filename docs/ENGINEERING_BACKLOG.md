# Engineering backlog

## P0 — required before describing the product as fully functional

- [ ] **Embeddings:** introduce pgvector migration, vector dimensions/model metadata, batching, retry/backoff, and re-use by chunk content hash.
- [ ] **Hybrid retrieval:** combine PostgreSQL lexical, vector, and symbol candidates with documented normalized scoring.
- [ ] **Grounded LLM answers:** invoke `ChatProvider` only when configured; validate every citation against retrieved sources before returning it.
- [ ] **Web repository management:** add repository URL form, validation, list actions, status polling, and error display.
- [ ] **Incremental sync correctness:** use `git diff --name-status <indexed SHA>..<HEAD>`; do not scan all files when the commit has changed.
- [ ] **Migrations:** replace runtime schema creation with Alembic revision history.

## P1 — quality and usability

- [ ] Use Tree-sitter AST nodes for declarations, parent relationships, signatures, byte offsets, and robust fallback chunk splitting.
- [ ] Full-text / trigram PostgreSQL indexes and result snippets/highlights.
- [ ] Import and reference extraction with language-specific resolvers and confidence levels.
- [ ] Repository browser folders, symbols drawer, syntax highlighting, selected ranges, and commit-aware deep links.
- [ ] Conversation list, repository selector, retrieved-source drawer, and retrieval-mode indicator.
- [ ] API request/response schemas split into dedicated modules and OpenAPI examples.

## P2 — security, reliability, and operations

- [ ] SSRF-safe Git URL policy plus provider allow-list.
- [ ] Secret scanning/redaction before embedding and before chat context creation.
- [ ] Credential reference abstraction; never accept or store raw PATs in database rows.
- [ ] Per-user/repository authorization and a single-user mode switch.
- [ ] Structured JSON logging with content-free events; Prometheus metrics and tracing.
- [ ] Job retry policy, cancellation, parse/embedding failure counters, and dashboards.

## Test backlog

- [ ] Unit tests: query grammar, language detection, secret exclusions, chunking, citation validation.
- [ ] Integration tests: clone/index/sync/delete against deterministic fixtures.
- [ ] API contract tests and OpenAPI snapshot.
- [ ] Browser E2E: add → index → search → open citation → chat.
- [ ] Load benchmark: repositories/files/chunks, search p95, worker throughput.
