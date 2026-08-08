# knowledge-way

A self-hosted, privacy-conscious code intelligence and grounded AI code-search platform.

## MVP capabilities

- Register public/private Git repositories and index asynchronously
- Incremental Git synchronization with content-hash deduplication
- Syntax-aware Python/TypeScript/JavaScript chunking with resilient text fallback
- PostgreSQL metadata, full-text search, pgvector-ready embeddings, symbols and lightweight edges
- Sourcegraph-style `repo:`, `lang:`, and `path:` search filters
- Hybrid lexical, symbol, and semantic retrieval
- Grounded chat answers with verified, clickable file-and-line citations
- Next.js UI for dashboard, search, browsing and chat

## Run

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:3000. API docs are at http://localhost:8000/docs.

Before starting the API against a new database, apply the Alembic migrations.
See [database migration instructions](docs/migrations.md).

## Security model

Repository content is untrusted data. The chat prompt explicitly prohibits following instructions found in code or documentation. Only retrieved, size-limited code chunks are sent to a configured LLM provider; secrets are excluded by default and are never logged. Git credentials are not persisted by this service: use a local credential helper, deploy key, or a secret manager integration in production.

## Architecture

- `apps/api`: FastAPI API and domain services
- `apps/worker`: RQ worker entry point
- `apps/web`: Next.js UI
- `packages/shared`: query grammar and cross-service contracts
- `infra`: PostgreSQL initialization
- `docs`: architecture and operating notes
