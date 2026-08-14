# ADR-006 — Ratify HUMAN-DIRECTIVE-005

- **Status:** Accepted
- **Date:** 2026-08-14
- **Decision owner:** Project owner
- **Authority:** `governance/directives/HUMAN-DIRECTIVE-005.md`

## Context

HUMAN-DIRECTIVE-005 supplies standing housekeeping, promotion, Vertex-readiness,
and external comparator evaluation rules while retaining ADR-003 PLAN change control and the
HD-004 merge gate. This ADR ratifies sections 1–4 of that directive.

## Decisions

1. A navigator verdict of **"close without merge"** authorizes the implementer
to close the superseded or obsolete PR unmerged, record the closure in RUNLOG,
and delete its branch. The navigator does not re-review a PR already marked for
closure. Apply this to PR #69 and retain only `packet/R.0-dryrun` among merged
legacy `packet/R.*` branches.
2. Stage-exit promotion is navigator-instructable work: after current-integration
exit criteria and quickstart smoke receive an exact-head stage-exit on-track
verdict, the implementer merges `integration/roadmap-v2` into `main`. STATUS
makes the keyless owner quickstart copy-paste ready. The same protocol governs
later stage exits.
3. Vertex is unconfigured until `VERTEX_PROJECT_ID` and ADC pass a subset probe
of no more than 10 chunks using `text-embedding-005`, returning 768-dimensional
vectors. Record outcome and approximate cost in
`governance/operations/vertex-readiness.md`; never run a full corpus before that
verification. Packet 0.3 records `semantic: unconfigured` honestly when needed,
then reruns its binding baseline after readiness. Embedding-generating packets
hard-pause and flag the owner when credentials are absent or unverified.
4. Packet 0.4 uses the owner-verified external comparator v1.6.9 runner facts: install with
`EXTERNAL_COMPARATOR_SKIP_OPTIONAL_GRAMMARS=1 ONNXRUNTIME_NODE_INSTALL=skip npm install -g external-comparator`,
measure equivalent timings, mark unavailable LadybugDB FTS as environment-limited,
use `eval-server`/`cypher` without copying third-party licensing code, capture
`epistemic` completeness fields, resolve trace UIDs before tracing, use
subset-first/accounted chat modes, and defer cross-repository groups to Stage 3.

## Consequences

- Scheduler operations and RUNLOG follow the authorized closure rule.
- The default local owner path remains keyless (`EMBEDDING_PROVIDER=none`).
- Vertex readiness is a recorded prerequisite, not an implicit fallback.
- external comparator evaluation compares observed behavior and results only.
