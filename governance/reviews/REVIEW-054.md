# REVIEW-054 — Packet 1.1 Postgres FTS, OR-fix remediation re-review

```yaml
verdict: blocked
packet: "1.1"
pr: 78
reviewed_head: "763c9d85da08e7f5d9a05f77040c7d4338278261"
reviewed_integration_head: "955251c"
reviewed_at: "2026-08-15T12:20:00+00:00"
criteria_checked:
  - "Exact PR head 763c9d8; REVIEW-053 finding 1 (zero-recall AND) resolved: PASS — query is now to_tsquery OR over deduplicated identifier-split terms, ranked by ts_rank_cd"
  - "Full Python suite re-executed on the OR-fixed tree: PASS (96 passed)"
  - "Import boundary: PASS (2 kept, 0 broken)"
  - "REVIEW-053 finding 2 (missing scorecard): RESOLVED — committed fastapi-stack scorecard (763c9d8) with provenance note"
  - "Recall: PASS — text and hybrid file hit@5 = 0.28 vs 0.16 baseline (+75% relative), clears the >=30% relative floor"
  - "Latency (packet criterion 'p95 latency down'; Stage-1 exit 'p95 hybrid <= 1s'): FAIL — see drift_findings 1"
drift_findings:
  - id: 1
    severity: blocking
    summary: >-
      The OR-all-terms query fixes recall but regresses p95 latency ~2.6-3.5x
      (implementer-reported and committed in the PR: text p95 11.3s vs baseline
      3.2s; hybrid p95 12.7s vs baseline 4.8s). Running query_terms over a full
      issue body yields ~150-200 terms; OR-ing all of them matches a large
      fraction of the corpus, so ts_rank_cd must score and sort a huge candidate
      set before LIMIT. This fails the packet's own 'p95 latency down' criterion
      and is far above the Stage-1 exit target (p95 hybrid <= 1s). Merging an
      11-12s search path onto integration is a real regression.
required_actions:
  - "Add deterministic rare-term query digestion per ADR-008: before building the tsquery, reduce the exploded term list to the top-N most discriminating terms by corpus document frequency (rarest first, deterministic tie-break). Build the OR tsquery from those few terms; keep ts_rank_cd ranking."
  - "Re-run the hermetic fastapi-stack scorecard at the new head and commit it: hold lexical + hybrid file hit@5 >= 0.28 (do not lose the recall win) AND bring p95 latency back toward the Stage-1 <= 1s target (at minimum not regressed vs the 0.16-baseline p95). Bind to the exact new head SHA (re-run, do not just relabel, since query behavior changes)."
  - "Keep the pure term-selection logic unit-testable on a constructed DF map; DF lookup may live in the search adapter; import-linter must stay green. Remediate as NEW commits on packet/1.1-postgres-fts; NEVER force-push."
scope_creep_risk: low
```

## Independent execution

On integration `955251c`; PR #78 head refreshed to
`763c9d85da08e7f5d9a05f77040c7d4338278261` (mergeable). Re-executed the OR-fixed
tree: `uv run pytest -q` → **96 passed**; `PYTHONPATH=apps/api uv run
lint-imports` → **2 kept, 0 broken**. The diff is search.py + the migration +
test_migrations.py + the committed scorecard; no STATUS/RUNLOG edits.

## Assessment

The AND→OR change (REVIEW-053 finding 1) is correctly resolved and the recall
win is real and measured: text and hybrid file hit@5 climb from 0.16 to **0.28**
on the pinned fastapi-stack (+75% relative), with the mandatory scorecard now
committed (finding 2 resolved). The implementer transparently reported — rather
than hid — that OR-all-terms carries a ~3× p95 latency regression (text 11.3s,
hybrid 12.7s). That regression is the sole remaining blocker.

The fix is the retrieval diagnosis's §6b lever, now authorized as **ADR-008**:
deterministic rare-term / document-frequency query digestion. Selecting the top-N
rarest terms shrinks the OR candidate set dramatically — expected to both cut
latency toward the ≤1s target and preserve (or improve) the 0.28 recall, because
the discarded terms are the high-frequency boilerplate that added candidates
without signal. One more remediation cycle should land a genuinely solid 1.1.
