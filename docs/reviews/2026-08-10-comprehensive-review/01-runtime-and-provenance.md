# 01 — Runtime and Provenance

> Established per §8.1 of `docs/CODING_AGENT_COMPREHENSIVE_REVIEW_PROGRAM.md` **before** any
> workstream started. This file is also the shared brief handed to every review subagent.

## Review timestamp

`2026-08-10` (session local date). All wall-clock times below are container-local
(`Europe/Berlin` host, UTC in Postgres columns).

## Two distinct targets — do not conflate them

This review has a **static target** and a **live target**, and they are not the same code.
Every finding must state which one it was observed against.

| | Static review target | Live runtime target |
|---|---|---|
| Ref | `origin/integration/consolidated-verified` | `main` + uncommitted working-tree changes |
| Commit | `c122529` (`docs: add comprehensive coding-agent review program`) | `5aedeb3` + 7 uncommitted files |
| Location | read-only detached worktree (scratchpad) | `/home/artur/Desktop/Projekte/knowledge-way` |
| Alembic head in code | `20260809_0008` | `20260808_0004` |
| Alembic head in database | — | `20260808_0004` (verified by query) |
| `code_cards.py`, `structural_cards.py` | present | **absent** |

`main` is the merge-base: `git merge-base main origin/integration/consolidated-verified`
= `5aedeb38d84` = `main` HEAD. The integration branch is therefore strictly ahead by 15
commits — `3340 insertions(+), 127 deletions(-)` across 52 files.

**Consequence for evidence levels:** the running stack cannot verify integration-branch
behaviour. Anything observed in the browser or via `curl` against `localhost` is evidence
about `main`, not about `c122529`. Files that differ between the two — and therefore where
live evidence does **not** transfer — are:

```text
apps/api/app/{main,config,ingestion,models,providers,search}.py
apps/web/app/graph/{graph-explorer,graph-canvas,page}.tsx
apps/web/app/graph/graph-model.ts                     (integration only)
apps/web/app/repositories/[repositoryId]/symbols/[symbolId]/page.tsx  (integration only)
apps/web/app/search/search-client.tsx
apps/web/app/chat/chat-client.tsx
```

## Uncommitted working-tree state on `main`

These changes are live in the running containers and are **not** on the integration branch.
They were made earlier in this session to fix two production defects:

```text
 M apps/api/app/config.py                  indexing_job_timeout = 3600
 M apps/api/app/main.py                    job_timeout= on enqueue; reconciler wiring
 M apps/api/app/worker.py                  reconcile on worker boot
 M apps/web/app/globals.css                graph picker styles
 M apps/web/app/graph/graph-explorer.tsx   repo + symbol pickers
 M apps/web/app/graph/page.tsx             server-side repository fetch
?? apps/api/app/reconcile.py               orphaned-job reaper (new file)
```

Their status on `integration/consolidated-verified` differs per defect — verified by
`git grep`, not assumed:

- **RQ job timeout — already fixed there, independently and differently.** Integration has
  `index_job_timeout: int = 1_800` (`config.py:37`) applied as
  `Queue(..., default_timeout=settings.index_job_timeout)` (`main.py:50`, `main.py:183`).
  The working-tree fix on `main` uses a different name (`indexing_job_timeout`), a different
  value (`3_600`) and a different mechanism (per-`enqueue` `job_timeout=`). Same defect, two
  independent fixes — a merge will need one of them dropped. Note 1 800 s clears the
  measured 697 s full re-index, but with less headroom.
- **Orphaned-job reaper — still absent there.** No `reconcile` symbol exists anywhere under
  `apps/api` on the integration branch, so a killed work-horse still leaves the repository
  `indexing` forever. This is an open defect on the review target, not a duplicate.

Similarly, integration's graph page already carries a repository `<select>`, `?repository=`
/ `?symbol=` deep links, a bounded repository overview and a symbol deep-link page — but
still requires a **raw symbol UUID typed into a text input**. The working-tree symbol-search
picker addresses that gap; the repository dropdown duplicates existing work.

Five of the six modified files therefore collide with integration's own newer versions
(`config.py` 17+/1-, `main.py` 113+/9-, `globals.css` 2+/1-, `graph-explorer.tsx` 46+/24-,
`graph/page.tsx` 2+/1-). Only `worker.py` and the new `reconcile.py` apply cleanly.

## Billable-work safety gate (§4)

Checked before the review began. **No billable or long-running work was in flight**, so the
review was cleared to proceed.

```text
indexing queue depth ......... 0
StartedJobRegistry ........... []            (no job executing)
FailedJobRegistry ............ 2 job ids     (both from this session, diagnosed below)
workers ...................... 1, state=idle, current_job=None
queues ....................... ['indexing']  (only one queue exists)
```

No code-card or embedding queue exists in the live deployment: `code_cards.py` is not on
`main`, and the database has no `code_cards` / `structural_cards` table (head is `0004`).
Therefore **no provider spend was at risk** during this review, and none was incurred.

## Database state

Alembic head in database: `20260808_0004`. Twelve tables:

```text
alembic_version  code_chunks  conversations  files  indexing_jobs  messages
repositories  symbol_edges  symbols  workspace_dependencies  workspace_repositories  workspaces
```

Row counts at review time:

| Table | Rows |
|---|---|
| repositories | 1 |
| **workspaces** | **0** |
| workspace_repositories | 0 (implied — no workspaces) |
| workspace_dependencies | 0 (implied — no workspaces) |
| files | 2 284 |
| symbols | 21 324 |
| code_chunks | 22 900 |
| symbol_edges | 136 566 |
| indexing_jobs | 4 |

The single repository:

```text
id                        21ffa409-9e13-493a-b919-7bb6a5b80bb9
name                      pydanticAI
clone_url                 https://github.com/pydantic/pydantic-ai   (public, no credentials)
indexed_branch            main
indexed_commit_sha        640d5171fe5795e58553b5af414cbcac3e0c7673
latest_detected_commit    640d5171fe5795e58553b5af414cbcac3e0c7673
indexing_status           ready
last_indexed_at           2026-08-10T11:49:38
```

**`workspaces` is empty.** No workspace has ever been created in this deployment — there is
no UI path to create one. Workspace behaviour therefore cannot be exercised in the browser
at all; workspace findings are necessarily `source-reviewed` or API-level.

## Indexing job history — all four rows explained

```text
8c6ddf6e  ready   11:29:07 → 11:30:02  (55s)     initial index, succeeded
5767f63f  failed  11:30:02 → 11:37:36            killed by RQ's 180s default job_timeout
cf074b18  ready   11:38:00 → 11:49:38  (11m37s)  re-index after job_timeout fix
c3807649  failed  11:50:26 → 11:51:28            deliberate SIGKILL, reaper verification
```

Rows 2 and 4 are diagnostic artifacts of this session, not spontaneous failures. Row 2 is
the original defect (a full re-index takes 11m37s against a 180s ceiling). Row 4 was an
intentional work-horse kill to prove the reaper flips orphaned rows to `failed`.

Note `indexing_jobs.status` uses `'ready'` for success — the *repository* status vocabulary
reused for *jobs*. Flagged for the data-model workstream.

## Container provenance

```text
api      started 2026-08-10T11:45:49Z   image 317dd3700097
web      started 2026-08-10T11:45:49Z   image 8a7aca735684
worker   started 2026-08-10T11:50:01Z   image fa9dd1255d05
postgres started 2026-08-10T11:26:32Z   pgvector/pgvector:pg16
redis    started 2026-08-10T11:26:32Z
```

Compose project `knowledge-way`, host ports `3000` (web), `8000` (api), `5432`, `6379`.
A separate `trellis-*` compose project was stopped earlier this session to free those
ports; it remains stopped.

Reachability confirmed: `GET /health` → 200, `GET :3000/` → 200, `GET :3000/graph` → 200.
Note the health route is `/health`, **not** `/api/health`.

## Code size

Small enough for exhaustive review, not sampling.

```text
apps/api/app    1 628 LOC across 13 modules   (main.py 347, ingestion.py 241,
                                               providers.py 215, code_cards.py 213)
apps/web         543 LOC across 17 files
API surface       42 routes on 1 FastAPI app object
```

## Untracked artifacts excluded from review

- `data/repositories/21ffa409-.../` — the **cloned pydantic-ai working copy** (~2 284 files).
  This is indexed payload, not project source. It is excluded from all findings. Any agent
  grepping the tree must exclude `data/`.
- `.env` — read for key *names* only; all values were redacted before display and no secret
  value appears in any review artifact.

## AMENDMENT — the runtime changed mid-review (recorded ~14:35)

Everything above describes the state the review **started** from, and is the state every
workstream's evidence was gathered against. It no longer describes the running stack. Three
changes landed while agents were in flight; all are recorded here rather than quietly
corrected, because several findings cite the pre-change state as fact.

**1. The working directory moved from `main` to `integration/consolidated-verified`.**
At the user's instruction, a local branch `integration/consolidated-verified` was created
tracking origin at `c122529`, and the session's uncommitted `main` fixes were ported onto it
selectively (see below). `main`'s versions of those files are preserved in
`git stash@{0}` plus a patch under the session scratchpad. The pinned read-only worktree at
`c122529` was untouched throughout and remains the correct static reference.

**2. The live database was migrated `20260808_0004` → `20260809_0008`.**
A sibling agent session added a `migrate` service to `docker-compose.yml`
(`alembic -c alembic.ini upgrade head`) and made `api` and `worker` depend on it via
`service_completed_successfully`, then restarted the stack. Because the checkout is now
integration, `head` resolved to `0008` and all four pending revisions applied.

This was not planned by this review and contradicts the §4 boundary stated above. Verified
consequences, measured after the fact:

```text
alembic_version            20260809_0008
new tables                 code_cards, structural_cards   (14 tables total, was 12)
symbol_edges.target_name   character varying(512) → text (unbounded)   [0008]
repositories 1 · files 2 284 · symbols 21 324 · symbol_edges 136 566   (all preserved)
```

No data was lost. This independently confirms workstream C's finding REV-319 — that
`0005`–`0008` are metadata-only and do not rewrite edge, embedding or card data — in
production rather than in a scratch database.

It also makes workstream C's **REV-302 live**: `0008`'s `downgrade` fails with
`StringDataRightTruncation` on data-bearing tables, so this database can no longer be
returned to `0004` by Alembic. Running `main` against it would fail
`verify_migration_ready()` at API startup. The deployment is now committed to the integration
lineage — which matches the user's intent, but by accident rather than by decision.

**3. The stack was rebuilt and restarted.** Six services, all healthy:
`postgres`, `redis`, `migrate` (exited 0), `api`, `worker`, `web`. `GET /health` → 200,
`GET :3000/graph` → 200. `apps/web/Dockerfile` `CMD` changed to
`node .next/standalone/server.js`, and `.dockerignore` files were added to both apps.
The running `api` image now contains `app/reconcile.py` and four `reconcile_indexing_jobs`
call sites — so the reaper is live for the first time on this branch.

### Citing the pre-rebuild frontend correctly

The frontend running before the 14:28 rebuild was **byte-identical to `git stash@{0}`**, not to
`5aedeb3`. `5aedeb3` is `main`'s committed tip and lacks the symbol picker entirely, so it is the
wrong ref for "what was running earlier" — the containers were built from `main` *plus* the seven
uncommitted files now preserved in that stash. Any finding that needs the earlier frontend should
cite `git show 'stash@{0}:apps/web/…'`. (Orchestrator guidance issued mid-review named `5aedeb3`
for this; that was imprecise and the browser workstream corrected it.)

### Playwright MCP could not launch on this machine

Recorded per §8.7. `@playwright/mcp` 0.0.79 defaults to the `chrome` channel, whose Linux path is
hard-coded to `/opt/google/chrome/chrome`; Google Chrome is not installed and installing it needs
root. Playwright's own bundled Chromium **is** present
(`~/.cache/ms-playwright/chromium-1223`).

Browser evidence in this review was therefore obtained by driving the same engine directly — the
MCP's bundled `playwright-core` with an explicit `executablePath` — which is why the 25 browser
findings legitimately carry `browser E2E verified`. Stated limits: Chromium only, headless, and an
ARIA tree rather than a real assistive technology, so accessibility findings are indicative and
not a substitute for AT testing.

Two independent passes used this route (the browser workstream and the orchestrator's own
verification of the ported picker), and they agree where they overlap.

### Evidence-integrity impact

- Findings labelled `PostgreSQL integration-tested` or `manual live acceptance` that were
  gathered **before** this amendment describe schema `0004`. Workstreams C, F and B fall in
  this window. Their findings remain valid as statements about `0004` and about the source at
  `c122529`; they should not be re-read as statements about the current database.
- Workstream C's confirmation that it left the live database untouched was accurate when
  written. The migration came from a different session, not from any review agent.
- Any workstream still running when this was recorded (A, D, E, browser) may have observed
  either schema. Their reports should be read with that ambiguity noted.

### Fixes ported from `main` onto the integration branch

Carried across (genuinely missing on integration):

- `apps/api/app/reconcile.py` — the orphaned-job reaper, new file, unchanged.
- `apps/api/app/worker.py` — reconcile on worker boot.
- `apps/api/app/main.py` — reconciler wiring at startup, on `GET /api/repositories`, and on
  `GET /api/repositories/{id}/status`. Dependencies verified present on this branch:
  `SessionLocal`, `IndexingJob.{status,started_at,finished_at,error_message}`, and
  `ingestion.py:190` setting `status='running'`.
- `apps/web/app/graph/graph-explorer.tsx` — symbol-search picker replacing the raw symbol
  UUID input (§2 / §3.2 gap), plus surfacing the API's `truncated` flag, which the frontend
  previously ignored on both `/subgraph` and `/graph`.
- `apps/web/app/globals.css` — styles for the picker.

Deliberately **not** carried across:

- The `indexing_job_timeout = 3_600` fix. Integration already solves the same defect with
  `index_job_timeout = 1_800` applied as `Queue(default_timeout=...)`. Keeping both would
  have been two mechanisms for one bug.
- The graph repository dropdown, node-kind colour fix and depth clamp. Integration already
  has all three, and its `graph-model.ts` handles node kinds better (dedicated colours per
  kind rather than a single fallback).

Verified after porting: `python3 -m py_compile` clean on all three API files; `docker compose
build web` passed Next's type check; and the full picker chain resolved live —
`RunContext` → class → 100 nodes / 211 edges / `truncated=true`, `toolset` → 38 / 94.

## Scope executed

Nine read-only subagents, one per workstream (§5 A–G) plus a live browser pass and a
concept/efficiency critique. Each wrote its own report; the orchestrator deduplicated and
built `00-executive-summary.md`, `09-findings-register.md`, `10-prioritized-roadmap.md`.

## Not assessed

- **Provider-backed paths end to end.** No OpenRouter / Vertex / Gemini call was made
  (§4 cost gate, no approval). All provider findings are `source-reviewed`.
- **Integration-branch runtime.** Not built or run; the stack was left on `main` lineage
  rather than migrating the live database to `0008`, which would have been an irreversible
  schema change during an analysis-only mandate.
- **Alembic downgrade paths.** Not executed against live Postgres (destructive).
- **Multi-repository and multi-workspace behaviour.** One repository, zero workspaces
  present; adding more would have triggered billable/long indexing work.
