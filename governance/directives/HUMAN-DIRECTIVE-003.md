# HUMAN-DIRECTIVE-003 — State-based automation restart: 3 jobs, 20-minute ticks, Sol navigates

**From:** Project owner
**To:** all scheduled agents
**Authority:** Owner directive; converts to ADR-005 via the normal flow (§8). PLAN change control (ADR-003) stays in force.
**Supersession:** Absorbs the never-committed HUMAN-DIRECTIVE-002. The Vertex provider decision is already ratified in ADR-004 and implemented — no action needed there. The goal is unchanged: evidence-backed multi-repo project intelligence, measured by the Stage 0 harness and the Stage 4 ablation. GitNexus remains the inspirational source and benchmark baseline (concepts yes, code never — PolyForm Noncommercial).

---

## 1. New job topology — exactly three jobs, every 20 minutes, state-based

The old four-job layout is replaced. Reconfigure the schedulers to:

| Job | Model | Every 20 min it does |
|---|---|---|
| **sol-navigator-run** | Sol high | Reads STATUS.md, PLAN.md, open PRs, latest reviews. Then exactly one of: **(a)** a PR is `pr_open` → review it (with re-execution per ADR-003), verdict, approve merge or block; **(b)** no PR open but a packet is `in_progress` → check for staleness (>6h without commits → write a nudge instruction); **(c)** nothing open and `todo` packets exist → write the **next instruction** (§2) for the implementer; **(d)** truly nothing actionable → no-op. Every 24h regardless: run the drift-audit checklist (boundaries, scope, scorecard trend, STATUS-vs-reality, integration-vs-main). Never writes code. |
| **implementer-run** | Hermes (Codex tier) | Reads STATUS.md. Exactly one of: **(a)** an instruction block addressed to it exists and its packet is not blocked → execute it (branch from integration, implement, full gauntlet, open PR, set `pr_open`); **(b)** its open PR is `review_blocked` → resolve the review's required_actions; **(c)** a merge was approved → merge, set `done`, clean up branch; **(d)** nothing addressed to it → no-op. Never picks work Sol has not instructed. Never merges without an approving verdict. |
| **benchmark-run** | Hermes (cheap tier) | State-based: **(a)** Stage 0 harness not yet built → no-op; **(b)** harness exists and integration head changed since last scorecard → run the retrieval scorecard, commit results; **(c)** GitNexus comparison harness exists (packet 0.4 makes it scripted) → run both sides — our system and GitNexus — on the same gold tasks and commit the comparative scorecard; **(d)** any regression vs the previous scorecard → write a drift flag for Sol. |

**Noise control:** no-op ticks append a RUNLOG heartbeat locally but push at most **one consolidated heartbeat commit per hour**. Action ticks push immediately. No-op ticks must be minimal-cost (state check only — no LLM reasoning beyond deciding "nothing to do").

## 2. Sol is the navigator — the implementer takes instructions from Sol

Sol knows the goal state (PLAN.md + directives) and the current state (STATUS, reviews, scorecards). The implementer no longer self-selects packets. Instead, Sol writes an instruction block into STATUS.md:

```yaml
next_instruction:
  issued_by: sol-navigator
  issued_at: <ISO timestamp>
  packet: "0.2"
  objective: "Mine 25–40 gold tasks from merged fix PRs of fastapi/starlette/pydantic per PLAN 0.2 and HD-001 §1."
  constraints: ["derive gold labels from the fix PR's changed files", "no LLM calls needed", "commit under benchmarks/tasks/"]
  done_when: "verify script benchmarks/checks/gold_tasks.sh passes; PR open into integration"
```

The instruction must always trace to a PLAN packet — Sol adapts *how* (ordering, emphasis, corrective feedback from the last review), never *what* (scope stays PLAN + directives). If Sol believes the plan itself needs changing, it writes an ADR proposal and flags the owner instead of instructing off-plan work. Review feedback loops stay as today: blocked PRs carry required_actions; the implementer's next tick resolves them.

## 3. Full autonomy mandate

Run **fully automatically, without the owner**, at least until the owner can test the system on the benchmark repos himself — concretely: packet 0.6's keyless quickstart passing on a clean machine, the fastapi-stack workspace indexed, and search/graph endpoints answering. Do not stop there: continue through Stages 0 → 1 → 2 → 3 → 4 per PLAN order (PostHog pair joins at Stage 3; Stage-R promotion to main fires as soon as 0.6 satisfies the quickstart invariant).

**Budget scope clarification:** the USD 50/40 cap governs **product LLM usage** — embeddings, card generation, query-planner fallback, rerank, GitNexus chat evaluation. The agents' own tick/review/instruction costs run on the owner's platform budget and are NOT counted against the cap (otherwise 20-minute ticks would exhaust it for the wrong reason). Sol notes approximate agent-loop consumption in the 24h drift-audit so the owner sees the trend, but it never pauses the pipeline.

**The only stopping conditions:** the drift brake (two consecutive drift verdicts on one topic), budget pause at USD 40 of the USD 50 cap, missing Vertex credentials when an embedding-generating packet starts (corpus-consistency rule from ADR-004 era: never silently embed with the fallback), gold-task sample validation failing, and the Stage 4 go/no-go — which is the owner's decision. Everything else keeps moving. Nothing waits for the owner "to be safe."

## 4. Small-subset-first rule (binding, new)

Any packet that introduces or changes **LLM or embedding usage** runs in two mandated phases:

1. **Subset phase:** execute on a bounded slice first — one repository (starlette) or ≤ 200 files / ≤ 500 chunks / ≤ 50 cards, whichever binds first. Record in the implementation evidence: output samples, failure rate, measured cost, and the **linear cost extrapolation to the full corpus**. If extrapolated cost would cross the budget cap, stop and flag.
2. **Full phase:** only after the subset evidence is committed and (for reviewed packets) Sol has seen it, run the full corpus.

This applies to: embedding generation (1.3/1.4), card generation (1.4, 3.3, 3.4), the LLM query-planner fallback (1.6), rerank evaluation (1.8), and any GitNexus chat-mode evaluation. Deterministic indexing (tree-sitter, FTS, graph) is exempt.

## 5. Automated benchmarking — both systems, no owner in the loop

- Packet **0.3** builds the retrieval scorecard harness as already planned; **benchmark-run** executes it automatically on integration changes (§1).
- Packet **0.4** is upgraded: don't just test-drive GitNexus once — **script it**. Deliver a repeatable headless runner (GitNexus CLI, keyless core; its optional chat mode via the existing key, subset-first per §4) that answers the 12 question classes on the gold-task repos and emits machine-readable results next to ours. From then on the comparative scorecard (ours vs GitNexus) is produced automatically by benchmark-run and committed — the Stage 4 parity table then assembles itself from accumulated data.
- Benchmark repos are **defined and final** (HD-001 §1): fastapi + starlette + pydantic now; PostHog/posthog-js at Stage 3.

## 6. Owner decision channel (unchanged, restated because it caused the last stall)

Owner decisions bind only as numbered directives in `governance/directives/`. A decision heard through any other channel → flag `awaiting_directive`, don't enforce, don't implement. Sol's instructions to the implementer (§2) are *navigation within* PLAN + directives, not a new decision channel.

## 7. What "done for the owner's first test" looks like (so everyone aims at it)

Clean clone → quickstart commands → workspace `fastapi-stack` indexed → the owner runs searches/symbol lookups/graph queries against real fastapi/starlette/pydantic code via UI, API, and MCP — keyless, semantic mode reporting `unconfigured` honestly unless Vertex creds are present. When that state is reached, note it prominently in STATUS.md (`owner_testable: true` + the quickstart command line) — and keep going.

## 8. Processing instructions

**Owner (one-time, because scheduler configuration lives in the Hermes runtime, not the repo):** retire the old jobs and create the three §9 jobs at 20-minute intervals using the ready-to-paste prompts below. Everything after that is agent-side.

**Implementer, first tick after receiving this:**
1. Commit this file to `governance/directives/HUMAN-DIRECTIVE-003.md`.
2. Create **ADR-005 — Ratify HUMAN-DIRECTIVE-003** (job topology, navigator pattern, subset-first rule, automated benchmarking, autonomy mandate, budget scope) **and in the same PR update PLAN.md's scheduler table** to the §1 three-job layout — the ADR in the same PR satisfies PLAN change control.
3. Document the new contracts in `governance/operations/schedulers.md`; reset RUNLOG expectations per the noise rule.
4. Update STATUS.md: add the `next_instruction` field; clear stale flags.

**Sol, first tick after that:** verify ADR-005 matches this directive; then issue the first instruction — expected: **packet 0.1** (commit `benchmarks/corpora.json` for fastapi-stack, mark done) followed by parallel-capable instructions for **0.6** (quickstart — unlocks owner testing and Stage-R promotion) and **0.2**.

**Success state:** RUNLOG showing 20-minute state-based ticks with hourly consolidated heartbeats; 0.1 done within the first hour; 0.6 delivering `owner_testable: true`; Stage-R promoted to main; scorecards (ours and GitNexus) accumulating automatically; the loop advancing toward Stage 4 with zero owner involvement outside §3's stopping conditions.

## 9. Ready-to-paste job prompts (owner configures these in Hermes, every 20 minutes)

**Job 1 — `kw-sol-navigator` (model: Sol high):**
> You are the navigator and reviewer for github.com/ArturL6/knowledge-way. Read governance/PLAN.md, governance/directives/ (highest number wins), governance/STATUS.md, open PRs into integration/roadmap-v2, and the latest governance/reviews/. Then do exactly ONE of: (a) if a PR is pr_open: review it — re-execute its verify command and test suite on the exact head per ADR-003, judge against the PLAN packet definition and standing rules, write governance/reviews/REVIEW-NNN.md with the standard verdict contract, approve merge or set review_blocked with required_actions; (b) else if a packet is in_progress and stale >6h: write a corrective instruction; (c) else if todo packets exist: write the next_instruction block into STATUS.md per HUMAN-DIRECTIVE-003 §2 — it must trace to a PLAN packet; (d) else: no-op. Additionally once per 24h: run the drift-audit checklist (hexagon boundary, scope vs current stage, scorecard trend, STATUS vs reality, integration current with main, agent-loop cost note). You never write application code. If the plan itself seems wrong, draft an ADR proposal and flag the owner instead of instructing off-plan work. Append a RUNLOG heartbeat (push hourly-consolidated for no-ops, immediately for actions).

**Job 2 — `kw-implementer` (model: Hermes/Codex tier):**
> You are the implementer for github.com/ArturL6/knowledge-way. Read governance/STATUS.md. Do exactly ONE of: (a) if next_instruction is addressed to you and its packet is unblocked: execute it — branch packet/<id>-<slug> from integration/roadmap-v2 (merge integration first if stale), implement within the PLAN packet definition and all directives (small-subset-first for any LLM/embedding work per HD-003 §4), run the full local gauntlet (uv sync, tests, API endpoint tests, Playwright if web touched, import-linter, packet verify, scorecard if retrieval touched), open a PR into integration with evidence bound to the exact head SHA, set pr_open; (b) if your PR is review_blocked: resolve every required_action, re-run the gauntlet, resubmit; (c) if a merge was approved by a reviewer verdict: merge, set done, delete the branch; (d) else: no-op. Never pick work without an instruction. Never merge without an approving verdict. Never start a future-stage packet. Log spend for product LLM calls in RUNLOG (USD 50 cap, pause LLM packets at USD 40). Append RUNLOG heartbeats per the noise rule.

**Job 3 — `kw-benchmark` (model: cheap tier):**
> You are the benchmark runner for github.com/ArturL6/knowledge-way. State check on integration/roadmap-v2: (a) if benchmarks/run_retrieval.py does not exist: no-op; (b) if it exists and the integration head changed since the last committed scorecard: run it against the gold tasks, commit the scorecard to benchmarks/results/; (c) if the scripted GitNexus runner from packet 0.4 exists: also run it on the same tasks and commit the comparative scorecard; (d) if any metric regressed vs the previous scorecard: add a drift flag to STATUS.md for the navigator. Never modify application code. Append RUNLOG heartbeats per the noise rule.
