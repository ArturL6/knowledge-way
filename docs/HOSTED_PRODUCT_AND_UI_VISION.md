# Hosted Product and UI Vision

## Product principle

Knowledge Way is API-first but not API-only: the same scoped retrieval service powers a human UI, MCP, and later CLI clients. Users must be able to manage a workspace, repositories, indexing, search, graphs and per-query reranking in the UI without handling infrastructure credentials.

## UI information architecture

### 1. Workspace overview

- Workspace switcher and description.
- Repository cards with latest indexed commit, branch, health and indexing status.
- Explicit cross-repository dependency view, with evidence origin and confidence.
- High-level actions: add repository, link an existing repository, create dependency declaration.

### 2. Repository operations

- Add Git URL and select branch.
- Start full index, incremental sync, or bounded Code Card run.
- Show job timeline: queued, clone, parse, embed, code-card generation, complete/failed.
- Display file/symbol/chunk counts, indexed commit, model identity, and cost/usage metadata.
- Credentials are never entered or displayed as raw secrets in the UI.

### 3. Explore and answer

- Search modes: hybrid, lexical, symbol, semantic.
- Per-query checkbox: `Reranker verwenden`; it only controls ranking for that request.
- Visible provider/capability state: disabled, configured, active, degraded.
- Evidence-first result cards: repository, path, lines, commit, confidence, source/graph links.
- Graph exploration with verified versus unresolved relationships clearly distinguished.

### 4. Configuration boundary

The UI configures product behavior and per-query options. Provider secrets, Cloud SQL access, Git credentials and deployment values remain server-side in a secret manager and deployment configuration. Workspace membership/authorization is enforced by the backend, never only by the UI.

## Reference UX patterns to borrow

- **GitHub:** repository cards, commit provenance, operation histories.
- **Linear:** compact workspace switching, strong status hierarchy, keyboard-oriented navigation.
- **Sourcegraph:** scoped code search, code citations, symbol/relationship navigation.
- **Datadog / Grafana:** job/status panels and explicit healthy/degraded states.
- **Vercel:** deployment timelines, progressive disclosure for advanced configuration.

Borrow interaction patterns and information hierarchy—not logos, proprietary assets, or a cloned UI.

## Hosted Google Cloud target (later)

```text
Browser
  → Firebase Authentication
  → Web UI: Firebase Hosting or Cloud Run
  → Knowledge Way API: Cloud Run
  → Cloud SQL PostgreSQL + pgvector
  → Redis-compatible job queue and workers: Cloud Run Jobs / Cloud Run workers
  → Vertex AI; optional external model providers through server-side adapters
  → Secret Manager for provider and Git credentials
```

Start with Cloud Run: it is simpler for the API and background workers, scales to zero, and fits the current containerized architecture. Move to GKE/Kubernetes only when sustained parallel indexing, custom networking, long-running worker pools, or operational requirements justify its added complexity.

## Later items retained in roadmap

- Provider abstraction for Code Cards and rerankers.
- Manifest- and export-backed cross-repository resolution.
- Repository Cards and Knowledge Clouds after relationship quality is proven.
- Auth, role-based workspace access, auditing, quotas, cost controls and production observability before public exposure.
