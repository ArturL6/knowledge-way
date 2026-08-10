# 00 — Executive Summary

## What was reviewed

| | |
|---|---|
| Static target | `origin/integration/consolidated-verified` @ **`c122529`**, in a pinned read-only worktree |
| Live target at start | `main` @ `5aedeb3` + 7 uncommitted files, database at Alembic `20260808_0004` |
| Live target at end | `integration` + working-tree edits, database at **`20260809_0008`** (migrated mid-review, see `01`) |
| Date | 2026-08-10 |
| Code size | `apps/api` 1 628 LOC / 13 modules · `apps/web` 638 LOC / 17 files · 42 API routes |
| Corpus | 1 repository (`pydanticAI`), 2 284 files, 21 324 symbols, 136 566 edges, 22 900 chunks, **0 workspaces** |
| Method | 9 read-only subagents, one per §5 workstream plus a live browser pass and a concept critique |
| Provider spend | **none** — no provider call, no indexing run, no code-card run |

Full provenance, including the two unplanned mid-review changes, is in
`01-runtime-and-provenance.md`. Read that before citing any live measurement, because the
runtime moved underneath the review and each finding is labelled by era.

## Counts

**213 findings** across all nine workstreams.

| Severity | blocker | critical | high | medium | low | info |
|---|---|---|---|---|---|---|
| | 4 | 16 | 70 | 87 | 29 | 7 |

| Category | Count | | Evidence level | Count |
|---|---|---|---|---|
| `DESIGN_GAP` | 65 | | source-reviewed | 83 |
| `CORRECTNESS_RISK` | 36 | | PostgreSQL integration-tested | 46 |
| `BUG_CONFIRMED` | 33 | | manual live acceptance | 30 |
| `TEST_GAP` | 27 | | unit/API-tested | 28 |
| `PERFORMANCE_RISK` | 16 | | **browser E2E verified** | **25** |
| `DOCUMENTATION_GAP` | 13 | | documented only / pending | 1 |
| `SECURITY_RISK` | 11 | | **provider E2E verified** | **0** |
| `OPTIMIZATION_OPPORTUNITY` | 6 | | | |
| `BUG_SUSPECTED` | 3 | | | |

Three things to keep honest about this table:

1. **The largest evidence bucket is `source-reviewed`** — reasoned claims about code, not
   observed behaviour. Per §7 they must not be reported as verified.
2. **`provider E2E verified` is zero, by design.** No provider path was executed. Every claim
   about embeddings, code cards or reranking is source-reviewed only.
3. **The 25 `browser E2E verified` findings are real browser observations, but not regression
   tests.** Ad-hoc agent observation does not become coverage; there is still no web test
   runner (`REV-701`). They also span two builds — the stack was rebuilt mid-review — so each
   is labelled by era.

`213` overstates the number of distinct problems. **13 duplicate clusters absorb 68 IDs** —
the same defect found independently by up to eight workstreams. The register (`09`) leads with
those clusters; they are the correct unit of work.

## Top 5 risks

1. **`REV-600` — unauthenticated Redis on `0.0.0.0:6379` + RQ's pickle serializer is remote code
   execution as root** in the `worker` container, which holds the PostgreSQL superuser DSN, a
   read-write host bind mount, and (on integration) the operator's Google ADC. `blocker`,
   `manual live acceptance`. One line of compose to fix.
2. **`REV-500` — a failed index job commits its own destructive rewrite.** There is no
   `rollback()` before the `except` block's bookkeeping commit, so the *common* failure path
   publishes a half-deleted index under a `failed` status. Proven by test. This session's
   earlier "the data survived a SIGKILL" observation was misleading: SIGKILL is the only
   failure mode that skips that block. `blocker`, ~3 lines.
3. **Cluster C2 — the graph's edges are not evidence.** Edge resolution matches a bare callee
   name across the whole repository with no import, scope or receiver information, then stamps
   `confidence = 100`. Roughly 4 400 edges bind Python builtin calls (`any`, `set`, `append`)
   to unrelated methods, and the UI draws them as the thickest, most confident lines. This
   inverts the platform's core promise, and it is already baked into the 22 900 embedded
   chunks — so a correct fix implies a billable re-embed. `critical`.
4. **Cluster C1 — repository scope is a Python post-filter applied after the SQL `LIMIT`.**
   Every retrieval modality truncates candidates in the database, then filters by repository
   in process. Measured: a scoped query returning 0 hits where the same scope at a higher limit
   returns matches. It fails *closed*, so it looks like an empty index rather than a bug. It is
   invisible today only because one repository is indexed, and it blocks workspace-scoped
   search outright. `critical`.
5. **Cluster C6 — truncation is a bare boolean with no cause and no counts, and there is no
   edge budget at all.** A "bounded" 100-node overview returned **7 952 edges and 3.6 MB**;
   `Agent`'s depth-2 neighbourhood is 3 220 symbols reduced to 100, selected
   codepoint-alphabetically, so 97 of the 100 are pytest methods. The shape the user reads is
   an artefact of the cap. `critical`.

## Top 5 safe improvements

Cheap, additive, low-risk, and each one measurably worth doing.

1. **Bind the four published ports to `127.0.0.1`.** Two lines of compose, no code, no
   migration. Collapses most of workstream F's severity, including `REV-600` and `REV-601`.
2. **Add four btree indexes on the columns referencing `symbols.id`.** One additive migration.
   This *is* the 12.7× re-index regression (55 s → 11 m 37 s): each symbol delete currently
   triggers four sequential scans. The mid-review migration handed us an in-schema control —
   `code_cards.symbol_id`, indexed via its UNIQUE constraint, resolves the same predicate in
   0.014 ms against 10–20 ms for the four unindexed ones.
3. **Return `select(File.id, File.path)` in `GET /tree`.** One line; removes ~160 ms of ~170 ms
   by not detoasting 76 MB of file content for a 2 117-byte response.
4. **Add truncation cause and counts to both graph responses, and an edge budget.** Purely
   additive to the payload; turns a misleading boolean into usable evidence.
5. **Add a CI workflow.** There is none on either branch, and the two commands needed already
   pass (integration API 50 tests, MCP 10). Until this exists, every other finding is advisory.

A sixth, nearly free: **delete the "Minimum confidence" filter.** Verified live on the current
build that moving it to 90% changes nothing at all — every graph-visible edge is exactly 100.
It is a control over a fabrication.

## Confirmed bugs vs suspected risks vs design gaps

Kept separate deliberately, because they carry different obligations.

- **`BUG_CONFIRMED` (30)** — reproduced or proven from source. Includes the post-`LIMIT` scope
  filter, the embedding cache that misses 100% of the time (stored by `content_hash`, looked up
  by document hash), `LIMIT` without `ORDER BY` returning six different result sets for six
  identical queries, and `LIKE` wildcard injection through `tree?path=`.
- **`BUG_SUSPECTED` (3)** — plausible with a stated hypothesis, not reproduced. Chiefly the
  absence of any `AbortController`, which makes a superseded async result renderable.
- **`DESIGN_GAP` (50)** — the capability was never built, so there is nothing to fix, only to
  decide and then build. Workspace-first is the whole story here: 13 workspace API operations
  have **zero** clients (`grep -rin workspace apps/web/` returns nothing), and
  `POST /api/repositories` has no workspace field, so even a workspace switcher shipped
  tomorrow could not put a repository into a workspace.

Design gaps must not be counted as regressions, and confirmed bugs must not be deferred as
design questions. The register marks each explicitly.

## Already addressed on the working branch — do not schedule twice

Four findings were fixed while the review was running, by the branch port recorded in `01` and by
a sibling session. Each was **re-verified live in a browser against the rebuilt stack** after the
fact, so this list is observed, not assumed. The findings themselves stand as written — they were
true of `c122529` and of what was deployed when observed — but the roadmap must not re-bill them.

| Finding | Status | Live re-verification |
|---|---|---|
| `REV-800`, `REV-403`, `REV-137` — any filter change permanently zeroes the graph | **fixed** | Relationship filter set to `call` → 35 nodes, canvas intact. Cause was `d3-force` mutating `link.source` from an id into a node object; `linkEndpointId` normalises it. |
| `REV-106`, `REV-410` — a raw symbol UUID was the only route to a focused subgraph | **fixed** | 0 inputs demanding a UUID; searching `RunContext` returned 15 hits with `path:line`, resolving to a class. |
| `REV-101`, `REV-402` (frontend half) — `truncated` returned by the API and discarded by the UI | **partly fixed** | Summary bar now reads `100 nodes · 211 relationships · truncated at the node cap`. **The API half is unchanged** — still no cause and no counts, which is the larger part. |
| `REV-135` — inverted button `type` attributes made Enter trigger "Focus symbol" | **fixed** | Enter in the form now runs the symbol search; "Focus symbol" is an explicit `type="button"`. |

Also fixed, and not carrying a finding ID because it was diagnosed before the review began: a
killed work-horse left the repository `indexing` forever, because RQ calls `handle_job_failure`
directly for a killed work-horse and never runs `on_failure` callbacks. A reconciler now reaps
orphaned `running` rows. It ships with **no test** (`REV-703`), and its `except Exception:
return 0` means a permanently broken reaper is indistinguishable from an idle one.

Explicitly **not** fixed, despite being adjacent: `REV-405`/`REV-803` (no edge budget — a
100-node overview still returns 7 952 edges and 3.6 MB), `REV-415`/`REV-804` (the confidence
filter is still a live no-op), and `REV-105`/`REV-819` (a `ready` repository still displays
"finalizing · 2284 files").

And one **regression the branch move introduced**, in the opposite direction: `REV-813`. On the
current build, `/graph` shows "The selected filters returned no connected nodes. Adjust filters or
load the fixture demo." *before anything has been loaded* — blaming filters the user never
touched. This is integration's own empty state, which the `main`-lineage build did not have; the
selective port carried the picker across but not `main`'s neutral empty prompt. It is a one-line
conditional distinguishing "nothing requested yet" from "filters excluded everything", and it is
left unfixed here only because this review is report-only.

## Decision recommendation

**`critical fix first`, then `needs product decision`.**

Not `report accepted`: two `blocker` findings are live, and one of them (`REV-600`) is a
one-line fix guarding root-level code execution. Not `safe UX slice` first either — the
tempting slice is the workspace shell, and it is provably premature: with no workspace field on
repository creation and no server-side scope derivation, a workspace switcher would produce a
workspace that cannot contain anything, built on a search layer that cannot scope a query.

Sequence:

1. **Contain (hours).** Rebind the ports; add the missing `rollback()`; add the four FK indexes.
   All three are small, reversible, and independently valuable.
2. **Stop the misleading evidence (days).** Truncation counts and an edge budget; stop
   rendering a uniqueness artefact as confidence. Additive, no migration, no re-index.
3. **Decide (human, blocking).** The Unassigned-repository policy and the workspace contract.
   This gates every workspace slice and cannot be resolved from the code.
4. **Then build**, in the order set out in `10-prioritized-roadmap.md`.

`blocked by active provider job` does **not** apply: the queue was empty and the worker idle
throughout, and no billable work was started. Note however that
`POST /api/repositories/{id}/code-cards` is now backed by a real (empty) table on a deployed
image — a single anonymous call would start a billable Gemini run over 21 324 symbols.

## Not assessed

- **Provider-backed paths end to end.** No OpenRouter / Vertex / Gemini / Cohere call was made.
- **Alembic downgrade against real data.** Proven to fail for `0008` on data-bearing tables in
  a scratch database; not attempted on the live one, which is now past that revision and
  therefore **cannot be returned to `0004` by Alembic**.
- **Multi-repository and multi-workspace behaviour.** One repository, zero workspaces. Several
  critical findings (C1 above especially) are latent precisely because of this, and would
  become user-visible on the second repository.
- **Automated browser regression testing.** A browser pass was performed and is real evidence,
  but ad-hoc agent observation is not a regression test. There is still no web test runner of
  any kind.

## Report index

| File | Workstream | Findings |
|---|---|---|
| `01-runtime-and-provenance.md` | Provenance, safety gates, mid-review amendment | — |
| `02-product-and-ux.md` | A — Product, UX, information architecture | 39 |
| `03-api-and-scope.md` | B — API, contract, scope | 27 |
| `04-data-model-and-migrations.md` | C — Data model, migrations, integrity | 20 |
| `05-graph-and-evidence.md` | D — Graph and evidence | 23 |
| `06-indexing-retrieval-providers.md` | E — Indexing, retrieval, providers, cost | 21 |
| `07-security-and-operations.md` | F — Security, permissions, operations | 20 |
| `08-test-and-e2e-gap-analysis.md` | G — Test strategy and E2E gaps | 23 |
| `08b-browser-e2e-observations.md` | Live browser pass | 25 |
| `09b-concept-and-efficiency-critique.md` | Concept coherence and efficiency | 15 |
| `09-findings-register.md` | Consolidated register + duplicate clusters | 213 |
| `10-prioritized-roadmap.md` | Dependency-ordered slices | — |
| `evidence/` | Sanitized screenshots | 44 files |

## Is the concept itself problematic?

The user asked this directly, so it is answered directly.

**The concept is sound; the evidence layer under it currently is not.** The thesis — every
claim traceable to repository, file, line and commit — is the right one, and the primary design
document is honest about what is and is not built. The problem is a three-way mismatch between
what the documents claim, what the schema can store, and what the data actually contains, and
it lands exactly on the thesis: the graph is a name-collision index whose most confident-looking
claims are its most fabricated, and `SymbolEdge` has no column in which to record how an edge
was resolved.

**Workspace-first is the right primitive, and it is currently bolted on.** Not because the
model is wrong, but because retrieval has no server-side scope pushdown and the dependency
table has no evidence-origin field — so the layer cannot yet carry the product's own roadmap.

**The efficiency problems are real, boring and cheap.** Unindexed foreign keys, no text index,
an unbounded vector query, full-table graph loads. None is architectural. Contrast that with
the confidence semantics, which are.
