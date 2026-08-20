# HUMAN-DIRECTIVE-009 — Full restart of the autonomous loop (self-contained)

**From:** Project owner · **Date:** 2026-08-20
**To:** the three scheduled agents (navigator/reviewer, implementer, benchmark runner)
**Authority:** Owner directive. Ratify as the next ADR via the normal flow (§7). This file is deliberately **self-explanatory**: a fresh agent needs only this file + the repo. Where this snapshot and the repo disagree, the repo wins (`governance/STATUS.md`, directives — highest number wins, reviews).
**Repo:** `github.com/ArturL6/knowledge-way`, working branch `integration/roadmap-v2`.

---

## 1. The mission (unchanged)

Build an **evidence-backed multi-repository software knowledge index**: workspaces of interacting repos indexed into lexical + symbol + graph + semantic layers; every answer carries exact evidence (file, lines, commit SHA), confidence AND completeness. Progress is **measured, never demoed**:

- **Retrieval metric:** file hit@5 / MRR on the 25 gold tasks (real fix-PRs from fastapi/starlette/pydantic, pinned in `benchmarks/corpora.json`).
- **Final proof (Stage 4):** ablation — a coding agent solves historical tasks with measurably fewer tool calls using our MCP tools vs grep-only vs the GitNexus reference.

## 2. Where we are (verified 2026-08-20)

**Metric story:** baseline **0.16** → FTS (packet 1.1) **0.32** → Vertex semantic (1.3, pgvector HNSW) **0.60** → weighted RRF (1.5) → **hybrid 0.68**, beating the Stage-1 target (0.44) and the GitNexus reference (0.44); `hybrid ≥ every single mode` holds. Scorecards in `benchmarks/results/2026-08-15-*`.

**Done:** all of Stage R (governance loop, hexagonal restructure, import-linter, evidence table, keyless quickstart, first promotion to main); Stage 0 packets 0.1–0.4 + 0.6; Stage 1 packets 1.1, 1.3, 1.5, 1.9, 1.9a. Vertex verified (`governance/operations/vertex-readiness.md`; project `ai-tinker-lab`, `text-embedding-005` @768; ADC at `~/.gcloud-kw/application_default_credentials.json` — mount as `${HOME}/.gcloud-kw:/root/.config/gcloud:ro` for Docker). ~19k chunks embedded, hash-gated (same-SHA reindex = no re-spend). Product-LLM spend ≈ $1.50 of the $50 cap. `owner_testable: true`.

**Idle:** navigator + implementer silent since 2026-08-15; `next_instruction` empty; only the benchmark cron still ticks — **keyless**, so its latest scorecards (hybrid 0.24) understate the real system. The loop is parked, not broken.

**Known issues on file:** stale PR **#55** (old benchmark branch — close unmerged); `docker-compose.yml` worker command `python -m app.worker` is a dead shim (real entrypoint `python -m app.adapters.outbound.rq_jobs.worker`); hybrid p95 latency ~3.5s.

## 3. Owner decisions (binding, resolve all open questions)

1. **Sequencing:** finish Stage 1's measurable exit criteria first — **packet 1.2** (latency) then **1.2b** (exact-mode tuning, defined below) — before any new capability work.
2. **Local embedding model — approved as a measured experiment, not a leap.** Create **ADR-010** amending the Vertex-only mandate (ADR-004/005): packet **1.4** evaluates a small local/ONNX code-embedding provider behind the existing `EmbeddingProvider` Protocol, **subset-first**, head-to-head vs Vertex on the 25 tasks. **Adopt only if** hybrid hit@5 with the local model is within **0.05 absolute** of the Vertex result; adoption = full re-embed + new binding baseline recorded in the ADR. Until then, **Vertex remains the binding corpus**. 1.4 additionally embeds **cards (compact units)** alongside/instead of raw chunks, measured the same way.
3. **Workspace membership:** keep **one-workspace-per-repo** (current, UX is honest about it). Revisit multi-membership after Stage 4 only if the ablation shows a need.
4. **Benchmark scoring:** the **binding scorecard is semantic-enabled** — the benchmark job gets the Vertex mount + env (§2). A keyless run may additionally be recorded, clearly labeled `keyless`, as the quickstart-experience metric; it never gates anything.
5. **Housekeeping is authorized now:** close PR #55 unmerged; fix the worker-shim compose bug as micro-packet **1.0x**; both are case-(c)/instruction work, no ceremony.
6. **Budget unchanged:** $50/month product-LLM cap, pause at $40, spend logged in RUNLOG. Agent-loop costs excluded.

## 4. Consolidated binding rules (from HD-001..008 + ADRs; violations = drift)

1. **Merge gate:** a PR merges when a `REVIEW-NNN.md` with `verdict: on_track` exists at the PR's **current exact head SHA**. GitHub review approval is impossible (single account) and is never requested or waited for.
2. **Reviewer re-execution:** every review re-runs the packet verify + test suite + import-linter on the exact head (detached checkout). Implementer-committed output alone never suffices. CI stays advisory; never add hosted CI.
3. **Change control:** PLAN.md changes require an ADR in the same PR. Owner decisions bind **only** as numbered directives in `governance/directives/`; decisions heard elsewhere → flag `awaiting_directive`, never enforce or implement.
4. **Branching:** `main` frozen except stage promotions (+`hotfix/*` merged back within one tick). Packets: `packet/<id>-<slug>` from/into `integration/roadmap-v2`. **No history rewriting, no force pushes of any kind** — remediation = new commits, or fresh `-v2` branch + new PR with the old one closed unmerged. Navigator verdict "close without merge" → implementer closes it as housekeeping.
5. **Shared files:** packet branches never touch `STATUS.md` or `RUNLOG-*.md`; state transitions/heartbeats are committed directly on integration by the acting job; RUNLOGs are per-job, merge=union, no-ops consolidated hourly.
6. **Git isolation (operational lesson):** never run more than one git-mutating agent on a shared checkout — serialize, or give each agent its own `git worktree`. Review PR heads in **detached HEAD**, never by moving the integration pointer. Long operations run in the **foreground** with blocking waits, reported in-turn. Watch disk (`df -h /`); `docker builder prune -f` reclaims most.
7. **Evidence rules (PLAN standing):** no edge without evidence; confidence ≠ completeness; every answer carries snapshot identity; deterministic before LLM; test-count ratchet (currently ~95+ API tests — decreases without a migration note = drift).
8. **Retrieval discipline:** every retrieval-touching packet ships a **hermetic scorecard delta** (ephemeral worktree at exact SHA → own stack → seed pinned corpora SHAs → verify served manifest == pinned → score → teardown). Regressions block merge.
9. **UI discipline (operational lesson):** web packets require **real-API Playwright E2E**, not mocked-only; the keyless quickstart (`scripts/quickstart_smoke.sh`, `EMBEDDING_PROVIDER=none`) must pass at every stage promotion.
10. **LLM/embedding discipline:** subset-first (≤200 files / ≤500 chunks / ≤50 cards with committed samples + cost extrapolation) before any full run; one provider+model per binding corpus (currently Vertex `text-embedding-005`@768); creds missing → pause + flag, never silently fall back.
11. **GitNexus boundary:** PolyForm Noncommercial — inspiration and external benchmark **only**; never a dependency, subprocess, vendored code, or Docker component of the product; runtime-installed in isolated benchmark environments only; findings reach product work through ADRs; any product-side reference = immediate drift. Not legal advice; commercial use triggers counsel review.
12. **Scope:** reliability > breadth; running > hardening. Ops hardening, Zoekt, SCIP, UI expansion beyond fixes, code-quality platforms stay descoped until after the Stage 4 verdict.

## 5. The work queue (exact order; each item = one packet, one branch, one PR)

1. **1.0x — housekeeping:** fix the compose worker entrypoint; close PR #55 unmerged. Verify: worker starts via `docker compose up` without command overrides; quickstart smoke passes.
2. **1.2 — hybrid latency p95 3.5s → ≤1s:** the ILIKE symbol pass dominates — replace with indexed exact/prefix `qualified_name` matching + trigram fallback; tune the RRF candidate window; measure with the hermetic harness (latency fields already in scorecards). Exit: p95 ≤ 1s with hit@5 not regressing below 0.68.
3. **1.2b — exact/quoted mode:** route quoted strings + identifier-shaped queries to the pg_trgm/exact path; target exact-mode hit@1 ≥ 0.9 on identifier queries (add a small identifier-query task subset to the harness for this — derived from gold symbols, committed like other tasks).
4. **ADR-010 + 1.4 — card embeddings + local-model evaluation** per §3.2 (subset-first, head-to-head, 0.05 tolerance).
5. **1.6 — query planner** (deterministic routing rules; LLM fallback routes only), **1.7 — hierarchical retrieval** (repo/module cards constrain symbol/chunk scope), **1.8 — rerank evaluation** (keep only if the scorecard pays for the latency).
6. **0.5 — formalize the benchmark cron** (it already runs; document contract + semantic-enabled env per §3.4).
7. **Stage 1 exit:** all PLAN exit criteria + quickstart pass → stage-exit review → **promotion to main**.
8. **Stage 2** (graph honesty: completeness end-to-end, resolution improvements, callers/references MCP tools, graph expansion in retrieval — benchmark GitNexus's `epistemic` field for parity), then **Stage 3** (extracted cross-repo edges; PostHog pair joins), then **Stage 4** (impact + ablation + GitNexus parity table → owner go/no-go).

## 6. Job contracts — paste each into a scheduled job, every 20 minutes

**Job 1 — `kw-navigator` (strongest model):**
> You are the navigator and sole reviewer for github.com/ArturL6/knowledge-way (branch integration/roadmap-v2). First read: governance/directives/ (highest number wins — HUMAN-DIRECTIVE-009 is the restart order and contains the work queue), governance/STATUS.md, governance/PLAN.md, open PRs, latest governance/reviews/. Each tick do exactly ONE of: (a) a PR is pr_open → check out its exact head DETACHED in your own git worktree, re-execute the packet verify + test suite + import-linter yourself, judge against the PLAN packet + HD-009 rules, write governance/reviews/REVIEW-NNN.md (verdict on_track|drift|blocked, criteria_checked, required_actions, reviewed head SHA); on_track = merge authorization — GitHub approval is never requested; (b) a packet is in_progress and stale >6h → corrective instruction; (c) no open PR and queue items remain → write next_instruction into STATUS.md for the next HD-009 §5 queue item (issued_by, issued_at, packet, objective, constraints, done_when), committed directly on integration; (d) nothing actionable → no-op heartbeat. Every 24h: drift audit (hexagon boundary via import-linter, scope vs §4.12, scorecard trend, STATUS vs reality, GitNexus absent from product paths, disk space, spend). You never write application code, never force-push, never enforce uncommitted owner decisions (flag awaiting_directive). Heartbeats → governance/operations/RUNLOG-navigator.md (no-ops consolidated hourly).

**Job 2 — `kw-implementer` (strong coding model):**
> You are the implementer for github.com/ArturL6/knowledge-way. Read governance/STATUS.md and governance/directives/ (highest number wins; HD-009 §5 is the work queue, §4 the rules). Work in your OWN git worktree; never run concurrently with another git-mutating agent on a shared checkout; run long operations in the foreground and report in-turn. Each tick do exactly ONE of: (a) next_instruction addressed to you, packet unblocked → branch packet/<id>-<slug> from integration (merge integration in if stale — never rebase, never force-push), implement strictly within the packet + rules (subset-first for LLM/embedding work; Vertex is the binding embedding corpus, ADC mount per HD-009 §2; packet branches never touch STATUS/RUNLOG; web changes need real-API Playwright E2E; no GitNexus in product paths), run the full gauntlet (uv sync, pytest — ratchet holds, API endpoint tests, Playwright if web touched, import-linter, packet verify, hermetic scorecard if retrieval touched), open a PR with evidence bound to the exact head SHA, set pr_open via a direct integration commit; (b) your PR is review_blocked → resolve every required_action as new commits (or fresh -v2 branch + new PR, closing the old unmerged), re-run gauntlet, request exact-head re-review; (c) an on_track review exists at your PR's current head → merge, set done, delete branch; also close any PR verdict-marked "close without merge"; (d) nothing addressed to you → no-op heartbeat. Log product-LLM spend in RUNLOG ($50 cap, pause at $40). Never start future-stage packets, never merge without the gate, never add hosted CI. Heartbeats → governance/operations/RUNLOG-implementer.md.

**Job 3 — `kw-benchmark` (cheap model):**
> You are the benchmark runner for github.com/ArturL6/knowledge-way. Each tick, state check on integration/roadmap-v2: (a) integration head unchanged since the last committed scorecard → no-op heartbeat; (b) changed → HERMETIC run: ephemeral worktree at the exact SHA, provision your OWN stack via scripts/quickstart_smoke.sh --keep-running with the semantic-enabled env (EMBEDDING_PROVIDER=vertex, VERTEX_PROJECT_ID=ai-tinker-lab, ADC volume ${HOME}/.gcloud-kw:/root/.config/gcloud:ro) — embeddings are hash-gated so same-SHA seeding costs ~$0; seed the pinned benchmarks/corpora.json SHAs, verify served snapshot manifest equals the pinned manifest (mismatch after self-provisioning = drift flag; never score a mismatched or pre-existing server), run the 25-task scorecard, commit to benchmarks/results/ labeled semantic-enabled, tear down. Optionally also record a clearly-labeled keyless run (non-binding). (c) any binding metric regressed vs the previous semantic-enabled scorecard → add a drift flag to STATUS.md. Never modify application code; GitNexus, if ever run, only in this isolated environment. Heartbeats → governance/operations/RUNLOG-benchmark.md.

## 7. Bootstrap sequence (first hour after the owner creates the jobs)

1. **Implementer tick 1:** commit this file to `governance/directives/HUMAN-DIRECTIVE-009.md`; create the ratifying ADR; append a RUNLOG line announcing the restart. No other work this tick.
2. **Navigator tick 1:** verify the ADR matches; reconcile STATUS with reality (mark 1.1/1.3/1.5/1.9/1.9a done if not already; add queue items 1.0x, 1.2, 1.2b, 1.4, 1.6–1.8, 0.5 as packets); issue `next_instruction: packet 1.0x`.
3. **Loop resumes:** 1.0x lands within a few ticks, then 1.2 — the first scorecard with p95 latency movement is the signal that the machine is truly back.
4. **Owner involvement thereafter:** ADR-010 adoption sign-off (one message, after 1.4's measured comparison), Stage-1 exit acknowledgment, Stage-4 go/no-go. Weekly ~10 min: latest drift audit + scorecard trend.

**Success state:** three RUNLOGs ticking; 1.0x and 1.2 merged; binding semantic-enabled scorecards flowing again (hybrid ≥ 0.68, p95 trending to ≤1s); the queue advancing toward Stage-1 exit and promotion — fully automatic, owner needed only at the named gates.
