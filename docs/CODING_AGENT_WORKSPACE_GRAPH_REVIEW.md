# Coding-agent review brief: workspace-first navigation and graphs

## Purpose

Perform a **read-only** architecture and product review of the tracked source on
`integration/consolidated-verified`. Do not modify files, run migrations, start/stop
services, call model providers, or change the active indexing worker.

The user goal is a human-first hierarchy:

```text
workspace → all-workspace overview or repository → tree/search/graph → focused symbol
```

A person must never have to enter repository or symbol UUIDs in a normal flow.

## Current evidence to verify

- The API has workspace CRUD, exclusive repository membership, and declared workspace
dependencies (`apps/api/app/main.py`, `apps/api/app/models.py`).
- The tracked web UI has no workspace chooser/creation/membership/dependency management
screen; it currently starts from global repository views.
- Repository graph and symbol-subgraph APIs are bounded, but there is no workspace-wide
graph endpoint.
- Workspace dependencies are **declarations** only. Do not represent them as inferred or
verified cross-repository code edges.
- Search and graph use repository scope today; workspace-scoped retrieval is not yet a
completed feature.

## Review questions

1. Identify concrete gaps/bugs between the desired workflow and the API/UI/database.
2. Assess whether the current exclusive-membership model is appropriate and identify
   required invariants and migration risks.
3. Specify a safe vertical-slice implementation order that avoids ingestion/provider
   changes while billable indexing is active.
4. Identify correctness, security, performance, accessibility, and provenance risks.
5. Separate what is implemented, API-tested, browser-E2E verified, and only documented.

## Non-negotiable product and data invariants

- A workspace-scoped request derives its repository set on the server. A supplied
  repository, file, symbol, graph, job, or dependency ID outside that workspace fails.
- Workspace selection changes clear or safely ignore stale repository/symbol/search/graph/chat state.
- “All workspace” has one deterministic global node/edge budget, truthful `truncated`
  metadata, and must not concatenate `N` repository graphs.
- Initial workspace topology displays repository nodes and declared dependency edges only.
  Relationship labels must distinguish `declared_dependency` from static `calls`,
  `references`, containment, or later evidence-backed resolution.
- Repository-local overview and focused symbol graphs remain repository-scoped until
  cross-repository resolution has independent evidence.
- Every displayed result/edge preserves repository, file/path, line range, and indexed
  commit. A workspace has a per-repository commit vector, not a fictional single commit.
- IDs are URL/API identities and deep-link parameters, not normal human input.
- Symbols are discoverable via scoped search, repository tree/file symbols, graph click,
  and deep links.
- Removing membership preserves the indexed repository; deleting a workspace preserves
  repositories; deleting a repository removes its indexed data. The UI must make these
  differences explicit.
- Workspace membership is not authorization. Authentication/tenant isolation must remain
  clearly marked as pending until enforced centrally by the API.

## Required acceptance criteria for a later implementation

### API and database

- Workspace-native repository creation/membership is atomic; no accidental orphan exists
  after a partial failure.
- Add workspace-scoped search, symbol discovery, and a bounded workspace overview before
  rendering the UI. Filters apply before result limits.
- Repository/subgraph responses include deterministic ordering and commit provenance.
- Invalid/stale/cross-workspace selections return deliberate 404/409/422 responses.
- A migration follows the then-current Alembic head, is tested on PostgreSQL with upgrade
  and downgrade, and defines treatment for legacy unassigned repositories.
- Database constraints and tests cover exclusive membership, source != target dependency,
  dependency endpoint membership, nullable uniqueness semantics, and deletion cascades.

### UI and graph

- Workspace selection/create/manage is the first useful interaction and persists in a
  shareable route/state contract.
- Search, graph, chat, and repository lists visibly reflect the active workspace and
  optional repository scope.
- No normal UI flow asks for UUIDs. Graph clicks can focus a symbol subgraph; tree and
  search can navigate to the same symbol.
- Empty, indexing, stale, failed, truncated, and unauthorized states are distinct.
- Fixture/demo data can never be mistaken for real indexed workspace data.
- Keyboard operation, focus management, dialogs, accessible names, and reduced-motion
  behavior receive explicit review.

### Testing and evidence

- Add API integration tests for scope, negative cross-workspace substitution, deterministic
  graph limits/order, commit vectors, and destructive-operation semantics.
- Add browser E2E for:
  `create/select workspace → add repository → index state → scoped search → tree/file → symbol → focused graph`.
- Include workspace switching, direct/deep links, no-symbol results, truncated graph,
  failed indexing, membership removal, deletion confirmation, and regression coverage for
  repository-only URLs, callers/callees, citations, and chat scope.
- Exercise bounded workspace overview and symbol discovery against a multi-repository
  fixture with real indexed data; do not treat unit tests or a static fixture screenshot
  as browser E2E proof.

## Explicit non-claims

The review and any resulting UI must not claim: inferred cross-repository code edges;
evidence origin/confidence for declared dependencies; atomic multi-repository index
snapshots; one workspace commit; authentication/authorization/tenant isolation; complete
static analysis; or browser-E2E validation before it has actually run.

## Deliverable from the coding agent

Return a prioritized findings report with severity, evidence path/line areas, proposed
smallest safe vertical slice, migration impact, exact tests to add, and release gates.
Do not implement until the active billable Code Card/embedding workload is terminal and
the source/migration head has been rechecked.
