# HUMAN-DIRECTIVE-001 — Final decisions (no open inputs)

**From:** Project owner
**To:** implementer-run (Hermes) and reviewer-run (Sol high)
**Authority:** Owner directive. It does NOT amend PLAN.md by itself — the implementer converts it into ADR-004 and STATUS changes via the normal governance flow (§5). PLAN change control (ADR-003) stays fully in force.
**Goal, unchanged:** evidence-backed multi-repo project intelligence that measurably reduces a coding agent's exploratory work — proven by the Stage 0 harness and Stage 4 ablation.
**Scope emphasis of this directive: RUNNING software over hardening.** Prefer the smallest thing that works and is measured. Ops/hardening work is descoped where noted. The owner wants the application locally runnable and testable early.

---

## 1. Benchmark workspace — DECIDED

**Primary workspace `fastapi-stack` (Stages 0–2), all public, no credentials needed:**

| Repo | Role | Why |
|---|---|---|
| `github.com/fastapi/fastapi` | consumer | imports/depends on both others → real cross-repo package + import edges |
| `github.com/encode/starlette` | provider (framework) | already validated by the repository-card POC |
| `github.com/pydantic/pydantic` | provider (models) | second DEPENDS_ON edge; rich symbol graph |

All-Python, small enough for fast reindex loops, densely interlinked, huge issue/PR history for gold tasks.

**Secondary pair, added at Stage 3 when the HTTP-contract extractor lands (packet 3.2):**

| Repo | Role |
|---|---|
| `github.com/PostHog/posthog` | Python backend providing HTTP API |
| `github.com/PostHog/posthog-js` | TypeScript client consuming that API → real cross-repo `CONSUMES_API` + TS parsing coverage |

Do not index the PostHog pair before Stage 3 (size costs iteration speed earlier).

**Gold tasks (packet 0.2) — mechanical, no owner bottleneck:** mine 25–40 closed issues from fastapi/starlette/pydantic that were resolved by a merged PR. Gold labels are **derived from the fix PR itself**: gold files/symbols = what the fix actually changed; tests = tests the fix touched; description = the issue text (not the PR). Sol validates a random sample of 10 against the source PRs; owner review is optional, not blocking.

## 2. LLM, embeddings, budget — DECIDED

- **Embeddings:** OpenRouter, `openai/text-embedding-3-small` (the existing settings default; 1536 dims via the existing OpenRouter provider). `EMBEDDING_PROVIDER=openrouter`.
- **Cards:** OpenRouter with the existing configured default card model. `CODE_CARD_PROVIDER=openrouter`.
- **Rerank:** `RERANK_PROVIDER=none` until packet 1.8 measures a scorecard delta that pays for it.
- **Provider switching:** the existing OpenRouter/Vertex adapter is sufficient — no new provider work. Changing the embedding provider or model later requires an ADR including the full re-embed cost (dimensions change).
- **Budget cap: 50 USD/month** across all jobs. Implementer appends cumulative estimated spend to RUNLOG each tick that calls an LLM; at 80% (40 USD), pause LLM-consuming packets, continue deterministic ones, flag the owner in STATUS `drift_flags`.

## 3. Local testing milestone — NEW, DECIDED

The owner will test the application locally. Two packets:

- **Packet 0.6 — Local quickstart v1** (Stage 0, unblocked immediately): one documented path from clean checkout to a usable system: `.env.example` (with `EMBEDDING_PROVIDER=none` as the keyless default — everything except semantic search must work with zero keys), `docker compose up`, one seed command that registers the `fastapi-stack` workspace and indexes all three repos, README-QUICKSTART.md with the exact commands and the URLs (API docs + Next.js UI). Verify: a scripted clean-machine run (fresh clone → commands → `curl` search returns results → Playwright smoke passes against it).
- **Quickstart refresh at every stage promotion:** from now on, a stage-exit verdict requires the quickstart script to still pass on the promoted integration head. Local testability becomes a permanent invariant, not a one-off.

## 4. Scope decisions (running > hardening)

1. **Main write policy:** main is frozen for feature work; only stage promotions + labeled `hotfix/*` (merged back into integration within one tick). The current 33-commit lead is legacy: new packet **R.7a — sync origin/main into integration** runs first, before Stage R exit promotion. Full gauntlet after; test count must grow back (~80) — deleted-not-migrated tests are drift.
2. **Descoped until after the Stage 4 verdict:** packet 5.4 (ops/auth/logging hardening), Zoekt (5.2), SCIP (5.3), Stage 6 UI expansion beyond what the quickstart needs. The existing Next.js UI is kept working (Playwright smoke) but not extended.
3. **Kept fully in scope:** Stage 0 (measurement), Stage 1 (retrieval solidity — this is the core of "running well"), Stage 2 (graph honesty), Stage 3 (cross-repo extraction), Stage 4 (impact + ablation), incremental indexing basics (5.1) since local testing needs tolerable reindex times.
4. **Reliability outranks breadth; cadence stays 2-hourly;** conflict-heavy tasks (R.7a) don't start with a partial session budget — plan in STATUS, execute next tick.
5. **GitNexus (0.4):** run the CLI locally on the `fastapi-stack` repos — core indexing/graph/search evaluation needs **no API keys**; only its chat-agent answers use BYOK via the existing OpenRouter key. Concepts yes, code never (PolyForm Noncommercial).
6. **Test-count ratchet** and **GitNexus parity table at Stage 4 exit** as previously directed.

## 5. Processing instructions

**Implementer, next tick:**
1. Commit this file to `governance/directives/HUMAN-DIRECTIVE-001.md`.
2. Create **ADR-004 — Ratify HUMAN-DIRECTIVE-001** covering §1–§4 (workspace choice, provider/budget, quickstart invariant, main policy, descopes).
3. STATUS.md: add **R.7a** (blocks stage-exit promotion); add Stage 0 packets **0.1 (prefilled from §1 — mark done once corpora.json is committed), 0.2, 0.3, 0.4, 0.5, 0.6** with §1/§3 definitions; record the §2 env decisions in `.env.example`.
4. Execute R.7a, then Stage R exit: run all stageR checks + quickstart script, reviewer issues the stage-exit verdict, promote integration → main.
5. Proceed into Stage 0 in packet order. 0.6 may run in parallel with 0.2–0.5.

**Reviewer:** verify ADR-004 matches this directive verbatim in substance; enforce the quickstart-passes-at-promotion rule and the test-count ratchet from now on; treat any hardening work in descoped areas (§4.2) as scope drift.

**Both:** conflicts between this directive and PLAN invariants are flagged and blocked, never silently resolved.
