# Repository Knowledge Concept

## Purpose

Knowledge Way turns multiple Git repositories into a navigable, evidence-backed knowledge base for people and coding agents. It answers two distinct questions:

1. **Retrieval:** Which code, symbol, file, test, or dependency is relevant?
2. **Explanation:** What does that evidence mean in the architecture?

The first must work deterministically. The second may use an LLM, but always cites the retrieved, commit-pinned evidence.

## Current implementation: what is real today

### Repository scope and versioning

Each repository is cloned and indexed as an independent, commit-pinned snapshot. The database stores repository, file, symbol, code-chunk, embedding, and edge records with `repository_id`; indexed code carries the indexed commit SHA.

### Static repository graph

For Python, JavaScript, JSX, TypeScript, and TSX, Tree-sitter extracts declarations and reference evidence.

- **Nodes:** files, symbols, code chunks, and optional Code Cards.
- **Edges:** `call` and `import` evidence.
- **Resolution rule:** a target becomes a resolved symbol only when its declaration name is unique *inside the same repository*.
- **Confidence:** resolved local edges are confidence 100; unresolved names/imports are retained as evidence at confidence 20.

This is intentionally conservative. A stored edge is not a claim of full static analysis; dynamic dispatch, reflection, generated code, runtime configuration, and cross-language resolution remain incomplete.

### Retrieval document and embeddings

For every code chunk, the embedding input contains deterministic metadata (repository, path, language, symbol, signature), local static calls/imports, then the original source code. If a Code Card exists, its summary and keywords are added before the code. The original code remains the primary evidence.

Search is hybrid: lexical content candidates, exact/prefix symbol candidates, and optional semantic-vector candidates are normalized, fused, and deduplicated. This gives useful results even if an embedding provider is unavailable.

### Optional Code Cards

A Code Card is a versioned Gemini-generated description attached to **one symbol**. It stores its model, prompt version, source hash, commit, summary, structured details, and token usage. A changed symbol invalidates its card; cards never overwrite source code or static facts.

### Cross-repository relationships: current state

The data model and API already support a **Workspace** containing repositories and explicit `WorkspaceDependency` declarations:

```text
Workspace
  ├── Repository A
  ├── Repository B
  └── dependency declaration: A --uses package/import path--> B
```

A dependency declaration records source repository, target repository, optional package name/import path, reason, and note. Both repositories must be members of the same workspace. The API supports creating, listing, editing, and deleting these declarations.

**Important boundary:** ingestion currently resolves `SymbolEdge` objects only within a repository. It does not yet automatically turn `import foo` in Repository A into a verified symbol-level edge in Repository B. Workspace dependencies are therefore currently explicit repository-level integration facts, not automatic cross-repository call resolution.

## Target concept: complete enough, not over-engineered

The system should use a layered graph. Each layer has a clear identity, evidence source, and confidence. This keeps navigation useful without inventing certainty.

```text
Workspace / Product
  └── Repository relationship graph
        └── Repository knowledge map
              └── Module / file relationship graph
                    └── Symbol graph
                          └── Code chunks and exact source evidence
```

### 1. Workspace and repository layer

A workspace represents one product/system and groups repositories such as frontend, backend, shared SDK, infrastructure, and documentation.

Repository-to-repository edges are typed and evidence-backed:

- `declared_dependency`: manually confirmed package or import relation
- `manifest_dependency`: found in `package.json`, `pyproject.toml`, `go.mod`, Maven/Gradle, Cargo, etc.
- `workspace_reference`: monorepo/workspace configuration points to another package
- `api_contract`: an OpenAPI, protobuf, GraphQL, event schema, or shared client connects repositories
- `runtime_endpoint`: an explicitly configured service URL/topic/queue relationship

A relation can start as a declaration and gain stronger evidence from manifests and actual imports. It must show its evidence and confidence in the UI/MCP response.

### 2. Package and module layer

Inside a repository, group files into modules/packages using deterministic structure first: directory, language module/package boundaries, manifest configuration, and exports. A module summary may be generated later, but it is derived from listed symbols and files.

### 3. Symbol layer

Symbols are functions, methods, classes, interfaces, and declarations parsed from source. Edges remain fine-grained:

- calls
- imports
- parent/contains
- later: implements, extends, references, route handler, test-of, schema-uses

An edge should retain: source, target (or unresolved target spelling), source location, resolver type, confidence, and index commit.

### 4. Code Card and repository card layer

Code Cards explain individual symbols. A **Repository Card** explains one repository as a compact navigation entry point, not as a source of truth.

Suggested Repository Card fields:

```yaml
identity:
  repository: frontend-web
  indexed_commit: abc123
  default_branch: main
purpose: "User-facing web application for …"
entry_points:
  - apps/web/app/page.tsx
  - apps/web/app/api/...
major_modules:
  - name: search
    paths: [apps/web/app/search]
    responsibility: "Search UI and result presentation"
public_contracts:
  - type: HTTP API
    target: knowledge-way-api
    evidence: [NEXT_PUBLIC_API_URL]
external_dependencies:
  - package: next
  - package: react
cross_repository_dependencies:
  - target: knowledge-way-api
    relation: runtime_endpoint
    confidence: declared
important_tests:
  - ...
known_limits:
  - "Generated from static facts plus optional LLM synthesis; verify with citations."
```

Generation is staged:

1. deterministic facts are collected first;
2. bounded source evidence and Code Cards are supplied to an LLM;
3. the generated card is validated against its fact schema;
4. it is versioned by input hashes/commit/model/prompt;
5. the UI marks it as generated and lets the user open cited source evidence.

### 5. Knowledge clouds / map

A knowledge cloud is a **view**, not a second unverified graph. It clusters modules/symbols using:

- deterministic topology: imports, calls, containment, package relationships;
- semantic similarity: contextual embeddings;
- optional generated labels: concise names for clusters only.

The user can switch granularity: workspace → repositories → modules → symbols. Edges are filtered by type and confidence. Unresolved imports must stay visually distinct from verified links.

## Cross-repository resolution roadmap

### Phase A — explicit and manifest-backed relations

1. Maintain Workspace membership and explicit dependencies (already implemented).
2. Parse common manifests and workspace configs.
3. Create repository-level edges with origin (`manual`, `manifest`, `configuration`) and confidence.
4. Add a workspace search scope that retrieves from member repositories but retains repository and commit on every result.

### Phase B — package/export resolution

1. Build each repository's exported package/module inventory.
2. Match imports from a source repository to a target repository's declared package/export path.
3. Create `cross_repo_import` evidence only when package identity and export path match unambiguously.
4. Preserve ambiguity rather than selecting a plausible target.

### Phase C — contract and runtime relations

1. Parse OpenAPI/protobuf/GraphQL/event schemas and explicit service configuration.
2. Link client calls to a contract operation or event, then link the contract to its server/consumer when evidence exists.
3. Distinguish `declared`, `static`, and `observed runtime` evidence. Runtime evidence requires a separately approved, privacy-safe telemetry design.

### Non-goals for the first version

- No claim of perfect cross-language or dynamic runtime call resolution.
- No global fuzzy name matching such as linking every `get_user` across repositories.
- No autonomous source-code modifications from the knowledge system.
- No LLM-created edge without an explicit evidence label.

## Retrieval and reranking design

A reranker is valuable as a late, bounded quality step:

```text
Query
  → lexical + symbol + vector retrieval (30–50 candidates)
  → optional graph-neighbor expansion
  → reranker over candidates only
  → top 5–10 cited evidence items
  → optional LLM explanation
```

It should run for natural-language questions where ranking quality matters, not for direct symbol lookup. It must not replace deterministic filtering, workspace/repository scope, or source citations.

## Example: frontend uses backend tools

A frontend symbol imports a typed API client from a backend/shared-tools repository:

1. both repositories belong to `Product X` workspace;
2. manifest parsing finds the package relation;
3. import resolution matches `@product/api-client` to the target repository export inventory;
4. a `cross_repo_import` edge links the importing file/symbol to that export with evidence and confidence;
5. when users ask “who uses this endpoint?”, the graph follows frontend symbol → client export → API contract/handler where available;
6. every answer returns repository, path, lines, commit, relationship type, and confidence.

## Acceptance criteria before claiming cross-repo navigation

- A workspace with at least two indexed repositories has a persisted, inspectable relation.
- The relation identifies its origin and confidence.
- A workspace-scoped query returns cited results from both repositories without mixing their commits.
- At least one unambiguous package/import relation resolves to a target export.
- Ambiguous/dynamic imports remain unresolved rather than being guessed.
- API tests cover membership rules, relation creation, resolution, and scope boundaries.
