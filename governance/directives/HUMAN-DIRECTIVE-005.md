# HUMAN-DIRECTIVE-005 — Housekeeping, promotion, Vertex readiness, GitNexus runner intel

**From:** Project owner
**To:** sol-navigator-run, implementer-run, benchmark-run
**Authority:** Owner directive; ratify as **ADR-006** via the normal flow. PLAN change control (ADR-003) and the merge gate (HD-004) remain in force. Goal unchanged.

---

## 1. Housekeeping rule — superseded PRs (fixes the PR #69 loop)

New standing rule, effective immediately and recorded in `governance/operations/schedulers.md`:

> When the navigator's review verdict on a PR is **"close without merge"** (superseded or obsolete work), closing that PR unmerged is an authorized implementer housekeeping action under case (c) of its contract — no further review needed. The implementer closes it on its next tick, notes the closure in RUNLOG, and deletes the branch. The navigator does not re-review a PR it has already verdict-marked for closure; it skips it as non-actionable.

**Apply now:** implementer closes **PR #69** unmerged on its next tick (per REVIEW-034/036) and deletes `packet/bootstrap-hd003-automation`. Also delete merged legacy `packet/R.*` remote branches (their history is preserved in integration; keep `packet/R.0-dryrun` as governance evidence).

## 2. Stage-R exit promotion is instructable work — do it now

Packet 0.6 is done, so the quickstart invariant is satisfied and **all Stage-R + Stage-0-prerequisite conditions for the first promotion are met**. Clarification: stage-exit promotion is a normal navigator-instructable task, not a ritual that waits for the owner.

1. **Sol:** issue the promotion instruction — verify Stage-R exit criteria + quickstart smoke on the current integration head, write the stage-exit verdict, authorize the merge of `integration/roadmap-v2 → main` at the exact head.
2. **Implementer:** execute the promotion merge on that authorization; from then on main's frozen-except-promotions policy is fully live.
3. **STATUS.md:** set `owner_testable: true` together with the exact quickstart command sequence (copy-paste ready), so the owner can test without reading anything else. Backfill this even before the promotion completes — 0.6 is merged on integration, which is what the owner clones.
4. Future stage exits (Stage 0, 1, …) follow the same pattern automatically: exit criteria + quickstart pass → stage-exit verdict → promotion. No owner involvement.

## 3. Vertex credential readiness protocol

The owner will provision Vertex credentials in the agents' runtime environment: `VERTEX_PROJECT_ID=<owner fills in>` plus application-default credentials (ADC). Until §3-verification passes, treat Vertex as **not configured**. Rules:

1. **Readiness check (implementer, one-time when env vars appear, and as part of packet 0.3):** run a minimal subset probe per HD-003 §4 — embed ≤ 10 chunks with `text-embedding-005`, verify 768-dim vectors return, record cost (~cents) and result in `governance/operations/vertex-readiness.md`. Never proceed to any full-corpus embedding on an unverified configuration.
2. **Packet 0.3 baseline:** run the full scorecard regardless of credential state. If Vertex is unconfigured, the baseline records `semantic: unconfigured` honestly — **and** a follow-up rule applies: once credentials verify, re-run the baseline with semantic enabled and commit it as the binding pre-Stage-1 baseline. Stage 1's "≥30% relative improvement" exit criterion compares against the baseline that includes semantic, never the degraded one.
3. **Packet 1.4 and any embedding-generating packet:** hard-pause + owner flag if credentials are absent or unverified (corpus-consistency rule, ADR-004/005 era — never silently embed with the fallback).
4. Keyless quickstart (`EMBEDDING_PROVIDER=none`) is unaffected and stays the default local path.

## 4. GitNexus runner intel — owner-verified by live test (v1.6.9), binding input for packet 0.4

The owner executed GitNexus in a clean Linux container today. Build the scripted runner on these facts:

1. **Install (no C++ toolchain needed):** `GITNEXUS_SKIP_OPTIONAL_GRAMMARS=1 ONNXRUNTIME_NODE_INSTALL=skip npm install -g gitnexus`. Plain `npx gitnexus` failed under npm 11 in this environment; the global install with flags worked in ~33s.
2. **Performance bar:** `gitnexus analyze` indexed starlette in **~9.5s keyless** — 2,820 nodes, 4,821 edges, 121 clusters, 70 flows. Record equivalent timings for our system in the comparative scorecard; this is also the UX bar for our quickstart indexing.
3. **FTS/BM25 fairness caveat:** keyword search needs a one-time LadybugDB extension download from `extension.ladybugdb.com`. Verify egress or prefetch the extension; if unavailable, GitNexus's keyword half is degraded and the comparison must mark it as environment-limited, not a product result. Repair with `gitnexus analyze --repair-fts` once reachable.
4. **Programmatic access:** use `gitnexus eval-server` for fast tool calls during evaluation; `gitnexus cypher` gives raw graph access (edges live in a `CodeRelation` table with a `type` property, e.g. `CALLS`; expect duplicate edge rows — dedupe before counting).
5. **Capture the `epistemic` field** (`exact` | `lower-bound`, with boundary explanations) returned by `context` and `impact` — GitNexus already implements completeness honesty; our Stage 2 packet 2.1 benchmarks against it, so this data must be in the 0.4 results.
6. **Symbol ambiguity:** `trace` requires `--from-uid`/`--to-uid` for reliable runs — the runner should resolve uids first, never pass bare names.
7. **Chat/LLM modes:** subset-first per HD-003 §4, BYOK via the existing key, product-budget accounted. Cross-repo (`gitnexus group`) is exercised at Stage 3, not now.
8. License discipline unchanged: PolyForm Noncommercial — behaviors and results, never code.

## 5. Processing

**Implementer, next tick:** commit this file to `governance/directives/HUMAN-DIRECTIVE-005.md`; create ADR-006 ratifying §1–§4; apply §1 (close #69, prune branches); record the §1 rule and §3 protocol in `governance/operations/`; set `owner_testable: true` per §2.3.
**Sol, next tick after:** verify ADR-006 matches; issue the §2 promotion instruction; resume normal navigation (0.2 gold tasks are already instructed and unaffected by this directive).
**Benchmark-run:** unaffected until 0.3/0.4 exist; then §3.2 and §4 govern its runs.

**Success state:** PR #69 closed; branch list clean; main receives its first promotion; `owner_testable: true` with copy-paste quickstart in STATUS; Vertex readiness protocol on file awaiting the owner's env values; packet 0.4's runner built on verified facts instead of discovery.
