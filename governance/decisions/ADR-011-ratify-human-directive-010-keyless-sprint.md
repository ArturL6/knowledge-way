# ADR-011 — Ratify HUMAN-DIRECTIVE-010 keyless retrieval sprint

- **Status:** accepted
- **Date:** 2026-08-20
- **Authority:** `HUMAN-DIRECTIVE-010`; it supersedes HD-009 only where it re-sequences work. HD-009 §4 standing rules remain binding.

## Decision

Prioritize the keyless retrieval sprint after the completed housekeeping packet `1.0x`:

1. Execute `K.1` (query digestion, BM25 re-scoring, lexical latency), then `K.2` (name-first compact retrieval units and exact/quoted routing), then `K.3` (flagged graph expansion in fusion), strictly in that order.
2. Binding sprint exits are keyless file hit@5 >= 0.44, semantic-enabled hybrid >= 0.68 without regression, and hybrid p95 <= 1s. K.2 additionally requires identifier/exact hit@1 >= 0.9 on the committed identifier subset.
3. Every K packet records both a hermetic keyless scorecard (co-binding for K exits) and a hermetic semantic-enabled scorecard (binding regression guard), each at the exact integration head against the pinned corpus manifest.
4. Mechanisms must be independently designed from public IR literature. Each implementation PR/ADR must cite its relevant public source, such as Spärck Jones (1972) for IDF, Robertson & Zaragoza (2009) for BM25, and Cormack, Clarke & Buettcher (2009) for RRF. Comparator code is never read, fetched, cited, or referenced; product paths remain comparator-free.
5. Mark `1.4`, `1.6`, `1.8`, and `0.5` deferred in STATUS, retaining the directive’s post-sprint resume order. Existing `1.2` and `1.2b` are absorbed by K.1/K.2 rather than executed separately.

## Consequences

The keyless quickstart becomes a measurable owner-testable product path rather than a non-gating fallback. Local-model/card-embedding evaluation remains deferred and retains the ADR-010 owner sign-off requirement. The navigator issues `1.0x` only if not complete; otherwise it issues K.1 and advances exclusively through K.3 before Stage-1 exit review.
