# Knowledge-Way — session handoff (2026-08-15)

You are taking over an **autonomous multi-agent build loop** on `github.com/ArturL6/knowledge-way`
(local checkout `/home/artur/Desktop/Projekte/knowledge-way`, working branch
`integration/roadmap-v2`). The human is the project **owner**; you act as **navigator + reviewer**
(strongest model) and spawn subagents as **implementer** (sonnet, high effort) and **merger**
(sonnet, low). The repo's `governance/` dir is the source of truth — read `governance/STATUS.md`,
`governance/PLAN.md`, `governance/directives/HUMAN-DIRECTIVE-00X.md` (highest number wins),
`governance/decisions/ADR-00X.md`, and `governance/reviews/REVIEW-0NN.md` first.

The original mission + rules are in `docs/KNOWLEDGE-WAY-HANDOFF.md` (repo). This doc only covers
**what changed this session and what's next** — don't re-read what's already in artifacts.

## Loop mechanics that WORK (reuse these)
- Navigator (you): write ADR/HD + `next_instruction` in STATUS → commit on integration → spawn implementer.
- Implementer subagent → branch `packet/<id>-<slug>`, PR into integration, never force-push.
- Reviewer (you): checkout the **exact PR head (detached)**, re-execute gauntlet, write `REVIEW-0NN.md`
  (verdict on_track|blocked), `on_track` = merge authorization per HD-004 (GitHub approval is NOT a gate).
- Merger: `gh pr merge <n> --merge --delete-branch`, set STATUS packet `done` + `integration_merge`,
  append `governance/operations/RUNLOG-*.md`. (I ended up doing merges inline to avoid collisions — fine.)

## CRITICAL operational lessons (do not repeat my mistakes)
1. **Never run >1 git-mutating subagent on the shared checkout at once.** They `git checkout`/`reset --hard`
   and clobber each other (it corrupted my local `integration` pointer once; recovered via
   `git reset --hard origin/integration/roadmap-v2`). Serialize, or require each agent to use an isolated
   `git worktree`. Review PR heads in **detached HEAD**, not by moving the integration branch.
2. **UI packets MUST have real-API E2E, not mocked-only Playwright** — mocked E2E passed while real
   workspace/graph bugs shipped. See memory `web-packets-need-real-api-e2e.md`.
3. **Disk filled to 100% once** (crashed Postgres mid-embed). Keep an eye on `df -h /`; `docker builder prune -f`
   reclaims the most. Currently ~20G free.
4. Subagents tend to **background long ops and stop mid-task** — instruct them to run long steps in the
   FOREGROUND with blocking `until` loops and report in-turn.

## Metric progress (the point of the project)
Gold-task file hit@5 on the pinned fastapi-stack (25 tasks): **0.16 → 0.68 hybrid** this session.
- baseline 0.16 → FTS (1.1) 0.32 → semantic (1.3) 0.60 → **weighted RRF (1.5) hybrid 0.68**
- 0.68 **beats the Stage-1 target 0.44 and the GitNexus reference 0.44**; `hybrid ≥ every mode` now holds.
- Scorecards: `benchmarks/results/2026-08-15-*` (semantic-enabled `...-114f062.json`, weighted-rrf `...-cc84891.json`).

## Merged this session (see STATUS + reviews for detail)
1.1 Postgres FTS · 1.3 pgvector ANN (HNSW) · 1.5 weighted RRF (`app/domain/retrieval.py`) ·
1.9 workspace+graph UI · 1.9a UI bug fixes. Governance: HD-007/008, ADR-007/008/009, REVIEW-053..059.

## Vertex / embeddings (money-sensitive — owner said "don't spend too much")
- Vertex verified: `governance/operations/vertex-readiness.md`. Project `ai-tinker-lab`,
  `text-embedding-005` @768. ADC lives at **`~/.gcloud-kw/application_default_credentials.json`**
  (NOT `~/.config/gcloud`, which is root-owned/empty). For Docker, override the api+worker volume to
  `${HOME}/.gcloud-kw:/root/.config/gcloud:ro`, set `EMBEDDING_PROVIDER=vertex`,
  `VERTEX_PROJECT_ID=ai-tinker-lab`.
- Full-corpus embed (~19,147 chunks) costs ~$0.46–0.79 (owner-approved once). Embeddings are
  hash-gated (reindex to same SHA = no re-spend). Total session spend ~$1–1.5. Cap $50/mo, pause at $40.
- **Owner's strategic asks (open, high-value):** (a) add a **local ONNX code-embedding model**
  provider (kills Vertex cost, keyless — like GitNexus) — needs a new ADR superseding ADR-004/005's
  Vertex-only mandate; (b) **packet 1.4** = embed **code cards** (compact units) instead of raw chunks
  (denser, cheaper, GitNexus's actual winning trick). `providers.py` has a clean `EmbeddingProvider`
  Protocol to add a local impl.

## Stage-1 remaining (exit criteria in PLAN.md)
- ✅ hybrid ≥ 0.44 and ≥ every single mode (0.68) — DONE
- ⬜ **p95 hybrid ≤ 1s** — currently ~3.5s. Levers: packet **1.2** (symbol-search hardening; the ILIKE
  symbol pass dominates hybrid latency) + tuning the RRF candidate window.
- ⬜ **exact/quoted hit@1 ≥ 0.9** — not yet measured/tuned (exact mode currently 0.0; pg_trgm path exists).
- Also pending: packet **1.6** (query planner), **1.7** (hierarchical), **1.8** (rerank eval), and Stage-0
  formality **0.5** (benchmark cron).

## Known pre-existing bugs to file (found, not yet fixed)
- `docker-compose.yml` worker command `python -m app.worker` is a **dead shim** (the `__main__` guard is in
  the wrong module). Real entrypoint: `python -m app.adapters.outbound.rq_jobs.worker`. Ephemeral stacks
  had to override `command:`. Worth a small fix packet.

## Live state right now
- Integration head: `c27ca74` (all above merged). Only open PR is stale **#55** (old benchmark branch —
  navigator should triage/close).
- **UI stack rebuilding/seeding on the fixed code**: new URL **http://127.0.0.1:46291** (API :39671),
  keyless (lexical+graph+workspaces work; semantic does NOT in this keyless UI). Seeding the 3 pinned repos
  ran in background (`scratchpad/seed4.log`) — verify all 3 `ready` + a workspace exists, or re-seed via the
  API pattern (POST /api/repositories → reindex to pinned SHA → PUT into a workspace). NOTE: seed scripts
  auto-created a `fastapi-stack` workspace before; a repo can only be in ONE workspace (409), so don't let a
  default workspace hoard all repos or the user can't populate a new one.
- GitNexus external benchmark: isolated at `/home/artur/external-benchmarks/comparator/` (OWNER-REPORT.md);
  corpora/install were deleted to save disk. Governance boundary HD-007: GitNexus is inspiration/benchmark
  ONLY, never in the repo.

## Immediate next steps (suggested)
1. Confirm the rebuilt UI (46291) is seeded + usable; hand the owner the URL. (Owner has been frustrated by
   UI churn — a stable working UI is a priority.)
2. Ask the owner: pursue the **local-embedding-model ADR + packet 1.4 (card embeddings)** now (their idea,
   cheaper) vs. push Stage-1 **latency** (packet 1.2). Both are queued.
3. Open design question for owner: keep **one-workspace-per-repo** (current, UX now honest about it) vs allow
   **multi-membership** (small backend change).

## Suggested skills
- **ponytail** (`ponytail:ponytail`) — active all session; keep solutions minimal (e.g. don't build a custom
  embedding model when a small off-the-shelf/local one suffices — YAGNI).
- **code-review** / **review** — for reviewing packet PRs at exact head (you are the reviewer).
- **diagnose** — for the latency work (p95 hybrid 3.5s → ≤1s) and any regressions.
- Do NOT need workflow/ultracode unless the owner asks.

## Memory (persisted, auto-loaded)
`backlog-execution-contract`, `product-north-star`, `external-comparator-benchmark`,
`web-packets-need-real-api-e2e` (in `~/.claude/projects/-home-artur-Desktop-Projekte-knowledge-way/memory/`).
