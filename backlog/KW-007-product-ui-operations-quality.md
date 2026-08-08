# KW-007 — Repository lifecycle UX, observability, and delivery quality

**Priority:** P1  
**Depends on:** KW-001, KW-002, KW-004

## Scope
- UI: add approved repository, validate URL, select workspace, sync/reindex/delete with confirmation, status/progress/target commit/error display.
- Search/chat: repository selector, loading/error/empty/stale-index/semantic-disabled states, source citations and graph entry points.
- Tests: one-command API setup, disposable Postgres+pgvector/Redis integration fixtures, worker Git fixtures, browser E2E.
- CI: formatting, types, unit/integration/E2E, migrations, dependency/image vulnerability scans.
- Operations: local vs production Compose, non-root/reproducible images, private DB/Redis by default, structured redacted logs, metrics/tracing, backup/restore runbook.

## Acceptance criteria
- Browser E2E covers add → index progress → search → source link → graph context → chat citations.
- UI exposes actionable sanitized failure states, never raw stack traces.
- CI is green from a clean checkout without custom `PYTHONPATH` incantations.
- Readiness validates dependencies and migration compatibility; API/worker/job correlation IDs are observable.
- A documented restore drill verifies PostgreSQL and checkout metadata recovery.
