# ADR-010 — Ratify HUMAN-DIRECTIVE-009 and restart the autonomous loop

- **Status:** accepted
- **Date:** 2026-08-20
- **Authority:** Owner directive `HUMAN-DIRECTIVE-009`; normal PLAN change control remains binding.

## Decision

Ratify `governance/directives/HUMAN-DIRECTIVE-009.md` as the governing restart order for the three-agent loop on `integration/roadmap-v2`.

1. Stage 1 proceeds in the directive’s queue order: `1.0x`, `1.2`, `1.2b`, then ADR-010/packet `1.4`, followed by `1.6`–`1.8`, `0.5`, and the Stage-1 exit review.
2. The semantic-enabled Vertex scorecard is binding. Keyless scorecards remain allowed only as explicitly labelled quickstart metrics and never gate progress.
3. Vertex `text-embedding-005` at 768 dimensions remains the binding corpus. Packet `1.4` may evaluate a local/ONNX provider and compact card embeddings subset-first behind `EmbeddingProvider`; adoption requires owner sign-off after a measured result within 0.05 absolute hybrid hit@5 of Vertex.
4. The product LLM cap remains USD 50/month, with pause at USD 40. Agent-loop costs are excluded.
5. PR #55 is obsolete and must close unmerged. The Compose worker entrypoint repair is micro-packet `1.0x`.
6. Reviewers re-execute verification on the exact PR head; a committed `on_track` review whose `reviewed_head_sha` equals that head is the sole merge gate. Hosted CI remains advisory and must not be introduced as a gate.
7. GitNexus remains an external, isolated benchmark only: no product dependency, subprocess, vendored code, Docker component, or product-path reference.

## Consequences

The navigator must reconcile the machine-readable packet board with the directive and issue `1.0x` first. Implementers and benchmark runners operate only in isolated worktrees/stacks and follow the directive’s job contracts. This ADR supersedes inconsistent operational interpretations of prior directives, while preserving their compatible governance rules.
