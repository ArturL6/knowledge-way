# 10 — Prioritized Roadmap

> Dependency-ordered vertical slices. Each is small enough to land and revert on its own, and
> each names its preconditions, its do-not-touch boundary, its tests, and its release gate.
> Ordering follows §8.5: data loss, scope leak, misleading evidence and cost risk first; then
> UX blockers; then scale, maintainability and comfort.
>
> Nothing here has been implemented. Per §4 this review changed no product code, with one
> exception recorded in `01`: the orphaned-job reaper and the graph symbol picker were ported
> from `main` onto the integration branch at the user's instruction, before the roadmap existed.

## Global preconditions

Before any slice below:

1. **The database cannot be rolled back past `20260809_0008`.** `0008`'s `downgrade` fails with
   `StringDataRightTruncation` on data-bearing tables (`REV-302`). Any rollback plan that
   assumes Alembic can reverse it is wrong; plan restores from a dump instead.
2. **Take a dump before the first migration-bearing slice.** There is no backup procedure
   documented anywhere in the repository. This is itself a gap worth closing.
3. **Confirm the queue is idle** (`StartedJobRegistry` empty, worker `idle`) before touching
   `ingestion.py`, `code_cards.py`, provider config, queue/worker behaviour, the data model or
   migrations. This is §4 and it held for this review; it must hold for each slice too.
4. **`POST /api/repositories/{id}/code-cards` is now live against a real empty table.** One
   anonymous call starts a billable Gemini run over 21 324 symbols. Treat it as armed.

---

## Slice 0 — Contain (hours, no migration, no schema change)

Three unrelated one-liners with outsized effect. Do these before anything else; none depends on
a product decision.

| Item | Change | Fixes |
|---|---|---|
| 0a | Bind the four published ports to `127.0.0.1` in `docker-compose.yml` | `REV-600` blocker, `REV-601`, `REV-602`, `REV-603`, `REV-605` |
| 0b | `db.rollback()` before the failure bookkeeping commit in `ingestion.py` | `REV-500` blocker, `REV-407` |
| 0c | `engine.dispose()` in the work-horse after RQ's `fork()` | `REV-501` |

**Do not touch:** anything else in `ingestion.py`. 0b is a three-line change inside the
`except` block; resist widening it into the atomicity work (Slice 4).

**Tests:** 0b needs a test that raises mid-index and asserts the *previous* index is still
intact — the exact assertion nothing in the suite makes today (`REV-703`). 0c needs a
cross-process test, or at minimum a post-run assertion that `pg_stat_activity` shows no
`idle in transaction` session for the worker.

**Release gate:** `GET /health` from the host still 200; `psql -h 127.0.0.1` still works;
`docker exec … redis-cli PING` works from inside the network and **fails from the LAN**.

**Rollback:** revert the compose file and restart; 0b/0c are pure code reverts.

---

## Slice 1 — Make the re-index cost honest (one additive migration)

Add btree indexes on the four columns referencing `symbols.id`
(`REV-503`, `REV-902`, and the `symbol_edges` pair behind `REV-311`).

**Why first among the perf work:** it is the entire 55 s → 11 m 37 s regression, it is additive,
and it is measurable before and after with data already in the database.

**Precondition:** Slice 0 landed (so a failed migration cannot compound a destructive commit).
Use `CREATE INDEX CONCURRENTLY` outside a transaction, or accept a brief `ACCESS EXCLUSIVE`
window — and set `lock_timeout`, which no migration currently does (`REV-311`).

**Do not touch:** `symbols.id`'s type or generation. Stable logical identity is Slice 5 and a
separate decision.

**Measurement (required, §7):** record full re-index wall-clock before and after on the same
repository and commit. Baseline is `11 m 37 s` for `pydanticAI` @ `640d5171`. Expected to
approach the 55 s first-index cost; **state the measured number, do not claim a ratio.**

**Release gate:** re-index completes; row counts identical to
`2 284 / 21 324 / 136 566 / 22 900`; no new `idle in transaction` sessions.

**Rollback:** `DROP INDEX`. Free.

---

## Slice 2 — Stop the misleading evidence (additive, no migration, no re-index)

The cluster the review ranks highest after the blockers, because it is what makes the product
*wrong* rather than slow. All four parts are additive to responses and UI.

| Item | Change | Fixes |
|---|---|---|
| 2a | Return truncation **cause and counts** from both graph routes (`total_nodes`, `total_edges`, `reason`) | `REV-402`, `REV-421` |
| 2b | Add a hard **edge budget** alongside the node cap; count structural edges against it | `REV-405`, `REV-102`, `REV-414` |
| 2c | Stop shipping full `source_text` on every graph node | `REV-405`, `REV-102` |
| 2d | Replace the `confidence` percentage with a **resolution label**, and delete the "Minimum confidence" filter | `REV-401`, `REV-901`, `REV-415`, `REV-110`, `REV-136` |
| 2e | Count **distinct** relationships, not duplicate edges, in degree ranking and the summary | `REV-423` |

**2d is the highest-leverage single change in the review.** It repairs the premise rather than
the plumbing: three expressions, no migration, no re-index. Verified live that the filter it
removes is a no-op — moving it to 90% changes nothing, because every graph-visible edge is
exactly 100.

**Do not touch:** the resolver itself. Changing *how* edges are resolved changes the embedded
chunks' "Static calls:" headers and implies a billable re-embed — that is Slice 6, gated on a
cost decision.

**Tests:** a truncation test where the cap actually fires (today's fixture has 3 symbols against
`max_nodes=10`, so it never does — `REV-719`); an assertion that a builtin call does **not**
produce a `call` edge to an unrelated method — the review's only "assert the absence of a wrong
edge" gap (`REV-914`).

**Release gate:** a 100-node response reports its true totals; payload for a 100-node subgraph
drops from the measured 3.6 MB; no edge whose endpoint is absent from the node set.

---

## Slice 3 — Fix scope before building anything that needs it (behavioural, no migration)

Push the repository predicate **into SQL, before the `LIMIT`**, in every retrieval modality
(`REV-200`, `REV-502`, `REV-907`, `REV-217`, `REV-515`).

**This gates every workspace slice.** A workspace-scoped search built on today's `search.py`
inherits a filter that runs after truncation, so it would silently return fewer results — or
none — the moment a second repository exists.

**Precondition:** none technically, but see the measurement note: the defect is currently
*invisible* because one repository is indexed. Index a second, small repository first so the
fix can be demonstrated rather than asserted.

**Do not touch:** ranking or fusion semantics. `_fuse` dedupes on location rather than identity
(`REV-218`) — a real bug, but a separate change; conflating them makes the regression
un-bisectable.

**Tests:** the case nothing covers today — two repositories, a term common to both, a scoped
query at a small limit, asserting the scoped result set is non-empty and contains no foreign
rows. `REV-220` records that **no** existing test passes `repository_id` at all.

**Release gate:** with two repositories indexed, scoped `limit=5` returns 5 in-scope hits where
today it returns 0. Add `ORDER BY` at the same time (`REV-204`): six identical queries currently
return six different result sets.

---

## Slice 4 — Decisions that cannot be derived from the code (human, blocking)

No implementation. These block Slices 5–7 and must be answered by a person.

1. **Unassigned-repository policy.** Membership is currently the *absence* of a row; there is no
   `Unassigned` state (`REV-306`). The live repository belongs to nothing: invisible in
   workspace views, visible globally. Options: a real state; a default workspace with backfill;
   or workspace membership becomes mandatory at creation. **`REV-206`/`REV-121`: `POST
   /api/repositories` has no workspace field, so today nothing in the product can attach one.**
2. **Does a declared dependency need an evidence origin?** `WorkspaceDependency` has no field
   recording where a declaration came from (`REV-910`). §3.4 forbids rendering declared
   dependencies as verified `calls`. Without this column the UI cannot honour that distinction
   at all, and the same omission on `SymbolEdge` is what enabled the confidence problem.
3. **Is `symbols.id` a durable citation identity?** It is `uuid4()`, regenerated every index run
   (`REV-404`, `REV-507`). Deep links rot, and the capped node set changes between re-indexes.
   A stable sort key is cheap; stable *logical* identity is a data-model change.
4. **Authentication and tenancy.** Not implemented, and §3.9/§7 forbid presenting workspace
   membership as a substitute. Slice 0a contains the exposure; it does not resolve the question
   of what a principal is.
5. **Re-embed budget.** If edge resolution is corrected (Slice 6), the 22 900 existing chunks
   carry stale "Static calls:" headers. Re-embedding is billable and needs an explicit cap.

---

## Slice 5 — Enforcement (no product change)

| Item | Change | Fixes |
|---|---|---|
| 5a | A CI workflow running the two suites that already pass | `REV-700` blocker |
| 5b | A 6-line `conftest.py` enabling `PRAGMA foreign_keys=ON`, or move DB tests to real Postgres | `REV-702`, `REV-317`, `REV-514` |
| 5c | A web test runner + the first component test over the pure helpers | `REV-701`, `REV-122` |

**Why after Slice 0–3 and not before:** CI that goes green on a suite which cannot observe
`ON DELETE CASCADE` (all 12 declarations are inert under SQLite with FKs off) creates false
confidence. 5b makes 5a worth having. Both are small.

**Release gate:** CI red on a deliberately broken assertion; `DELETE /api/repositories` covered
by a test that actually exercises the cascade.

---

## Slice 6 — Earn the evidence claim (larger, gated on Slice 4)

Only after the decisions above.

- Give `SymbolEdge` a resolver/evidence-origin column and populate it.
- Use the qualifier information the parser already captures and currently **discards**
  (`REV-904`) — name-uniqueness resolution structurally excludes 8 842 of 21 324 symbols
  (41.5%, including all 380 `__init__`).
- Restore the unchanged-file skip that integration removed (`REV-507`, `REV-905`), so `sync`
  stops being a full destructive rewrite, and only then talk about git-diff delta indexing.
- Publish atomic index generations instead of mutating live rows (`REV-520`).

**Cost note:** correcting resolution invalidates the embedded chunks' call headers. Budget the
re-embed explicitly or accept documented staleness — do not let it happen implicitly.

---

## Slice 7 — Workspace-first, for real (gated on Slices 3 and 4)

Only once scope is server-derived and the Unassigned policy is decided.

1. Atomic create-repository-in-workspace (`REV-206`).
2. Workspace switcher, membership management, dependency management — the 13 API operations that
   today have zero clients (`REV-100`, `REV-909`).
3. A genuinely workspace-scoped discovery path, with **one global deterministic node/edge
   budget**, never `N × max_nodes` stitched client-side (§3.3).
4. A workspace overview showing repositories and `declared_dependency` edges only, visually
   distinct from verified relationships (§3.4).

**Do not claim** inferred cross-repository code edges, a single workspace commit, or tenant
isolation (§7). A workspace is a commit *vector*, one per member repository.

---

## Adjacent quick wins, unordered

Independent of the above, each small and self-contained:

- `select(File.id, File.path)` in `GET /tree` — removes ~160 ms of ~170 ms (`REV-223`).
- Push the direction predicate into SQL for `/callers` and `/callees` — a 52 MB, 2.4 s response
  for a symbol with no callers (`REV-203`, `REV-604`).
- Escape `%` and `_` in `tree?path=` (`REV-211`, wildcard injection fabricating entries).
- Validate `repository_id` in `POST /api/chat` — currently an FK violation surfacing as a
  `500 text/plain` (`REV-202`).
- Clear `indexing_progress` on completion — a `ready` repository permanently displays
  "finalizing · 2284 files" (`REV-105`).
- Adopt `next/link`: every navigation is currently a full document load that destroys search
  results, graph state and the entire chat transcript (`REV-113`).
- Correct the three documentation claims that assert controls which do not exist — the
  prompt-injection defence, enforced authorization, and incremental sync (`REV-609`, `REV-610`,
  `REV-512`). These are what a future coding agent will trust.
- Add `response_model` to the routes, starting with the graph pair: 38 of 42 operations publish
  `{}` as their response schema, so any field rename is an undetectable breaking change
  (`REV-205`, `REV-714`).
