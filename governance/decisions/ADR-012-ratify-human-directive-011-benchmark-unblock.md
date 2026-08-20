# ADR-012 — Ratify HUMAN-DIRECTIVE-011 benchmark unblock

- **Status:** accepted
- **Date:** 2026-08-20
- **Authority:** `HUMAN-DIRECTIVE-011`; highest-numbered owner directive. HD-009 and HD-010 remain binding except where this ADR inserts the K.0 provisioning prerequisite and refines blocked-scorecard handling.

## Decision

1. Insert micro-packet `K.0` before K.1’s scorecard gate. K.0 changes only benchmark provisioning: the quickstart retains keyless default behavior while honoring caller-provided semantic settings, validates ADC before Vertex startup, mounts ADC safely, and makes browser smoke dependencies available in disposable worktrees. It must not alter product retrieval code.
2. K.0 exits only when the same exact integration head has produced hermetic keyless and semantic-enabled scorecards against a verified pinned corpus manifest, with teardown, and the unchanged default keyless quickstart passes.
3. ADC for the Vertex project `ai-tinker-lab` is owner-provisioned at `/home/hermes/.gcloud-kw/application_default_credentials.json` with mode `0600`. Until it appears, no fallback provider may stand in for the semantic scorecard. The benchmark continues keyless scorecards; navigator reviews may approve K-packets on keyless evidence only with the mandatory `awaiting_owner` follow-up condition: the first post-ADC semantic scorecard confirms hybrid >=0.68, and regression reopens drift.
4. Before every benchmark provisioning attempt, check free disk. If free space is below 5 GB, run only `docker builder prune -af`, record reclaimed space, and block as `disk` if free space remains below 5 GB. Teardown removes disposable resources and may prune dangling images older than 24 hours. Never automate `docker system prune --volumes` or prune volumes belonging to a running stack.
5. Navigator’s daily audit records `df -h /`; two consecutive audits below 10 GB create an owner drift flag.

## Consequences

The K-sprint remains keyless-first without deleting or weakening semantic retrieval. K.1 implementation may proceed in parallel if already started, but K.1 cannot pass review until K.0 has landed and both exact-head scorecards exist. The semantic guard remains binding; the only temporary change is explicit `awaiting_owner` review status while owner-provisioned ADC is absent.
