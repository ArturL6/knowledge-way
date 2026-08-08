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
- Workspace-scoped declared repository dependency maps (metadata only; no inferred cross-repository code edges)

## Run

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:3000. API docs are at http://localhost:8000/docs.

Before starting the API against a new database, apply the Alembic migrations.
See [database migration instructions](docs/migrations.md).

## MCP code-intelligence bridge

The optional read-only stdio MCP server calls the public API rather than the
database. For a local test, first start the stack with `docker compose up -d`, then configure your MCP-capable agent to start `knowledge_way_mcp.server` with `KW_API_BASE_URL=http://localhost:8000`. The agent talks MCP over stdio; the bridge calls this service's REST API. See the copy-paste [local setup, launch, test, and client configuration](docs/mcp.md).

For a repeatable UI, API, graph, MCP, workspace, and cleanup walkthrough, see
the [guided demo playbook](docs/demo-playbook.md). For an implementation-neutral,
reproducible comparison scaffold, see the [benchmark harness](benchmarks/README.md).

For a repeatable UI, API, graph, MCP, workspace, and cleanup walkthrough, see
the [guided demo playbook](docs/demo-playbook.md).

## Security model

Repository content is untrusted data. The chat prompt explicitly prohibits following instructions found in code or documentation. Only retrieved, size-limited code chunks are sent to a configured LLM provider; secrets are excluded by default and are never logged. Git credentials are never persisted by this service; configure read-only deploy-key or HTTPS-token secret mounts as described in [Git credential security](docs/security.md).

## Architecture

- `apps/api`: FastAPI API and domain services
- `apps/worker`: RQ worker entry point
- `apps/web`: Next.js UI
- `packages/shared`: query grammar and cross-service contracts
- `infra`: PostgreSQL initialization
- `docs`: architecture and operating notes
