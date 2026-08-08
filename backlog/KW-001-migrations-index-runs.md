# KW-001 — Versioned migrations and immutable index runs

**Priority:** P0  
**Depends on:** none

## Problem
Runtime `create_all` and ad-hoc schema mutation cannot provide safe upgrades, rollback discipline, or stable snapshots for search and graph results.

## Scope
- Add Alembic with a reproducible initial migration and documented migration command.
- Remove API startup DDL; startup only checks migration readiness.
- Add `index_runs`: repository, base/target SHA, status, parser/resolver/embedding versions, counts, diagnostics, timestamps.
- Attach symbols, chunks, and edges to an index run / indexed commit.
- Publish a new run atomically; retain the last completed snapshot if a run fails.

## Acceptance criteria
- Empty database migration and upgrade-from-prior-schema tests pass on PostgreSQL + pgvector.
- API/worker do not issue schema DDL at ordinary startup.
- Every search, citation, and edge response identifies an indexed commit SHA.
- Failed index run cannot make a previously ready repository unqueryable.
