# ADR-007 — Ratify HUMAN-DIRECTIVE-007 and finalize the Stage 1 exit bar

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decision owner:** Project owner
- **Authority:** `governance/directives/HUMAN-DIRECTIVE-007.md` (highest-numbered directive; wins on conflict)

## Context

HUMAN-DIRECTIVE-007 supersedes the in-repository comparative-benchmark
implementation model. The external comparator (GitNexus, PolyForm-Noncommercial —
benchmark reference and design *inspiration* only, never a code source) must not
exist in the Knowledge-Way repository or its development workflow in any form.
Comparative benchmarking is an independent operational activity run entirely
outside every Knowledge-Way checkout; it reports results to the owner and does
**not** block or authorize repository implementation automatically. Design
proposals derived from it reach product work only through human-reviewed ADRs
based on behavioral conclusions.

This creates a direct conflict with HUMAN-DIRECTIVE-006, which inserted an
**in-repository** packet `0.4b` (comparative scorecard) as a gate blocking Stage 1.
Under highest-number-wins, HD-007 controls: the in-repo `0.4b` gate is void.

The external comparison has now been executed per HD-007 (isolated location,
read-only gold-task export, pinned corpus SHAs, keyless with the LadybugDB FTS
extension installed). Keyless, file-level, all 25 gold tasks:

| System                            | hit@5 | MRR   |
|-----------------------------------|-------|-------|
| External comparator (defs-first)  | 0.44  | 0.329 |
| External comparator (doc-order)   | 0.32  | 0.160 |
| Knowledge-Way baseline            | 0.16  | 0.160 |

The comparator reaches ~3× the Knowledge-Way baseline on hit@5 **without
embeddings**, confirming the gold tasks are solvable and that candidate quality
(rare-term/IDF keyword weighting) — not fusion or semantics — is the dominant gap.

## Decisions

1. **HD-007 is ratified.** The external comparator is a benchmark/inspiration
   reference only. No comparator-specific runner, result artifact, dependency,
   Docker material, bundled binary, vendored code, or product invocation may
   exist in this repository. Any product-side reference is immediate drift.
2. **The in-repository packet `0.4b` gate (HD-006) is retired.** Stage 1
   implementation is no longer blocked by any in-repo comparative packet. The
   comparison is the HD-007 external operation, which does not gate repo work.
   HD-006's remaining constraints (hermetic single-side benchmarks, licensing
   boundary, small-subset-first, budget) stay in force.
3. **The Stage 1 exit bar is finalized** from the external comparator numbers.
   In addition to the existing Stage 1 exit criteria, the absolute target is:
   **hybrid file hit@5 ≥ 0.44** on the Stage 0 harness (match/beat the keyless
   comparator). The PLAN's "≥ 30% relative over baseline" remains the minimum
   floor; ≥ 0.44 is the target. All other Stage 1 exit criteria are unchanged.
4. **Comparator findings inform design, never code.** The behavioral mechanism
   findings (BM25/IDF rare-term weighting → packet 1.1; compact/entity-first
   units → 1.7; query digestion → ADR extension to 1.1/1.6) are inputs to
   Knowledge-Way's own custom implementation. No comparator code, schema, or
   query text is copied.

## Consequences

- STATUS may issue Stage 1 `next_instruction` immediately; packet 1.1 is first.
- Every Stage 1 retrieval packet still lands with a hermetic scorecard delta;
  Stage 1 closes only when hybrid hit@5 ≥ 0.44 and the other criteria hold.
- The PLAN Stage 1 exit criteria are updated in the same change as this ADR
  (ADR-003 PLAN change control).
