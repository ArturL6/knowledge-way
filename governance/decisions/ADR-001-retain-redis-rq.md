# ADR-001 — Retain Redis + RQ for background jobs

- **Status:** Accepted
- **Date:** 2026-08-12
- **Decision owner:** Knowledge-Way roadmap v2

## Context

Knowledge-Way already uses Redis and RQ for asynchronous indexing and related work. Replacing the queue with a PostgreSQL queue during adoption would add migration and operational risk without a measured product benefit.

## Decision

Retain Redis + RQ as the `JobQueue` outbound adapter. The Stage R hexagonal retrofit isolates the application behind a port so a future replacement remains possible without a domain/use-case rewrite.

## Consequences

- Existing queue behavior and worker tests are preserved during Stage R.
- New queue infrastructure is not introduced merely for architectural preference.
- Any future reversal requires an ADR supported by measurements and the relevant benchmark/operations evidence.
