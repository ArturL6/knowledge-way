# REVIEW-053 — Packet 1.1 Postgres FTS for lexical search

```yaml
verdict: blocked
packet: "1.1"
pr: 78
reviewed_head: "d2fb3b923aeb6812c4ab6a2fe5f66e38ac5b36c6"
reviewed_integration_head: "89e6654"
reviewed_at: "2026-08-15T11:40:00+00:00"
criteria_checked:
  - "Exact PR head d2fb3b92; diff limited to search.py + one migration + test_migrations.py; no STATUS/RUNLOG edits: PASS"
  - "Full Python suite re-executed on exact head: PASS (96 passed, +1 vs 95 ratchet)"
  - "Import boundary re-executed: PASS (2 contracts kept, 0 broken; FTS SQL kept out of app.application/app.domain)"
  - "Migration chain: PASS (20260815_0011 chains off 20260813_0010; Postgres-guarded; STORED generated tsvector expression is IMMUTABLE; real tsvector 1MB-limit bug found and fixed via left(...,100000))"
  - "Code-aware tokenizer: PASS (split_identifier_tokens mirrors the migration FTS_EXPR regex; verified getUserById -> 'get user by id')"
  - "GIN index usage: PASS (independently reproduced: fts_tokens @@ uses Bitmap Index Scan on ix_chunks_fts_tokens; exact ILIKE uses ix_chunks_source_text_trgm)"
  - "Mandatory scorecard delta (PLAN L18 / rule 11 'no retrieval change merges without a scorecard delta'): FAIL — not produced"
  - "Retrieval quality on realistic gold queries: FAIL — see drift_findings 1"
drift_findings:
  - id: 1
    severity: blocking
    summary: >-
      The Postgres FTS fuzzy fallback uses websearch_to_tsquery, which joins
      terms with implicit AND. query_terms explodes a real gold-task issue body
      into ~300 terms (298 for encode-starlette-issue-1108) with no rare-term
      selection, so the tsquery requires all ~300 terms to co-occur in a single
      chunk. Measured on a live Postgres index (23,100 chunks, migration
      applied): the PR's websearch_to_tsquery match count = 0; an OR tsquery over
      the same tokens = 22,566. The Postgres lexical fallback therefore returns
      ZERO candidates for realistic queries -> lexical/hybrid file hit@5 ~ 0, a
      regression below the 0.16 baseline. SQLite tests passed only because they
      exercise the ILIKE-OR branch, never the Postgres FTS branch.
  - id: 2
    severity: blocking
    summary: >-
      No hermetic scorecard delta on the fastapi-stack workspace was committed.
      Rule 11 / PLAN forbid merging a retrieval change without one. The
      regression in finding 1 is exactly what the scorecard exists to catch.
required_actions:
  - "Fix query construction so lexical recall is non-zero on multi-term bodies. Implement the Stage-1/section-6 leverage: deterministic rare-term selection — keep the top-N corpus-rarest terms (document-frequency stats over the indexed corpus) and build the tsquery from those (OR among the few discriminating terms, or per-term OR groups), letting ts_rank_cd provide IDF-like ranking. Do NOT AND ~300 undifferentiated body terms; do NOT plain-OR all of them (that is the pre-existing noise problem)."
  - "Produce and commit the hermetic scorecard delta on the pinned fastapi-stack (before = integration baseline, after = PR head): lexical AND hybrid file hit@5 must be >= 0.16 baseline (trajectory toward the ADR-007 Stage-1 target 0.44), p95 latency not regressed. Bind evidence to the exact PR head SHA."
  - "Remediate as NEW commits on packet/1.1-postgres-fts (or a fresh -v2 branch + new PR). NEVER rebase or force-push. Keep the correct parts: tsvector generated column, GIN + pg_trgm indexes, dialect branch, tokenizer, 100k truncation."
scope_creep_risk: low
```

## Independent execution

Refs refreshed to PR #78 head `d2fb3b923aeb6812c4ab6a2fe5f66e38ac5b36c6`,
integration head `89e6654`. GitHub reports the PR mergeable; the diff is three
files (+107/-10) and touches no shared governance files.

Re-executed on the exact head: `uv run pytest -q` → **96 passed**;
`PYTHONPATH=apps/api uv run lint-imports` → **2 kept, 0 broken**. The migration,
tokenizer, and both GIN indexes were independently verified against a live
Postgres instance (the migration was already applied there: `fts_tokens` column
+ `ix_chunks_fts_tokens` + `ix_chunks_source_text_trgm`, 23,100 chunks). EXPLAIN
confirmed real index scans.

## Why blocked (evidence)

The plumbing is correct and well-documented (the implementer even caught a real
tsvector 1 MB-limit bug against live data). The defect is the query semantics.
For gold task `encode-starlette-issue-1108`, `query_terms` yields **298 terms**
(199 unique). Feeding them to `websearch_to_tsquery('simple', …)` — the PR's
Postgres path — produces an all-AND query. Measured on the live index:

| Query construction (same tokens)            | matching chunks |
|---------------------------------------------|-----------------|
| `websearch_to_tsquery` (PR, implicit AND)   | **0**           |
| `to_tsquery` with `\|` (OR)                  | 22,566          |

Zero candidates means the Postgres lexical fallback contributes nothing to
fusion for realistic queries, so hybrid recall on the real workspace would fall
**below** the 0.16 baseline. This is a correctness regression against the
packet objective, not a tuning nit, and it is invisible to the SQLite unit
suite. The mandatory scorecard delta (which would have surfaced it) was also not
produced. Both must be resolved before an on_track verdict is possible.

The fix direction is the actual packet-1.1 win from the retrieval diagnosis:
rare-term / IDF weighting via deterministic top-N rarest-term selection, not
raw AND or raw OR. The existing tsvector/GIN/pg_trgm/tokenizer scaffolding is
kept — only the query construction and the missing scorecard need work.
