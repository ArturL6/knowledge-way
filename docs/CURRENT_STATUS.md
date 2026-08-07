# Current validation status

## Verified locally

- Docker Compose starts PostgreSQL with `pgvector`, Redis, API, worker, and web services.
- API health endpoint: `GET /health` returns `{"status":"ok"}`.
- Web app responds on port 3000.
- Next.js production build succeeds.
- Python module compilation succeeds.
- Query-filter unit test passes.

## Present MVP behavior

Repository records can be created through the API, queued for Git clone/indexing, and inspected. The worker scans source files, stores files/symbol candidates/chunks, and supports lexical plus symbol retrieval. Search, a source viewer, and citation links are available in the UI.

## Not yet production-complete

Semantic search is an API/UI mode and extension seam, but embeddings are not yet persisted or queried with pgvector. The OpenAI provider is an adapter but chat currently returns verified retrieved citations rather than an LLM synthesis. Tree-sitter is installed as an extension point; the first indexer uses conservative declaration-aware regex extraction. These are deliberate backlog items, not claims of finished functionality.
