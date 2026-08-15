# REVIEW-057 — Packet 1.3 pgvector ANN semantic queries

```yaml
verdict: on_track
packet: "1.3"
pr: 80
reviewed_head: "c14785c33a246b712429e8abd9a74143cebb65f3"
reviewed_integration_head: "4da8484"
reviewed_at: "2026-08-15T14:45:00+00:00"
criteria_checked:
  - "Exact PR head c14785c == GitHub PR #80 head; mergeable: PASS"
  - "Diff scope: models.py, search.py, one migration, two test files, test_migrations, cost note; no STATUS/RUNLOG; no gitnexus/ladybug refs: PASS"
  - "pytest re-executed at head: PASS (103 passed — UP from 102; implementer's report of 93 was a misreport, independently re-run shows 103, no ratchet regression)"
  - "lint-imports re-executed: PASS (2 kept, 0 broken; ANN SQL confined to search.py, not app.application/app.domain)"
  - "HNSW migration 20260816_0013 (down_revision 20260815_0012): Postgres-guarded; fixes embedding to vector(768) (required for HNSW), nulls non-768 rows with rationale, creates hnsw vector_cosine_ops index; downgrade reverts: PASS"
  - "Semantic dialect branch: Postgres uses cosine_distance (compiles to <=>) ORDER BY + LIMIT (window limit*8 for RRF), distance->similarity conversion; SQLite keeps Python cosine fallback; scoped by embedding_model + repo: PASS"
  - "EXPLAIN shows HNSW index scan (implementer evidence, after ANALYZE — see observations): PASS-with-note"
  - "Cost control (HD-003 §4): only 500 chunks embedded (~$0.0135), full-corpus extrapolation committed (~$0.46-0.79), full embed NOT run, held for owner approval; total packet spend ~1-2 cents: PASS"
drift_findings: []
required_actions: []
observations:
  - "EXPLAIN required `ANALYZE code_chunks` first (a freshly bulk-loaded table has stale stats, so the planner seq-scans until analyzed). Honestly reported. Operational follow-up: ingestion should ANALYZE code_chunks after a bulk embedding insert, else production semantic queries may seq-scan despite the HNSW index. Not a 1.3 blocker; flag for ingestion/navigator."
  - "Full semantic scorecard is DEFERRED — it needs the full-corpus embed, which is held for owner cost approval (~$0.46-0.79). Until then the semantic hit@5 lift toward the ADR-007 0.44 target is unmeasured; packet 1.3 delivers the ANN infrastructure + validated pipeline, not the scored lift."
  - "Valuable incidental fix: ingestion tests (test_ingestion_graph, test_incremental_structural_cards) were not mocking embedding_provider, so on a checkout with a real repo-root .env (EMBEDDING_PROVIDER=openrouter + key) every pytest run made live, billed embedding calls. Patched to default embedding_provider->None for parse/graph tests. Directly protects the budget."
  - "Cost-note pricing ($0.000025/1k chars) came from third-party aggregators, not the live Google pricing console — the note flags this; reconfirm before treating the $ figure as authoritative."
  - "No isolated mocked-dialect unit test for the ANN SQL shape (validated against a real Postgres+pgvector instance instead); ann_limit reuses the untuned limit*8 heuristic. Acceptable."
scope_creep_risk: low
```

## Independent execution

On integration `4da8484`; PR #80 head `c14785c33a246b712429e8abd9a74143cebb65f3`
(mergeable). Re-executed at the exact head: `uv run pytest -q` → **103 passed**
(resolving the reported "93" — it was a misreport; the true count rose by one for
the new coverage). `PYTHONPATH=apps/api uv run lint-imports` → **2 kept, 0 broken**.
Diff hygiene: no STATUS/RUNLOG, no gitnexus/ladybug. Reviewed the migration and
the semantic dialect branch by inspection: the HNSW `vector_cosine_ops` index and
the query's `cosine_distance` (`<=>`) operator match (a mismatch would silently
seq-scan), the vector(768) pin aligns with ADR-004/005, and the SQLite fallback
is preserved. The committed EXPLAIN (Index Scan using ix_chunks_embedding_hnsw_cosine,
post-ANALYZE) is accepted as evidence; re-running it would incur avoidable Vertex
spend for no additional certainty given the unambiguous SQL.

## Assessment

Packet 1.3 delivers the real pgvector ANN path: HNSW cosine index + `<=>` ORDER BY
/ LIMIT query behind a Postgres/SQLite dialect branch, replacing the O(n) Python
cosine scan on the production path while keeping it for portable tests. Cost
discipline is exemplary — 500-chunk subset validated end-to-end (a real semantic
query returned on-topic results), a committed full-corpus extrapolation (~$0.46-
0.79), the full embed deliberately withheld for owner approval, and ~1-2 cents
actually spent. The incidental cost-leak fix is a real budget safeguard. Per
HD-004 this on_track verdict at head `c14785c` authorizes merge of PR #80. The
full-corpus embed + semantic scorecard remain a separate owner decision.
