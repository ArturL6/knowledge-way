# KW-004 — Commit-diff incremental indexing and graph invalidation

**Priority:** P0  
**Depends on:** KW-001, KW-003

## Problem
Sync currently scans the entire checkout and concurrent jobs can race. Graph and future embeddings need a commit-aware incremental lifecycle.

## Scope
- Resolve and persist an immutable target SHA before work begins.
- Use `git diff --name-status base..target` for add/modify/delete/rename classification.
- Remove/supersede only file-attributable symbols, chunks, raw references, and edges.
- Mark importers/callers/inheritance neighbors dirty and rerun bounded resolution batches.
- Enforce one active index job per repository; coalesce duplicate work; support cancellation and sanitized errors.
- Reuse unchanged content/embeddings by hash and model/version.

## Acceptance criteria
- Fixture with changed, deleted, renamed, and unchanged paths matches a clean full index at target SHA.
- No stale symbols/chunks/edges cite deleted or old renamed paths.
- No-op sync does not generate vectors or mutate graph cardinality.
- Job status reports target/base SHA and changed/deleted/dirty/parsed/resolved/unresolved counts.
