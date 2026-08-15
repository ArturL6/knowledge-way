# REVIEW-055 — Packet 1.1 Postgres FTS, rare-term digestion (ADR-008), final

```yaml
verdict: on_track
packet: "1.1"
pr: 78
reviewed_head: "17644ae0d5a5bd394e6da0edb473f2bfb1d806d7"
reviewed_integration_head: "feff5ca"
reviewed_at: "2026-08-15T13:20:00+00:00"
criteria_checked:
  - "Exact PR head 17644ae equals GitHub PR #78 head; mergeable: PASS"
  - "Diff limited to search.py, config.py, models.py, ingestion.py, two migrations, two tests, three scorecards; no STATUS/RUNLOG edits; no gitnexus/ladybug refs in apps/: PASS"
  - "Full Python suite re-executed at clean HEAD: PASS (102 passed, up from 96; +6 for DF/selection/migration coverage)"
  - "Import boundary re-executed at clean HEAD: PASS (2 kept, 0 broken; FTS/DF SQL confined to adapter + search.py, pure select_discriminating_terms testable)"
  - "REVIEW-053 finding 1 (zero-recall AND) and finding 2 (missing scorecard): RESOLVED"
  - "REVIEW-054 finding 1 (OR-all-terms ~3x p95 regression): RESOLVED via ADR-008 rare-term/DF digestion"
  - "Recall: PASS — hybrid file hit@5 = 0.32 vs 0.16 baseline (+100% relative; exceeds the >=30% Stage-1 floor and the earlier OR-all 0.28); text hit@5 = 0.24 (+50%)"
  - "Latency: PASS (packet 'p95 down' criterion) — text p95 1.03s and hybrid p95 2.17s, both BELOW the 0.16-baseline p95 (3.2s / 4.8s)"
  - "N=50 chosen via a documented 6-point sweep {25,50,75,100,150,200}; RARE_TERM_LIMIT is settings.rare_term_limit (env-overridable, default 50): PASS"
drift_findings: []
required_actions: []
evidence_notes:
  - "Scorecard binding: the committed N=50 scorecard (benchmarks/results/...-31236fb.json) records harness_git_sha 607d804, two commits behind HEAD 17644ae. The diff 607d804..HEAD is ONLY the RARE_TERM_LIMIT constant->settings.rare_term_limit(default 50) wiring (verified by git diff of search.py + config.py); the scored run used the settings-driven code with N=50, byte-identical in retrieval behavior to HEAD's committed default. pytest and lint-imports were independently re-run at clean HEAD. The result is representative of HEAD; the sha-label lag is a minor evidence imperfection, not a behavior gap. Future retrieval scorecards should be generated from a clean HEAD so harness_git_sha == head."
  - "Two intermediate scorecards (f4c6871 OR-all, 2316793) are also committed. Harmless provenance of the remediation trail; not required."
observations:
  - "Stage-1 EXIT target p95 hybrid <= 1s is NOT yet met (hybrid 2.17s). That is a STAGE-exit criterion, not a packet-1.1 gate; hybrid latency is dominated by the still-ILIKE symbol pass + fusion (packet 1.2 scope), not the lexical FTS path (text alone is ~1s). Latency still improved vs baseline."
  - "Implementer flagged a PRE-EXISTING bug unrelated to 1.1: app/worker.py's `if __name__=='__main__'` guard is in the imported submodule, not the `-m app.worker` entry module, so a compose-managed worker started that way silently no-ops. Navigator should file this separately; out of scope for 1.1 (quickstart uses a different, working worker entry)."
scope_creep_risk: low
```

## Independent execution

On integration `feff5ca`; PR #78 head refreshed to
`17644ae0d5a5bd394e6da0edb473f2bfb1d806d7` (mergeable). Re-executed at the exact
head: `uv run pytest -q` → **102 passed**; `PYTHONPATH=apps/api uv run
lint-imports` → **2 kept, 0 broken**. Diff hygiene verified: no STATUS/RUNLOG
edits, no gitnexus/ladybug references anywhere in `apps/`. Confirmed the final
scorecard's N=50 behavior is byte-identical to HEAD's committed default by
inspecting `git diff 607d804..HEAD` (constant→settings only).

## Assessment

Packet 1.1 is complete and solid. The lexical path is now real Postgres FTS: a
code-aware `tsvector` generated column (identifier splitting) + GIN, a pg_trgm
exact path, `ts_rank_cd` ranking, and ADR-008 rare-term/DF query digestion that
keeps only the ~50 rarest (most discriminating) query terms. This resolves the
full remediation arc:

- REVIEW-053: AND-semantics returned 0 candidates → fixed (OR).
- REVIEW-054: OR-all-terms regressed p95 ~3× → fixed (rare-term digestion).

Result on the pinned fastapi-stack: **hybrid file hit@5 0.16 → 0.32 (+100%)**,
text 0.16 → 0.24 (+50%), with p95 latency *improved* over baseline (text 1.0s,
hybrid 2.2s). The N=50 operating point was chosen from a transparent sweep and
is env-tunable. hit@1 = 0.04 (≈ the old all-or-nothing recall signature persists)
— ranking within top-5 is future work (semantic 1.3, graph 2.4), consistent with
the diagnosis; recall is the win 1.1 was scoped to deliver.

Per HD-004 this on_track verdict at head `17644ae` authorizes the merge of
PR #78 into `integration/roadmap-v2`. GitHub review approval is not a gate.
