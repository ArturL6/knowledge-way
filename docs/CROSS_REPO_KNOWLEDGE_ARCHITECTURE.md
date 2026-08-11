# Cross-Repository Knowledge Architecture

**Status:** agreed target architecture — evidence-first; implementation is staged.

## User outcome

When a developer or coding agent plans a change, Knowledge Way should make the following path fast and auditable:

```text
change/question at workspace level
  → identify repositories that may matter
  → distinguish proven impact from review candidates
  → orient in a repository through a Repository Card
  → drill into module, contract, file, symbol and exact source
  → optionally receive an LLM explanation with citations
```

The product is therefore not merely an LLM wiki, vector search, or code graph. It is a single, commit-pinned evidence base with several navigation and explanation projections.

## Architectural rule

```text
Git snapshots + parser facts + manifests + contracts + explicit declarations
  → versioned evidence nodes and typed relationships
  → Cards / retrieval documents / embeddings / graph views
  → bounded retrieval and graph traversal
  → LLM explanation of cited evidence
```

Deterministic facts and evidence edges are canonical. Generated Cards, vectors, rankings, clusters, and LLM prose are derived, replaceable views. An LLM may summarize, label, rank candidates, and explain visible evidence. It must not silently create authoritative technical relationships or claim complete impact.

## Responsibilities of the layers

### Evidence graph: prove structure and impact

The graph answers: *Why is this repository affected?* It stores provenance-rich relationships such as:

- `manifest_dependency`, `workspace_reference`, `declared_dependency`
- `cross_repo_import` only after unambiguous package/export resolution
- contract paths such as client → OpenAPI/protobuf/GraphQL/event operation → provider/consumer
- local resolved `call`, `import`, containment and test-related evidence

Each edge has source location(s), producer and version, resolution status, reason/confidence, and repository snapshot or workspace manifest scope.

### Embeddings: discover candidates

Embeddings answer: *Which repositories, modules, contracts, or symbols might be relevant to this intent?* They are useful for recall and orientation, but semantic similarity is never a structural dependency or proven change impact.

Index retrieval documents at several granularities:

1. repository: deterministic purpose, packages/build targets, entry points, exports, contracts and inbound/outbound boundaries;
2. module/package: responsibilities, public surface and bounded relationship facts;
3. contract: operations/events/exports as cross-repository boundary entities;
4. symbol/source: implementation-level drill-down with original source and stable metadata.

Generated Card text can enrich these documents but cannot be their only technical evidence. Reuse embeddings only when the complete contextual input hash, embedding model, and index version match.

### Cards and LLM wiki: orient and explain

- **Symbol Cards** describe one implementation for deep exploration.
- **Module/file cards** bridge local source to repository structure.
- **Repository Cards** are compact landing pages for a repository snapshot, not a free-form summary of all child summaries.

A Repository Card should separate:

1. deterministic profile: commit, packages, entry points, exports/contracts, tests, direct relationships and known index gaps;
2. derived architecture view: important modules, boundaries, hotspots and cited evidence;
3. optional generated prose: schema-validated, input-hashed, model/prompt-versioned and visibly cited.

Parent Cards must be derived from primary facts plus selected evidence, not recursively from child prose alone.

## Honest change-impact result

For “I change X — which repositories should I inspect?”, return distinct classes:

- `verified_affected`: reachable through defined, evidence-backed paths;
- `likely_review`: strong but incomplete evidence, such as a manifest relation without resolved usage;
- `related_context`: semantic similarity or other non-causal context;
- `unknown`: dynamic/unresolved/unsupported paths or missing resolver coverage.

A response must include the workspace snapshot manifest, relation path, scope, truncation and limitations. The existing local impact endpoint is intentionally only a **bounded static reverse-call impact**, not a complete change-safety assertion.

## Snapshot and provenance boundary

A repository commit is insufficient for reproducible portfolio-wide answers. Cross-repository queries must use an immutable workspace snapshot manifest containing the selected repository snapshots and resolver versions. Every materialized card, embedding and graph view must carry its input provenance.

Minimum provenance fields:

```text
workspace_snapshot_manifest_id or repository_snapshot_id
producer and producer_version
input hashes
indexed commit(s)
resolution status and evidence locations
created/updated time
```

## Efficient incremental indexing

Do not regenerate all LLM Cards or embeddings for every commit.

1. Derive a Git `ChangePlan` from old snapshot → new snapshot, including changed, deleted, moved and renamed paths.
2. Parse only dirty source and invalidate old/new neighbor relationships.
3. Traverse derivation dependencies to mark affected Cards, retrieval documents and vectors dirty.
4. Recompute only dirty materialized projections; retain valid identities and reused vectors.
5. Generate LLM Cards lazily or prioritize entry points, public exports, boundaries and hotspots.
6. Apply per-workspace/repository budgets, redaction and provider provenance.

For the initial expected scale (roughly 10–30 related repositories), PostgreSQL plus pgvector and indexed relational edge queries remain the primary store. A dedicated graph database becomes justified only after measured traversal, volume or concurrent-read pressure demonstrates a real limit.

## Delivery stages

1. **Evidence foundation:** stable identities, immutable snapshots, ChangePlan, provenance and deterministic local facts.
2. **Single-repository wiki:** deterministic repository/module Cards, optional cited LLM prose, source drill-down.
3. **Portfolio navigation:** repository/module/contract vectors, workspace-scoped search and cost controls.
4. **Verified cross-repository edges:** manifests, exports/imports, then contracts and explicit runtime configuration.
5. **Cross-repository impact:** diff seeds, bounded reverse traversal, separate certainty classes and historical evaluation.

## Anti-patterns

- embedding everything first and treating vectors as dependencies;
- using LLM output as an authoritative resolver;
- global fuzzy matching of symbol names across repositories;
- treating Cards as canonical data;
- presenting semantic proximity as impact;
- mixing arbitrary current commits in a workspace query;
- adding a graph database before relational queries have measured limits;
- promising completeness for reflection, code generation, dependency injection or runtime configuration.
