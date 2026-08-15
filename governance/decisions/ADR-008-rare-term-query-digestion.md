# ADR-008 — Rare-term query digestion as a packet 1.1/1.6 extension

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decision owner:** Project owner
- **Authority:** PLAN change control (ADR-003); extends PLAN packet 1.1, informs 1.6.

## Context

Packet 1.1 replaced the ILIKE-percentage lexical heuristic with Postgres FTS.
The retrieval diagnosis established that gold-task queries are raw GitHub issue
bodies that `query_terms` explodes into 150–300 undifferentiated terms with no
term-importance weighting. Two naive query constructions both fail:

- **AND-all-terms** (`websearch_to_tsquery`): requires every term in one chunk →
  0 candidates on real bodies (measured 0 matches vs 22,566 for OR on a live
  23,100-chunk index). Zero recall.
- **OR-all-terms** (`to_tsquery` with `|`): recall recovers (fastapi-stack text
  and hybrid file hit@5 = 0.28, up from the 0.16 baseline, +75% relative), BUT
  OR-ing ~200 terms matches a large fraction of the corpus, so `ts_rank_cd` must
  score and sort a huge candidate set. Measured p95: text 11.3 s, hybrid 12.7 s
  vs baseline 3.2 s / 4.8 s — a ~3× regression that fails the packet criterion
  ("p95 latency down") and the Stage-1 exit criterion (p95 hybrid ≤ 1 s).

The retrieval diagnosis (handoff §6b) anticipated this exact need and flagged it
as an ADR extension because the PLAN packet text does not name query digestion
explicitly. This ADR authorizes it.

## Decision

1. **Packet 1.1 includes deterministic rare-term query digestion.** Before
   building the lexical tsquery, reduce the exploded term list to the top-N
   most discriminating terms by corpus document frequency (rarest first). The
   selection is deterministic and DF-statistics based — no LLM. N is a bounded
   constant (start at ~20–30; tune by scorecard). Ties broken deterministically
   (e.g. longer term, then lexicographic).
2. **Source of DF stats.** Use the indexed corpus itself (e.g. counts derived
   from the FTS column / a lightweight term-frequency lookup). It must be a
   deterministic query against already-indexed data; no new external service.
3. **Boundary.** Digestion is a pure, deterministic transformation of the query
   term list. Keep the pure selection logic testable (unit-testable on a
   constructed DF map); the DF lookup itself may live in the search adapter.
   No FTS/DF SQL in `app.application`/`app.domain` (import-linter stays green).
4. **Success bar (unchanged Stage-1 direction).** With digestion, packet 1.1
   must hold lexical + hybrid file hit@5 ≥ 0.28 (do not regress the OR recall
   win) while bringing p95 latency back toward the Stage-1 ≤ 1 s target (at
   minimum, not regressed vs the 0.16-baseline p95). Every change ships a
   scorecard delta.

## Consequences

- PR #78 (packet 1.1) is remediated to add rare-term digestion; the current
  OR-all-terms head is not merged because of the latency regression.
- The DF-based selection is reusable by the packet 1.6 query planner.
- No new dependency, no LLM in the retrieval inner loop, no PLAN goal change.
