# 08 — Test Strategy and Real E2E Gap Analysis (Workstream G, §5.G)

> Builds on `01-runtime-and-provenance.md`. Static target = `c122529`
> (`origin/integration/consolidated-verified`) in a read-only worktree; live target = `main`
> + 7 uncommitted files in the running containers. Every finding names which one it applies to.
> `data/` excluded throughout.

## Summary

The suite that exists is good at what it covers and covers very little of what matters. It is
**827 lines of test for 1 628 lines of API plus 638 lines of web**, and it is *entirely* unenforced:
there is no CI configuration, no Makefile, no pre-commit hook, and no git hook anywhere on either
branch. Nothing in this repository ever runs a test unless a human types the command.

Three structural facts dominate every other finding:

1. **Nothing enforces anything.** No `.github/`, no `.gitlab-ci.yml`, no `Jenkinsfile`, no
   `Makefile`, no `.pre-commit-config.yaml` on `main` or `integration`. (REV-700)
2. **Every database-backed test runs on SQLite in-memory with foreign keys disabled.** Six
   production PostgreSQL semantics were empirically demonstrated to be unobservable in this
   harness, including `ON DELETE CASCADE` and FK enforcement itself. (REV-702)
3. **The web layer has no test of any kind and no tooling to write one** — no Playwright, no
   Cypress, no Vitest, no Jest, no Testing Library, and not even an ESLint config despite a
   `next lint` script. (REV-701)

On top of that, the only documented way to run the suite (`docker compose exec -T api pytest -q`,
`docs/HANDOFF.md:66`) tests the **image-baked snapshot**, not the working tree — `docker-compose.yml`
declares no source bind mount for `api`/`worker`. It reports 31 passing tests while the integration
tree contains 50. (REV-710)

Coverage of the §5.G target E2E path: **0 of 8 steps automated**. Coverage of the §5.G negative-test
list: **3 of 9 partially covered, 6 not covered at all**. Route coverage: **18 of 42 routes touched
by any test, 24 untested** — and the untested 24 include every mutating repository route, every
retrieval route, and the entire job lifecycle.

Both defects fixed live this session (RQ `job_timeout`, orphaned `running` job rows) sit in code that
**no test touches on either branch**. `IndexingJob` appears in exactly one place in the whole test
tree: as a string literal in a migration-source grep (`test_migrations.py:21`). The reaper
(`apps/api/app/reconcile.py`, untracked on `main`) ships with zero tests. (REV-703)

### Evidence-level scheme used (§5.G)

| Level | Meaning in this report | Used for |
|---|---|---|
| `source-reviewed` | Read the code; no execution. | Most coverage gaps. |
| `unit/API-tested` | An existing automated test executes it (SQLite/mocked). | The 18 covered routes. |
| `PostgreSQL integration-tested` | Verified against the live pgvector Postgres. | Catalogue queries in REV-702 only. |
| `manual live acceptance` | An ad-hoc `GET`/CLI run this session. | Negative-path probes, suite execution. |
| `browser E2E verified` | Automated browser assertion. | **Never used. Nothing qualifies.** |
| `provider E2E verified` | Real provider call asserted. | **Never used. Nothing qualifies.** |
| `documented only / pending` | Claimed in docs, not executed here. | HANDOFF browser check, nightly fork script. |

Per mandate §7: a browser observation made ad hoc by an agent (including the Playwright MCP evidence
a sibling workstream is collecting in this same session) is **`manual live acceptance`, not
`browser E2E verified`**. It is not repeatable, not versioned, not gated, and does not fail a build.
No finding in this report upgrades its evidence level on the strength of it.

---

## Suite execution result

Run inside a throwaway container from the `knowledge-way-api` image with `--network none`, the
read-only worktree mounted at `/review`, and `PYTHONPATH=/review` so `app.*` resolves to the
**integration** sources rather than the image's baked `main` copy. Verified safe before running:

```
$ grep -rn "create_engine\|DATABASE_URL" apps/api/tests/
apps/api/tests/test_incremental_structural_cards.py:3:from sqlalchemy import create_engine, select
apps/api/tests/test_incremental_structural_cards.py:13: engine=create_engine('sqlite://'); ...
apps/api/tests/test_workspaces_api.py:1:from sqlalchemy import create_engine
apps/api/tests/test_workspaces_api.py:12:    engine = create_engine(
apps/api/tests/test_ingestion_graph.py:3:from sqlalchemy import create_engine, select
apps/api/tests/test_ingestion_graph.py:21:    engine = create_engine("sqlite://")
```

Every engine is `sqlite://`. No test reads `DATABASE_URL`. `app/db.py:10` creates the Postgres engine
at import but SQLAlchemy engines are lazy, `Queue`/`Redis` are constructed inside `enqueue()` behind a
bare `except` (`main.py:49-51`), and no test enters `TestClient` as a context manager, so the
`@app.on_event('startup')` → `verify_migration_ready()` DB call never fires. `--network none` was
used anyway.

### 1. API suite — integration target (`c122529`)

```
$ docker run --rm --network none -e PYTHONPATH=/review \
    -v <worktree>/apps/api:/review:ro -w /review knowledge-way-api \
    python -m pytest -q -p no:cacheprovider tests

..................................................                       [100%]
50 passed, 20 warnings in 1.28s
```

Per file: `test_git_auth` 14, `test_code_cards` 7, `test_semantic` 7, `test_ingestion_graph` 5,
`test_parser_facts` 4, `test_graph_api` 3, `test_migrations` 3, `test_search` 3,
`test_readonly_api` 2, `test_incremental_structural_cards` 1, `test_workspaces_api` 1.

### 2. API suite — live target (`main`, as baked into the running image)

```
$ docker run --rm --network none knowledge-way-api pytest -q -p no:cacheprovider
31 passed, 11 warnings in 0.91s

$ docker run --rm --network none knowledge-way-api ls /app/tests
test_git_auth.py  test_graph_api.py  test_ingestion_graph.py  test_migrations.py
test_parser_facts.py  test_search.py  test_semantic.py  test_workspaces_api.py
```

8 files / 31 tests on `main`; 11 files / 50 tests on `integration`.

### 3. MCP suite (both branches, identical file)

```
$ ... -e PYTHONPATH=/review/apps/mcp ... python -m pytest -q apps/mcp/tests
10 passed in 0.02s
```

### 4. Benchmarks suite (integration only for `test_fork_realism.py`)

Native, as the checkout-owning user:

```
$ python3 -B benchmarks/tests/test_manifests.py -v      → Ran 3 tests ... OK
$ python3 -B benchmarks/tests/test_fork_realism.py -v   → Ran 1 test  ... OK
```

Containerised (uid mismatch against the mounted checkout) — **1 failed, 3 passed**:

```
FAILED benchmarks/tests/test_manifests.py::BenchmarkManifestTests::
       test_runner_emits_a_valid_result_without_network_or_credentials
E   subprocess.CalledProcessError: Command '['git', 'rev-parse', 'HEAD']' returned non-zero exit status 128
    (benchmarks/scripts/run_benchmark.py:11, called from :60 with cwd=ROOT.parent)

$ docker run --rm -v /home/artur/.../knowledge-way:/repo:ro -w /repo knowledge-way-api git rev-parse HEAD
fatal: detected dubious ownership in repository at '/repo'
```

Root cause is environmental (git `safe.directory`), not a product defect — but it is precisely the
environment any container-based CI would have. See REV-717.

### 5. Suite fragility: invocation from the repository root

```
$ ... -v <worktree>:/review:ro -w /review knowledge-way-api pytest -q     # no PYTHONPATH override
ImportError: cannot import name 'code_cards' from 'app' (unknown location)
ImportError: cannot import name 'StructuralCard' from 'app.models' (/app/app/models.py)
ImportError: cannot import name 'CodeCard' from 'app.models' (/app/app/models.py)
ImportError: cannot import name 'VertexEmbeddingProvider' from 'app.providers' (/app/app/providers.py)
ModuleNotFoundError: No module named 'knowledge_way_mcp'
!!!!!!!!!!!!!!!!!!! Interrupted: 5 errors during collection !!!!!!!!!!!!!!!!!!!!
```

Note the resolved paths: `/app/app/models.py`. The six tests that *did* collect silently imported the
**image's `main` code** while claiming to test the mounted integration tree. See REV-709.

### Net: is the suite green?

Yes — 50/50 on integration, 31/31 on `main`, 10/10 MCP, 4/4 benchmarks natively — **under exactly one
undocumented invocation each**. It is green and it is close to meaningless as a release gate, because
of what it does not execute.

---

## Per-layer coverage

| Layer | Exists | What it actually proves | Missing | Evidence level |
|---|---|---|---|---|
| **Unit — pure logic** | `test_parser_facts` (4), `test_search` (3), `test_git_auth` (14), `test_code_cards` (7 partly), `test_semantic` (8 partly) | Genuinely good. Tree-sitter facts incl. non-ASCII byte offsets; Sourcegraph filter parsing; clone-URL rejection and secret redaction; Vertex 429/`Retry-After`, batch splitting, in-flight cap; JSON-schema bounds and truncated-output rejection. | Nothing significant. This is the one healthy layer. | `unit/API-tested` |
| **API — HTTP via TestClient** | `test_workspaces_api` (1 test, 11 routes), `test_graph_api` (3), `test_readonly_api` (2) | Workspace CRUD, exclusive+idempotent membership 409/200, dependency 422s, symbol/callers/callees evidence, subgraph depth 422 + node truncation, repo-graph node kinds, explanation/documentation citations and 404s. All against **fake dict-like DB objects or SQLite**. | 24 of 42 routes (table below). No auth/CORS assertions. No response-schema assertion (0 `response_model` declarations in `main.py`). No error-body stability test. | `unit/API-tested` |
| **PostgreSQL integration** | **none** | — | Everything: FK enforcement, `ON DELETE CASCADE`, unique constraints over nullable columns, `ILIKE` vs `lower() LIKE`, concurrent transactions, index usage, pgvector. | `source-reviewed` |
| **Migrations** | `test_migrations` (3) | (a) alembic head equals a hardcoded literal; (b) `0001` source text contains 8 `create_table` calls and the pgvector `CREATE EXTENSION`; (c) `main.py` source text does not contain `create_all`. All three are **text greps or literal comparisons**, none executes a migration. | No `upgrade head` against real Postgres. No `downgrade`. No model↔schema drift check (e.g. `alembic check` / autogenerate-is-empty). No data-preserving upgrade test. | `source-reviewed` |
| **MCP** | `apps/mcp/tests/test_client.py` (10) | URL/query encoding, GET-only, bearer header, path quoting, input bounds (query length, mode allow-list, limit ≤ 50, depth ≤ 2, max_nodes ≤ 100), base-URL scheme rejection, env-var config errors. Strong for its 124 lines. | `server.py` (57 LOC, 6 tool functions) is entirely untested — no test asserts a tool is registered, named, or that its schema matches the client. No test proves the MCP contract matches the live API (client asserts routes as *strings*; nothing cross-checks them against FastAPI's route table). | `unit/API-tested` (client) / `source-reviewed` (server) |
| **Web / component** | **none** | — | All of it. 638 LOC, 12 components. No test runner, no test script in `apps/web/package.json`, no `eslint` anywhere (`grep -c eslint apps/web/package-lock.json` → `0`) despite `"lint": "next lint"`. `graph-model.ts` (39 LOC, pure functions `graphNodeKind` + `nodeStyles`) is a free win and has no test. | `source-reviewed` |
| **Browser E2E** | **none** | — | All of it. No Playwright/Cypress/Selenium artefact anywhere in the tree. `docs/HANDOFF.md:85` records a manual browser check in prose. | `documented only / pending` |
| **Provider E2E** | `benchmarks/scripts/run_fork_e2e_nightly.py` (134 LOC) | Nothing today: it is a manually-invoked orchestrator, not in any suite, targeting a `kw-e2e` compose project and `/tmp/kw-e2e-compose.yml` that do not exist here. It does real `POST /code-cards` (Gemini) and `reembed_repository` (Vertex) — i.e. **billable**, so it can never be a CI gate as written. | Automated, mock-boundary-contract tests that pin the provider wire format; a cost/token-budget assertion. | `documented only / pending` |
| **Benchmarks (as tests)** | `benchmarks/tests/test_manifests.py` (3), `benchmarks/tests/test_fork_realism.py` (1) | Real tests, offline, no credentials: JSON manifests validate, task ids unique, the runner emits a schema-valid result and **redacts adapter env vars** (`test_manifests.py:39`). They test the *harness*, not the product. | Nothing hits the product. `verify_live_queries.py` is the only product oracle and is broken (REV-716). `fetch_corpora.py` clones over the network (not CI-safe). | `unit/API-tested` |

---

## Route → test coverage (42 routes, integration target)

`main.py` line numbers are from the static target. 43 `@app.` decorators minus
`@app.on_event('startup')` = 42 routes; note lines 125–126 stack `PUT` and `POST` on one function.

| # | Line | Route | Test file | Note |
|---|---|---|---|---|
| 1 | 72 | `GET /health` | **none** | Live-probed only (`01-runtime`). |
| 2 | 74 | `GET /api/workspaces` | **none** | The workspace-first entry point has no test. |
| 3 | 76 | `POST /api/workspaces` | `test_workspaces_api.py:29-31` | |
| 4 | 79 | `GET /api/workspaces/{id}` | `test_workspaces_api.py:63` | 404-after-delete only; no 200 assertion. |
| 5 | 84 | `PATCH /api/workspaces/{id}` | `test_workspaces_api.py:33` | |
| 6 | 90 | `DELETE /api/workspaces/{id}` | `test_workspaces_api.py:60-62` | Does not assert repositories survive. |
| 7 | 95 | `GET /api/workspaces/{id}/dependencies` | `test_workspaces_api.py:53` | |
| 8 | 99 | `POST /api/workspaces/{id}/dependencies` | `test_workspaces_api.py:46-58` | |
| 9 | 107 | `PATCH .../dependencies/{dep_id}` | `test_workspaces_api.py:54-56` | |
| 10 | 115 | `DELETE .../dependencies/{dep_id}` | `test_workspaces_api.py:59` | |
| 11 | 120 | `GET .../repositories` | `test_workspaces_api.py:40,43` | |
| 12 | 125 | `PUT .../repositories/{repo_id}` | `test_workspaces_api.py:35-39` | |
| 13 | 126 | `POST .../repositories/{repo_id}` | **none** | The `POST` alias is never called by any test. |
| 14 | 141 | `DELETE .../repositories/{repo_id}` | `test_workspaces_api.py:42` | Does not assert repository survives. |
| 15 | 147 | `GET /api/repositories` | **none** | On `main` this route now calls `reconcile_indexing_jobs`. |
| 16 | 149 | `POST /api/repositories` | **none** | Atomic create+enqueue, `job_timeout`, orphan risk: untested. |
| 17 | 154 | `GET /api/repositories/{id}` | **none** | |
| 18 | 159 | `DELETE /api/repositories/{id}` | **none** | Relies on DB `ON DELETE CASCADE` for files/symbols/chunks/edges/jobs. |
| 19 | 164 | `POST .../sync` | **none** | |
| 20 | 168 | `POST .../reindex` | **none** | |
| 21 | 174 | `GET .../status` | **none** | On `main` this is the reaper trigger point. |
| 22 | 179 | `POST .../code-cards` | **none** | Billable route, no test. |
| 23 | 186 | `GET .../symbols/{id}/code-card` | **none** | |
| 24 | 192 | `GET .../structural-cards` | **none** | |
| 25 | 202 | `GET .../structural-cards/{kind}` | **none** | |
| 26 | 207 | `GET .../tree` | **none** | §5.G target-path step. |
| 27 | 216 | `GET /api/files/{file_id}` | **none** | §5.G target-path step. |
| 28 | 221 | `GET /api/files/{file_id}/symbols` | **none** | |
| 29 | 223 | `GET .../symbols/{symbol_id}` | `test_graph_api.py:51,59` | Includes foreign-repository 404. |
| 30 | 237 | `GET .../symbols/{id}/callers` | `test_graph_api.py:52` | |
| 31 | 239 | `GET .../symbols/{id}/callees` | `test_graph_api.py:53` | |
| 32 | 241 | `GET .../symbols/{id}/subgraph` | `test_graph_api.py:64-72` | Node truncation + depth 422. |
| 33 | 262 | `GET /api/repositories/{id}/graph` | `test_graph_api.py:77` | 3 symbols, `max_nodes=10` → truncation never exercised. |
| 34 | 296 | `GET /api/search` | **none** | `test_search.py` tests helpers only; `search()` never executed. |
| 35 | 301 | `GET /api/search/symbols` | **none** | |
| 36 | 303 | `POST /api/search/semantic` | **none** | |
| 37 | 307 | `POST /api/explanations` | `test_readonly_api.py:32,36` | `search_with_capability` monkeypatched. |
| 38 | 314 | `POST /api/documentation/generate` | `test_readonly_api.py:42,45` | |
| 39 | 328 | `POST /api/chat` | **none** | |
| 40 | 337 | `GET /api/jobs/{job_id}` | **none** | |
| 41 | 342 | `GET /api/conversations` | **none** | |
| 42 | 344 | `GET /api/conversations/{id}` | **none** | |

**18 routes covered, 24 uncovered (57 %).** On `main` the picture is worse in kind, not degree:
`main` exposes only 35 routes (routes 22–25, 33, 37, 38 do not exist there) and drops
`test_readonly_api.py`, `test_code_cards.py`, `test_incremental_structural_cards.py`.

Reproduce:

```
grep -n "^@app\." apps/api/app/main.py
grep -rhoE "['\"](/api/[^'\"]*|/health)['\"]" apps/api/tests/ apps/mcp/tests/ | tr -d "'\"" | sort -u
```

---

## §5.G target E2E path — automation status

| # | Step | Automated? | Best existing coverage | Evidence level |
|---|---|---|---|---|
| 1 | Create/select workspace | **no** | `POST /api/workspaces` via TestClient on SQLite (`test_workspaces_api.py:29`). No UI path exists at all — `workspaces` table has 0 rows in the live DB. | `unit/API-tested` (API only) |
| 2 | Add repository atomically | **no** | Nothing. `POST /api/repositories` (`main.py:149-153`) and `PUT .../repositories/{id}` are separate calls; no test — and no code — makes them one transaction. | `source-reviewed` |
| 3 | Await/check index status | **no** | Nothing. `GET .../status` untested; `IndexingJob` never instantiated in any test. | `source-reviewed` |
| 4 | Workspace-scoped search | **impossible** | The capability does not exist: `GET /api/search` (`main.py:296`) takes no workspace parameter. Nothing to test. | `source-reviewed` |
| 5 | Tree / file / symbol | **partial** | Symbol only (`test_graph_api.py:51`). `GET .../tree`, `GET /api/files/{id}`, `GET /api/files/{id}/symbols` untested. | `unit/API-tested` (symbol) |
| 6 | Repository graph | **partial** | `test_graph_api.py:77` on a 3-symbol fake DB. Not reachable on the live stack: `main` has no `/graph` route (verified: `GET /api/repositories/<id>/graph?max_nodes=10` → `404 {"detail":"Not Found"}`). | `unit/API-tested` |
| 7 | Symbol subgraph | **partial** | `test_graph_api.py:64-72`. Best-covered step. | `unit/API-tested` |
| 8 | Switch workspace, verify scope isolation | **no** | Nothing. No workspace-scoped read path exists, so there is no isolation to assert and no test asserting invariant §3.1 (server-derived scope) anywhere in the tree. | `source-reviewed` |

**0 of 8 steps automated end to end. 3 of 8 have partial single-step API coverage. 2 of 8 (4, 8)
cannot be tested because the capability does not exist.** No single test walks more than one step.

---

## §5.G negative-test coverage

| Negative case | Covered? | Evidence | Applies to |
|---|---|---|---|
| Foreign workspace ids | **partial** | Exclusive membership 409 tested (`test_workspaces_api.py:37,39`). Dependency 422 tested only for *nonexistent* ids (`:58` uses `"missing"`) and self-reference (`:57`) — **never for a real repository owned by a different workspace**, which is the actual scope-leak shape. Live 404s manually probed (`GET /api/workspaces/000…0/{,repositories,dependencies}` → 404). | both |
| Empty workspace | **partial** | Only post-removal empty list (`:43`). No test of a freshly created workspace's `GET .../repositories`, and none of a workspace-scoped search over an empty workspace (capability absent). | both |
| Unassigned repository | **no** | No test. No `Unassigned` state in the model or API; the live DB is exactly this case (1 repository, 0 workspaces) and no test describes the expected behaviour. | both |
| Missing symbol | **partial** | Foreign-repository symbol → 404 (`test_graph_api.py:59`); documentation with `symbol_id:'missing'` → 404 (`test_readonly_api.py:45`). No test for missing symbol on `callers`/`callees`/`subgraph`. Live probe: `GET .../symbols/000…0` → `404 {"detail":"Symbol not found"}`. | both |
| Graph truncation | **partial** | Node truncation on subgraph only (`test_graph_api.py:71`, `truncated is True`). No edge-budget truncation test, no truncation **cause/count** assertion, and repository-graph truncation is never triggered (3 symbols vs `max_nodes=10`) — so invariant §3.3's single hard global budget has no test. | both |
| Failed index job | **no** | No test anywhere. Both live defects live here. See REV-703. | both |
| Membership removal | **partial** | 204 + empty list (`:42-43`). **Does not assert the `Repository` row survives** — invariant §3.8 untested. | both |
| Repository / workspace deletion | **partial** | Workspace deletion asserts membership/dependency rows are 0 (`:61-62`) — but those are app-level `delete()` statements (`main.py:94`), not DB cascade, and the test does not assert repositories survive. `DELETE /api/repositories/{id}` has **no test at all**, and it is the one that depends on real `ON DELETE CASCADE` (REV-702). | both |
| Stale async response | **no** | No test. Invariant §3.7 (discard/isolate stale search, graph, chat, symbol responses on workspace/repository switch) has zero coverage — and cannot have any, because there is no web test layer. | both |

**0 fully covered, 6 partially, 3 absent.**

---

## Findings

| ID | Category | Sev | One-line |
|---|---|---|---|
| REV-700 | TEST_GAP | blocker | No CI, no Makefile, no git hook: nothing ever runs a test automatically. |
| REV-701 | TEST_GAP | critical | Zero web tests and zero web test tooling (not even ESLint) for 638 LOC across 12 components. |
| REV-702 | TEST_GAP | critical | All DB tests run on SQLite with FKs off; six PostgreSQL semantics empirically shown unobservable. |
| REV-703 | TEST_GAP | critical | The indexing-job lifecycle has no test; neither live defect would have been caught; the reaper ships untested. |
| REV-710 | CORRECTNESS_RISK | high | The only documented test command tests the container image, not the working tree (31 vs 50 tests). |
| REV-704 | TEST_GAP | high | 24 of 42 routes untested, including every mutating repository route and every retrieval route. |
| REV-705 | TEST_GAP | high | 0 of 8 §5.G target-path steps automated end to end; no test spans two steps. |
| REV-706 | TEST_GAP | high | Harness cannot express concurrency: one shared Session + StaticPool makes race/IntegrityError paths unreachable. |
| REV-707 | TEST_GAP | high | Invariant §3.8 deletion semantics unasserted; `DELETE /api/repositories` wholly untested. |
| REV-708 | TEST_GAP | high | `app.search.search()` is never executed against any database by any test. |
| REV-722 | TEST_GAP | high | Invariant §3.1 (server-derived scope) has no test anywhere; workspace-scoped read paths do not exist. |
| REV-709 | TEST_GAP | medium | No `conftest.py`/pytest config: root invocation fails with 5 collection errors and can silently test the wrong code copy. |
| REV-711 | TEST_GAP | medium | Migration tests are literal/grep tripwires; no migration is ever executed against PostgreSQL. |
| REV-712 | TEST_GAP | medium | MCP `server.py` untested; nothing cross-checks MCP route strings against the FastAPI route table. |
| REV-713 | TEST_GAP | medium | §5.G negative list: 0 of 9 fully covered, 3 entirely absent. |
| REV-714 | TEST_GAP | medium | Zero `response_model` declarations and no OpenAPI snapshot: silent response-shape breakage is shippable. |
| REV-716 | BUG_CONFIRMED | medium | The only live-acceptance oracle is pinned to four vanished repositories; ran it, 0/4 pass. |
| REV-717 | CORRECTNESS_RISK | medium | A benchmark test fails in any container/CI whose uid differs from the checkout owner. |
| REV-718 | TEST_GAP | medium | `test_workspaces_api.py` is one monolithic test over 11 routes; the first failure masks all later assertions. |
| REV-719 | TEST_GAP | medium | Graph edge budgets and truncation cause/count are untested; repository-graph truncation never fires. |
| REV-720 | TEST_GAP | medium | Provider coverage is mock-only; the sole provider E2E is manual, unversioned and billable. |
| REV-715 | DOCUMENTATION_GAP | low | `docs/HANDOFF.md:66-68` records "34 passed", matching neither branch (31 / 50). |
| REV-721 | TEST_GAP | low | `test_normal_startup_has_no_create_all_ddl` is a source-text grep, not a behavioural assertion. |

---

### REV-700

- ID: REV-700
- Category: TEST_GAP
- Severity: blocker
- Evidence level: `source-reviewed`
- Applies to: both
- Impact: Every other finding in this report is unenforceable. A contributor can push code that
  breaks all 50 tests and nothing objects. The 42-route API, the migration head assertion, the secret
  redaction tests and the input-bound tests are all advisory. There is no gate before merge, before
  image build, or before `docker compose up --build`.
- Evidence:
  ```
  $ git ls-tree -r --name-only main | grep -iE "\.github|workflow|\.gitlab|Jenkins|circleci|Makefile|justfile|Taskfile|\.pre-commit"
  none
  $ find <worktree> -name conftest.py -o -name pytest.ini -o -name tox.ini -o -name setup.cfg -o -name pyproject.toml
  (no output)
  $ ls <worktree>/.github
  ls: cannot access '.github': No such file or directory
  $ ls /home/artur/Desktop/Projekte/knowledge-way/.git/hooks/ | grep -v sample
  no active git hooks
  ```
  The only recorded invocation is prose: `docs/HANDOFF.md:66` — `docker compose exec -T api pytest -q`.
  `apps/web/package.json` has no `test` script. `scripts/knowledge-way-transfer` (integration only)
  contains no test invocation.
- Probable cause + diagnostic confidence: **certain.** The project was built solo and locally; test
  running was never externalised.
- Smallest safe next step: one `.github/workflows/test.yml` that runs the three commands already known
  to pass, nothing more:
  `(cd apps/api && PYTHONPATH=. python -m pytest -q tests)`,
  `PYTHONPATH=apps/mcp python -m pytest -q apps/mcp/tests`,
  `python -m pytest -q benchmarks/tests` — the last needs
  `git config --global --add safe.directory "$GITHUB_WORKSPACE"` (REV-717).
- Affected data/migrations/providers/cost: none. No provider call, no DB. Runs in ~2 s of compute.
- Recommended tests + acceptance criteria: no new test. Acceptance: a red build on a deliberately
  broken assertion, and a green build on `c122529`.
- Fix status: report-only

---

### REV-701

- ID: REV-701
- Category: TEST_GAP
- Severity: critical
- Evidence level: `source-reviewed`
- Applies to: both
- Impact: The entire user-facing surface — every state the mandate §5.A asks about (Empty, Loading,
  Indexing, Failed, Stale, Truncated, No-results), every accessibility requirement (focus, keyboard,
  dialog Escape/restore, canvas alternative, reduced motion), browser back/forward, deep links, and
  invariant §3.7 (discard stale responses on workspace switch) — is verifiable only by a human
  looking at a screen. Regressions in the graph explorer, search client or symbol page are invisible
  until someone notices.
- Evidence:
  ```
  $ grep -rn "playwright\|cypress\|vitest\|jest\|testing-library\|@testing" \
      --include="*.json" --include="*.ts" --include="*.tsx" --include="*.yml" --include="*.md" . \
      | grep -v '^./data/' | grep -v package-lock
  (no output)
  $ cat apps/web/package.json
  {"name":"knowledge-way-web","private":true,
   "scripts":{"dev":"next dev","build":"next build","start":"next start","lint":"next lint"},
   "dependencies":{"next":"^16.3.0","react":"19.0.0","react-dom":"19.0.0","react-force-graph-2d":"^1.29.1"},
   "devDependencies":{"@types/node":"22.10.5","@types/react":"19.0.3","typescript":"5.7.2"}}
  $ grep -c "eslint" apps/web/package-lock.json
  0
  $ ls -a apps/web/            # no eslint.config.*, no .eslintrc*
  ```
  So `npm run lint` cannot succeed as configured either. Untested web surface: 638 LOC —
  `graph-explorer.tsx` 116, `dashboard-client.tsx` 98, `graph-canvas.tsx` 80, `search-client.tsx` 66,
  `lib/repositories.ts` 41, `graph/graph-model.ts` 39, `symbols/[symbolId]/page.tsx` 22,
  `chat-client.tsx` 26, `lib/api.ts` 14, plus route shells.
- Probable cause + diagnostic confidence: **certain.** No tooling was ever added.
- Smallest safe next step: Playwright (`@playwright/test`) for browser E2E, Vitest +
  `@testing-library/react` for components. Playwright is the right choice here specifically because
  the graph is a `<canvas>` (`react-force-graph-2d`): only a real browser can assert it rendered and
  auto-fitted, and Playwright's `toHaveScreenshot` plus `page.on('console')` give canvas regression
  and console-error gates that jsdom cannot. Start with **one** Playwright spec covering the flow
  `docs/HANDOFF.md:85` already claims manually: search → symbol view → documentation.
  Cheapest first commit is smaller still: a Vitest test for `graph-model.ts`'s `graphNodeKind` +
  `nodeStyles` (39 LOC of pure functions, no DOM, no server).
- Affected data/migrations/providers/cost: Playwright needs a browser download in CI (~1 min, cached)
  and a running stack. No provider spend if the target repository is pre-indexed.
- Recommended tests + acceptance criteria:
  1. `graph-model.spec.ts` — every `GraphNodeKind` maps to a `nodeStyles` entry; unknown input →
     `'unknown'`. Acceptance: fails if a kind is added without a style.
  2. `search-to-doc.spec.ts` (Playwright) — search a known symbol, open it, generate documentation;
     assert the repository name, path, line range and `indexed_commit_sha` are all visible.
     Acceptance: fails if any provenance field disappears.
  3. `graph.spec.ts` — assert the canvas has non-zero pixels, the legend distinguishes `contains` /
     `defines` / `calls` / `declared_dependency`, and `page.on('console')` recorded no error.
  **Explicitly: obtaining any of these observations once via the Playwright MCP server in an agent
  session is `manual live acceptance`, not `browser E2E verified`, and must not be recorded as
  test coverage.**
- Fix status: report-only

---

### REV-702

- ID: REV-702
- Category: TEST_GAP
- Severity: critical
- Evidence level: `PostgreSQL integration-tested` (the Postgres side, via catalogue/expression
  `SELECT`s against the live DB) + `unit/API-tested` (the SQLite side, executed)
- Applies to: both
- Impact: This is the central finding of the workstream. Production is PostgreSQL 16 + pgvector;
  every database-backed test is SQLite in-memory **with foreign keys disabled**. Six classes of
  production behaviour are therefore not merely uncovered but *unobservable* in the current harness.
  A test can pass while asserting the opposite of production behaviour — most dangerously for
  `DELETE /api/repositories/{id}`, which relies on real `ON DELETE CASCADE` to remove 2 284 files,
  21 324 symbols, 22 900 chunks and 136 566 edges.
- Evidence: probe run in the throwaway container (`--network none`) against `app.db.Base` +
  `app.models`, using the same `create_engine("sqlite://", poolclass=StaticPool)` construction as
  `test_workspaces_api.py:12-14`:
  ```
  1) PRAGMA foreign_keys = 0
  2) FK-violating membership row COMMITTED on SQLite (PostgreSQL: FK error)
  3) after raw repository DELETE -> files rows left: 1  membership rows left: 1
       (PostgreSQL ON DELETE CASCADE would leave 0/0)
  4) duplicate dependency rows with NULL package_name/import_path stored: 2
       (PostgreSQL NULLS DISTINCT: identical result)
  5) ilike renders on SQLite as: lower(symbols.name) LIKE lower(?)
     sqlite lower('CAFÉ') = cafÉ        (PostgreSQL lower() = café)
  6) pgvector operator unavailable on SQLite: OperationalError
  ```
  PostgreSQL side, verified by read-only query against the live database:
  ```
  $ docker compose exec -T postgres psql -U knowledgeway -d knowledgeway \
      -c "SELECT lower('CAFÉ') AS pg_lower, 'CAFÉ' ILIKE '%café%' AS pg_ilike;"
   pg_lower | pg_ilike
   café     | t

  $ ... "SELECT conname, confdeltype FROM pg_constraint WHERE contype='f' AND conrelid::regclass::text IN (...)"
   17 rows: 12 × confdeltype='c' (CASCADE)  — files/symbols/code_chunks/symbol_edges/
            indexing_jobs/workspace_repositories/workspace_dependencies → repositories & workspaces
            1 × 'n' (SET NULL) code_chunks_symbol_id_fkey
            4 × 'a' (NO ACTION) symbol_edges source/target symbol, symbols_parent_symbol_id

  $ ... "SELECT indexdef FROM pg_indexes WHERE tablename IN ('workspace_dependencies','workspace_repositories');"
   CREATE UNIQUE INDEX uq_workspace_dependencies_declaration ON public.workspace_dependencies
     USING btree (workspace_id, source_repository_id, target_repository_id, package_name, import_path)
  ```
  Enumerated, precisely:
  1. **FK enforcement** — SQLite's `PRAGMA foreign_keys` defaults to `0` and SQLAlchemy does not set
     it; there is no `conftest.py` to add the `connect` event that would. A membership row pointing
     at a nonexistent workspace **and** a nonexistent repository commits cleanly. All 17 production
     FKs are inert in every test.
  2. **`ON DELETE CASCADE`** — `models.py` declares `ondelete='CASCADE'` on 12 FKs (lines 17, 20, 23,
     26, 29, 32, 35, 37, 39, 43) and `models.py` declares **no `relationship()` at all**, so
     `db.delete(r)` in `delete_repository` (`main.py:159-163`) emits a bare
     `DELETE FROM repositories`. Under SQLite the dependent rows survive as orphans; under PostgreSQL
     they cascade. A test written today would encode the orphan behaviour as correct.
  3. **Unique constraints over nullable columns** — `uq_workspace_dependencies_declaration`
     (`models.py:19`) spans nullable `package_name` and `import_path`. Both engines apply
     NULLS DISTINCT, so two byte-identical `{source, target}` declarations with both fields omitted
     are accepted — verified: 2 rows stored. The 409 handler at `main.py:104` can therefore never
     fire for the most common client payload. **No test asserts anything about this on either
     engine**; `test_workspaces_api.py:46-50` only ever creates one dependency, with both fields
     populated.
  4. **`ILIKE` semantics** — `search.py:65,68,72,77` uses `.ilike()`. SQLAlchemy renders that as
     `lower(x) LIKE lower(?)` on SQLite and `ILIKE` on PostgreSQL. SQLite's built-in `lower()` is
     ASCII-only: `lower('CAFÉ')` = `cafÉ`, so a query for `café` misses. PostgreSQL returns `café`
     and `'CAFÉ' ILIKE '%café%'` is true. Non-ASCII identifiers are a live concern in this codebase —
     `test_parser_facts.py:10` deliberately uses `class Café`. Moot today only because **no test
     executes `search()` at all** (REV-708).
  5. **Vector operations** — SQLite cannot run `<=>`/`<->`. Inverted risk here: `search.py:82-95`
     does **not** use a pgvector operator; it streams every embedded chunk into Python and calls
     `_cosine` per row. So SQLite hides nothing today — but there is no test that would notice a
     switch to a pgvector operator, and none that bounds the full-corpus scan.
  6. **Concurrency, `RETURNING`, index usage** — see REV-706. SQLite in-memory with `StaticPool` is a
     single connection; there is no second transaction to race. `grep -rn "returning\|on_conflict\|
     with_for_update\|FOR UPDATE" apps/api/app/` returns nothing, so no `RETURNING`/upsert path
     exists to test — but equally, the natural PostgreSQL fix for the membership race
     (`INSERT ... ON CONFLICT`) could not be tested if written. No test asserts any index is used;
     `EXPLAIN` plans differ entirely between engines.
- Probable cause + diagnostic confidence: **certain.** SQLite was chosen for speed and zero setup;
  the divergences were not enumerated.
- Smallest safe next step: add `apps/api/tests/conftest.py` with **two** fixtures: (a) the existing
  SQLite one, plus a `sqlite3` `connect` event issuing `PRAGMA foreign_keys=ON` — this alone converts
  divergences 1 and 2 into real assertions at zero infrastructure cost; (b) a
  `postgres_db` fixture gated on a `KW_TEST_DATABASE_URL` env var, skipped when absent, pointed at a
  **throwaway** `pgvector/pgvector:pg16` container created by `alembic upgrade head`. Never at the
  live database.
- Affected data/migrations/providers/cost: the Postgres fixture must run `alembic upgrade head`
  against a disposable database. Zero provider cost. Do not point it at `knowledgeway`.
- Recommended tests + acceptance criteria (PostgreSQL-only, marked `@pytest.mark.postgres`):
  1. `DELETE /api/repositories/{id}` on a repository with files, symbols, chunks, edges and jobs →
     204 and **0** rows remaining in each table. Acceptance: fails on SQLite (proving the fixture is
     load-bearing) and passes on PostgreSQL.
  2. Two identical dependency `POST`s with `package_name`/`import_path` omitted → assert the *decided*
     contract (409, or a partial unique index making it 409). Acceptance: currently 201/201; the test
     documents the decision.
  3. Insert a membership row with a bogus `repository_id` → `IntegrityError`. Acceptance: fails
     without `PRAGMA foreign_keys=ON` / on plain SQLite.
  4. `GET /api/search?q=Café` against a symbol named `Café` → 1 hit on PostgreSQL. Acceptance:
     documents the collation dependency.
  5. `alembic upgrade head` then `downgrade base` then `upgrade head` on an empty database → no
     error (REV-711).
- Fix status: report-only

---

### REV-703

- ID: REV-703
- Category: TEST_GAP
- Severity: critical
- Evidence level: `source-reviewed` (test absence) + `manual live acceptance` (both defects observed
  live this session per `01-runtime-and-provenance.md:141-149`)
- Applies to: both — the `job_timeout` gap applies to both branches; the reaper gap applies to `main`
  (where `reconcile.py` exists untested) and is a *missing feature*, not just a missing test, on
  `integration`
- Impact: The indexing-job lifecycle — the one subsystem that demonstrably broke twice in one session
  and left a repository stuck in `indexing` forever — has **no test of any kind**. `IndexingJob`
  appears exactly once in the entire test tree, as a string literal inside a migration source grep:
  ```
  $ grep -rn "IndexingJob\|indexing_job\|job_timeout\|enqueue" apps/api/tests/ apps/mcp/tests/
  apps/api/tests/test_migrations.py:21:        "indexing_jobs", "conversations", "messages",
  ```
- Evidence, defect by defect:

  **(a) RQ `job_timeout` — would no existing test have caught it?** No, and structurally could not.
  `enqueue()` (`integration main.py:49-51`) is:
  ```python
  def enqueue(repo_id,full=False):
   try: return Queue('indexing',connection=Redis.from_url(settings.redis_url),default_timeout=settings.index_job_timeout).enqueue(...).id
   except Exception: return None
  ```
  A bare `except Exception: return None` means that in any test environment without Redis the function
  returns `None` **silently**. No test calls `enqueue`, no test calls `POST /api/repositories`,
  `/sync` or `/reindex` (routes 16, 19, 20 — all `none` in the route table), and no test asserts a
  timeout is passed at all. The live symptom was a 697 s re-index killed by RQ's 180 s default
  (`01-runtime-and-provenance.md:143`). A test asserting only "a timeout is passed" would have caught
  it; a test asserting "the configured timeout exceeds the measured full-index duration" would have
  caught the integration branch's remaining thin margin (1 800 s) too.

  **(b) Orphaned `running` rows — would no existing test have caught it?** No. There is no test that
  creates an `IndexingJob`, no test of `GET .../status` (route 21), and no test of
  `GET /api/repositories` (route 15) — the two places the reaper is now wired in on `main`
  (`main.py` diff: `status` calls `if reconcile_indexing_jobs(db): db.expire_all()`; `repositories`
  calls it unconditionally). The live proof of the defect was a deliberate `SIGKILL`
  (`01-runtime-and-provenance.md:145`, job `c3807649`).

  **(c) The reaper itself is entirely untested.** `apps/api/app/reconcile.py` (64 LOC, untracked on
  `main`, present in the running image — verified
  `docker compose exec -T api ls /app/app/` → `reconcile.py`) has four independent behaviours and
  zero assertions:
  - `reconcile.py:45-47` — a 60 s `ORPHAN_GRACE` window using `datetime.utcnow()`, plus
    `job.started_at is None` treated as *eligible*. That `is None` branch is the risky one: a
    `pending` row promoted to `running` before `started_at` is written would be reaped immediately.
  - `reconcile.py:49-50` — liveness derived from `Worker.all()` + `worker.get_current_job()`, matched
    on `str(job.args[0])`. Silently mis-behaves if the job signature ever changes argument order.
  - `reconcile.py:56-58` — the repository is only flipped when `indexing_status == 'indexing'`.
  - `reconcile.py:62-64` — `except Exception: db.rollback(); return 0` swallows **everything**. A
    permanently broken reaper is indistinguishable from an idle one. Nothing would ever report it.
- Probable cause + diagnostic confidence: **certain** for the test absence (grep is exhaustive).
  **High** that a `job_timeout` assertion would have prevented defect (a).
- Smallest safe next step: three pure-SQLite tests, no new infrastructure — they need no Postgres,
  no Redis and no worker (fake the RQ liveness lookup).
- Affected data/migrations/providers/cost: none. All three run against SQLite in-memory with
  `_repository_ids_being_indexed` monkeypatched.
- Recommended tests + acceptance criteria:
  1. `test_index_enqueue_survives_a_full_reindex_duration` — monkeypatch `Queue` with a spy; call
     `POST /api/repositories`; assert a timeout was passed and that it is `>= 3600`. Acceptance: fails
     against the pre-fix code and against any future accidental removal. This is the single highest
     value-per-line test in this report.
  2. `test_orphaned_running_job_is_failed_and_repository_follows` — insert a `Repository`
     (`indexing_status='indexing'`) and an `IndexingJob` (`status='running'`,
     `started_at=utcnow()-120s`); monkeypatch `_repository_ids_being_indexed` → `set()`; call
     `reconcile_indexing_jobs`; assert return `1`, `job.status=='failed'`, `finished_at` set,
     `error_message == ORPHAN_MESSAGE`, `repository.indexing_status=='failed'`.
  3. `test_live_and_recent_jobs_are_never_reaped` — three cases in one test: (i) `started_at` 5 s ago
     → not reaped (grace window); (ii) `started_at` 120 s ago but repository id returned by
     `_repository_ids_being_indexed` → not reaped (live worker); (iii) `started_at is None` → assert
     the *decided* behaviour explicitly, since the current code reaps it. Acceptance: (iii) fails if
     someone changes the `None` branch silently.
  4. `test_status_endpoint_reports_a_reaped_job_as_failed` — `GET .../status` after seeding an orphan
     returns `status: 'failed'` with the message, proving the `db.expire_all()` wiring works.
  5. Postgres-marked follow-up: the reaper's `SELECT ... WHERE status='running'` under a concurrent
     worker writing the same row — needs `FOR UPDATE SKIP LOCKED` semantics that SQLite cannot
     express (REV-706).
- Fix status: report-only

---

### REV-710

- ID: REV-710
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: `manual live acceptance`
- Applies to: both
- Impact: The one documented way to run the tests validates a **stale artefact**. Anyone following
  `docs/HANDOFF.md:66` gets a green result about code that may be arbitrarily old, and would conclude
  the working tree is tested. Right now on `main` the working tree has 7 uncommitted files including
  the whole of `reconcile.py`; a contributor who edits any of them and runs the documented command
  gets 31 passing tests that never loaded the edit.
- Evidence: `docker-compose.yml` declares **no source bind mount** for `api` or `worker`:
  ```yaml
  api:
    build: ./apps/api
    volumes: ["./data:/data", "${HOME}/.config/gcloud:/root/.config/gcloud:ro"]
  worker:
    build: ./apps/api
    volumes: ["./data:/data", "${HOME}/.config/gcloud:/root/.config/gcloud:ro"]
  ```
  The `apps/api` Dockerfile does `COPY . .` at build time. So `docker compose exec -T api pytest -q`
  executes `/app/tests` — the image snapshot. Measured divergence in this session: the image runs
  **31** tests (8 files) while the integration tree contains **50** (11 files).
  A second, sharper hazard: the image sets `ENV PYTHONPATH=/app`, so mounting a different checkout
  and running `pytest` from its root resolves `app.*` to `/app`, not to the mount:
  ```
  ImportError: cannot import name 'StructuralCard' from 'app.models' (/app/app/models.py)
  ```
  Six of the eleven files collected anyway and would have reported PASS **for the wrong code**.
- Probable cause + diagnostic confidence: **certain.** Production-shaped image (no dev mount) reused
  as the test runner.
- Smallest safe next step: change the documented command to run tests where the source is —
  `(cd apps/api && PYTHONPATH=. python -m pytest -q tests)` in a venv, or
  `docker run --rm -e PYTHONPATH=/src -v "$PWD/apps/api":/src -w /src knowledge-way-api python -m pytest -q tests`.
  Update `docs/HANDOFF.md:66`. Do not add a bind mount to the production compose service.
- Affected data/migrations/providers/cost: none. Documentation and CI invocation only.
- Recommended tests + acceptance criteria: no test; this is the CI command from REV-700. Acceptance:
  edit one assertion in the working tree, run the documented command, observe it fails.
- Fix status: report-only

---

### REV-704

- ID: REV-704
- Category: TEST_GAP
- Severity: high
- Evidence level: `source-reviewed`
- Applies to: both (42 routes on integration, 35 on `main`)
- Impact: 24 of 42 routes have no test. The uncovered set is not random — it is exactly the mutating
  and retrieval halves of the API: repository create/delete/sync/reindex/status, both card
  generation/read paths, tree, file, file-symbols, all four search modes, chat, jobs and both
  conversation routes. Any of them can 500, change response shape, or lose a scope check with no
  automated signal.
- Evidence: the full table above. Reproduce with
  `grep -n "^@app\." apps/api/app/main.py` and
  `grep -rhoE "['\"](/api/[^'\"]*|/health)['\"]" apps/api/tests/ apps/mcp/tests/ | tr -d "'\"" | sort -u`.
  Three specific gaps worth naming:
  - `main.py:126` — `@app.post('/api/workspaces/{id}/repositories/{repo_id}')` is stacked on the same
    handler as the `PUT` and is **never** called by any test. The two verbs share a body, so the
    coverage is arguably transitive, but nothing pins the alias's existence.
  - `main.py:296` `GET /api/search` — the flagship route. `test_search.py` covers only `parse_query`,
    `query_terms`, `result`; `test_readonly_api.py:26` *monkeypatches* `search_with_capability` away.
  - `main.py:337` `GET /api/jobs/{job_id}` — the polling endpoint an agent or UI uses to learn a job
    failed. Untested (see REV-703).
- Probable cause + diagnostic confidence: **certain.** Tests were written per feature commit, not
  against the route table.
- Smallest safe next step: one parametrised smoke test over the whole route table asserting each
  route returns a *documented* status for a well-formed request and a 404 (not a 500) for an unknown
  id. That single test file raises touched-route coverage from 18 to 42 for a few dozen lines.
- Affected data/migrations/providers/cost: must exclude or mock `POST .../code-cards`,
  `POST /api/search/semantic` and `POST /api/chat` — all provider-touching. `providers.py`
  already returns `None` without a key (`test_semantic.py:7-18`), so a smoke test with no key
  configured is free; assert the `503`/capability-disabled response rather than a provider result.
- Recommended tests + acceptance criteria:
  1. `test_every_route_is_reachable_and_scoped` — enumerate `app.routes`, and for each
     `{repo_id}`/`{workspace_id}`/`{file_id}`/`{symbol_id}`/`{job_id}`/`{conversation_id}` path,
     request a nonexistent id and assert `404` with a `detail` string, never `5xx`. Acceptance: fails
     if a new route is added without a scope check — the strongest available proxy for invariant §3.1.
  2. `test_route_table_is_intentional` — assert the sorted `(method, path)` list equals a checked-in
     literal. Acceptance: any added, removed or renamed route fails, forcing a deliberate update.
     Prefer this over a coverage percentage; it is cheap and self-documenting.
- Fix status: report-only

---

### REV-705

- ID: REV-705
- Category: TEST_GAP
- Severity: high
- Evidence level: `source-reviewed`
- Applies to: both
- Impact: The §5.G target path is the product. Not one of its eight steps is automated end to end,
  and no test spans even two consecutive steps. Every step boundary — where scope, provenance and
  commit vectors are actually lost — is unobserved. Steps 4 and 8 cannot be tested at all because
  the capability is absent, so the path is not merely untested but currently unwalkable.
- Evidence: the target-path table above. Concretely: the longest chain any test walks is
  `test_workspaces_api.py`, which creates a workspace and assigns repositories but never indexes,
  searches, browses or graphs; and `test_graph_api.py`, which reads a symbol and its subgraph from a
  hand-built fake but never arrives there from a search or a tree. `GET /api/search` takes no
  workspace parameter (`main.py:296`), and there is no workspace graph route in the 42.
  Live confirmation that step 6 is not even reachable on the running stack:
  ```
  $ curl -s "http://localhost:8000/api/repositories/21ffa409-.../graph?max_nodes=10"
  {"detail":"Not Found"}          # main has no /graph route; integration main.py:262 does
  ```
- Probable cause + diagnostic confidence: **certain** for the absence. The path was specified in the
  mandate *after* the code was written.
- Smallest safe next step: one API-level integration test (no browser) that walks steps 1→3→5→6→7
  against a **tiny committed fixture repository** — 3 files, one commit, `ingestion.index_repository`
  with `run` monkeypatched exactly as `test_ingestion_graph.py:26-30` and
  `test_incremental_structural_cards.py:25-29` already do. Both patterns exist; nothing new is needed
  to build a real indexed repository in-process in under a second.
- Affected data/migrations/providers/cost: none — `embedding_provider()` returns `None` without a
  key, so indexing stays deterministic and free. Should be a Postgres-marked test (REV-702) to make
  cascade and scope assertions real.
- Recommended tests + acceptance criteria:
  1. `test_workspace_to_symbol_graph_walkthrough` — create workspace → create repository → assign →
     index the fixture → poll `GET .../status` until `ready` → `GET .../tree` → `GET /api/files/{id}`
     → `GET .../symbols/{id}` → `GET .../graph` → `GET .../subgraph`. Assert at every step that
     `repository_id`, `path`, `start_line`/`end_line` and `indexed_commit_sha` are present and equal
     the fixture's commit (invariant §3.6). Acceptance: fails if any hop drops provenance, and fails
     loudly at whichever hop is not yet wired.
  2. Steps 4 and 8 (`workspace-scoped search`, `scope isolation on switch`) — write them **now as
     `xfail`** against the intended contract: `GET /api/search?workspace_id=X` must return only
     member repositories, and must 404/422 for a repository outside `X`. Acceptance: they flip to pass
     the day the capability lands, and until then they are the executable specification.
- Fix status: report-only

---

### REV-706

- ID: REV-706
- Category: TEST_GAP
- Severity: high
- Evidence level: `source-reviewed`
- Applies to: both
- Impact: `add_workspace_repository` (`main.py:127-140`) is written defensively against a race — it
  pre-checks membership, inserts, and then catches `IntegrityError` to re-read and decide 200 vs 409.
  That `except IntegrityError` branch (`main.py:136-140`) is **structurally unreachable** in the
  current harness, so the code guarding exclusive membership under concurrency has never executed in
  a test. The same applies to the two dependency handlers (`main.py:103-104`, `main.py:112-113`).
  Exclusive workspace membership is invariant-adjacent (§2, §3.8); if the `IntegrityError` path is
  wrong, a repository can end up in two workspaces or a legitimate request can 409 spuriously.
- Evidence: `test_workspaces_api.py:12-26`:
  ```python
  engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
  ...
  db = Session()
  app.dependency_overrides[get_db] = lambda: db
  ```
  A single `Session` object is returned to **every** request in the test. There is one connection
  (`StaticPool`) and one transaction; requests share uncommitted state. There is no second session to
  race, no isolation level to violate, and the unique constraint can only be hit by a sequential
  duplicate — which the pre-check at `main.py:130` intercepts first, so the insert never runs.
  Corroborating: the SQLite probe (REV-702) shows FK enforcement off, and no `FOR UPDATE`,
  `SKIP LOCKED` or `ON CONFLICT` construct exists anywhere:
  `grep -rn "with_for_update\|FOR UPDATE\|on_conflict\|returning" apps/api/app/` → no output.
- Probable cause + diagnostic confidence: **certain** that the branch is unreachable in the harness.
  **Medium** on whether the branch is actually wrong — that is workstream C's call; my claim is only
  that no test can currently tell us.
- Smallest safe next step: the `postgres_db` fixture from REV-702, plus a test using **two** sessions
  against real Postgres. Do not attempt this on SQLite; it will produce a false green.
- Affected data/migrations/providers/cost: needs a throwaway Postgres. No provider cost.
- Recommended tests + acceptance criteria (all `@pytest.mark.postgres`):
  1. `test_concurrent_membership_claims_leave_exactly_one_owner` — two sessions insert the same
     `repository_id` into two different workspaces, both flush, then commit in sequence. Assert
     exactly one succeeds, the loser sees `IntegrityError`, the API surfaces 409, and
     `SELECT count(*) FROM workspace_repositories WHERE repository_id=...` is `1`. Acceptance: this
     test is the only way the `except IntegrityError` branch is ever executed.
  2. `test_idempotent_reclaim_under_race` — both sessions target the **same** workspace; assert both
     end up 200 and one row exists (the `main.py:138-139` re-read path).
  3. `test_reaper_and_worker_do_not_both_finalise_a_job` — concurrent `reconcile_indexing_jobs` and a
     worker updating the same `indexing_jobs` row; assert no lost update. Acceptance: documents
     whether `FOR UPDATE SKIP LOCKED` is needed (REV-703 item 5).
- Fix status: report-only

---

### REV-707

- ID: REV-707
- Category: TEST_GAP
- Severity: high
- Evidence level: `unit/API-tested` (what is asserted) + `PostgreSQL integration-tested` (the cascade
  topology that is not)
- Applies to: both
- Impact: Mandate invariant §3.8 states plainly: removing membership ≠ deleting the repository, and
  deleting a workspace ≠ deleting the repositories. **No test asserts either half.** The one deletion
  test checks that join rows vanish and never checks that the repositories survive — so a refactor
  that made workspace deletion cascade into `repositories` (destroying 2 284 files, 21 324 symbols
  and 136 566 edges) would pass the suite. And the one route that genuinely depends on real
  `ON DELETE CASCADE` — `DELETE /api/repositories/{id}` — has no test at all.
- Evidence:
  ```python
  # test_workspaces_api.py:42-43  (membership removal)
  assert api.delete(f"/api/workspaces/{first_id}/repositories/repo-1").status_code == 204
  assert api.get(f"/api/workspaces/{first_id}/repositories").json() == []
  # ...no assertion that Repository 'repo-1' still exists.

  # test_workspaces_api.py:60-63  (workspace deletion)
  assert api.delete(f"/api/workspaces/{first_id}").status_code == 204
  assert db.query(WorkspaceRepository).count() == 0
  assert db.query(WorkspaceDependency).count() == 0
  assert api.get(f"/api/workspaces/{first_id}").status_code == 404
  # ...no assertion that either Repository still exists.
  ```
  Those two counts pass only because `delete_workspace` (`main.py:94`) issues explicit
  `delete(WorkspaceDependency)` / `delete(WorkspaceRepository)` statements — application code, not DB
  cascade. Under SQLite with FKs off, a DB-cascade implementation would fail this test; under
  Postgres it would pass. The test cannot distinguish the two, and the asymmetry is invisible.
  `DELETE /api/repositories/{id}` (`main.py:159-163`, route 18) is untested, and per REV-702 the live
  schema really does cascade repositories → files, symbols, code_chunks, symbol_edges, indexing_jobs,
  code_cards, structural_cards (`confdeltype='c'`).
- Probable cause + diagnostic confidence: **certain.** The assertions were written to prove cleanup
  happened, not to prove nothing extra was destroyed.
- Smallest safe next step: add two assertion lines to the existing test — `Repository` count is
  unchanged after membership removal, and unchanged after workspace deletion. Two lines, no new
  infrastructure, closes the §3.8 gap for the workspace half immediately.
- Affected data/migrations/providers/cost: none for the two-line fix. The repository-deletion cascade
  test needs the Postgres fixture (REV-702).
- Recommended tests + acceptance criteria:
  1. `test_removing_membership_never_deletes_the_repository` — after 204, assert
     `db.get(Repository, 'repo-1') is not None` and its `indexed_commit_sha` is unchanged. Acceptance:
     fails if `remove_workspace_repository` ever grows a repository delete.
  2. `test_deleting_a_workspace_never_deletes_its_repositories` — after 204, assert both repositories
     still exist. Acceptance: as above for `delete_workspace`.
  3. `test_deleting_a_repository_cascades_only_its_own_derived_rows` (Postgres) — two repositories,
     each with files/symbols/chunks/edges/jobs; delete one; assert its derived rows are 0 and the
     other repository's counts are untouched. Acceptance: catches both an over-broad cascade and the
     SQLite orphan illusion.
- Fix status: report-only

---

### REV-708

- ID: REV-708
- Category: TEST_GAP
- Severity: high
- Evidence level: `source-reviewed`
- Applies to: both
- Impact: Retrieval is the product's core read path and its SQL is never executed by a test. Four
  routes (`/api/search`, `/api/search/symbols`, `/api/search/semantic`, and the search inside
  `/api/chat`) plus `/api/explanations` all funnel through `app.search.search` /
  `search_with_capability`, and the only test that touches those routes deliberately replaces the
  function with a stub. So filter-before-`LIMIT` ordering (mandate §5.B), per-modality scope and
  provenance (§5.E), the `ilike` collation dependency (REV-702 #4) and the full-corpus embedding scan
  at `search.py:88-90` are all unverified.
- Evidence:
  ```
  $ grep -rn "search(" apps/api/tests/
  (no output — no test calls search() or search_with_capability())
  $ grep -n "app.main.search_with_capability" apps/api/tests/test_readonly_api.py
  26: monkeypatch.setattr('app.main.search_with_capability',lambda *args,**kwargs:(results or [],{'enabled':False}))
  ```
  `test_search.py` covers three pure helpers only: `parse_query` (`:5-9`), `query_terms` (`:12-13`),
  `result` (`:16-23`). The scoring/limiting/fusion path is represented by a single synthetic
  `_fuse` test (`test_semantic.py:108-111`) that never touches a database.
  The un-executed code includes `search.py:65-77` (four `.ilike()` clauses) and `search.py:82-95`,
  which selects **every** embedded chunk in the repository with no `LIMIT` and scores it in Python.
- Probable cause + diagnostic confidence: **certain.** Testing `search()` needs a populated database,
  which the fake-object harness cannot provide; so it was stubbed instead.
- Smallest safe next step: reuse the existing in-process indexing fixture pattern
  (`test_ingestion_graph.py:20-31`) to build a 3-file repository, then call `search()` directly
  against that session. No new infrastructure. Provider-free: `embedding_provider()` returns `None`
  without a key, so `mode='semantic'` yields the documented capability-disabled shape.
- Affected data/migrations/providers/cost: none provider-side. Should be duplicated as a
  Postgres-marked test so `ILIKE` is real.
- Recommended tests + acceptance criteria:
  1. `test_lexical_search_returns_scoped_hits_with_full_provenance` — assert each hit carries
     `repository_id`, `path`, `start_line`, `end_line`, `symbol_id`, `indexed_commit_sha`, and that a
     second repository's identically-named symbol never appears. Acceptance: fails on any scope leak
     or dropped provenance field.
  2. `test_repo_lang_path_filters_apply_before_the_limit` — 30 matching rows across two languages,
     `lang:python limit=5`; assert all 5 are Python. Acceptance: fails if filtering happens after
     `LIMIT` (§5.B).
  3. `test_semantic_search_without_a_provider_reports_capability_not_an_error` — assert the
     capability dict and a 200, not a 500.
  4. `test_symbol_search_matches_a_non_ascii_identifier` (Postgres) — index `class Café`, search
     `café`. Acceptance: passes on Postgres, and if run on SQLite it fails — documenting REV-702 #4.
- Fix status: report-only

---

### REV-722

- ID: REV-722
- Category: TEST_GAP
- Severity: high
- Evidence level: `source-reviewed`
- Applies to: both
- Impact: Mandate invariant §3.1 — "Scope kommt vom Server": for every workspace-scoped operation the
  permitted repository set is derived server-side, and a client-supplied repository/file/symbol/job/
  dependency id outside the workspace is rejected. **No test in the tree asserts this for any read
  path**, because no workspace-scoped read path exists. That makes §5.G steps 4 and 8 untestable and
  leaves the project's central scope guarantee entirely unverified. The risk is not a broken test but
  a false claim: nothing stops a report or UI asserting workspace isolation that has never been
  exercised (§7).
- Evidence: of the 42 routes, exactly 6 take a `{workspace_id}` and **all 6 are workspace-CRUD or
  membership/dependency management** (`main.py:74-141`). Every read path — search, tree, file,
  symbol, callers, callees, subgraph, graph, chat, jobs, conversations — is repository-scoped or
  global:
  ```
  main.py:296  @app.get('/api/search')                       # no workspace parameter
  main.py:262  @app.get('/api/repositories/{repo_id}/graph')  # repository-scoped by design (§3.5)
  main.py:337  @app.get('/api/jobs/{job_id}')                 # global, no scope check at all
  ```
  The nearest existing scope test is *repository*, not workspace, isolation:
  `test_graph_api.py:59` — `assert api.get("/api/repositories/repo/symbols/foreign").status_code == 404`,
  where `foreign` has `repository_id="other"`. Good test; wrong axis.
  Nothing prevents the specific §5.G negative case either: a dependency whose source is a real
  repository owned by a *different* workspace is never tried — `test_workspaces_api.py:57-58` uses
  only a self-reference and a nonexistent id.
  Live corroboration (`manual live acceptance`): `GET /api/jobs/000…0` → `404 {"detail":"Job not
  found"}` — a 404 by row absence, not by scope derivation. With `workspaces` empty in the live DB
  (`01-runtime-and-provenance.md:112`) no workspace scope can be exercised in the browser at all.
- Probable cause + diagnostic confidence: **certain** for the absence of workspace-scoped reads and
  their tests. The gap is a product gap first (workstream A/B), a test gap second.
- Smallest safe next step: write the scope tests as `xfail` now (see REV-705 item 2) so the contract
  is executable before the capability lands, and add the generic
  `test_every_route_is_reachable_and_scoped` from REV-704 to prevent new routes shipping without a
  scope check.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria:
  1. `test_foreign_workspace_repository_is_rejected_not_filtered` — workspace A holds repo-1,
     workspace B holds repo-2; a workspace-A-scoped request naming repo-2 must 404/422, **not**
     silently return empty. Acceptance: distinguishes rejection from silent filtering, which §3.1
     requires.
  2. `test_dependency_source_from_another_workspace_is_rejected` — real repository, real id, wrong
     workspace → 422. Acceptance: closes the actual scope-leak shape the current 422 tests miss.
  3. `test_job_and_conversation_reads_are_scope_checked` — assert `GET /api/jobs/{id}` and
     `GET /api/conversations/{id}` verify the caller's scope, not just row existence. Acceptance:
     currently fails; documents the gap.
- Fix status: report-only

---

### REV-709

- ID: REV-709
- Category: TEST_GAP
- Severity: medium
- Evidence level: `manual live acceptance`
- Applies to: both
- Impact: With no `conftest.py` and no pytest configuration, the suite runs under exactly one
  undocumented invocation per package and fails under the obvious ones. Worse than failing: in the
  environment the project actually documents (the API image, `ENV PYTHONPATH=/app`) a wrong
  invocation **silently tests a different copy of the application** and reports PASS.
- Evidence:
  ```
  $ find <worktree> -name conftest.py -o -name pytest.ini -o -name tox.ini \
                    -o -name setup.cfg -o -name pyproject.toml
  (no output)
  ```
  `apps/api/tests/` has no `__init__.py`, so pytest's `prepend` import mode inserts
  `apps/api/tests` — not `apps/api` — on `sys.path`. `from app import ...` therefore requires
  `apps/api` on `PYTHONPATH` or `cwd`. Observed:
  - repo root, no `PYTHONPATH`: `Interrupted: 5 errors during collection`, with resolutions leaking
    to `/app/app/models.py` (the image copy) for the six files that *did* collect;
  - repo root, `python -m pytest`: identical 5 errors;
  - `apps/api` with `PYTHONPATH=.`: `50 passed`;
  - `apps/mcp` tests need `PYTHONPATH=apps/mcp` (documented, `docs/mcp.md:42`);
  - `benchmarks/tests` need neither but are `unittest`-based and not importable as a package
    (`unittest discover -t .` → `ImportError: Start directory is not importable`).
  Four packages, four different invocations, none of them written down in one place.
- Probable cause + diagnostic confidence: **certain.** No packaging metadata was ever added.
- Smallest safe next step: one `pyproject.toml` (or `pytest.ini`) at the repo root:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["apps/api/tests", "apps/mcp/tests", "benchmarks/tests"]
  pythonpath = ["apps/api", "apps/mcp"]
  markers = ["postgres: requires a throwaway PostgreSQL+pgvector database"]
  ```
  `pythonpath` is native to pytest ≥ 7 (the project pins 8.3.4), needs no plugin, and makes bare
  `pytest` at the repo root correct — collecting all 64 tests in one command. That single file also
  unblocks REV-700.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: no test. Acceptance: bare `pytest -q` at the repo root
  collects 64 tests and passes, and `python -c "import app; print(app.__file__)"` under the CI
  invocation resolves inside the checkout, never `/app`.
- Fix status: report-only

---

### REV-711

- ID: REV-711
- Category: TEST_GAP
- Severity: medium
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: `test_migrations.py` is three assertions, none of which runs a migration. Its head test is a
  pure tripwire that must be hand-edited on every migration — which trains contributors to edit the
  test rather than think about it — and it proves nothing about whether the migration chain actually
  applies. Migration correctness against PostgreSQL + pgvector, `downgrade` reversibility, and
  model↔schema drift are all unverified. The mandate (§5.C) asks for upgrade **and** downgrade against
  real PostgreSQL.
- Evidence: the file is 28 lines and identical between branches except the literal:
  ```python
  # integration  apps/api/tests/test_migrations.py:10-12
  def test_migrations_have_expected_head():
      script = ScriptDirectory.from_config(Config(str(API_DIR / "alembic.ini")))
      assert script.get_heads() == ["20260809_0008"]
  # main (git show main:apps/api/tests/test_migrations.py)
      assert script.get_heads() == ["20260808_0004"]
  ```
  The literal has already been edited at least four times across `0004`→`0008`. What it does buy: it
  is the only guard against a **branched migration head** (`get_heads()` returning two revisions after
  a bad merge) — a real hazard given two branches each adding migrations. That is worth keeping, but
  it should be expressed as `len(get_heads()) == 1` (no maintenance) rather than a literal (edited
  every time). The other two assertions are `read_text()` greps: `:18-23` looks for
  `CREATE EXTENSION IF NOT EXISTS vector` and 8 `op.create_table("...")` substrings — which would pass
  for a migration whose body is entirely inside `if False:`.
  No alembic command is ever executed by any test: `grep -rn "upgrade\|downgrade\|command\." apps/api/tests/`
  finds nothing.
- Probable cause + diagnostic confidence: **certain.** A cheap static tripwire stood in for an
  integration test.
- Smallest safe next step: replace the literal with `assert len(script.get_heads()) == 1` — keeps the
  branched-head guard, removes the per-migration edit. Then add the disposable-Postgres upgrade test
  from REV-702. **Never run alembic against the live database** (mandate §4; live head is
  `20260808_0004` and the integration code expects `20260809_0008`, so an accidental upgrade would be
  an irreversible schema change).
- Affected data/migrations/providers/cost: a throwaway `pgvector/pgvector:pg16` container per CI run
  (~10 s). Zero provider cost. Live DB must not be a target.
- Recommended tests + acceptance criteria (`@pytest.mark.postgres`):
  1. `test_single_migration_head` — `len(get_heads()) == 1`. Acceptance: fails on a branched head,
     never needs editing.
  2. `test_upgrade_head_from_empty_matches_the_models` — `alembic upgrade head` on an empty database,
     then compare `Base.metadata` against the reflected schema (or assert an autogenerate diff is
     empty). Acceptance: fails on any model change shipped without a migration — the check the grep
     tests only pretend to make.
  3. `test_downgrade_and_reupgrade_is_clean` — `upgrade head` → `downgrade base` → `upgrade head`.
     Acceptance: fails if any revision lacks a working `downgrade`.
  4. `test_upgrade_preserves_existing_rows` — seed one repository + file + symbol + chunk at `0004`,
     upgrade to head, assert the rows and their `indexed_commit_sha` survive. Acceptance: directly
     addresses §5.C's "new migrations must not damage index provenance, cards, embeddings or running
     jobs".
- Fix status: report-only

---

### REV-712

- ID: REV-712
- Category: TEST_GAP
- Severity: medium
- Evidence level: `unit/API-tested` (client) / `source-reviewed` (server)
- Applies to: both
- Impact: MCP is the agent-facing contract (§5.B: API, web client and MCP must share the same
  scope/provenance contract). The client's 10 tests are good, but they assert route paths as
  **string literals**, cross-checked against nothing. If a FastAPI route is renamed, all 10 MCP tests
  still pass and every agent breaks at runtime. And `server.py` — the actual MCP surface — has no
  test at all: nothing asserts a tool is registered, that its name and parameters are stable, or that
  its bounds match the client's.
- Evidence:
  ```
  apps/mcp/knowledge_way_mcp/client.py  124 LOC   → 10 tests
  apps/mcp/knowledge_way_mcp/server.py   57 LOC   →  0 tests
  $ grep -n "def " apps/mcp/knowledge_way_mcp/server.py
  14:def client()  20:def list_repositories()  26:def search_code(...)  32:def get_symbol(...)
  38:def get_callers(...)  44:def get_callees(...)  50:def get_subgraph(...)
  ```
  The literals that nothing verifies (`apps/mcp/tests/test_client.py:33-38`):
  ```python
  ("/api/repositories/repo%2Fa/symbols/symbol%20b", None),
  ("/api/repositories/repo/symbols/sym/callers", None),
  ("/api/repositories/repo/symbols/sym/callees", None),
  ("/api/repositories/repo/symbols/sym/subgraph", {"depth": 2, "max_nodes": 100}),
  ```
  Also unverified: `get_subgraph(max_nodes=100)` is allowed by the client (`:48` bounds it at ≤ 100)
  while the API's own ceiling is `MAX_GRAPH_NODES=100` (`main.py:52`). Two independently maintained
  constants, no test tying them together.
- Probable cause + diagnostic confidence: **certain.** The MCP package is standalone and has no
  import path to the API app.
- Smallest safe next step: one test in `apps/api/tests/` (which *can* import both) asserting every
  path template the MCP client emits exists in `app.routes`. Small, and it is the only thing that
  makes the existing 10 tests meaningful.
- Affected data/migrations/providers/cost: none. `PYTHONPATH` must include both packages — fixed by
  the `pythonpath` setting in REV-709.
- Recommended tests + acceptance criteria:
  1. `test_mcp_client_routes_exist_on_the_api` — for each MCP path, assert a matching
     `{path_format}` in `app.routes`. Acceptance: fails the moment a route is renamed on either side.
  2. `test_mcp_bounds_match_the_api_bounds` — assert the client's `max_nodes` ceiling equals
     `app.main.MAX_GRAPH_NODES` and its depth ceiling equals the API's `Query(le=...)`. Acceptance:
     fails if either drifts.
  3. `test_mcp_server_registers_exactly_the_expected_read_only_tools` — assert the tool set is
     `{list_repositories, search_code, get_symbol, get_callers, get_callees, get_subgraph}` and that
     no tool performs a write. Acceptance: fails if a mutating tool is ever added — the read-only
     guarantee in `docs/mcp.md` currently rests on nothing.
- Fix status: report-only

---

### REV-713

- ID: REV-713
- Category: TEST_GAP
- Severity: medium
- Evidence level: `source-reviewed` + `manual live acceptance` (the live 404 probes)
- Applies to: both
- Impact: Summary finding for the §5.G negative-test list. **0 of 9 fully covered, 6 partially, 3
  absent.** Negative behaviour is where scope leaks, misleading evidence and silent data loss appear;
  it is the half of the contract with the least coverage. Three cases are entirely absent, and one of
  them (`failed index job`) is exactly the pair of defects that broke live this session.
- Evidence: the negative-test table above. Live probes taken this session (`main`,
  `manual live acceptance`, all free GETs):
  ```
  /api/workspaces                                     -> 200  []
  /api/workspaces/000…0                               -> 404  {"detail":"Workspace not found"}
  /api/workspaces/000…0/repositories                  -> 404  {"detail":"Workspace not found"}
  /api/workspaces/000…0/dependencies                  -> 404  {"detail":"Workspace not found"}
  /api/repositories/21ffa409-…/symbols/000…0           -> 404  {"detail":"Symbol not found"}
  /api/repositories/not-a-repo/graph                  -> 404  {"detail":"Not Found"}
  /api/jobs/000…0                                     -> 404  {"detail":"Job not found"}
  /api/repositories/21ffa409-…/status                  -> 200  {"status":"ready",…}
  ```
  These behave correctly and **no automated test asserts any of them**. Note the inconsistency the
  probes expose: `{"detail":"Not Found"}` (FastAPI's default, because `/graph` does not exist on
  `main`) versus the application's own `{"detail":"Repository not found"}` — an error-shape
  distinction §5.B asks about and which nothing pins.
- Probable cause + diagnostic confidence: **certain.**
- Smallest safe next step: the parametrised negative smoke test from REV-704 item 1 covers
  `foreign workspace ids`, `missing symbol` and the 404-not-500 property for all 42 routes in one
  file. Then the three absent cases individually.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: one test per absent case —
  1. `test_unassigned_repository_has_a_defined_state` — a repository in no workspace: assert what
     `GET /api/repositories` reports for it and that workspace-scoped reads exclude it. Acceptance:
     encodes the `Unassigned` policy decision §11 requires; currently the live deployment *is* this
     state and no test describes it.
  2. `test_failed_index_job_is_visible_and_terminal` — see REV-703 items 2–4.
  3. `test_stale_response_after_workspace_switch_is_discarded` — browser-level (REV-701); assert that
     switching workspace while a search is in flight never renders the previous workspace's results
     (invariant §3.7). Acceptance: needs Playwright; cannot be done at API level.
- Fix status: report-only

---

### REV-714

- ID: REV-714
- Category: TEST_GAP
- Severity: medium
- Evidence level: `source-reviewed`
- Applies to: both
- Impact: All 42 routes return loose hand-built dicts and **zero** declare a `response_model`. Nothing
  — no schema, no test, no OpenAPI snapshot — pins the response shape. Renaming a key
  (`indexed_commit_sha` → `commit_sha`), dropping a provenance field, or changing a type is silently
  shippable: the web client and MCP client would break at runtime with a green suite. This is the
  §5.B requirement for "explicit, versionable schemas instead of loose dictionaries" and it has no
  test backing at all.
- Evidence:
  ```
  $ grep -c "response_model" apps/api/app/main.py
  0
  $ grep -rn "openapi" apps/api/tests/
  (no output)
  ```
  Response shapes are assembled by hand — e.g. `symbol_out` (`main.py:53`), `edge_out` (`main.py:54`),
  `workspace_dependency_out` (`main.py:44`), and the inline `status` dict (`main.py:178`).
  The nearest thing to a contract test is `test_graph_api.py:56`, which asserts one full edge dict
  literally — genuinely useful, and the only route where a key rename would fail:
  ```python
  assert callers.json()["callers"] == [{"symbol": ..., "edge": {"id": "e1", "source_symbol_id": "b",
    "target_symbol_id": "a", "target_name": "pkg.root", "type": "calls", "confidence": 95,
    "line": 11, "source_file_id": "fb"}}]
  ```
  and `test_readonly_api.py:35`, which pins the citation dict. Two routes out of 42.
- Probable cause + diagnostic confidence: **certain.** The dense hand-rolled style predates any
  schema discipline.
- Smallest safe next step: one snapshot test comparing `app.openapi()` to a checked-in JSON file.
  It requires **no** change to the routes, needs no `response_model`, and turns every future shape
  change into a reviewable diff. That is strictly the laziest option that closes the gap; declaring
  40 Pydantic response models is the thorough one and can wait.
- Affected data/migrations/providers/cost: none. Note the snapshot will be thin precisely *because*
  there are no response models — it pins paths, methods, parameters and status codes but not response
  bodies. Pair it with per-route body assertions on the provenance-bearing routes.
- Recommended tests + acceptance criteria:
  1. `test_openapi_schema_matches_snapshot` — assert `app.openapi()` equals
     `tests/fixtures/openapi.json`; regenerate deliberately. Acceptance: any route/parameter/status
     change produces a reviewable diff.
  2. `test_provenance_fields_are_present_on_every_evidence_response` — for search hits, symbol
     details, graph nodes, citations and documentation scope, assert the exact key set
     `{repository_id, path, start_line, end_line, indexed_commit_sha}` is present. Acceptance: fails
     if any provenance key is renamed or dropped (invariant §3.6). This is the highest-value shape
     test; do it before the 40 response models.
- Fix status: report-only

---

### REV-716

- ID: REV-716
- Category: BUG_CONFIRMED
- Severity: medium
- Evidence level: `manual live acceptance`
- Applies to: integration (the script and its oracle exist only there)
- Impact: `benchmarks/scripts/verify_live_queries.py` is the **only** artefact in the repository that
  asserts real product behaviour against real indexed data — the closest thing to an acceptance test.
  Its oracle is pinned to four repository *names* that exist in no current deployment, so it reports
  4/4 failure regardless of whether retrieval works. It cannot be adopted as a gate, and its output
  is actively misleading: a reader sees "FAILED: click-exact-symbol, …" and may conclude search is
  broken when it is fine.
- Evidence: executed against the live API (GET only, free):
  ```
  $ python3 benchmarks/scripts/verify_live_queries.py
  {'id': 'click-exact-symbol',    'pass': False, 'result_count': 0}
  {'id': 'jinja-exact-symbol',    'pass': False, 'result_count': 2,
   'top_hit_repo': 'pydanticAI', 'top_hit_symbol': 'test_s3_url_with_bucket_owner'}
  {'id': 'requests-exact-symbol', 'pass': False, 'result_count': 0}
  {'id': 'fastapi-exact-symbol',  'pass': False, 'result_count': 0}
  FAILED: click-exact-symbol, jinja-exact-symbol, requests-exact-symbol, fastapi-exact-symbol
  ```
  `benchmarks/real-indexed-query-cases.json` pins `repository` to
  `"Click benchmark 8.1.7 1786186126"`, `"Jinja demo dependency suite"`, `"requests-graph-e2e"`,
  `"FastAPI public integration fixture"`. The live database holds exactly one repository,
  `pydanticAI` (`01-runtime-and-provenance.md:126`). The `jinja` case proves the **script** works —
  it reached the API and got 2 hits — and only the expectation is stale. Note also that the oracle
  keys on a mutable display `name` (one even embeds a timestamp, `1786186126`) rather than on
  `repository_id` + `indexed_commit_sha`, so it would drift again after any re-fixture even in the
  deployment it was written for.
- Probable cause + diagnostic confidence: **certain.** The fixtures were built in a different (now
  gone) E2E deployment and the file was committed as if portable.
- Smallest safe next step: make the script self-describing rather than deleting it — resolve
  `GET /api/repositories` first, skip any case whose repository is absent, and exit non-zero only
  when a *present* repository fails its case. Then add one case pinned to the repository that is
  actually indexed.
- Affected data/migrations/providers/cost: none. `GET /api/search` only; no provider, no writes.
- Recommended tests + acceptance criteria:
  1. Rework the oracle to key on `repository_id` + `indexed_commit_sha`, not display name.
     Acceptance: re-indexing the same commit does not change the result; renaming a repository does
     not break it.
  2. `test_live_query_cases_reference_present_repositories` (offline) — assert every case's
     repository selector is resolvable in the manifest set. Acceptance: fails at commit time on a
     stale oracle, instead of failing confusingly at run time.
  3. Add a `pydanticAI` case (e.g. a known symbol at commit `640d5171…`) so the script has at least
     one passing assertion in this deployment. Acceptance: `PASS: N live query cases`, exit 0.
- Fix status: report-only

---

### REV-717

- ID: REV-717
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: `manual live acceptance`
- Applies to: both (`test_manifests.py` exists on both branches)
- Impact: A test that passes natively and fails in a container is the classic CI adoption blocker —
  and it fails for a reason unrelated to what it tests, which will be misread as a real regression the
  first time REV-700's CI is added. `run_benchmark.py` hard-requires a resolvable
  `git rev-parse HEAD` at the repository root to stamp `provenance.harness_git_sha`, so the harness
  cannot run from an exported tarball, a `git worktree` whose gitdir is outside the mount, or any
  container whose uid differs from the checkout owner.
- Evidence:
  ```
  # native, as the checkout owner
  $ python3 -B benchmarks/tests/test_manifests.py -v      → Ran 3 tests ... OK

  # containerised, read-only mount of the same checkout (root vs uid 1000)
  FAILED benchmarks/tests/test_manifests.py::BenchmarkManifestTests::
         test_runner_emits_a_valid_result_without_network_or_credentials
  E   subprocess.CalledProcessError: Command '['git', 'rev-parse', 'HEAD']' returned non-zero exit status 128
  $ docker run --rm -v <checkout>:/repo:ro -w /repo knowledge-way-api git rev-parse HEAD
  fatal: detected dubious ownership in repository at '/repo'
  # and in the detached review worktree:
  fatal: not a git repository: /home/artur/.../.git/worktrees/kw-integration
  ```
  Origin: `benchmarks/scripts/run_benchmark.py:60` calls
  `git("rev-parse","HEAD",cwd=ROOT.parent)` via `:11`, which is `check=True` with no fallback.
  This is an environment fault, **not** a product defect — stated plainly so the failure in the
  execution section above is not mistaken for one.
- Probable cause + diagnostic confidence: **certain**, root-caused to git `safe.directory`.
- Smallest safe next step: two options, both one line. In CI:
  `git config --global --add safe.directory "$GITHUB_WORKSPACE"`. In the harness: make the SHA
  optional — `except subprocess.CalledProcessError: return "unknown"` — since
  `provenance.harness_git_sha` is metadata, not a measurement. Prefer both; the harness change also
  makes the benchmark runnable from a release tarball.
- Affected data/migrations/providers/cost: none. `benchmarks/result.schema.json` may need to allow
  `"unknown"` for `harness_git_sha`.
- Recommended tests + acceptance criteria:
  1. `test_runner_records_provenance_without_a_git_checkout` — run the harness in a temp directory
     that is not a git repository; assert a schema-valid result with a sentinel SHA. Acceptance:
     fails today, passes after the one-line fallback, and permanently removes this CI blocker.
- Fix status: report-only

---

### REV-718

- ID: REV-718
- Category: TEST_GAP
- Severity: medium
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: `test_workspaces_api.py` is **one** test function covering 11 routes with ~20 sequential
  assertions against shared mutable state. The first failure aborts everything after it, so a break
  in workspace creation hides every membership and dependency assertion — the suite reports one
  failure where a dozen behaviours may be broken. It also cannot be run selectively, and it forces
  every assertion to depend on the side effects of the previous ones (e.g. the dependency block at
  `:46-59` only works because `:44-45` re-added both memberships).
- Evidence: `pytest --collect-only` reports exactly `1` test in the file:
  ```
        1 tests/test_workspaces_api.py
        3 tests/test_graph_api.py
        2 tests/test_readonly_api.py
        1 tests/test_incremental_structural_cards.py
  ```
  67 lines, one `def test_workspace_crud_and_exclusive_idempotent_membership()`, one `db` session for
  all of it, `try/finally` for cleanup. The same shape appears in
  `test_incremental_structural_cards.py` (45 lines, 1 test, two full index runs).
- Probable cause + diagnostic confidence: **certain.** Deliberate density — the whole codebase is
  written this way (semicolon-joined statements, 1-space indents). It is consistent, not accidental.
- Smallest safe next step: extract the shared engine/session/client into the `conftest.py` that
  REV-702 introduces anyway, then split along the three natural seams already present in the body:
  workspace CRUD (`:29-33`), membership (`:35-45`), dependencies (`:46-59`), deletion (`:60-63`).
  Four tests, same assertions, no new coverage — purely diagnosability. Low priority relative to
  everything above; do it *while* adding the REV-707 assertions to the same file, not as its own task.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: no new behaviour. Acceptance: breaking
  `POST /api/workspaces` produces one failure and 3 still-passing tests, instead of one failure that
  hides 19 assertions.
- Fix status: report-only

---

### REV-719

- ID: REV-719
- Category: TEST_GAP
- Severity: medium
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: Mandate §3.3 requires one global hard budget and §5.D requires hard node **and edge**
  budgets with an honest `truncated` flag carrying cause and count. Testing covers node truncation on
  one route and nothing else. Edge budgets, structural nodes/edges, truncation cause, truncation
  count, and the guarantee that every edge endpoint is present in the node set are unverified — so a
  graph could silently drop edges, or report `truncated: false` while having dropped them, with a
  green suite. That is a §3.4/§7 misleading-evidence risk, not just a coverage number.
- Evidence: the only truncation assertion in the tree is `test_graph_api.py:64-72`:
  ```python
  response = api.get("/api/repositories/repo/symbols/a/subgraph?depth=2&max_nodes=2")
  assert [node["id"] for node in graph["nodes"]] == ["b", "a"]
  assert [edge["id"] for edge in graph["edges"]] == ["e1"]
  assert graph["truncated"] is True
  ```
  Good: it pins deterministic ordering *and* truncation together, and asserts the surviving edge's
  endpoints are both in the node list. But it is boolean-only — no cause, no dropped count, and node
  budget only.
  The repository-graph test (`test_graph_api.py:77`) uses `max_nodes=10` against a fixture with 3
  in-scope symbols and 3 files, so the budget is never reached and `truncated` is never asserted at
  all on that route. There is no edge-budget parameter tested anywhere, and `MAX_GRAPH_NODES=100`
  (`main.py:52`) has no corresponding edge ceiling in any test.
  Live corroboration is unavailable on `main`: `GET /api/repositories/<id>/graph?max_nodes=10` →
  `404` (route is integration-only), so the one repository with 136 566 edges cannot be used to
  observe truncation on the running stack.
- Probable cause + diagnostic confidence: **certain** for the coverage gap. Whether the
  implementation actually honours an edge budget is workstream D's call.
- Smallest safe next step: change `max_nodes=10` to `max_nodes=2` in the existing repository-graph
  test and assert `truncated is True` — one character of fixture change, and the second route gains a
  truncation assertion.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria:
  1. `test_repository_graph_truncation_is_honest_about_cause_and_count` — assert `truncated` is True,
     and that the response states *why* (node budget vs edge budget) and *how many* were dropped.
     Acceptance: fails today; forces the honest-truncation contract §5.D asks for.
  2. `test_every_returned_edge_has_both_endpoints_in_the_node_set` — property assertion over both
     graph routes at several budgets. Acceptance: fails on any dangling edge, the most likely
     truncation bug.
  3. `test_edge_budget_is_enforced_independently_of_the_node_budget` — a fixture with few nodes and
     many edges between them. Acceptance: fails if only nodes are budgeted — which the current tests
     could not detect.
  4. `test_graph_ordering_is_stable_across_repeated_requests` — same request twice, identical node
     and edge id sequences. Acceptance: guards the deterministic tie-breakers §5.D requires.
- Fix status: report-only

---

### REV-720

- ID: REV-720
- Category: TEST_GAP
- Severity: medium
- Evidence level: `source-reviewed` + `documented only / pending`
- Applies to: integration (`code_cards.py` and the nightly script are integration-only; the Vertex
  embedding tests exist on both)
- Impact: Provider coverage is entirely mock-based, which per §7 forbids any claim of provider E2E
  verification — correct, and this report makes none. The gap that matters is different: the mocks
  encode an **assumed** wire format that nothing ever validates against the real APIs, and there is
  no test at all for the cost/telemetry surface §5.E requires (`context_s`, `provider_s`, `parse_s`,
  `persist_s`, `total_s`, valid/invalid/empty counts, token audit). The one real provider E2E path is
  a manual script that spends money and therefore can never gate CI as written.
- Evidence: what the mocks *do* cover is genuinely strong, and should be credited —
  `test_semantic.py:47-75` (429 + `Retry-After` honoured, one retry, measured delay),
  `:78-105` (a rejected 2-item batch is split into two 1-item calls),
  `test_code_cards.py:17-33` (`Retry-After: 2` → `delays == [2.0]`),
  `:36-54` (bounded retries, `MAX_RATE_LIMIT_RETRIES`),
  `:57-72` (in-flight concurrency cap: `peak == 3`),
  `:87-94` (native JSON schema, `maxOutputTokens == 512`, required keys),
  `:97-104` (truncated model output rejected).
  And provider-free-by-default is tested: `test_semantic.py:7-18,40-44` prove no provider is
  constructed without an explicit key/project, so a mis-set env cannot silently start spending.
  What is missing: every one of those fakes is a hand-written `FakeResponse`/`FakeClient` whose shape
  (`{"predictions":[{"embeddings":{"values":[…]}}]}`) is asserted nowhere against Vertex. And:
  ```
  $ grep -rn "context_s\|provider_s\|parse_s\|persist_s\|total_s\|input_tokens\|output_tokens" apps/api/tests/
  apps/api/tests/test_ingestion_graph.py:114:  ... input_tokens=10, output_tokens=5 ...
  apps/api/tests/test_ingestion_graph.py:127:  assert cards[0].input_tokens == 10
  ```
  — token fields are asserted only incidentally, as values preserved across a re-index. No test
  asserts telemetry is emitted, or that a token/cost budget is enforced.
  `benchmarks/scripts/run_fork_e2e_nightly.py` is the only provider E2E: 134 LOC, in no suite,
  targeting a `kw-e2e` compose project and `/tmp/kw-e2e-compose.yml` that do not exist in this
  environment, doing real `POST /repositories/{id}/code-cards` (Gemini, `:101`) and
  `reembed_repository` (Vertex, `:110`). It does carry its own safety rails — `CARD_BATCH_SIZE=250`,
  `MAX_CARD_INPUT_TOKENS=10_000_000` with an explicit cap check (`:98-99`), and it enables Vertex only
  after cards are durable — which is careful design; it is simply not a test.
- Probable cause + diagnostic confidence: **certain.** Deliberate: §3.10 requires providers be
  testable *without* provider access, and the suite honours that. The gap is the missing second tier.
- Smallest safe next step: do **not** add live provider calls to CI. Add the free half: a telemetry
  assertion and a recorded-response contract test. If a real-provider tier is ever wanted, it belongs
  in a separate, manually-triggered, budget-capped job — never on push.
- Affected data/migrations/providers/cost: zero for the recommendations below. The nightly script, if
  ever run, costs real Gemini + Vertex spend and needs explicit approval per §4.
- Recommended tests + acceptance criteria:
  1. `test_indexing_emits_the_documented_telemetry_fields` — assert `context_s`, `provider_s`,
     `parse_s`, `persist_s`, `total_s` and valid/invalid/empty counts are recorded. Acceptance: fails
     if a field disappears; makes the §5.E telemetry contract real at zero cost.
  2. `test_code_card_run_respects_an_input_token_budget` — with a fake provider, assert the run stops
     at the configured token cap. Acceptance: the cost guard is currently only in the nightly
     script's Python, not in the product; this test would say which.
  3. `test_provider_payload_matches_a_recorded_response` — store one **sanitised** real Vertex and one
     Gemini response as a fixture (no keys, no project ids) and drive the parsers from it. Acceptance:
     the mocks stop being self-fulfilling; a wire-format change fails a test instead of production.
  4. Keep provider E2E out of CI and record it as `documented only / pending` in every report until a
     budgeted manual run happens.
- Fix status: report-only

---

### REV-715

- ID: REV-715
- Category: DOCUMENTATION_GAP
- Severity: low
- Evidence level: `manual live acceptance`
- Applies to: both
- Impact: The documented test evidence is stale and understated, so a reader cannot tell what is
  actually covered. `docs/HANDOFF.md` records a pass count matching neither branch, and
  `docs/CURRENT_STATUS.md` describes the whole suite as one unit test. Combined with REV-710 (the
  documented command tests the image), the documentation gives a reader no way to reproduce or trust
  the stated verification.
- Evidence:
  ```
  docs/HANDOFF.md:66-68
    docker compose exec -T api pytest -q
    # 34 passed, 11 warnings in 1.33s
  ```
  Measured this session: `main` image → **31 passed**; integration tree → **50 passed**. 34 matches
  neither; it is a figure from an intermediate commit.
  ```
  docs/CURRENT_STATUS.md:10
    - Query-filter unit test passes.
  ```
  That is one assertion out of 50. And `docs/HANDOFF.md:85` —
  "Browser-Check: Suche → Symbolansicht → Dokumentationsgenerierung funktionierte gegen den lokalen
  Stack" — is a manual observation written in prose, with no artefact, which per §7 must not be read
  as browser E2E verification.
- Probable cause + diagnostic confidence: **certain.** Hand-maintained counts drift.
- Smallest safe next step: stop recording counts by hand. Once REV-700's CI exists, cite the workflow
  run instead, and replace `docs/HANDOFF.md:85` with an explicit
  "manual browser check, not automated — see 08-test-and-e2e-gap-analysis.md" note.
- Affected data/migrations/providers/cost: documentation only.
- Recommended tests + acceptance criteria: no test. Acceptance: no hand-written pass count remains in
  `docs/`, and every verification claim states its evidence level.
- Fix status: report-only

---

### REV-721

- ID: REV-721
- Category: TEST_GAP
- Severity: low
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: `test_normal_startup_has_no_create_all_ddl` guards a real invariant (§5.C: no start-up DDL
  in API/worker) with a substring search over source text. It passes if `create_all` is reached
  indirectly (`getattr(Base.metadata, "create_" + "all")()`), if the DDL moves to any other module —
  `worker.py`, `ingestion.py`, `db.py` are all unchecked — or if `Base.metadata.create_all` is called
  from an imported helper. It would also fail spuriously on a comment mentioning `create_all`. The
  invariant is worth guarding; this does not really guard it.
- Evidence: `apps/api/tests/test_migrations.py:26-28`, identical on both branches:
  ```python
  def test_normal_startup_has_no_create_all_ddl():
      source = (API_DIR / "app" / "main.py").read_text()
      assert "create_all" not in source
      assert "verify_migration_ready" in source
  ```
  Only `app/main.py` is inspected. Meanwhile the tests themselves legitimately call
  `Base.metadata.create_all(engine)` (`test_ingestion_graph.py:22`,
  `test_incremental_structural_cards.py:13`), so a blanket repo-wide grep is not the fix either — the
  assertion needs to be behavioural.
- Probable cause + diagnostic confidence: **certain.** A quick guard, never revisited.
- Smallest safe next step: assert behaviour instead of text — enter `TestClient(app)` as a context
  manager (which fires the startup event) with a spy on `Base.metadata.create_all`, and assert it was
  never called while `verify_migration_ready` was.
- Affected data/migrations/providers/cost: the startup handler calls `verify_migration_ready()`, which
  touches the database — so this test **must** run against the SQLite/throwaway fixture, never the
  live DB. On `main` startup also calls `reconcile_indexing_jobs` (REV-703), giving the same test a
  second, more valuable assertion.
- Recommended tests + acceptance criteria:
  1. `test_startup_verifies_migrations_and_never_creates_schema` — with `create_all` spied and
     `verify_migration_ready` spied, enter the `TestClient` context; assert `create_all` call count is
     0 and `verify_migration_ready` count is 1. Acceptance: catches indirect and relocated DDL, which
     the grep cannot, and is the only test that would exercise the startup handler at all.
  2. Extend to the worker entry point (`worker.py`), currently unchecked by any test — and where the
     `main` working tree added the boot-time reconcile call.
- Fix status: report-only

---

## Smallest set of tests that would de-risk the most

Ordered by risk removed per line written. Items 1–4 need no new infrastructure and total well under
200 lines.

1. **One CI workflow (REV-700).** Zero test code. Until this exists every item below is advisory.
   Runs the three commands already proven green, plus
   `git config --global --add safe.directory "$GITHUB_WORKSPACE"` for REV-717. *Removes: the entire
   enforcement gap.*
2. **One root `pyproject.toml` `[tool.pytest.ini_options]` with `pythonpath` (REV-709).** ~5 lines.
   Makes bare `pytest` at the repo root collect all 64 tests, and eliminates the
   silently-testing-the-wrong-copy hazard (REV-710). *Prerequisite for item 1 being simple.*
3. **`conftest.py` with `PRAGMA foreign_keys=ON` (REV-702).** ~6 lines. Converts 17 inert production
   foreign keys and 12 `ON DELETE CASCADE` declarations into things a test can actually observe,
   without any Postgres. Highest structural leverage in this list.
4. **Four indexing-job tests (REV-703).** ~60 lines, pure SQLite, RQ liveness faked. Covers the
   `job_timeout` assertion, orphan reaping, the grace window and live-worker exclusion, and the
   `status` endpoint. *These are the only tests that would have caught either defect that broke
   production this session, and the reaper's 64 lines currently have none.*
5. **Two assertion lines for invariant §3.8 (REV-707).** Repository count unchanged after membership
   removal and after workspace deletion. Two lines guarding against catastrophic, silent data loss.
6. **One parametrised route smoke test (REV-704, REV-713).** ~40 lines. Raises touched-route coverage
   from 18/42 to 42/42, asserts 404-not-500 for unknown ids on every path parameter, and is the
   strongest cheap proxy for invariant §3.1.
7. **One route-table snapshot + one OpenAPI snapshot (REV-704 item 2, REV-714 item 1).** ~15 lines
   plus a fixture. Makes every future contract change a reviewable diff.
8. **One provenance-field assertion across all evidence responses (REV-714 item 2).** ~20 lines.
   Guards invariant §3.6 on search hits, symbol details, graph nodes, citations and documentation
   scope simultaneously.
9. **`search()` executed against a real fixture index (REV-708).** ~50 lines reusing
   `test_ingestion_graph.py`'s existing in-process indexing pattern. Puts the flagship read path
   under test for the first time.
10. **A `@pytest.mark.postgres` tier on a throwaway pgvector container (REV-702, REV-706, REV-711).**
    The first infrastructure cost. Unlocks cascade correctness, the concurrent-membership race, and
    real `upgrade`/`downgrade`/drift checks. Nothing above it needs this, so it can land later — but
    nothing else can substitute for it.
11. **One Playwright spec plus one Vitest spec for `graph-model.ts` (REV-701).** The first browser
    assertion the project has ever had; start with the flow `docs/HANDOFF.md:85` already claims.
12. **`xfail` specs for workspace-scoped search and scope isolation (REV-705, REV-722).** ~30 lines
    that cost nothing today and become the executable specification for the next product slice.

Deliberately *not* recommended: a coverage-percentage gate (the route-table and OpenAPI snapshots are
cheaper and more honest), live provider calls in CI (§3.10, §4), and any restructuring of the existing
dense test style beyond splitting `test_workspaces_api.py` while editing it anyway (REV-718).

---

## Not assessed

- **Whether the tests would pass against real PostgreSQL.** No throwaway pgvector database was
  created; the live one was read via `SELECT` only. Migrating or pointing tests at
  `knowledgeway` would have been an irreversible schema change under an analysis-only mandate
  (§4). All PostgreSQL divergences in REV-702 are backed by catalogue/expression queries against the
  live DB plus executed SQLite comparisons — never by running the suite on Postgres.
- **Whether the `except IntegrityError` branches are correct** (`main.py:104,113,136`). They are
  unreachable in the current harness (REV-706), so only their existence was reviewed. Correctness is
  workstream C's call.
- **Whether the graph implementation honours an edge budget.** REV-719 establishes only that no test
  covers it. Reading `main.py:262-295` to decide was left to workstream D to avoid contradictory
  findings.
- **Runtime behaviour of the integration branch.** Not built or run (per `01-runtime-and-provenance`).
  Integration tests were executed in a throwaway container against mounted integration sources, which
  is `unit/API-tested`, not live evidence. `GET /api/repositories/{id}/graph` and
  `POST /api/explanations` could not be probed live because those routes do not exist on `main`.
- **`benchmarks/scripts/run_fork_e2e_nightly.py` execution.** Not run: it does billable Gemini and
  Vertex work (§4, no cost approval) and its `kw-e2e` compose project and `/tmp/kw-e2e-compose.yml`
  do not exist here. Assessed by source only.
- **`benchmarks/scripts/fetch_corpora.py` execution.** Clones third-party repositories over the
  network; not run.
- **`apps/web` build and lint.** `npm run build` / `npm run lint` were not executed (no Node toolchain
  invoked, and `next lint` cannot succeed without an ESLint config — REV-701). The absence of test
  tooling is `source-reviewed` from `package.json` and `package-lock.json`.
- **Mutating endpoints.** `POST /api/repositories`, `/reindex`, `/sync`, `/code-cards`,
  `/explanations`, `/documentation/generate`, `/chat`, `/search/semantic` were never called, per the
  workstream constraints. Their coverage status is `source-reviewed` from the route table.
- **Whether adding `PRAGMA foreign_keys=ON` would break the existing 50 tests.** Not tried — it would
  require writing a `conftest.py`, which the read-only constraint forbids. Stated as a likely
  consequence in REV-702, not as a verified result. Two candidates worth checking first:
  `test_ingestion_graph.py:85` (a `SymbolEdge` with `target_symbol_id=None`) and
  `test_graph_api.py`'s fake-object DB (which bypasses SQL entirely and is unaffected).
- **Coverage percentages.** No `coverage.py` run; `pytest-cov` is not in `requirements.txt` and
  installing it would have modified the environment. All coverage claims in this report are
  route-level and file-level counts derived from grep and `--collect-only`, not line coverage.
