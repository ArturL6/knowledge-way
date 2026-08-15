# ADR-009 — Ratify HUMAN-DIRECTIVE-008 (minimal product UI packet)

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decision owner:** Project owner
- **Authority:** `governance/directives/HUMAN-DIRECTIVE-008.md`

## Context

Rule 12 descopes UI expansion until after the Stage-4 verdict. The owner has,
via HD-008, directed a bounded exception: the current UI has no workspace
management and an unusable code-graph flow, blocking hands-on use of the system.

## Decision

1. Ratify HD-008. Authorize a single UI packet, `1.9 — Usable workspace + code
   graph UI`, covering: (a) usable code graph (auto-refreshing repo picker,
   repo/module graph browse, node expansion), (b) workspace management UI over
   the existing `/api/workspaces*` endpoints, (c) Dashboard add-repo/index
   progress polish.
2. This is a bounded exception to rule 12 for this packet only. Rule 12 otherwise
   stands (no broad UI expansion, no Zoekt/SCIP/SonarQube-class tooling).
3. All other binding rules hold: hexagon boundary + import-linter, mandatory
   Playwright E2E on web changes, keyless quickstart must still pass, no
   force-push, GitNexus stays inspiration-only (no code/dependency).
4. Packet 1.9 runs in parallel with the retrieval track; it does not change the
   Stage-1 retrieval exit criteria or the ADR-007 target. As a UI-only packet it
   is not gated by the retrieval scorecard, but must not regress it.

## Consequences

- STATUS gains packet 1.9 with a next_instruction; it may proceed immediately.
- The retrieval track (Vertex readiness → packet 1.3) continues independently.
