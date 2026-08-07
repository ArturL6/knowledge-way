# Delivery roadmap

## Phase 1 — Close the functional vertical slice

**Goal:** add a repository in the browser, index it, search it, browse the result, and ask a grounded question.

- Build repository add/delete/sync/re-index controls in the dashboard.
- Add polling and clear indexing phase/progress/error states.
- Persist and expose repository statistics: files, symbols, chunks, duration.
- Replace placeholder chat response with optional OpenAI grounded synthesis.
- Add end-to-end test using a small public fixture repository.

**Definition of done:** a fresh Docker deployment can index a public repository through the UI and provide an answer with clickable verified citations.

## Phase 2 — Retrieval quality

- Add pgvector column/migration and embedding batches with hash-based reuse.
- Implement semantic nearest-neighbor search and normalized hybrid score fusion.
- Add lexical FTS/trigram indexes, quoted exact search, line-level highlighting, and diverse result selection.
- Extract real Tree-sitter symbols for Python, TypeScript, JavaScript, Go, and Java.
- Add import/call/reference edges with explicit confidence and unresolved-name support.

## Phase 3 — Code intelligence workflows

- Symbol detail and reference/caller pages.
- Test discovery and impact-analysis endpoint/UI.
- Similar-code search from selected symbol/range.
- Repository tree with deep-link URLs containing repository, commit, path, and line range.
- Conversation history and follow-up reference resolution.

## Phase 4 — Production hardening and scale

- Alembic migrations; remove `create_all` from runtime startup.
- Durable job retries, idempotency keys, cancellation, and dead-letter handling.
- Auth/authorization, encrypted credential references, secret manager integration.
- Structured logs, metrics, traces, rate limits, audit events, backups, and retention.
- Horizontal workers, bounded concurrency, repository quotas, and benchmark suite.
