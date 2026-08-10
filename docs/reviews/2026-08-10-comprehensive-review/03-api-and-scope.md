# 03 — API, Contract and Scope Analysis

> Workstream §5.B. Static target `origin/integration/consolidated-verified` = `c122529`
> (read-only worktree). Live target = `main` lineage at alembic head `0004`.
> Provenance, safety gates and exclusions are established in `01-runtime-and-provenance.md`
> and are not restated here.

## Summary

`apps/api/app/main.py` (347 LOC) mounts **42 route operations** on one `FastAPI` object
(`grep -oE '^@app\.(get|post|put|patch|delete)' apps/api/app/main.py | wc -l` = 42; the
`/openapi.json` operation count from an isolated `TestClient` is also 42). There is **no
router split, no dependency layer, no response model and no authentication**.

Three things are true simultaneously and must not be conflated:

1. **Repository-level scope is real and consistently applied** to symbol, edge and graph
   reads. `scoped_symbol` / `scoped_edges` / `scoped_symbols` / `scoped_files`
   (`main.py:56-62`) each carry a `repository_id` predicate *and* a redundant Python
   re-check. A symbol id from repository B requested under repository A returns
   `404 Symbol not found` — verified, not assumed.
2. **Workspace-level scope is essentially not implemented.** Exactly one code path derives a
   permitted repository set server-side: `validate_dependency_membership`
   (`main.py:45-48`). Every other route — tree, file, symbol, callers, callees, subgraph,
   graph, search, chat, jobs, conversations, status, reindex, delete — takes a
   repository/file/symbol/job/conversation id straight from the client and never consults
   `workspace_repositories`. Invariant §3.1 is therefore satisfied for dependency
   declarations and for nothing else.
3. **The one scope filter the API does expose is applied in the wrong place.** The
   `repository_id` narrowing in `search.py` runs in Python **after** the SQL `LIMIT`. A
   repository-scoped query can return **zero** results while the same unscoped query returns
   hits. This is reproduced below (REV-200) and is the highest-severity finding in this
   workstream.

Beyond scope: no route declares a `response_model`, so **38 of 42 operations publish an
empty `{}` JSON schema** in OpenAPI, and `404` / `409` / `503` — all of which the code
raises — appear in **no** OpenAPI operation. Repository creation and workspace assignment are
two independent transactions with no linking parameter, so every repository is born
unassigned. And `enqueue()` swallows every exception, so `POST /api/repositories` answers
`202 Accepted` with `job_id: null` when Redis is unreachable, leaving a committed row stuck
in `pending`.

Contract drift across the three clients is significant: the web client makes **zero**
workspace calls on either branch (`grep -rin workspace apps/web/` → no matches), and the MCP
client accepts a search `mode` the API does not implement (`lexical`, which silently returns
0 results) while rejecting two it does (`text`, `exact`).

### How evidence was produced

| Channel | What it establishes | Safety |
|---|---|---|
| Static read of `main.py`, `search.py`, `db.py`, `models.py`, `config.py`, `git_auth.py` | `source-reviewed` claims | read-only worktree |
| `docker run --rm --network none -v <worktree>/apps/api:/src:ro … knowledge-way-api:latest` with `DATABASE_URL=sqlite://` | `unit/API-tested` claims against the **static target** | no network, in-memory SQLite, `PRAGMA foreign_keys=ON` to mirror PostgreSQL FK enforcement; no live row touched, no provider call possible |
| `curl` GETs + expected-rejection requests against `localhost:8000` | `manual live acceptance` claims about **`main`** | GET-only plus 404/422-expected probes; nothing mutating |
| `docker compose exec -T postgres psql … SELECT` | corpus sizing and query plans | read-only SQL |
| `pytest` in the same isolated container | test-suite state | `50 passed` in 1.23 s, all SQLite/in-memory, `--network none` |

Probe scripts live in the session scratchpad (`probe_scope.py`, `probe_atomicity.py`,
`probe_graph.py`); they are **not** added to the repository.

---

## Route-by-route scope table

Line numbers are `apps/api/app/main.py` on the static target. "WS scope" = does the route
derive the permitted repository set from `workspace_repositories`?

| # | Operation | Lines | Id validation | Repo scope | WS scope | Foreign id | Missing id |
|---|---|---|---|---|---|---|---|
| 1 | `GET /health` | 72-73 | — | — | — | — | — |
| 2 | `GET /api/workspaces` | 74-75 | — | — | n/a | — | `[]` |
| 3 | `POST /api/workspaces` | 76-78 | body `WorkspaceIn` | — | n/a | — | — |
| 4 | `GET /api/workspaces/{ws}` | 79-83 | none (str) | — | n/a | n/a | 404 `Workspace not found` |
| 5 | `PATCH /api/workspaces/{ws}` | 84-89 | body `WorkspaceUpdate` | — | n/a | n/a | 404 |
| 6 | `DELETE /api/workspaces/{ws}` | 90-94 | none | — | n/a | n/a | 404 |
| 7 | `GET /api/workspaces/{ws}/dependencies` | 95-98 | none | — | **yes** (`workspace_id ==`) | not listed | 404 |
| 8 | `POST /api/workspaces/{ws}/dependencies` | 99-106 | body | — | **yes** (`validate_dependency_membership`) | **422** `must both belong to this workspace` | 404 ws |
| 9 | `PATCH …/dependencies/{dep}` | 107-114 | body | — | **yes** (composite `where`) | 404 `Dependency not found` | 404 |
| 10 | `DELETE …/dependencies/{dep}` | 115-119 | none | — | **yes** (composite `where`) | 404 | 404 |
| 11 | `GET /api/workspaces/{ws}/repositories` | 120-124 | none | — | **yes** (join) | not listed | 404 |
| 12 | `PUT /api/workspaces/{ws}/repositories/{repo}` | 125-140 | none | repo exists | **yes** (exclusivity) | 409 `already belongs to another workspace` | 404 |
| 13 | `POST` same path | 126 | duplicate decorator on the same handler | | | | |
| 14 | `DELETE /api/workspaces/{ws}/repositories/{repo}` | 141-146 | none | — | **yes** | 404 `not a member of this workspace` | 404 |
| 15 | `GET /api/repositories` | 147-148 | — | — | **no** — global list | — | `[]` |
| 16 | `POST /api/repositories` | 149-153 | body + `validate_clone_url` | — | **no** — no `workspace_id` field | — | 422 |
| 17 | `GET /api/repositories/{repo}` | 154-158 | none | exists | **no** | n/a | 404 |
| 18 | `DELETE /api/repositories/{repo}` | 159-163 | none | exists | **no** | n/a | 404 |
| 19 | `POST /api/repositories/{repo}/sync` | 164-167 | none | exists | **no** | n/a | 404 |
| 20 | `POST /api/repositories/{repo}/reindex` | 168-173 | body optional | exists | **no** | n/a | 404 |
| 21 | `GET /api/repositories/{repo}/status` | 174-178 | none | exists | **no** | n/a | 404 |
| 22 | `POST /api/repositories/{repo}/code-cards` | 179-185 | body `CodeCardRunIn` | exists | **no** | n/a | 404, else 409/503 |
| 23 | `GET /api/repositories/{repo}/symbols/{sym}/code-card` | 186-191 | none | **yes** via `scoped_symbol` | **no** | 404 `Symbol not found` | 404 — **no repo check first** |
| 24 | `GET /api/repositories/{repo}/structural-cards` | 192-201 | `limit` bounded, `kind` set-checked | exists + `repository_id ==` | **no** | n/a | 404 / 422 bad kind |
| 25 | `GET /api/repositories/{repo}/structural-cards/{kind}` | 202-206 | **`kind` not set-checked here** | `repository_id ==` | **no** | n/a | 404 `Structural card not found` — **no repo check** |
| 26 | `GET /api/repositories/{repo}/tree` | 207-215 | none; `path` interpolated into `LIKE` | exists + `repository_id ==` | **no** | n/a | 404 repo / `[]` path |
| 27 | `GET /api/files/{file}` | 216-220 | none | **none** — global by id | **no** | n/a | 404 |
| 28 | `GET /api/files/{file}/symbols` | 221-222 | none | **none** — global by id | **no** | n/a | **200 `[]`** |
| 29 | `GET /api/repositories/{repo}/symbols/{sym}` | 223-226 | none | **yes** | **no** | 404 | 404 |
| 30 | `GET …/symbols/{sym}/callers` | 237-238 | none | **yes** | **no** | 404 | 404 |
| 31 | `GET …/symbols/{sym}/callees` | 239-240 | none | **yes** | **no** | 404 | 404 |
| 32 | `GET …/symbols/{sym}/subgraph` | 241-261 | `depth` 1-2, `max_nodes` 1-100 | **yes** | **no** | 404 | 404 |
| 33 | `GET /api/repositories/{repo}/graph` | 262-295 | `max_nodes` 10-100 | **yes** | **no** | n/a | 404 |
| 34 | `GET /api/search` | 296-300 | `q` required; `mode` unvalidated; `limit` silently clamped | `repository_id` **after** SQL `LIMIT` | **no** | 404 for unknown `repository_id` | — |
| 35 | `GET /api/search/symbols` | 301-302 | `q` only — **no `repository_id`, no `limit`** | **none** | **no** | n/a | — |
| 36 | `POST /api/search/semantic` | 303-306 | **`body: dict`** — no schema at all | **none** | **no** | n/a | — |
| 37 | `POST /api/explanations` | 307-313 | body `ExplanationIn` | exists + post-`LIMIT` filter | **no** | 404 | 404 |
| 38 | `POST /api/documentation/generate` | 314-327 | body `DocumentationIn` | **yes** | **no** | 404 | 404 |
| 39 | `POST /api/chat` | 328-336 | body `ChatIn` | **`repository_id` never validated** | **no** | **500** (FK) | **500** |
| 40 | `GET /api/jobs/{job}` | 337-341 | none | **none** — global by id | **no** | n/a | 404 |
| 41 | `GET /api/conversations` | 342-343 | — | **none** — global list | **no** | — | `[]` |
| 42 | `GET /api/conversations/{conv}` | 344-347 | none | **none** — global by id | **no** | n/a | 404 |

Reproduction of the "WS scope: no" column (isolated in-memory SQLite, static target;
`repo-b` deliberately belongs to **no** workspace):

```text
1a workspace members: ['repo-a']
1b dependency on non-member repo-b -> status: 422
   detail: Source and target repositories must both belong to this workspace
2a GET /api/repositories (global list, no workspace filter): ['repo-b', 'repo-a']
2b GET /api/repositories/repo-b/graph  (repo-b is in NO workspace): 200
2c GET /api/repositories/repo-b/tree:                                200
2d GET /api/repositories/repo-b/symbols/sb-000:                      200
3a repo-a + symbol from repo-b -> status: 404   ("Symbol not found")
4a GET /api/files/file-b (repo-b, outside every workspace) -> 200, body contains repo-b content
4b GET /api/files/file-b/symbols -> 200 objects
4c GET /api/files/<nonexistent>/symbols -> [200, []]
```

---

## Findings

| ID | Category | Severity | One-line |
|---|---|---|---|
| REV-200 | BUG_CONFIRMED | critical | `repository_id` scope filter runs in Python **after** the SQL `LIMIT`; a scoped search can return 0 hits while unscoped returns hits |
| REV-201 | DESIGN_GAP | critical | Invariant §3.1 unimplemented outside dependency declarations — no workspace-scoped read path exists on any route |
| REV-202 | BUG_CONFIRMED | high | `POST /api/chat` never validates `repository_id`; unknown id → FK violation → `500 text/plain` |
| REV-203 | PERFORMANCE_RISK | high | `/callers` `/callees` `/subgraph` `/graph` materialise the whole `symbol_edges` table with no `LIMIT`; measured 2.4 s floor and a 52 MB unpaginated response |
| REV-204 | BUG_CONFIRMED | high | Retrieval candidate `SELECT`s have `LIMIT` without `ORDER BY`; six identical `/api/search` calls returned six different result sets |
| REV-205 | DESIGN_GAP | high | No `response_model` anywhere: 38/42 operations publish an empty `{}` 2xx schema and OpenAPI documents no 404/409/503 |
| REV-206 | DESIGN_GAP | high | Repository creation and workspace assignment are two unlinked transactions; `RepositoryIn` has no `workspace_id`, so every repository is born unassigned |
| REV-207 | BUG_CONFIRMED | high | `enqueue()` swallows every exception → `202 Accepted` with `job_id: null` and a committed row stuck in `pending` |
| REV-208 | BUG_CONFIRMED | high | `graph-explorer.tsx` asserts in a comment that `repo:` narrows before the limit; it does not — the symbol picker finds nothing for the selected repository in a multi-repo deployment |
| REV-209 | BUG_CONFIRMED | medium | MCP accepts search `mode="lexical"`, which the API does not implement → 0 results; MCP rejects `text`/`exact`, which the API supports |
| REV-210 | CORRECTNESS_RISK | medium | `/api/files/{id}` and `/api/files/{id}/symbols` have no repository or workspace gate; the latter answers `200 []` for a nonexistent file |
| REV-211 | BUG_CONFIRMED | medium | `tree?path=` is interpolated into `LIKE` unescaped → wildcard injection fabricates directory entries |
| REV-212 | CORRECTNESS_RISK | medium | `DELETE /api/repositories/{id}` succeeds while `indexing_status='indexing'` with no `409` guard |
| REV-213 | CORRECTNESS_RISK | medium | `/graph` returns two incompatible edge shapes and two incompatible node shapes in one array, and overloads `confidence` |
| REV-214 | CORRECTNESS_RISK | medium | `conversation_id` continuation is not ownership-checked — a repo-B question is appended to a repo-A conversation |
| REV-215 | DESIGN_GAP | medium | `mode` unvalidated (bogus mode → `200` empty) and `limit` silently clamped while OpenAPI declares it unbounded |
| REV-216 | DESIGN_GAP | medium | `POST /api/search/semantic` takes `body: dict` — no schema, no repository scope, no limit |
| REV-217 | DESIGN_GAP | medium | `GET /api/search/symbols` exposes only `q`: no `repository_id`, no `limit`, hard-coded 30 |
| REV-218 | BUG_CONFIRMED | medium | `_fuse` dedupes on `(type, file_id, start_line, end_line)` instead of row identity, collapsing distinct results |
| REV-219 | DESIGN_GAP | medium | Unhandled exceptions surface as `500 text/plain "Internal Server Error"` with no request id — stable but untraceable |
| REV-220 | TEST_GAP | high | 17 of 42 operations have zero test coverage; **no** test asserts repository scoping in search |
| REV-221 | CORRECTNESS_RISK | medium | The documented `409` for a duplicate dependency declaration is unreachable when `package_name`/`import_path` are `NULL` |
| REV-222 | DESIGN_GAP | medium | Web client and MCP client share no workspace contract with the API; the Next rewrite proxies every route verbatim |
| REV-223 | PERFORMANCE_RISK | medium | `GET /tree` detoasts 76 MB of `File.content` to return 2 117 bytes; measured 160 ms of the ~170 ms request |
| REV-224 | DESIGN_GAP | low | 404 messages inconsistent: `code-card` and single `structural-card` skip the repository existence check |
| REV-225 | OPTIMIZATION_OPPORTUNITY | low | `structural-cards` loads every card row, then filters and limits in Python |
| REV-226 | INFO | info | Verified **non**-finding: `validate_clone_url` rejects embedded credentials and its 422 messages never echo the URL |

---

### REV-200

- ID: REV-200
- Category: BUG_CONFIRMED
- Severity: critical
- Evidence level: `unit/API-tested`
- Applies to: **both** (defect is in `search.py`, identical on both branches; reachable via `/api/search?repository_id=` on integration and via `POST /api/chat` / `POST /api/explanations` on both)
- Impact: The only repository-scope filter the retrieval layer offers is applied **after** the
  SQL row limit. In a corpus with more than one repository, a scoped query silently returns a
  subset — or nothing — even when the scoped repository contains many matches. Because
  `/api/explanations` (the web chat's grounded-answer path) uses `limit=8`, its SQL window is
  16 chunk rows drawn from *all* repositories; a second, busier repository can starve it to
  zero citations. The user sees "No indexed code in this repository evidences an answer",
  which is a false statement about the index.
- Evidence:

  `apps/api/app/search.py:57-80` — the filter and the limit, in that order:

  ```python
  def search_with_capability(db, raw, mode='hybrid', limit=30, repository_id=None, rerank=False):
      q, terms = parse_query(raw), query_terms(parse_query(raw).text)
      repos = {r.id: r for r in db.scalars(select(Repository)).all()}          # 59: ALL repos
      def allowed(repo): return repo and (not repository_id or repo.id == repository_id) \
                                    and (not q.repo or q.repo.lower() in repo.name.lower())   # 61
      ...
      for chunk, file in db.execute(chunk_stmt().where(
              CodeChunk.source_text.ilike(f'%{q.text}%')).limit(limit * 2)):    # 68: LIMIT here
          repo = repos.get(chunk.repository_id)
          if allowed(repo): lexical.append(...)                                # 70: FILTER here
  ```

  The same inversion recurs at `search.py:73` (`.limit(limit * 8)`), `search.py:78`
  (`.limit(limit * 3)`) and `search.py:88` (semantic branch — no limit at all, but the
  repository predicate is still Python-side). `chunk_stmt()` (`search.py:62-66`) *does* push
  `lang:` and `path:` into SQL before the limit; only the repository dimension is post-limit.

  Reproduction — static target, in-memory SQLite, `--network none`. Fixture: `repo-a` has 3
  matching chunks and 3 matching symbols, `repo-b` has 200 of each and is inserted first so it
  fills any unordered limit window:

  ```text
  5a /api/search?q=needle&repository_id=repo-a&limit=5 -> hits: 0     <-- scoped: EMPTY
     repos present in hits: []
  5b same query WITHOUT repository_id -> hits: 2
     repos present: ['repo-b']
  5c same scoped query with limit=100 -> hits: 2                       <-- same scope, wider window
     repos present: ['repo-a']
  ```

  `5a` vs `5c` is the proof: identical scope, identical query, only `limit` differs, and the
  narrow window loses every valid in-scope row.

  The inline `repo:` filter behaves identically (this is the path `main`'s working-tree symbol
  picker relies on — see REV-208):

  ```text
  5d /api/search/symbols?q=needlefn repo:alpha -> hits: 0
  5e /api/search/symbols?q=needlefn (no scope) -> [1, ['repo-b']]
  ```

- Probable cause + diagnostic confidence: **high.** `search_with_capability` was written to
  post-process a single global candidate set; `repository_id` was added as a Python predicate
  (`allowed`) rather than as a `where` clause on `chunk_stmt()` / the symbol statement. The
  git history supports this: `repository_id` already existed as a *parameter* on `main` but
  was only wired to a route on the integration branch.
- Smallest safe next step: add `if repository_id: stmt = stmt.where(<Entity>.repository_id == repository_id)`
  inside `chunk_stmt()` and on the symbol statement, keeping `allowed()` as the belt-and-braces
  Python re-check (matching the existing `scoped_*` idiom in `main.py:56-62`). Six lines, no
  migration, no schema change. Resolve `q.repo` (a name substring) to a concrete id set *before*
  the query, or drop `repo:` in favour of the explicit parameter.
- Affected data/migrations/providers/cost: none. No schema change. Reduces provider load if
  anything, because the semantic branch would stop cosine-scoring out-of-scope vectors.
- Recommended tests + acceptance criteria: a two-repository SQLite API test asserting
  `search(q, repository_id=A, limit=1)` returns only repo-A rows **and** is non-empty whenever
  `search(q, repository_id=A, limit=100)` is non-empty; a test asserting the emitted SQL
  contains a `repository_id` predicate.
- Fix status: report-only

---

### REV-201

- ID: REV-201
- Category: DESIGN_GAP
- Severity: critical
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: Invariant §3.1 ("scope comes from the server") is honoured by exactly one function.
  Every read route that returns code, symbols, edges, graphs, jobs or conversations accepts a
  client-supplied id and never consults `workspace_repositories`. There is no route on which a
  workspace id even appears alongside file/symbol/graph/search data, so "can a client pass an
  id from outside the workspace and get data back?" has no interesting answer — **there is no
  workspace-scoped operation to violate.** The product claim in §2 ("workspace-weit suchen")
  is not implementable against the current surface.
- Evidence:
  - The only server-side derivation: `main.py:45-48`

    ```python
    def validate_dependency_membership(db,workspace_id,source_repository_id,target_repository_id):
     if source_repository_id==target_repository_id: raise HTTPException(422,'Source and target repositories must differ')
     members=set(db.scalars(select(WorkspaceRepository.repository_id).where(WorkspaceRepository.workspace_id==workspace_id)).all())
     if source_repository_id not in members or target_repository_id not in members: raise HTTPException(422,'…must both belong to this workspace')
    ```

  - `WorkspaceRepository` is referenced on only five lines outside the workspace CRUD block:
    `main.py:47, 123, 130, 144, 146, 163`. None of them is a data route.
  - `apps/api/app/search.py` contains no occurrence of `Workspace` or `workspace`.
  - `GET /api/repositories` (`main.py:147-148`) is an unfiltered global list — the entry point
    §2 says should not be the entry point.
  - Probe output above: `2b/2c/2d` all `200` for a repository in no workspace.
  - `grep -rin workspace apps/web/` → **no matches** on either branch. Nothing in the UI can
    even name a workspace.
- Probable cause + diagnostic confidence: **high** — this is unfinished feature scope, not a
  regression. Workspace CRUD, exclusive membership and declared dependencies were built as a
  standalone slice; the read surface was never re-based onto it.
- Smallest safe next step: do not retrofit a `workspace_id` query parameter onto 20 routes.
  Add one dependency, e.g. `workspace_scope(workspace_id) -> set[str]`, plus **one**
  workspace-scoped discovery route (`GET /api/workspaces/{ws}/search`) that passes the derived
  set into `search_with_capability` — which requires REV-200 fixed first, otherwise the new
  route inherits the post-limit defect. Leave repository-local routes repository-local per §3.5.
- Affected data/migrations/providers/cost: none for the scope helper. A workspace-scoped
  search endpoint touches no schema.
- Recommended tests + acceptance criteria: negative tests from §5.G — foreign workspace id,
  empty workspace, unassigned repository — each asserting that the permitted set is derived
  from `workspace_repositories` and that a client-supplied out-of-workspace id is rejected
  rather than silently honoured.
- Fix status: report-only

---

### REV-202

- ID: REV-202
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: `POST /api/chat` is the only body-taking route that never checks that
  `repository_id` exists. It is written straight into `Conversation.repository_id`, which is a
  foreign key to `repositories.id`. PostgreSQL rejects the insert, the exception is unhandled,
  and the client receives `500 Internal Server Error` as `text/plain` instead of `404`.
  Every sibling route (`/explanations`, `/documentation/generate`, `/search`) does check.
- Evidence: `apps/api/app/main.py:328-336`

  ```python
  @app.post('/api/chat')
  def chat(body:ChatIn,db:Session=Depends(get_db)):
   results, semantic = search_with_capability(db,body.question,'hybrid',12,repository_id=body.repository_id)
   ...
   convo=db.get(Conversation,body.conversation_id) if body.conversation_id else None
   if not convo: convo=Conversation(repository_id=body.repository_id,title=body.question[:120]);db.add(convo);db.flush()
  ```

  `Conversation.repository_id` is `ForeignKey('repositories.id')` (`models.py:41`) and the
  constraint exists in the live database (`conversations_repository_id_fkey`, verified in the
  `\d files`-style output for the referencing side). Reproduction with FK enforcement enabled
  in SQLite to mirror PostgreSQL:

  ```text
  6a POST /api/chat unknown repository_id -> raised: IntegrityError
     message head: (sqlite3.IntegrityError) FOREIGN KEY constraint failed
  ```

  With `raise_server_exceptions=False` the same call produced
  `[500, 'text/plain; charset=utf-8', 'Internal Server Error']` — the shape a real client sees.

  This probe ran in the isolated `--network none` container against in-memory SQLite. `POST
  /api/chat` was **not** called against the live stack, per the mandate.
- Probable cause + diagnostic confidence: **high.** `ChatIn.repository_id` is `str | None`
  (`main.py:34`) and the author treated `None` as the only alternative to a valid id.
- Smallest safe next step: one line mirroring `/explanations` (`main.py:309-310`):
  `if body.repository_id and not db.get(Repository, body.repository_id): raise HTTPException(404,'Repository not found')`.
- Affected data/migrations/providers/cost: none. The failing transaction rolls back, so no
  orphan row — but the failed request still ran a full hybrid retrieval first, so a caller can
  burn retrieval work on a guaranteed-500.
- Recommended tests + acceptance criteria: API test asserting `404` (not `500`) for an unknown
  `repository_id`, and that no `conversations` row is created.
- Fix status: report-only

---

### REV-203

- ID: REV-203
- Category: PERFORMANCE_RISK
- Severity: high
- Evidence level: `manual live acceptance` (timings against `main`) + `source-reviewed` (code identical on both branches)
- Applies to: both
- Impact: `scoped_edges` materialises **every** edge row of the repository into Python and
  sorts it, on every graph-family request, regardless of how few edges the answer needs. There
  is no `LIMIT`, no pagination and no cap on the response. Two separate consequences:
  a fixed multi-second floor for trivial queries, and an unbounded response body.
- Evidence: `apps/api/app/main.py:60`

  ```python
  def scoped_edges(db,repo_id): return sorted((e for e in db.scalars(select(SymbolEdge).where(SymbolEdge.repository_id==repo_id)).all() if e.repository_id==repo_id),key=edge_key)
  ```

  Callers: `neighbors` (`main.py:230`), `subgraph` (`main.py:245`), `repository_graph`
  (`main.py:267`), `documentation` (`main.py:320`). Live corpus: one repository,
  `SELECT count(*) FROM symbol_edges` = **136 566**.

  ```text
  # symbol with ZERO inbound edges — answer is 65 bytes
  callers(low): 2.433306s size_dl=65
  callers(low): 2.388488s size_dl=65
  callers(low): 2.444120s size_dl=65

  # highest-degree symbol (IsStr, 6 277 inbound edges)
  callers: 3.294520s size_dl=52364872      <-- 52 MB, unpaginated
  callers: 3.312234s size_dl=3.1s / same size
  subgraph d2: 3.228833s size_dl=590862
  ```

  The 2.4 s floor on a 65-byte answer isolates the cost to the unconditional full-table
  materialisation, not to result size. The 52 MB body is a second, independent defect:
  `neighbors` returns `symbol_out(...)` per neighbour (`main.py:235`), and `symbol_out`
  includes the entire `source_text` of each symbol (`main.py:53`), with no `limit` parameter on
  the route at all.
- Probable cause + diagnostic confidence: **high** for the floor (measured, and the code has
  no predicate other than `repository_id`). The split between SQL time, ORM hydration and the
  Python `sorted()` was **not** attributed — that is a follow-up measurement, not a claim here.
- Smallest safe next step: for `/callers` and `/callees`, push the direction predicate into
  SQL (`where(SymbolEdge.target_symbol_id == symbol_id)`) instead of filtering
  `scoped_edges(...)` in Python, and add a bounded `limit` query parameter with an explicit
  `truncated` flag. Leave `subgraph`/`graph` alone until §5.D has ruled on their budgets.
- Affected data/migrations/providers/cost: no schema change. An index on
  `(repository_id, target_symbol_id)` / `(repository_id, source_symbol_id)` would be a
  separate, reversible migration — currently `symbol_edges` has only `ix_symbol_edges_repository_id`
  and `ix_symbol_edges_target_name`.
- Recommended tests + acceptance criteria: assert `/callers` on a zero-inbound-edge symbol
  issues a query whose row count is O(edges for that symbol), not O(edges in repository);
  assert the response is bounded and reports `truncated`.
- Fix status: report-only

---

### REV-204

- ID: REV-204
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: `manual live acceptance`
- Applies to: both (`search.py:68,73,78` identical; verified with `git diff main origin/integration/consolidated-verified -- apps/api/app/search.py`)
- Impact: Every candidate `SELECT` applies `LIMIT` without `ORDER BY`. PostgreSQL is free to
  return any rows, so the candidate set — and therefore the final result set — differs between
  identical requests. The `_fuse` docstring claims "Deterministic reciprocal-rank fusion, with
  stable identity tie-breaking" (`search.py:47`); the fusion *is* deterministic, but its input
  is not, so the endpoint is not. This defeats reproducible evidence (§3.6) and makes any
  search regression test flaky by construction.
- Evidence: six identical live requests, hashing the `(type, path, start_line, end_line)`
  tuple list:

  ```text
  $ for i in 1 2 3 4 5 6; do curl -s "localhost:8000/api/search?q=Agent&limit=10" | …sha256…; done
  10 1b44e1e7933e6185 pydantic_ai_slim/pydantic_ai/template.py
  10 e42bd0800206900a pydantic_ai_slim/pydantic_ai/template.py
  10 e22b1764dbfb3637 pydantic_ai_slim/pydantic_ai/template.py
  10 bdea22d14be7667b pydantic_ai_slim/pydantic_ai/template.py
  10 c0da41115ab32734 pydantic_ai_slim/pydantic_ai/template.py
  10 7a2f7576e1e8a5bf pydantic_ai_slim/pydantic_ai/template.py
  ```

  Six calls, six distinct result sets. Response sizes for the same query also varied
  (`32845`, `37553`, `42254` bytes). `mode=text` drifted too (2 of 3 identical). The
  statements, all without `order_by`: `search.py:68`, `:73`, `:78`.
- Probable cause + diagnostic confidence: **high.** `.limit(n)` on an unordered `SELECT`.
  Confirmed by the plan for the analogous `files` query being a `Seq Scan` — heap order is not
  a stable contract.
- Smallest safe next step: add a deterministic `order_by` to each candidate statement (e.g.
  `CodeChunk.repository_id, CodeChunk.file_id, CodeChunk.start_line, CodeChunk.id`). Cheap,
  no schema change; note it makes the truncation *deterministic*, not *correct* — REV-200 must
  also be fixed or the deterministic window will deterministically exclude the scoped repository.
- Affected data/migrations/providers/cost: none. May slightly change which rows the semantic
  branch embeds; no provider call is added.
- Recommended tests + acceptance criteria: run the same query twice in one test against a
  fixture with more matches than `limit` and assert byte-identical result lists.
- Fix status: report-only

---

### REV-205

- ID: REV-205
- Category: DESIGN_GAP
- Severity: high
- Evidence level: `unit/API-tested` (static target) + `manual live acceptance` (`main` OpenAPI)
- Applies to: both
- Impact: No route declares `response_model`. Every response is a hand-built dict assembled by
  `repo_out` / `workspace_out` / `symbol_out` / `edge_out` / `citation` or inline literals. The
  published OpenAPI therefore describes **no** response body, and generated clients, contract
  tests and the MCP bridge have nothing to validate against. There is no schema version, so a
  field rename is an undetectable breaking change. Separately, the error contract is
  undocumented: the code raises `404`, `409`, `422` and `503`, but OpenAPI lists only
  `200/201/202/204/422`.
- Evidence:
  - `grep -n "response_model" apps/api/app/main.py` → no matches. `BaseModel` appears only for
    **request** bodies (`main.py:21-40`).
  - Static target, from an isolated `TestClient`:

    ```text
    9a operations with an empty 2xx JSON schema: 38
    9b total operations: 42
    9c documented status codes: ['200', '201', '202', '204', '422']
    ```

    (The 4 non-empty ones are the `204` operations, which legitimately have no content.)
  - Live `main` (`curl -s localhost:8000/openapi.json`): 26 paths / 35 operations, every 2xx
    `content.application/json.schema` is `{}`, `components.schemas` contains only the eight
    request models plus `ValidationError`/`HTTPValidationError`. No operation lists `404`.
  - `POST /api/search/semantic` publishes `{"additionalProperties": true, "type": "object"}` as
    its request body — see REV-216.
- Probable cause + diagnostic confidence: **high** — deliberate terseness (the whole module is
  written in a dense one-line style). The cost is contract fidelity, not correctness.
- Smallest safe next step: do not model all 42 at once. Add `response_model` to the four
  response shapes that already have a single constructor function (`repo_out`,
  `workspace_out`, `workspace_dependency_out`, `symbol_out`) — that covers 14 operations from
  four small classes — and add `responses={404: ...}` to the routes that raise it. Everything
  else can follow incrementally.
- Affected data/migrations/providers/cost: none. `response_model` will start *filtering*
  extra keys, so add the models with the existing key set exactly, and diff the live JSON
  before and after.
- Recommended tests + acceptance criteria: a test that asserts every operation in
  `app.openapi()` has a non-empty 2xx schema, run as a ratchet (assert the count of untyped
  operations never increases).
- Fix status: report-only

---

### REV-206

- ID: REV-206
- Category: DESIGN_GAP
- Severity: high
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: There is no atomic "create repository in workspace" operation. `RepositoryIn` has no
  `workspace_id` field, so `POST /api/repositories` **always** produces an unassigned
  repository, and indexing starts immediately. Assignment requires a second, independent
  request (`PUT /api/workspaces/{ws}/repositories/{repo}`). Any failure between the two — client
  crash, closed tab, network drop — leaves a permanently orphaned repository that is being
  indexed, is visible in the global `GET /api/repositories` list, and belongs to no workspace.
  There is no API to enumerate unassigned repositories and no `Unassigned` status.
  This is not a race to be tightened; it is a missing operation.
- Evidence: commit boundaries, `main.py:149-153`:

  ```python
  @app.post('/api/repositories',status_code=202)
  def add_repository(body:RepositoryIn,db:Session=Depends(get_db)):
   try: body.clone_url=validate_clone_url(body.clone_url)
   except ValueError as error: raise HTTPException(422,str(error))
   r=Repository(...,indexing_status='pending');db.add(r);db.commit();db.refresh(r); return {'repository':repo_out(r),'job_id':enqueue(r.id,True)}
  ```

  One `commit()` before `enqueue`, and `enqueue` is outside any transaction. Membership is
  created in a *different* request with its own `commit()` (`main.py:135`).

  ```text
  A4 committed repository rows: [('7d8ccb75-…', 'pending')]
  A5 RepositoryIn accepts a workspace_id?: False
  A6 memberships after creation: 0
  ```

  `RepositoryIn` (`main.py:21-22`) carries `name`, `clone_url`, `requested_revision` — nothing
  else. The web dashboard posts exactly those (`apps/web/app/dashboard-client.tsx:30`).
  Consistent with §01: the live database has 1 repository and 0 workspaces, so the live
  repository *is* an orphan by this definition.
- Probable cause + diagnostic confidence: **high.** Repository CRUD predates the workspace
  model and was never re-based onto it.
- Smallest safe next step: add an optional `workspace_id` to `RepositoryIn`; when present,
  validate the workspace, then `db.add(Repository)` **and** `db.add(WorkspaceRepository)`
  before a single `commit()`, and only then `enqueue`. That makes creation-plus-assignment one
  transaction without changing the unassigned path. Decide the `Unassigned` policy (§11.2)
  before adding a filter to `GET /api/repositories`.
- Affected data/migrations/providers/cost: no migration. Adding an optional field is
  backward-compatible. Indexing cost unchanged.
- Recommended tests + acceptance criteria: assert that a `POST` with an invalid `workspace_id`
  creates **no** repository row and enqueues **no** job; assert that a successful `POST` with
  `workspace_id` yields exactly one membership row in the same transaction.
- Fix status: report-only

---

### REV-207

- ID: REV-207
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: `enqueue()` catches `Exception` and returns `None`. All three enqueueing routes then
  answer `202 Accepted` with `job_id: null`. For `POST /api/repositories` the repository row is
  already committed with `indexing_status='pending'`, so a Redis outage produces a repository
  that will never index, reports `pending` forever, and told the client it was accepted. The
  UI has no way to distinguish "queued" from "silently dropped". Note the contrast with
  `generate_code_cards` (`main.py:183-184`), which *does* raise `503` on the same failure —
  so the correct behaviour is already established in the same file.
- Evidence: `main.py:49-51`

  ```python
  def enqueue(repo_id,full=False):
   try: return Queue('indexing',connection=Redis.from_url(settings.redis_url),default_timeout=settings.index_job_timeout).enqueue('app.ingestion.index_repository',repo_id,full).id
   except Exception: return None
  ```

  Reproduction (Redis unreachable by construction — `--network none`):

  ```text
  A1 POST /api/repositories (Redis unreachable) -> status: 202
  A2 job_id in body: None
  A3 indexing_status in body: pending
  A4 committed repository rows: [('7d8ccb75-…', 'pending')]
  A7 POST /reindex -> [202, {'job_id': None}]
  A8 POST /sync    -> [202, {'job_id': None}]
  ```

- Probable cause + diagnostic confidence: **high.** The bare `except Exception: return None`
  is explicit in the source.
- Smallest safe next step: mirror `generate_code_cards` — raise `HTTPException(503, 'Could not
  enqueue indexing')` and, for `add_repository`, either roll back the repository row or commit
  it with `indexing_status='failed'` and an explicit `error_message`. Prefer the second: it is
  observable and does not lose the user's input.
- Affected data/migrations/providers/cost: no migration. Interacts with the orphaned-job reaper
  (`reconcile.py`, `main` working tree only) — the reaper handles *killed work-horses*, not
  *never-enqueued* jobs, so it does not cover this case.
- Recommended tests + acceptance criteria: monkeypatch `Queue.enqueue` to raise; assert `503`
  and that the repository is not left in `pending` with no job.
- Fix status: report-only

---

### REV-208

- ID: REV-208
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: `unit/API-tested`
- Applies to: **`main` working tree** (uncommitted `apps/web/app/graph/graph-explorer.tsx`; not present on integration, whose graph page still takes a typed symbol UUID)
- Impact: The new symbol picker — the fix for "no human UUID entry" (§3.2) — relies on a
  server-side narrowing that does not exist, and its inline code comment asserts the opposite.
  In a multi-repository deployment the picker shows "no symbol" for symbols that are indexed
  and findable, because the server's 90-row global window is consumed by other repositories
  before the client-side id filter runs. Today's single-repository deployment masks it
  completely.
- Evidence: `apps/web/app/graph/graph-explorer.tsx`, the `findSymbols` function. This file is an
  uncommitted working-tree change and was **under concurrent edit during this review**: the
  quoted comment was at line 109 when first read and at line 96 when re-verified minutes later.
  Locate it by content, not line number:
  `grep -n "narrows server-side before the result limit" apps/web/app/graph/graph-explorer.tsx`

  ```tsx
  // `repo:` narrows server-side before the result limit applies; the id check below is the authoritative filter.
  const scope = repository && !/\s/.test(repository.name) ? ` repo:${repository.name}` : '';
  const response = await api<{ results: SymbolHit[] }>(`/search/symbols?q=${encodeURIComponent(query + scope)}`);
  setHits(response.results.filter((hit) => hit.repository_id === repositoryId).slice(0, SYMBOL_HIT_LIMIT));
  ```

  The comment is false. `repo:` is parsed into `Query.repo` (`search.py:20-23`) and consumed
  only by `allowed()` (`search.py:61`), which runs **after** `.limit(limit * 3)`
  (`search.py:78`). `GET /api/search/symbols` also passes no `limit`, so the window is the
  default `30 * 3 = 90` rows for the whole corpus (`main.py:302`).

  ```text
  5d /api/search/symbols?q=needlefn repo:alpha -> hits: 0     (repo-a has 3 matching symbols)
  5e /api/search/symbols?q=needlefn            -> [1, ['repo-b']]
  ```

  Two further contract weaknesses in the same block: `repo:` matches on a **name substring**
  (`q.repo.lower() in repo.name.lower()`, `search.py:61`), so a repository named `api` scopes
  to every repository whose name contains `api`; and the scope is dropped entirely when the
  repository name contains whitespace (the `/\s/` guard), silently degrading to a global search.
- Probable cause + diagnostic confidence: **high.** The comment states an assumption about
  `search.py` that the code does not implement; the client-side `.filter()` was added as a
  safety net and is in fact the only filter.
- Smallest safe next step: fix REV-200, then give `GET /api/search/symbols` a real
  `repository_id` parameter (REV-217) and have the picker pass the id instead of a name
  substring. Until then, correct the comment — it is actively misleading the next reader.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: a two-repository test asserting the symbol picker
  finds a repo-A symbol when repo-B contains more than `limit * 3` matches for the same query.
- Fix status: report-only

---

### REV-209

- ID: REV-209
- Category: BUG_CONFIRMED
- Severity: medium
- Evidence level: `manual live acceptance`
- Applies to: both (`git diff --stat main origin/integration/consolidated-verified -- apps/mcp/` is empty — the MCP server is byte-identical on both branches)
- Impact: The MCP bridge validates a search `mode` vocabulary that does not match the API's.
  `lexical` passes MCP validation and is accepted by the API with `200`, but falls through
  every branch in `search_with_capability` and returns an empty result set. An agent asking for
  a lexical search receives "no matches" rather than an error — an indistinguishable false
  negative. Conversely `text` and `exact`, which the API implements, are rejected by MCP
  before the request is made.
- Evidence: `apps/mcp/knowledge_way_mcp/client.py:99-103`

  ```python
  def search_code(self, query, mode="hybrid", limit=20):
      query = _bounded_text(query, "query", MAX_QUERY_LENGTH)
      if mode not in {"hybrid", "lexical", "symbols", "semantic"}:
          raise InputError("mode must be one of hybrid, lexical, symbols, or semantic")
  ```

  The API's vocabulary is `hybrid | text | exact | symbols | semantic`
  (`search.py:67,71,76,83,98-100`); `lexical` appears nowhere in `apps/api`. Live:

  ```text
  $ curl -s "localhost:8000/api/search?q=Agent&mode=lexical&limit=5"  -> mode echoed: lexical  results: 0
  $ curl -s "localhost:8000/api/search?q=Agent&mode=text&limit=5"     -> results: 5
  $ curl -s "localhost:8000/api/search?q=Agent&mode=hybrid&limit=5"   -> results: 5
  ```

  The MCP contract is narrower than the API in two further respects that are *deliberate and
  fine*: GET-only (`client.py:72-74` rejects any non-`/api/` path), and no mutation tools. But
  it also carries **no repository or workspace scope** on `search_code` at all, so an MCP agent
  always searches every indexed repository. `apps/mcp/tests/test_client.py` (63 lines) tests
  URL construction and input bounds, not mode compatibility.
- Probable cause + diagnostic confidence: **high** — two independently written vocabularies,
  no shared constant, and REV-215 means the API never rejects an unknown mode, so the drift
  cannot fail loudly.
- Smallest safe next step: make `mode` an `Enum` in the API (REV-215) so it appears in
  OpenAPI, and derive the MCP set from it or assert equality in an MCP test.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: a test asserting the MCP mode set equals the API
  mode set; an MCP test asserting `mode="text"` is accepted.
- Fix status: report-only

---

### REV-210

- ID: REV-210
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: `unit/API-tested` + `manual live acceptance`
- Applies to: both
- Impact: `/api/files/{file_id}` returns full file content addressed by a bare id, with no
  repository or workspace predicate — the only route returning source text that is not
  repository-scoped. `/api/files/{file_id}/symbols` is worse: it performs **no existence check
  at all** and answers `200 []` for any id, so a client cannot distinguish "file has no
  symbols" from "file does not exist", and `main`'s symbol picker consumes exactly this route
  (`graph-explorer.tsx`, `chooseSymbol`). Today, with no authentication, this leaks nothing beyond what
  other routes already expose; it becomes a scope hole the moment any tenancy boundary exists,
  and it is inconsistent with §3.1 today.
- Evidence: `main.py:216-222`

  ```python
  @app.get('/api/files/{file_id}')
  def file(file_id:str,db:Session=Depends(get_db)):
   f=db.get(File,file_id)
   if not f: raise HTTPException(404,'File not found')
   return {'id':f.id,'repository_id':f.repository_id,'path':f.path,'language':f.language,'content':f.content,'indexed_commit_sha':f.indexed_commit_sha}
  @app.get('/api/files/{file_id}/symbols')
  def symbols(file_id:str,db:Session=Depends(get_db)): return [{...} for s in db.scalars(select(Symbol).where(Symbol.file_id==file_id)).all()]
  ```

  Note the absent `order_by` on the symbol list as well — the order is whatever PostgreSQL
  returns. Live and isolated:

  ```text
  $ curl -s -w " [HTTP %{http_code}]" localhost:8000/api/files/00000000-0000-4000-8000-000000000000/symbols
  [] [HTTP 200]

  4a GET /api/files/file-b (repo-b, outside every workspace) -> 200, contains repo-b content
  4c GET /api/files/<nonexistent>/symbols -> [200, []]
  ```

  The same routes are reached from the browser through the Next rewrite (`next.config.ts:8`)
  and are used by `apps/web/app/files/[id]/page.tsx:1` on both branches.
- Probable cause + diagnostic confidence: **high** — `file_id` is globally unique so a repo
  predicate looked redundant; the missing 404 on the symbols route is a plain omission.
- Smallest safe next step: add `if not db.get(File, file_id): raise HTTPException(404,'File not found')`
  plus a deterministic `order_by(Symbol.start_line, Symbol.id)` to the symbols route. Re-siting
  these under `/api/repositories/{repo_id}/files/{file_id}` is the correct long-term shape but
  is a breaking change for the web client — defer.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: `404` for an unknown `file_id` on both routes;
  stable symbol ordering asserted twice in one test.
- Fix status: report-only

---

### REV-211

- ID: REV-211
- Category: BUG_CONFIRMED
- Severity: medium
- Evidence level: `manual live acceptance`
- Applies to: both
- Impact: The `path` query parameter is interpolated into a SQL `LIKE` pattern without escaping
  `%` or `_`. This is not SQL injection — the value is bound — but it *is* LIKE-pattern
  injection: `%` becomes a wildcard, the subsequent fixed-width slice `f.path[len(prefix):]`
  then cuts real paths at the wrong offset, and the endpoint returns fabricated directory
  entries with impossible paths. A tree UI following such an entry navigates to a path that
  does not exist. Any user-supplied path containing `%` or `_` (both legal in filenames) is
  silently mis-handled.
- Evidence: `main.py:207-215`

  ```python
  prefix=path.strip('/')+'/' if path else ''
  files=db.scalars(select(File).where(File.repository_id==repo_id,File.path.like(prefix+'%'))).all(); children={}
  for f in files:
   rest=f.path[len(prefix):]; first=rest.split('/')[0]
   children[first]={'name':first,'type':'file' if '/' not in rest else 'directory','path':prefix+first,...}
  ```

  Live, against the indexed repository:

  ```text
  $ curl -s "localhost:8000/api/repositories/21ffa409-…/tree?path=%25"
  entries 14
  [{"name":"acroscope","type":"directory","path":"%/acroscope"},
   {"name":"ai","type":"directory","path":"%/ai"},
   {"name":"amples","type":"directory","path":"%/amples"},
   {"name":"dantic_ai_slim","type":"directory","path":"%/dantic_ai_slim"}, …]
  ```

  `amples` is `examples` with two characters shaved off by `f.path[len('%/'):]`; `%/acroscope`
  is not a path in the repository. Isolated target, single-file fixture:

  ```text
  8a tree?path=%  -> [{'name': 'mod.py', 'type': 'file', 'path': '%/mod.py', 'file_id': 'file-b'}]
  ```

  The same unescaped interpolation appears in `search.py:65` (`File.path.ilike(f'%{q.path}%')`)
  where the consequence is only over-broad matching, not fabricated output.
- Probable cause + diagnostic confidence: **high** — visible in the quoted line.
- Smallest safe next step: `File.path.like(prefix.replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%', escape='\\')`,
  or better, drop `LIKE` for `startswith` semantics and derive `rest` from a verified prefix
  match rather than a byte offset.
- Affected data/migrations/providers/cost: none. Note the query is a `Seq Scan` for a bare `%`
  (measured); whether a real prefix can use `ix_files_repo_path` depends on database collation
  and was **not assessed**.
- Recommended tests + acceptance criteria: `?path=%` and `?path=_` return `[]` (no such
  directory), and a file literally named `we%rd/x.py` is listed correctly.
- Fix status: report-only

---

### REV-212

- ID: REV-212
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: `DELETE /api/repositories/{id}` performs no state check. Deleting a repository while
  its indexing job is running removes the rows the worker is about to write to; the in-flight
  job then fails on foreign keys, and the failure is attributed to indexing rather than to the
  concurrent delete. There is no `409 Conflict` for "cannot delete while indexing", and the
  route does not remove the on-disk clone under `settings.repository_storage_path`.
- Evidence: `main.py:159-163`

  ```python
  @app.delete('/api/repositories/{repo_id}',status_code=204)
  def delete_repository(repo_id:str,db:Session=Depends(get_db)):
   r=db.get(Repository,repo_id)
   if not r: raise HTTPException(404,'Repository not found')
   db.execute(delete(WorkspaceDependency).where(...)); db.execute(delete(WorkspaceRepository).where(...)); db.delete(r);db.commit()
  ```

  ```text
  B1 DELETE /api/repositories/<id> while indexing_status='indexing' -> status: 204
  B2 rows left: 0
  ```

  Positive note on the same route and its siblings: the cascade *semantics* are correct per
  §3.8 — `delete_workspace` (`main.py:90-94`) removes dependencies and memberships but not
  repositories, and `remove_workspace_repository` (`main.py:141-146`) removes only membership
  plus the dependencies that reference it. Each does so in **one** `commit()`, so all three
  delete paths are atomic.
- Probable cause + diagnostic confidence: **high** for the missing guard (no status check in
  the quoted code). The precise worker failure mode is **not** reproduced here — it belongs to
  the indexing workstream — so the consequence is stated as a risk, not a measured outcome.
- Smallest safe next step: `if r.indexing_status == 'indexing': raise HTTPException(409, 'Repository is indexing')`,
  and document that on-disk clone cleanup is a separate concern.
- Affected data/migrations/providers/cost: no migration. Prevents wasted indexing work.
- Recommended tests + acceptance criteria: `409` when `indexing_status='indexing'`; `204` and
  full cascade otherwise.
- Fix status: report-only

---

### REV-213

- ID: REV-213
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: `unit/API-tested`
- Applies to: **integration** (route absent on `main`; `GET /api/repositories/<id>/graph` returns `404 Not Found` live, confirming the boundary in §01)
- Impact: `/graph` returns one `edges` array containing two mutually incompatible object
  shapes, and one `nodes` array containing two more. A client must sniff which keys are present
  to interpret an element. Worse, `confidence` is overloaded: synthetic structural edges carry
  the literal `1` while real parser edges carry the stored 0-100 integer, so a UI rendering
  "confidence" shows a `contains` edge as 1 % and a `calls` edge as 80 %. §3.4 requires
  `contains` / `defines` / `calls` / `declared_dependency` to be distinguishable and confidence
  shown only when actually stored — the current payload makes both hard to do correctly.
- Evidence: `main.py:285-295` builds structural edges as
  `{'source','target','relationship','confidence'}` (lines 288, 291, 293) and then appends
  `edge_out(edge)` (line 294), which is
  `{'id','source_symbol_id','target_symbol_id','target_name','type','confidence','line','source_file_id'}`
  (`main.py:54`). Observed on the static target:

  ```text
  edge key-sets:
    ['confidence','relationship','source','target'] | {"source":"directory:pkg","target":"directory:pkg/sub","relationship":"contains","confidence":1}
    ['confidence','relationship','source','target'] | {"source":"file:f","target":"s1","relationship":"defines","confidence":1}
    ['confidence','id','line','source_file_id','source_symbol_id','target_name','target_symbol_id','type']
                                                   | {"id":"e1","source_symbol_id":"s1","target_symbol_id":"s2","type":"calls","confidence":80,…}
  node key-sets:
    repository -> ['id','kind','name']
    directory  -> ['id','kind','name']
    file       -> ['id','kind','name','path']
    function   -> ['end_byte','end_line','file_id','id','kind','language','name','parent_symbol_id',
                   'qualified_name','repository_id','signature','source_text','start_byte','start_line','type']
  ```

  Note also the split id namespace: structural nodes are prefixed (`repository:`, `directory:`,
  `file:`) while symbol nodes use a bare UUID, so a `defines` edge has a prefixed `source` and
  an unprefixed `target`. And symbol nodes carry the full `source_text`, inflating a graph
  overview payload with data no overview needs.
- Probable cause + diagnostic confidence: **high** — `edge_out` was reused for the code-edge
  slice without normalising it to the structural shape.
- Smallest safe next step: normalise every element of `edges` to
  `{'source','target','relationship','confidence','line','id'}` with `confidence: None` for
  synthetic edges, and drop `source_text` from graph nodes. Both are response-shaping changes
  in one function; `apps/web/app/graph/graph-model.ts` already normalises on the client and
  will need the matching edit.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: assert all `edges` elements share one key set and
  that synthetic edges do not report a numeric confidence.
- Fix status: report-only

---

### REV-214

- ID: REV-214
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: `POST /api/chat` loads a conversation by client-supplied id and never checks that it
  belongs to the requested repository. Messages and citations from repository B are appended to
  a conversation whose `repository_id` is A. `GET /api/conversations/{id}` then returns one
  thread with citations from two repositories, and the conversation row still claims A. This
  violates §3.6 (evidence keeps its repository) and §3.7 (a repository switch must discard or
  isolate old answers) at the storage layer, where no UI change can repair it.
- Evidence: `main.py:333-335`

  ```python
  convo=db.get(Conversation,body.conversation_id) if body.conversation_id else None
  if not convo: convo=Conversation(repository_id=body.repository_id,title=body.question[:120]);db.add(convo);db.flush()
  db.add(Message(conversation_id=convo.id,role='user',content=body.question));db.add(Message(...));db.commit()
  ```

  ```text
  7a continuing repo-a conversation with repository_id=repo-b -> status: 200
  7a same conversation id reused: True
  7b conversation row repository_id stays: repo-a
  7c messages now in one conversation: 4
  ```

  `GET /api/conversations` (`main.py:342-343`) also lists every conversation globally with no
  repository filter and does not expose `repository_id` in the list payload, so a client cannot
  even group them.
- Probable cause + diagnostic confidence: **high** — no predicate on the `db.get`.
- Smallest safe next step: reject the request when `convo.repository_id != body.repository_id`
  (`409` or `422`), and add `repository_id` to the conversation list payload.
- Affected data/migrations/providers/cost: no migration. Existing mixed conversations, if any,
  are not repaired by the guard — the live database has 0 conversations, so there is nothing to
  backfill today.
- Recommended tests + acceptance criteria: continuing a conversation with a different
  `repository_id` is rejected; citations in a stored conversation all share its repository.
- Fix status: report-only

---

### REV-215

- ID: REV-215
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: `mode` is a free-form `str`. An unknown value is accepted, echoed back, and produces
  an empty result set indistinguishable from "no matches" — which is precisely how REV-209
  stays invisible. `limit` is silently clamped in application code while OpenAPI advertises an
  unbounded integer, so a client asking for 1 000 results is told nothing about receiving 100,
  and a client asking for `-5` is told nothing about receiving 1. Neither bound is discoverable.
- Evidence: `main.py:296-300`

  ```python
  @app.get('/api/search')
  def text_search(q:str,mode:str='hybrid',limit:int=30,repository_id:str|None=None,rerank:bool=False,db:Session=Depends(get_db)):
   if repository_id and not db.get(Repository,repository_id): raise HTTPException(404,'Repository not found')
   results, semantic = search_with_capability(db,q,mode,min(max(limit,1),100),repository_id=repository_id,rerank=rerank)
   return {'query':q,'mode':mode,'results':results,'semantic':semantic}
  ```

  ```text
  C /api/search?q=x&mode=not-a-mode : [200, application/json, {"query":"x","mode":"not-a-mode","results":[], …}]
  C /api/search?q=x&limit=-5        : [200, …]   (clamped to 1)
  C /api/search?q=x&limit=100000    : [200, …]   (clamped to 100)
  C /api/search?q=x&rerank=maybe    : [422, …]   (Pydantic bool parsing — correct)
  C /api/search?q=x&repository_id=nope : [404, {"detail":"Repository not found"}]
  ```

  Live OpenAPI for `/api/search` declares `limit` as `{"type":"integer","default":30}` — no
  `minimum`, no `maximum` — and `mode` as a bare `string`. Contrast with the routes that get
  this right: `subgraph` uses `Query(1,ge=1,le=2)` / `Query(...,ge=1,le=MAX_GRAPH_NODES)`
  (`main.py:242`) and `structural_cards` uses `Query(50,ge=1,le=100)` (`main.py:193`), both of
  which do appear in OpenAPI. The pattern exists in the file; `/api/search` just does not use it.
- Probable cause + diagnostic confidence: **high.**
- Smallest safe next step: `mode: Literal['hybrid','text','exact','symbols','semantic'] = 'hybrid'`
  and `limit: int = Query(30, ge=1, le=100)`. Both are additive to OpenAPI; the `mode` change
  turns today's silent empty result into a `422`, which is the point — coordinate with REV-209
  so the MCP client is fixed in the same slice.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: `422` for an unknown mode and for `limit=0`/`limit=101`;
  OpenAPI exposes the enum and the bounds.
- Fix status: report-only

---

### REV-216

- ID: REV-216
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: `unit/API-tested` + `manual live acceptance`
- Applies to: both
- Impact: `POST /api/search/semantic` accepts an untyped `dict`. A misspelled key yields
  `body.get('query','')` = `''` and a `200` with an empty result set — no `422`, no signal. The
  route also hard-codes the default `limit=30` and passes **no** `repository_id`, so it is
  unconditionally global; and it is the only search route that is a `POST` with a body while
  its siblings are GETs with query parameters. Its OpenAPI request schema is
  `{"additionalProperties": true, "type": "object"}`, i.e. no contract.
- Evidence: `main.py:303-306`

  ```python
  @app.post('/api/search/semantic')
  def semantic_search(body:dict,db:Session=Depends(get_db)):
   results, semantic = search_with_capability(db,body.get('query',''),'semantic')
   return {'results':results,'semantic':semantic}
  ```

  Live OpenAPI confirms the free-form body. `git grep` shows **no** caller: neither
  `apps/web` nor `apps/mcp` references `/search/semantic` on either branch, and no test covers
  it. It is an unreferenced, unvalidated, unscoped public route.
- Probable cause + diagnostic confidence: **high.**
- Smallest safe next step: this is the YAGNI candidate of the surface — delete it, or give it
  a `SemanticSearchIn` model with `query`, `limit` and `repository_id` and point it at the same
  code path as `/api/search?mode=semantic`. Deleting is the smaller diff and removes an
  unscoped route; confirm no external MCP configuration depends on it first.
- Affected data/migrations/providers/cost: the semantic branch calls
  `embedding_provider().embed_texts([...])` (`search.py:85`), so this route **can** incur
  provider cost when `EMBEDDING_PROVIDER != none`. It is unauthenticated and takes an arbitrary
  string — a cost-exposure surface with no validation. Live config has `embedding_provider: none`
  (`config.py:12`), so no spend was possible during this review and none was incurred.
- Recommended tests + acceptance criteria: if kept, `422` for a missing `query`, and a test
  asserting no provider call when the provider is `none`.
- Fix status: report-only

---

### REV-217

- ID: REV-217
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: `GET /api/search/symbols` exposes only `q`. There is no `repository_id`, no `limit`
  and no `mode`; the limit is the `search()` default of 30, which becomes a `limit * 3 = 90`-row
  global SQL window. It is the route the symbol picker depends on (REV-208), so the missing
  `repository_id` is the direct cause of that defect, and the missing `limit` means a client
  cannot widen the window to work around it.
- Evidence: `main.py:301-302`

  ```python
  @app.get('/api/search/symbols')
  def symbol_search(q:str,db:Session=Depends(get_db)): return {'results':search(db,q,'symbols')}
  ```

  `search()` (`search.py:120-121`) defaults to `limit=30, repository_id=None`. Confirmed from
  the published contract:

  ```text
  C6 /api/search/symbols has a limit parameter?: ['q']
  ```

  The response is also inconsistent with `/api/search`, which returns `{query, mode, results,
  semantic}`; this one returns `{results}` only.
- Probable cause + diagnostic confidence: **high.**
- Smallest safe next step: add `repository_id: str | None = None` and
  `limit: int = Query(30, ge=1, le=100)`, forwarded to `search()`. Additive and
  backward-compatible. Only correct once REV-200 is fixed.
- Affected data/migrations/providers/cost: none — `mode='symbols'` makes no provider call.
- Recommended tests + acceptance criteria: scoped symbol search returns only in-scope symbols
  and is non-empty whenever the unscoped search contains in-scope symbols.
- Fix status: report-only

---

### REV-218

- ID: REV-218
- Category: BUG_CONFIRMED
- Severity: medium
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: The fusion key is a **location**, not an identity. Two distinct symbols or chunks
  that share `(type, file_id, start_line, end_line)` collapse into one result, and the survivor
  is whichever the iteration happened to reach first. Decorated functions, overloads,
  single-line definitions and multiple chunks derived from the same span all collide. Users see
  fewer hits than exist with no truncation signal.
- Evidence: `search.py:39` and `:46-54`

  ```python
  def _key(item): return (item['type'], item['file_id'], item['start_line'], item['end_line'])
  ...
  for rank, item in enumerate(sorted(results, key=lambda x: (-x['score'], _key(x))), 1):
      key = _key(item)
      if key not in combined: combined[key] = dict(item, score=0.0)
  ```

  `result()` (`search.py:30-36`) does emit `symbol_id`, so identity is available and simply not
  used in the key. Observed: the fixture in REV-200 has 3 distinct `CodeChunk` rows and 3
  distinct `Symbol` rows in repo-a, all at lines 1-2 of the same file; the scoped query with
  `limit=100` returned **2** results — one collapsed chunk and one collapsed symbol.
- Probable cause + diagnostic confidence: **high** for the mechanism (quoted). The real-world
  collision rate on the live corpus was **not** measured, so severity is capped at medium.
- Smallest safe next step: extend `_key` to include `item.get('symbol_id') or item['file_id']`
  and the row id. Keep it a total order so the existing tie-breaking guarantees survive.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: two distinct symbols at identical line ranges in one
  file both appear in the result set.
- Fix status: report-only

---

### REV-219

- ID: REV-219
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: The good news first: **no internal detail leaks to clients.** There is no custom
  exception handler, so Starlette's default converts any unhandled exception into
  `500 text/plain "Internal Server Error"` with no traceback, no SQL and no exception text.
  Every deliberate error is an `HTTPException` with a short static string. The bad news is the
  other half of the §5.B requirement: errors are stable and leak-free but **not traceable**.
  There is no request id, no correlation id and no structured error code, so a `500` reported by
  a user cannot be matched to a log line, and clients cannot branch on anything but the status.
- Evidence:
  - `grep -n "exception_handler\|add_exception_handler" apps/api/app/main.py` → no matches.
  - Observed shape (isolated target, `raise_server_exceptions=False`):
    `[500, 'text/plain; charset=utf-8', 'Internal Server Error']`.
  - All `HTTPException` details in `main.py` are static literals. The single dynamic one is
    `HTTPException(422,str(error))` at `main.py:152`, whose source is `validate_clone_url` —
    audited in REV-226 and confirmed safe.
  - `verify_migration_ready()` (`db.py:18-27`) raises a `RuntimeError` at startup, not per
    request, so its message reaches logs only. Correct fail-fast behaviour.
  - `@app.on_event('startup')` (`main.py:19`) is deprecated in this FastAPI version — it emits
    a `DeprecationWarning` on every test run.
- Probable cause + diagnostic confidence: **high** — absence of middleware is not ambiguous.
- Smallest safe next step: one middleware that generates a request id, puts it in a response
  header, and logs it with the exception. Roughly ten lines, no schema change, no client change
  required.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: a route that raises returns `500` with a request-id
  header, and the same id appears in the captured log record.
- Fix status: report-only

---

### REV-220

- ID: REV-220
- Category: TEST_GAP
- Severity: high
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: The suite passes and is genuinely useful, but it does not cover the contract this
  workstream is about. **No test anywhere passes `repository_id` to search**, so REV-200 —
  the critical finding — was invisible to CI and would remain invisible after a fix regressed.
  Seventeen of 42 operations have no test at all, including every route that mutates
  repository state.
- Evidence: suite state, static target, isolated container:

  ```text
  $ docker run --rm --network none -v <worktree>/apps/api:/src:ro -e DATABASE_URL=sqlite:// \
      knowledge-way-api:latest python -m pytest -q tests/
  50 passed, 20 warnings in 1.23s
  ```

  Verified SQLite-only before running: `grep -rn "sqlite\|create_engine" apps/api/tests/`
  returns only `sqlite://` engines (`test_workspaces_api.py:12-13`,
  `test_incremental_structural_cards.py:13`, `test_ingestion_graph.py:21`); the remaining API
  tests use hand-rolled fake session objects (`test_readonly_api.py:9-27`). `--network none`
  made a live-database connection impossible regardless.

  Routes appearing in **no** test (from `grep -rhoE '"/api/[^"]*"' apps/api/tests apps/mcp/tests`):

  ```text
  /health                                       /api/repositories (GET and POST)
  /api/repositories/{id} (GET, DELETE)          /api/repositories/{id}/sync
  /api/repositories/{id}/reindex                /api/repositories/{id}/status
  /api/repositories/{id}/code-cards             /api/repositories/{id}/symbols/{id}/code-card
  /api/repositories/{id}/structural-cards       /api/repositories/{id}/structural-cards/{kind}
  /api/repositories/{id}/tree                   /api/files/{id}
  /api/files/{id}/symbols                       /api/search/symbols
  /api/search/semantic                          /api/chat
  /api/jobs/{id}                                /api/conversations (both)
  ```

  `grep -rn "repository_id=\|workspace" apps/api/tests/test_search.py apps/api/tests/test_semantic.py`
  → **no matches**. `test_search.py` (23 lines) tests only `parse_query`, `query_terms` and
  `result` — the pure helpers, never the scoping.

  Real strengths, so the gap is not overstated: `test_workspaces_api.py` covers workspace CRUD,
  exclusive membership, idempotent re-add and the `409` conflict against a real (SQLite) engine;
  `test_graph_api.py` covers foreign-symbol rejection, `depth` bounds and `max_nodes`
  truncation; `test_migrations.py` pins the alembic head at `20260809_0008`.
- Probable cause + diagnostic confidence: **high.** Tests were written per feature slice; the
  scope dimension was never a slice of its own.
- Smallest safe next step: one new test module with a **two-repository** SQLite fixture, which
  is the missing precondition for every scope assertion. Start with the REV-200 assertion —
  scoped-and-narrow must not lose rows that scoped-and-wide finds.
- Affected data/migrations/providers/cost: none. The suite needs no PostgreSQL and no provider.
- Recommended tests + acceptance criteria: the §5.G negative list — foreign workspace id, empty
  workspace, unassigned repository, missing symbol, graph truncation, failed index job,
  membership removal, repository and workspace deletion, stale async response — with at least
  the search-scope case landing in the same change as any REV-200 fix.
- Fix status: report-only

---

### REV-221

- ID: REV-221
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: `source-reviewed`
- Applies to: both
- Impact: `POST /api/workspaces/{ws}/dependencies` promises `409 'Dependency declaration
  already exists'` on `IntegrityError`. The backing unique constraint spans two nullable
  columns, and PostgreSQL treats `NULL` values as distinct in a unique index. The common case —
  a declaration with no `package_name` and no `import_path`, which is exactly what the API
  allows since both fields are optional — therefore never violates the constraint, and
  unlimited duplicate rows accumulate. The documented `409` is unreachable for that shape.
- Evidence: `models.py:19`

  ```python
  __table_args__=(UniqueConstraint('workspace_id','source_repository_id','target_repository_id','package_name','import_path',name='uq_workspace_dependencies_declaration'),)
  ```

  `WorkspaceDependencyIn` (`main.py:30`) declares `package_name` and `import_path` as
  `str | None = None`, and `main.py:99-106` inserts `**body.model_dump()` with no
  normalisation. The `409` handler is `main.py:104-105`.

  This is deliberately **not** claimed as tested: the live database has 0 workspaces, and
  creating duplicate rows to prove it would be a write to live PostgreSQL, which the mandate
  forbids. SQLite's NULL-distinct behaviour matches PostgreSQL here, but a SQLite result would
  not be evidence about PostgreSQL semantics, so no such claim is made. Cross-reference: this
  is the API-visible face of a data-model issue owned by workstream §5.C.
- Probable cause + diagnostic confidence: **high** on the SQL semantics, **medium** on the
  behavioural consequence, because it was not executed against PostgreSQL.
- Smallest safe next step: verify with a throwaway PostgreSQL database (not the live one),
  then either coalesce the two columns to `''` at the API boundary or add a partial unique
  index for the all-NULL case. Both need a migration, so this is workstream §5.C's call.
- Affected data/migrations/providers/cost: needs a migration; duplicate rows may already exist
  in other deployments and would have to be de-duplicated before a stricter index can be built.
- Recommended tests + acceptance criteria: a PostgreSQL integration test posting the same
  dependency twice with both optional fields omitted and asserting `409`.
- Fix status: report-only

---

### REV-222

- ID: REV-222
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: `source-reviewed` + `manual live acceptance`
- Applies to: both
- Impact: The three clients do not share one scope-and-provenance contract; they share a base
  URL. The web client has no concept of a workspace at all, the MCP client has no concept of a
  workspace or a repository scope on search, and the API's workspace routes have no client.
  The Next.js rewrite proxies `/api/:path*` verbatim, so the browser origin can reach every
  route — including `DELETE /api/repositories/{id}` and `POST /api/repositories/{id}/reindex` —
  with no scope layer in between. Provenance fares better than scope but is uneven.
- Evidence:
  - `apps/web/next.config.ts:7-9`

    ```ts
    async rewrites() {
      return [{ source: '/api/:path*', destination: `${apiInternalUrl}/:path*` }];
    }
    ```

    A single wildcard proxy — no allowlist, no method restriction.
  - `apps/web/lib/api.ts:4-13` is a 10-line `fetch` wrapper with `cache: 'no-store'`. On
    failure it does `throw new Error(await response.text())`, so the raw API body — including
    a `422` validation array — becomes the user-facing message. No status code is preserved, so
    the client cannot distinguish `404` from `503`.
  - `grep -rin workspace apps/web/` → **no matches** on either branch. Zero of the 13 workspace
    operations has a client.
  - MCP (`apps/mcp/knowledge_way_mcp/client.py`) is genuinely well-bounded in other respects —
    GET-only (`request_for` rejects any path not starting `/api/`, line 73-74), bounded ids and
    query length (lines 45-57), `depth`/`max_nodes` clamped to the API's own maxima (lines
    114-118), and it truncates API error bodies to 1 000 characters (line 91). But
    `search_code` sends no repository scope, and no MCP tool exposes tree, file, graph or
    workspace, so an agent can only search globally.
  - Provenance: `/api/search` results carry `repository_id`, `path`, line range and
    `indexed_commit_sha` (`search.py:30-36`) — good. `citation()` (`main.py:63-65`) clamps line
    ranges to the file's real length and resolves a commit — good. But `/api/chat` citations
    drop `indexed_commit_sha` and `repository_id` entirely (`main.py:330`), keeping only
    `repository` (the display name), so chat evidence cannot be pinned to a commit.
- Probable cause + diagnostic confidence: **high** — three surfaces, three delivery dates.
- Smallest safe next step: the cheapest real improvement is `apps/web/lib/api.ts` — preserve
  the status code on the thrown error so callers can distinguish `404` from `503`. Adding
  `repository_id` and `indexed_commit_sha` to chat citations is a two-key change in
  `main.py:330`. Workspace UI is a product decision (§11.2), not a fix.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: an MCP test asserting the mode set matches the API;
  a web test asserting an API `404` surfaces as a distinguishable client error.
- Fix status: report-only

---

### REV-223

- ID: REV-223
- Category: PERFORMANCE_RISK
- Severity: medium
- Evidence level: `manual live acceptance` + `PostgreSQL integration-tested` (read-only `EXPLAIN`/timing)
- Applies to: both
- Impact: `GET /api/repositories/{id}/tree` selects the full `File` entity — including the
  `content` column — for every file under the requested prefix, uses only `id` and `path`, and
  returns a directory listing. At the repository root that is 2 284 rows and ~76 MB of TOAST
  data detoasted to produce a 2 117-byte response. The measurement attributes essentially the
  entire request latency to that read.
- Evidence: `main.py:211` — `select(File)` with no column list, and `models.py:23` shows
  `content: Mapped[str] = mapped_column(Text)` is **not** deferred.

  ```text
  $ for i in 1 2 3; do curl -s -o /dev/null -w "%{time_total}s size_dl=%{size_download}\n" \
      "localhost:8000/api/repositories/21ffa409-…/tree"; done
  0.181785s size_dl=2117
  0.168497s size_dl=2117
  0.159787s size_dl=2117
  ```

  Attribution, read-only SQL against live PostgreSQL:

  ```text
  -- payload actually present in the result set
  SELECT count(*), pg_size_pretty(sum(octet_length(content))::bigint) FROM files WHERE repository_id='21ffa409-…';
   files | content_bytes
      2284 | 76 MB

  -- forcing the same detoast the ORM performs
  SELECT sum(length(content)) FROM files WHERE repository_id='21ffa409-…' AND path LIKE '%';
     79646386
  Time: 160.127 ms

  -- plan only, rows not materialised to a client
  EXPLAIN (ANALYZE, BUFFERS) SELECT <all 10 columns> FROM files WHERE repository_id='…' AND path LIKE '%';
   Seq Scan on files (cost=0.00..261.26 rows=2284 width=761) (actual time=0.017..0.964 rows=2284 loops=1)
   Execution Time: 1.060 ms
  ```

  1 ms of planning and scanning, 160 ms of detoasting content that is discarded, 160-180 ms
  measured end to end. The gap between the `EXPLAIN` time and the detoast time is the cost.
- Probable cause + diagnostic confidence: **high**, and measured rather than inferred, as §7
  requires. Not attributed: how much of the residual ~10-20 ms is ORM hydration versus
  serialisation.
- Smallest safe next step: `select(File.id, File.path)` in `tree`. Two columns, no behaviour
  change, no migration — the function only reads `f.path` and `f.id` (`main.py:213-214`).
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: assert the emitted SQL does not select `content`;
  optionally a timing floor on a fixture repository.
- Fix status: report-only

---

### REV-224

- ID: REV-224
- Category: DESIGN_GAP
- Severity: low
- Evidence level: `unit/API-tested`
- Applies to: **integration** (both routes are integration-only)
- Impact: Two routes skip the repository existence check that their siblings perform, so a
  request against a nonexistent repository is answered with a 404 about the wrong entity. A
  client cannot distinguish "wrong repository id" from "this symbol has no card", which is the
  difference between a bug and an expected empty state.
- Evidence: `main.py:186-191` (`code_card` calls `scoped_symbol` first, with no
  `db.get(Repository, ...)`) and `main.py:202-206` (`structural_card` queries directly).
  Compare `symbol_detail` (`main.py:225`), which checks the repository first.

  ```text
  D1 GET /api/repositories/<missing>/symbols/<x>                     -> "Repository not found"
  D2 GET /api/repositories/<missing>/symbols/<x>/code-card           -> "Symbol not found"      <-- wrong entity
  D3 GET /api/repositories/<missing>/structural-cards                -> "Repository not found"
  D4 GET /api/repositories/<missing>/structural-cards/directory      -> "Structural card not found"  <-- wrong entity
  D6 GET /api/repositories/r1/structural-cards?kind=bogus            -> [422, "Invalid structural card kind"]
  D7 POST /api/workspaces/<missing>/dependencies                     -> "Workspace not found"
  D8 source == target inside a real workspace                        -> "Source and target repositories must differ"
  ```

  `D6` versus `D4` is a second inconsistency: the list route validates `kind` against
  `{'directory','package'}` and returns `422`, while the single-item route accepts any `kind`
  and returns `404`. Note that `D7`/`D8` show the workspace routes are internally consistent —
  the inconsistency is confined to the two card routes.
- Probable cause + diagnostic confidence: **high.**
- Smallest safe next step: add the two `db.get(Repository, repo_id)` guards and share the
  `kind` set between the two structural-card routes.
- Affected data/migrations/providers/cost: none. Neither route can be exercised live — the
  `code_cards` and `structural_cards` tables do not exist at alembic head `0004` (§01).
- Recommended tests + acceptance criteria: both routes return `Repository not found` for an
  unknown repository; the single-item route returns `422` for an invalid `kind`.
- Fix status: report-only

---

### REV-225

- ID: REV-225
- Category: OPTIMIZATION_OPPORTUNITY
- Severity: low
- Evidence level: `source-reviewed`
- Applies to: **integration** (route is integration-only)
- Impact: `structural_cards` gets the filter/limit ordering **right** — the path-prefix filter
  runs before the slice, and `truncated` is computed against the filtered count, so no valid
  card is silently dropped. The cost is that it loads every card row for the repository into
  Python first: the `limit` parameter never reaches SQL. Card counts are small today, so this
  is an efficiency note, not a defect.
- Evidence: `main.py:192-201`

  ```python
  cards=sorted(db.scalars(query).all(),key=lambda c:(c.path.count('/'),c.path,c.kind))   # 198: all rows
  prefix=path.strip('/')
  cards=[c for c in cards if c.path==prefix or (not prefix and c.path.count('/')==0) or (prefix and c.path.startswith(prefix+'/') and c.path[len(prefix)+1:].count('/')==0)]
  return {..., 'cards':[... for c in cards[:limit]], 'truncated':len(cards)>limit}        # 201: filter before limit
  ```

  The prefix predicate ("exactly one level below `prefix`") is not expressible as a plain
  `LIKE`, which is a legitimate reason for the Python filter. No live measurement is possible:
  the `structural_cards` table does not exist at head `0004`.
- Probable cause + diagnostic confidence: **high** on the mechanism; the practical impact is
  **not measured** and is expected to be negligible at current card counts.
- Smallest safe next step: none required. If card counts grow, push the depth predicate into
  SQL as `path LIKE prefix || '/%' AND path NOT LIKE prefix || '/%/%'` and apply a real `LIMIT`
  with `LIMIT limit + 1` to derive `truncated`.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: existing behaviour is correct; add a test pinning
  `truncated` to the filtered count if the query is ever pushed into SQL.
- Fix status: report-only

---

### REV-226

- ID: REV-226
- Category: INFO
- Severity: info
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: None — this records a **verified non-finding**, because §5.B explicitly asks whether
  error responses leak internal detail. The one route that puts a dynamic string into an
  HTTP error body is `POST /api/repositories`, and its message source was audited: it never
  echoes the submitted URL, so a clone URL containing credentials cannot be reflected back to
  the client or persisted in an error field.
- Evidence: `main.py:151-152` forwards `str(error)` from `validate_clone_url`
  (`apps/api/app/git_auth.py:21-42`), whose docstring states the intent — "Credentials in a
  URL are deliberately rejected: repository URLs are stored in the database and may be
  returned from the API" — and whose every `raise ValueError(...)` uses a fixed string with no
  interpolation of `value`. Verified rather than assumed:

  ```text
  E clone_url rejected: [422, '{"detail":"Git clone URL must be HTTPS or SSH without embedded credentials"}', "SECRET" in body: False]
  E clone_url rejected: [422, '{"detail":"Git clone URL must be HTTPS or SSH without embedded credentials"}', False]
  E clone_url rejected: [422, '{"detail":"Git clone URL path is invalid"}', False]
  ```

  The first case submitted `https://user:t0k3n-SECRET@example.test/x.git`; the token does not
  appear anywhere in the response. `git_auth.redact_git_error` provides the matching discipline
  for the log/job path. Deeper credential handling is workstream §5.F's, not repeated here.
- Probable cause + diagnostic confidence: n/a.
- Smallest safe next step: none. Keep the invariant — if a future `HTTPException` interpolates
  user input, re-audit.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: keep a test asserting a credentialed clone URL is
  rejected `422` and that the response body does not contain the credential substring.
- Fix status: report-only

---

## Not assessed

- **Live behaviour of integration-only routes.** `GET /api/repositories/{id}/graph`,
  `/code-cards`, `/symbols/{id}/code-card`, `/structural-cards`, `/structural-cards/{kind}`
  and the `repository_id`/`rerank` parameters on `/api/search` cannot be exercised against the
  running stack: the stack is `main` lineage at head `0004` and returns `404 Not Found` for
  `/graph` (verified). Findings on those routes are `source-reviewed` or `unit/API-tested`
  against the static target only.
- **PostgreSQL-specific constraint semantics (REV-221).** Proving the unreachable `409` needs
  duplicate `workspace_dependencies` rows. The live database has 0 workspaces and writing to it
  is forbidden by the mandate; no throwaway PostgreSQL instance was provisioned. A SQLite
  result would not be evidence about PostgreSQL, so none is claimed.
- **Concurrency and race behaviour.** Parallel `PUT /api/workspaces/{a}/repositories/{r}` and
  `PUT /api/workspaces/{b}/repositories/{r}` would require concurrent writes to a real
  PostgreSQL database. The `IntegrityError` retry at `main.py:136-139` reads as correct — it
  re-queries after rollback and returns `200` only if the winning row is this workspace — but
  it was **not** executed under contention. Owned by §5.C.
- **The worker-side consequence of REV-212.** Deleting a repository mid-index would have
  required starting an indexing job (long-running, and §4 forbids it). The API-side absence of
  a guard is proven; the resulting worker failure mode is stated as a risk, not a measurement.
- **Rate limiting, CORS effectiveness and DoS thresholds.** `CORSMiddleware` is configured with
  `allow_origins=settings.cors_origins.split(',')` and `allow_methods=['*']`
  (`main.py:18`), and the 52 MB `/callers` response (REV-203) is an obvious amplification
  vector, but no load test was run and no origin-bypass attempt was made. Owned by §5.F.
- **Whether `LIKE 'prefix%'` in `tree` can use `ix_files_repo_path`.** Only the degenerate
  `LIKE '%'` plan was captured (a `Seq Scan`, as expected). Index usability for a real prefix
  depends on database collation and `text_pattern_ops`, which was not inspected.
- **Browser-level behaviour of any finding.** No Playwright or browser session was run in this
  workstream. REV-208 and REV-222 are proven at the code and API level; the resulting on-screen
  behaviour is not claimed as `browser E2E verified`. Owned by the live browser pass.
- **Provider-backed paths.** `rerank=true` and `mode=semantic` with a real provider were never
  exercised (§4 cost gate; live config is `embedding_provider: none`, `rerank_provider: none`).
  No provider spend was incurred by this workstream.
- **`ingestion.py`, `code_cards.py`, `providers.py`, `parser_facts.py`, alembic upgrade or
  downgrade paths.** Out of §5.B scope; referenced only where a route's contract depends on
  them.
- **`data/`.** Excluded per the shared brief — it is the cloned pydantic-ai working copy, not
  project source.
