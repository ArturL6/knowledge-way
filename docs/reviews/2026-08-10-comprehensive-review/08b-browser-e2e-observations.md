# 08b — Live browser E2E observations

> Workstream: live browser pass (§5.A / §5.D / §5.G of
> `docs/CODING_AGENT_COMPREHENSIVE_REVIEW_PROGRAM.md`). Read-only.
> This report is the **only** source of `browser E2E verified` evidence in the review.
> It builds on `01-runtime-and-provenance.md` and does not restate it.

## 1. Tooling used, and its limits

### 1.1 The provided Playwright MCP server could not be used

| Item | Value |
|---|---|
| Plugin | `playwright@claude-plugins-official`, `.mcp.json` → `npx @playwright/mcp@latest` |
| Version resolved | `@playwright/mcp` **0.0.79**, bundling `playwright-core` `1.63.0-alpha-2026-08-05` |
| Result of first call | **failed to initialise** |

```text
mcp__plugin_playwright_playwright__browser_navigate → http://localhost:3000/
Error: async initializeServer: Chromium distribution 'chrome' is not found
       at /opt/google/chrome/chrome
Run "npx playwright install chrome"
```

Diagnosis, and why it is not recoverable inside this session:

- `@playwright/mcp` 0.0.79 defaults to the **`chrome` channel**, whose Linux path is
  hard-coded in `playwright-core/lib/coreBundle.js:32966` as `/opt/google/chrome/chrome`.
  There is no environment-variable override (`grep` for `process.env` in the package
  returns nothing relevant).
- Google Chrome is not installed. `npx playwright install chrome` requires root
  (`Switching to root user to install dependencies… sudo: a password is required`) and
  `sudo -n` is unavailable. `/opt` is `root:root drwxr-xr-x`.
- The server is already running with fixed argv, so `--browser chromium` /
  `--cdp-endpoint` cannot be supplied, and editing the plugin's `.mcp.json` is both
  outside my read-only mandate and would not take effect without a session restart.
- Only `chromium-1223` and `chromium_headless_shell-1223` are present in
  `~/.cache/ms-playwright`; no `firefox`/`webkit`/`msedge`, so no other channel resolves.

### 1.2 Substitute driver actually used

I drove the **same engine** directly instead, by requiring the `playwright-core` already
vendored in the MCP's own npx cache and pointing it at the installed Chromium build:

```text
playwright-core 1.63.0-alpha-2026-08-05  (the MCP server's own bundled version)
executablePath /home/artur/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome
Chromium 148.0.7778.96, headless, viewport 1440x1000 (and 390x844 for the mobile pass)
```

Driver scripts live in the session scratchpad
(`drive.mjs`, `graph.mjs`, `graph2.mjs`, `graph3.mjs`, `rest.mjs`, `final.mjs`,
`final2.mjs`, `gap.mjs`) and wrote nothing into the repository except the screenshots
listed in §6. This is a real browser rendering the real deployed build, so findings below
are legitimately `browser E2E verified`.

**Limits of this substitute, stated per §8.7:**

- Single engine only (Chromium). No Firefox/WebKit cross-browser evidence.
- Headless. Not a substitute for real GPU canvas behaviour or real screen-reader output;
  accessibility findings are DOM/ARIA-tree based, not NVDA/VoiceOver-verified.
- Assistive-technology announcement is inferred from `aria-live` / `role` attributes, not
  from an AT transcript.
- `browser_*` MCP tool semantics (snapshot refs, network panel) were unavailable; I used
  `ariaSnapshot()`, `page.on('console'|'pageerror'|'response'|'requestfailed')` and
  `locator.screenshot()` as equivalents.
- Plugin output is evidence but, per §8.7, does not replace the scope/provenance checks —
  which is why every finding below names the build it was observed against.

### 1.3 The live target changed **twice** while I was driving it — read this before using any finding

This materially affects `Applies to:` on every finding, so it is recorded as fact, not as
an aside.

| Window (local) | What was running | Frontend identity | DB head |
|---|---|---|---|
| until **14:28:14** | `main` lineage as described in `01-runtime-and-provenance.md` | byte-identical to `stash@{0}` | `20260808_0004` |
| from **14:28:14** | rebuilt containers, integration code | `c122529` **plus in-flight uncommitted edits** | `20260809_0008` |

Verified, not assumed:

- `docker inspect knowledge-way-web-1 --format '{{.State.StartedAt}}'` →
  `2026-08-10T12:28:14Z` = **14:28:14** local. A new `knowledge-way-migrate-1` service
  (`Exited (0)`) appeared, and `alembic_version` moved `20260808_0004` → `20260809_0008`
  with `code_cards` and `structural_cards` tables now present.
- Data survived the migration: 1 repository, 21 324 symbols, **still 0 workspaces**.
- The web container has **no bind mounts** and runs a baked production build, so
  working-tree edits never changed what I observed — only the two rebuilds did.

**Correction to the brief's citation advice.** For the pre-14:28 build, `git show
5aedeb3:apps/web/...` is the *wrong* ref — `5aedeb3` lacks the symbol picker entirely.
The running frontend was byte-identical to `stash@{0}`:

```text
apps/web/app/graph/graph-explorer.tsx  container 412eec4a…  5aedeb3 c59d23b0…  stash@{0} 412eec4a…  ✓
apps/web/app/globals.css               container e685575b…  5aedeb3 c3e86f3f…  stash@{0} e685575b…  ✓
apps/web/app/graph/graph-canvas.tsx    identical in 5aedeb3 and stash@{0}
```

I therefore extracted the running sources out of the container
(`docker cp knowledge-way-web-1:/app/app/... `) and cite those; they match `stash@{0}`.

Because the post-14:28 build contains **unreviewed in-flight edits**, I never present its
behaviour as evidence about `c122529`. Where the distinction matters I cross-checked the
pristine ref by source (`git show origin/integration/consolidated-verified:<path>`) and
labelled it `source-reviewed`.

Which frontend files are identical across the two lineages (so live evidence transfers):

```text
IDENTICAL  app/dashboard-client.tsx   app/files/[id]/page.tsx   app/layout.tsx   app/page.tsx
DIFFERS    app/search/search-client.tsx   app/chat/chat-client.tsx   app/graph/*
```

### 1.4 Cost gate — how I established that searching was free

The default `/search` mode is `hybrid`, and `search_with_capability()` calls
`embedding_provider()` for `mode in ('hybrid','semantic')`. Before running any query I
verified no provider could be reached, so no query could bill:

- `apps/api/app/config.py:12` → `embedding_provider: str = "none"`; no
  `EMBEDDING_PROVIDER` / `OPENROUTER_API_KEY` in `.env` or in the container environment.
- `providers.py:45-53` → `embedding_provider()` returns `None` unless provider is
  `openrouter` **and** a key is set. With `None`, the semantic branch is skipped entirely —
  no HTTP request is constructed.

Every lexical/symbol query below was therefore provider-free. I still did not run
`semantic` mode or submit chat, per instruction.

---

## 2. Route-by-route walkthrough

`Build` column: **M** = main lineage (pre-14:28), **C** = current build (post-14:28).

| Route | Build | Reachable by navigation? | States seen | Console errors / failed requests |
|---|---|---|---|---|
| `/` dashboard | M | yes — sidebar `Dashboard` | metrics (1/1/0), populated repo list with `ready` badge, add-repo form, client-side URL validation error, delete confirm dialog | only `favicon.ico` 404; no API 4xx |
| `/search` | M | yes — sidebar `Search` | initial empty, `Searching…`, 30 results, **0 results (indistinguishable from initial)**, results lost on reload | favicon 404 only |
| `/graph` | M | yes — sidebar `Code graph` | `No graph loaded yet.`, short-query error, symbol hit list, resolved symbol + UUID, `100 nodes · 112 relationships · truncated at the 100-node API limit`, **`0 nodes` dead end after any filter** | favicon 404 only |
| `/graph` | C | yes | `No graph data to display` **as the initial state**, `Repository map` = `100 nodes · 7952 relationships · truncated at the node cap`, symbol picker with `aria-live` hit list, `Focus symbol` subgraph, working filters, `Fixture demo · 8 nodes` | favicon 404 only |
| `/files/[id]` | C | **yes** — `Open source →` from a `/search` result card | file view: path heading, `markdown · commit 640d5171fe57`, per-line anchors, `#L477` scroll worked (`scrollY=3411`) | favicon 404 only |
| `/files/[id]` negative | C | n/a | **raw HTTP 500** `This page couldn't load` + `ERROR 1175352238` for nonexistent, malformed and wrong-type ids | `HTTP 500`, `pageerror: Minified React error #441` |
| `/chat` | M | yes — sidebar `AI Chat` | source-reviewed only: no repository scope selector, single textarea + `Ask codebase` | not assessed live (build swapped) |
| `/chat` | C | yes | heading `Grounded code questions`, **required repository selector showing `pydanticAI · 640d5171fe57`**, textarea, `Ask codebase` | clean |
| `/workspaces` | C | **no such route** | clean Next.js `404 This page could not be found.` inside the app shell | expected 404 |
| mobile 390×844 | C | yes | no horizontal overflow on `/`, `/search`, `/chat`; `/graph` overflows by 8 px and pushes the canvas 1 376 px below the fold | clean |

Recurring console noise on **every** page of **both** builds: one
`Failed to load resource: 404` for `/favicon.ico` (confirmed:
`curl -o /dev/null -w %{http_code} localhost:3000/favicon.ico` → `404`). No hydration
errors, and no polling 404s, were observed on any route.

**First-time-user reality (zero workspaces).** The sidebar offers only Dashboard, Search,
Code graph, AI Chat. There is no workspace switcher, no "create workspace" control, and
`/workspaces` 404s. `GET /api/workspaces` returns `[]`. A first-time user cannot begin the
§2 flow (`choose or create a workspace → …`) at all; the only available entry point is
"Connect a repository" on the dashboard. See REV-807.

---

## 3. Findings table

| ID | Category | Severity | One-line |
|---|---|---|---|
| REV-800 | BUG_CONFIRMED | high | Any graph filter change permanently zeroes the graph; "All types" does not restore it |
| REV-801 | CORRECTNESS_RISK | high | Symbol search is nondeterministic and cannot reach the repository's principal symbol (`Agent`) |
| REV-802 | BUG_CONFIRMED | high | `/files/<bad-id>` returns a raw HTTP 500 error page instead of a clean 404 |
| REV-803 | CORRECTNESS_RISK | high | "Repository map" caps nodes at 100 but returns 7 952 edges in a 3.61 MB payload; no edge budget |
| REV-804 | CORRECTNESS_RISK | high | One `confidence` field carries two scales (structural `1`, code `100`); the filter is a no-op |
| REV-805 | DESIGN_GAP | medium | `/search` no-results state is byte-identical to the untouched empty state |
| REV-806 | DESIGN_GAP | medium | `/search` keeps no URL state: reload and Back discard all results; no deep link |
| REV-807 | DESIGN_GAP | medium | Workspace-first is entirely absent from the UI; a first-time user cannot start the intended flow |
| REV-808 | BUG_CONFIRMED | medium | Delete dialog does not trap focus, ignores Escape, and does not restore focus on close |
| REV-809 | DESIGN_GAP | medium | Graph canvas has no text alternative and no keyboard access; truncation notice is visual-only |
| REV-810 | PERFORMANCE_RISK | medium | File view renders one DOM node per line — 11 554 lines → 23 140 elements, no virtualisation |
| REV-811 | CORRECTNESS_RISK | medium | Graph payloads ship full `source_text`; the node panel dumps it plus internal layout state |
| REV-812 | DESIGN_GAP | medium | Search result provenance omits the indexed commit (main lineage only) |
| REV-813 | DESIGN_GAP | medium | Current build's initial graph state claims "filters returned no connected nodes" before anything is loaded |
| REV-814 | DESIGN_GAP | medium | `/search` controls lack accessible names; arriving results are never announced |
| REV-815 | DESIGN_GAP | medium | The file view is a navigational dead end — no route onward to symbol, graph or repository |
| REV-816 | DESIGN_GAP | medium | Fixture demo is mistakable for real data; the repository selector still names the real repo |
| REV-817 | DESIGN_GAP | medium | `/graph` had no URL state on main lineage — nothing deep-linkable, Back leaves the page |
| REV-818 | DESIGN_GAP | low | Minimum query length is inconsistent and unenforced: 2 chars yields 30 substring hits |
| REV-819 | DESIGN_GAP | low | A `ready` repository still displays in-progress text "finalizing · 2284 files" |
| REV-820 | DESIGN_GAP | low | No `prefers-reduced-motion` handling; the force simulation animates indefinitely |
| REV-821 | PERFORMANCE_RISK | low | On a 390 px viewport the graph is pushed 1 376 px below the fold and overflows by 8 px |
| REV-822 | DESIGN_GAP | info | Missing `favicon.ico` logs a console error on every page load of every route |
| REV-823 | DESIGN_GAP | low | Main-lineage graph legend advertised four node kinds the subgraph API never returns |
| REV-824 | TEST_GAP | medium | No browser E2E coverage exists, and the live target was rebuilt twice mid-review |

---

## 4. Findings

### REV-800

- ID: REV-800
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: browser E2E verified (main lineage) + source-reviewed (`c122529`)
- Applies to: main (running, pre-14:28) **and** `c122529` — the defect is in code that is
  byte-identical on both. Fixed by an in-flight edit in the post-14:28 build.
- Impact: The two filter controls on the primary analysis surface destroy the graph on
  first use. Recovery requires re-running the whole symbol search and reloading the
  subgraph; there is no "reset filters" that works. The summary bar simultaneously
  reports an impossible graph — `0 nodes · 112 relationships` — and presents it as fact.
- Evidence:
  1. `/graph` → repository `pydanticAI` → symbol `Agent` → pick first hit → depth `2` →
     `Load graph`. Expected and got:
     `API result · 100 nodes · 112 relationships · truncated at the 100-node API limit`,
     canvas rendered (`graph-truncated-at-100-nodes.png`).
  2. Set **Relationship** to `call` — the only relationship type present, so a no-op
     filter. Expected: 100 nodes retained. **Actual:**
     `API result · 0 nodes · 112 relationships · truncated at the 100-node API limit`
     plus `No graph data to display. The selected filters returned no connected nodes.`
     Canvas element count dropped `1 → 0`
     (`graph-relationship-filter-empties-canvas.png`).
  3. Set **Relationship** back to `All types`. Expected: graph returns. **Actual:** still
     `0 nodes`, canvas still absent
     (`graph-relationship-filter-all-types-restored.png`).
  4. **Minimum confidence** `50% / 75% / 90%` — all three keep `0 nodes`
     (`graph-confidence-filter-noop.png`).
  5. Console and network were **clean** throughout — no error surfaces to the user.
- Probable cause + diagnostic confidence: **high, and self-proving from step 3.**
  `graph-explorer.tsx:90-96` (running build, = `stash@{0}`) computes
  `const connected = new Set(links.flatMap((link) => [link.source, link.target]))` and then
  `graph.nodes.filter((node) => connected.has(node.id) || graph.links.length === 0)`.
  `react-force-graph` mutates the link objects it is handed in place, replacing the
  `source`/`target` **string ids with node object references**. After the first render
  `connected` therefore holds objects, and `connected.has(node.id)` — a string lookup —
  can never match. Step 3 is conclusive: with `relationship === 'all'` and `minimum === 0`
  the filter returns *every* link, so if the endpoints were still strings every node would
  match; `0 nodes` is only possible if they are no longer strings.
  The identical logic is at `c122529` lines 71-73 of the same file, so `c122529` carries
  the defect too.
- Smallest safe next step: normalise the endpoint before the set lookup, e.g. a
  `linkEndpointId(v) => typeof v === 'object' ? v.id : String(v)` helper used in both the
  `flatMap` and the membership test. *An in-flight edit by another authorised session has
  already introduced exactly such a `linkEndpointId` helper; I re-tested the post-14:28
  build and the filters now retain `100 nodes · 211 relationships` through both controls
  (`current-build-filters.png`), which independently confirms the diagnosis. I drafted no
  code myself — this finding is report-only.*
- Affected data/migrations/providers/cost: none. Pure client-side rendering.
- Recommended tests + acceptance criteria: component test that renders `GraphCanvas`,
  lets the force layout mutate the links, then re-applies a filter and asserts
  `filteredGraph.nodes.length` is unchanged for a no-op filter. Browser E2E: load a
  subgraph, toggle every relationship option and every confidence threshold, assert the
  canvas is present and the node count never drops to `0` while links remain.
- Fix status: report-only

### REV-801

- ID: REV-801
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: browser E2E verified (both builds)
- Applies to: main (running) and current build; the responsible query is identical at
  `c122529` (`apps/api/app/search.py:78`) → **both**.
- Impact: The symbol picker is the only UUID-free route to a focused graph, and it cannot
  reach `Agent` — the single most important symbol in `pydantic-ai`. Worse, the same query
  returns a **different arbitrary result set on each run**, so the surface is
  non-reproducible, violating the determinism requirement in §5.D.
- Evidence:
  1. Main-lineage build, `/graph` → `Symbol` = `Agent` → `Find symbols`. Expected the
     `Agent` class near the top. **Actual:** 15 hits, `any hit named exactly "Agent"?
     false`, all drawn from just three test files
     (`tests/test_temporal.py`, `tests/test_capability_stream_teardown.py`,
     `tests/test_ui_web.py`) — screenshot
     `graph-symbol-search-Agent-all-from-one-test-file.png`.
  2. Current build, same query. **Actual:** again 15 hits, again `exact "Agent" present?
     false`, but now from a **completely different** file set —
     `tests/models/test_openai.py`, `examples/pydantic_ai_examples/rag.py`,
     `tests/models/test_google.py`, `tests/models/test_model_test.py`,
     `pydantic_ai_slim/pydantic_ai/_instrumentation.py`, `tests/models/test_xai.py`,
     `tests/evals/test_online_capability.py`, `tests/test_capabilities.py` — screenshot
     `current-build-symbol-search-Agent-still-unreachable.png`.
  3. The symbol exists and is richly connected — direct DB and API checks:
     `symbols` has exactly one row named `Agent`
     (`0a40f5da-73bc-4594-9aa8-4cba7b59d155`, `class`,
     `pydantic_ai_slim/pydantic_ai/agent/__init__.py:202`) with **3 652** incident edges,
     and `GET /api/repositories/{repo}/symbols/0a40f5da…/subgraph?depth=1` returns
     `nodes 100 edges 103 truncated True`. So the data is present and the graph is
     excellent — only the discovery path fails.
  4. Contrast: `RunContext` **does** work — hit #1 is
     `RunContext | pydantic_ai_slim/pydantic_ai/_run_context.py:37`
     (`current-build-symbol-search-picker.png`). The failure is query-dependent, which is
     why it can be missed in casual testing.
- Probable cause + diagnostic confidence: **high.** `search.py` builds
  `Symbol.name.ilike('%agent%') OR Symbol.qualified_name.ilike('%agent%')` and applies
  `.limit(limit * 3)` = 90 rows **with no `ORDER BY`**, then scores and re-sorts in Python.
  1 347 symbols match `%agent%`, so Postgres returns an arbitrary, physical-order 90-row
  slice; the exact-match boost (`1.0` vs `0.85` in `result()`) can only rank rows that
  happen to be in that slice. This is the "filters must bite before the SQL `LIMIT`"
  problem named in §5.B. The differing result sets across the two runs are consistent with
  heap order changing after the re-index/migration.
- Smallest safe next step: push ranking into SQL before the limit — order by an
  exact-match predicate then `qualified_name`, e.g.
  `ORDER BY (lower(name) = :term) DESC, (lower(qualified_name) = :term) DESC, qualified_name, id`
  and only then `LIMIT`. That also makes the result set deterministic and stably
  tie-broken.
- Affected data/migrations/providers/cost: read-only query change; no migration; no
  provider. Cheap — `symbols.name` / `qualified_name` would benefit from an index for the
  ordering, worth measuring before adding.
- Recommended tests + acceptance criteria: API test seeding one exact `Agent` plus 200
  `%agent%` decoys and asserting the exact match is rank 1; a determinism test asserting
  two identical requests return byte-identical `results`. Browser E2E: search `Agent` in
  the picker and assert the first hit's qualified name is exactly `Agent`.
- Fix status: report-only

### REV-802

- ID: REV-802
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: browser E2E verified (current build); `apps/web/app/files/[id]/page.tsx`
  is **byte-identical** on `stash@{0}` and `c122529` (`ff083367`), so it applies to both.
- Applies to: both
- Impact: Any stale, mistyped or shared link to a file yields a raw server-error page with
  an opaque incident number and no way back — no message, no "file not found", no link to
  the dashboard. Deep links are the documented identity mechanism (§3 invariant 2), so
  this is on a path users are expected to use.
- Evidence: three navigations, all expecting a clean 404 with an explanation:

  | URL | Expected | Actual |
  |---|---|---|
  | `/files/00000000-0000-4000-8000-000000000000` (well-formed, absent) | 404 + message | **HTTP 500** |
  | `/files/not-a-uuid-at-all` (malformed) | 404 or 422 + message | **HTTP 500** |
  | `/files/21ffa409-…-7bb6a5b80bb9` (a *repository* id, wrong entity type) | 404 + message | **HTTP 500** |

  All three render identically: `This page couldn't load | A server error occurred.
  Reload to try again. | Reload | ERROR 1175352238`. Console:
  `pageerror: Minified React error #441`; network: `HTTP 500 GET /files/…`.
  Screenshots `negative-files-nonexistent-uuid.png`,
  `negative-files-malformed-uuid.png`.
  For contrast, a genuinely unknown route is handled correctly: `/workspaces` → clean
  Next.js `404 This page could not be found.` inside the app shell
  (`negative-workspaces-route-404.png`).
- Probable cause + diagnostic confidence: **high.** `app/files/[id]/page.tsx` is an async
  server component that calls `api<…>('/files/' + id)` with no try/catch, and
  `lib/api.ts:8` does `if (!response.ok) throw new Error(await response.text())`. The API
  correctly returns 404, but the thrown error escapes the server component, so Next.js
  renders its generic 500 boundary. There is no `not-found.tsx` / `error.tsx` and no
  `notFound()` call anywhere under `apps/web/app`.
- Smallest safe next step: catch the failure in the page and call Next's `notFound()`, and
  add an `app/not-found.tsx` with a link back to the dashboard. Distinguish 404 from a
  real 5xx so genuine outages still surface as errors.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: browser E2E asserting HTTP 404 and visible text
  "file not found" (not "A server error occurred") for absent, malformed and wrong-type
  ids; assert no `pageerror` is logged.
- Fix status: report-only

### REV-803

- ID: REV-803
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: browser E2E verified (current build) + API measurement
- Applies to: current build; the endpoint exists at `c122529`
  (`apps/api/app/main.py:263`, `repository_graph`) with the same structure → effectively
  both, but it has no counterpart on the main-lineage runtime (route absent), so it could
  not be exercised there.
- Impact: The "Repository map" — the bounded workspace/repository overview §3 invariant 3
  demands — enforces a **node** budget while letting edges run unbounded. The browser is
  handed 7 952 relationships for 100 nodes: an unreadable hairball, a 3.61 MB transfer, and
  a 3.15 s server response. The `truncated` flag is honest that *something* was cut but
  never says what or how much, so a user cannot tell that they are seeing 100 of 21 324
  symbols (0.47 %).
- Evidence:
  1. `/graph` → `Repository map`. Summary bar:
     `API result · 100 nodes · 7952 relationships · truncated at the node cap`, canvas
     rendered (`current-build-repository-map.png`).
  2. `GET /api/repositories/21ffa409…/graph?max_nodes=100` measured directly:
     `BYTES=3609966 TIME=3.150556s`, `nodes 100 edges 7952 truncated True max_nodes 100`.
  3. Composition: node kinds `class 34, file 27, function 20, directory 18, repository 1`;
     edge types `call 7853` plus 99 structural edges. `source_text` accounts for
     **1 244 277 chars** of the payload (see REV-811).
  4. `truncated: true` carries no cause and no counts — no "showing 100 of 21 324
     symbols", no edge count that was dropped (none were).
  5. Same request on a 390 px viewport renders all 7 952 edges into a 348×632 canvas
     (`mobile-390-graph-loaded.png`) — see REV-821.
- Probable cause + diagnostic confidence: **high.** `main.py:263-285` computes a node
  budget (`budget = max_nodes - 1`, greedy fill by descending degree) but the edge phase
  that follows simply emits every edge whose endpoints are both selected, with no cap and
  no `truncated` contribution. §5.D requires hard node **and** edge budgets plus an honest
  `truncated` with cause and count.
- Smallest safe next step: add a `max_edges` bound applied with a deterministic ordering
  (`edge_key` already exists at `main.py:55`), and turn `truncated` into a structured
  object — `{node_cap_hit, edge_cap_hit, nodes_available, edges_available}` — so the UI can
  say what was dropped.
- Affected data/migrations/providers/cost: no migration, no provider. Reduces bandwidth
  and client CPU; measure the 3.15 s server time separately, it is dominated by loading
  all symbols and edges for the repository into Python.
- Recommended tests + acceptance criteria: API test asserting `len(edges) <= max_edges`
  and that `truncated` reports which cap fired; determinism test asserting two calls
  return identical node and edge ordering. Browser E2E asserting the summary bar states
  both the node and edge budget outcome.
- Fix status: report-only

### REV-804

- ID: REV-804
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: browser E2E verified (both builds) + API measurement
- Applies to: both, with different symptoms — see below.
- Impact: `confidence` is presented to users as a filterable evidence measure, but the same
  field carries **two different scales** in one response, so the control cannot mean
  anything. On the main-lineage build the filter was silently useless; on the current build
  the normalisation collapses everything to 1.0, so it is still useless. Either way the UI
  implies graded confidence the data does not support — precisely what §3 invariant 4 and
  the §7 non-claims forbid.
- Evidence:
  1. Schema: `symbol_edges.confidence` is an **integer** column
     (`information_schema.columns` → `confidence | integer`).
  2. Stored values, whole table: `call 122231 rows, min 20 max 100`;
     `import 14335 rows, min 20 max 100`. So code edges use a **0–100** scale.
  3. A live subgraph edge: `{"type": "call", "confidence": 100, …}`.
  4. The repository-map response mixes scales in one array: `7 853` edges with
     `confidence: 100` (code) and `99` edges with `confidence: 1` (structural
     `contains`/`defines`). One field, two scales.
  5. Main-lineage UI: thresholds are `0.5 / 0.75 / 0.9` compared with
     `link.confidence >= minimum` — `100 >= 0.9` is always true, so **no edge is ever
     filtered**. Browser-confirmed: selecting `90% or higher` changed nothing about the
     link count (`graph-confidence-filter-noop.png`; the `0 nodes` in that shot is
     REV-800).
  6. Current build normalises (`c122529` `graph-explorer.tsx:48`:
     `confidence > 1 ? confidence / 100 : confidence`, clamped to 0–1). Both `100 → 1.0`
     and `1 → 1.0`, so `90% or higher` still retains everything: browser-confirmed
     `100 nodes · 211 relationships` unchanged at every threshold
     (`current-build-filters.png`).
  7. Main-lineage `graph-canvas.tsx` link tooltip renders
     `${Math.round(item.confidence * 100)}%` — with a stored `100` that reads **10000 %**.
     Marked `source-reviewed`: I could not land a hover on a specific link edge to
     photograph the tooltip.
- Probable cause + diagnostic confidence: **high** for the scale mismatch (measured at
  every layer: column type, stored range, API payload, UI comparison). The deeper question
  — whether a 20–100 integer produced by the extractor is a *meaningful* confidence at all,
  or a fixed heuristic constant — is **not** resolved here and should not be presented as
  evidence-backed until it is.
- Smallest safe next step: decide one canonical scale at the API boundary and emit it
  uniformly for structural and code edges (a float 0–1 is the least surprising), then make
  the UI display it only where genuinely stored. Do not normalise in the client — that
  hides the inconsistency, as the current build shows.
- Affected data/migrations/providers/cost: touches `symbol_edges.confidence` semantics; a
  scale change is a data migration and must be coordinated with the ingestion writer. No
  provider cost.
- Recommended tests + acceptance criteria: API contract test asserting every edge's
  `confidence` is in one documented range regardless of `type`; a UI test asserting a
  `0.9` threshold actually removes edges below 0.9 in a fixture with graded values.
- Fix status: report-only

### REV-805

- ID: REV-805
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: browser E2E verified (main lineage) + source-reviewed (`c122529`)
- Applies to: both — neither `search-client.tsx` version renders anything for an empty
  result array.
- Impact: A user cannot tell "your query matched nothing" from "you have not searched
  yet", or from "the request failed". §5.A requires these states to be distinguishable.
- Evidence: `/search` → `zzqqxxnothingmatches` → Search. Expected a "no results" message.
  **Actual:** `result cards: 0`, and the page's rendered text is *identical* to the pristine
  page before searching — `Global code search / hybrid text symbols semantic / Search /
  Filters: repo: lang: path:` and nothing else. The only on-screen difference between
  `search-empty-state.png` and `search-no-results-indistinguishable-from-empty.png` is the
  query still sitting in the input; nothing is added below the form. The network call
  succeeded (`GET /api/search?q=…&mode=hybrid`, no 4xx).
  The related reload case in REV-806 is stronger still: after a reload,
  `search-state-lost-on-reload.png` is **byte-identical** to `search-empty-state.png`
  (both `md5 9d0c6533a32a7678ff6953d648d29c51`), i.e. the post-search page is
  indistinguishable from one that was never used.
  At `c122529` the render is still a bare `{results.map(…)}` with no empty branch.
- Probable cause + diagnostic confidence: high — no conditional for `results.length === 0`
  and no "has searched" state to distinguish it from the initial mount.
- Smallest safe next step: track whether a search has completed and render a distinct
  no-results block naming the query and the active mode and filters.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: browser E2E asserting distinct visible text for
  pristine / no-results / error; assert the no-results text echoes the query.
- Fix status: report-only

### REV-806

- ID: REV-806
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: browser E2E verified (reload on main lineage; Back/Forward on the current
  build) + source-reviewed (`c122529`)
- Applies to: both — neither version reads or writes `useSearchParams`/`router`.
- Impact: Search results cannot be shared, bookmarked or restored. Reload, Back and Forward
  all silently discard them, which is exactly the Back/Forward/refresh consistency §5.A
  asks about. For an evidence platform, an unshareable result is a significant gap.
- Evidence:
  1. Main-lineage build: `/search` → `RunContext` → 30 results. URL remained
     `http://localhost:3000/search` with no query string. Reload →
     `results after reload: 0`, i.e. the pristine empty state — and the screenshot is
     **byte-identical** to the never-used page (`search-state-lost-on-reload.png` vs
     `search-empty-state.png`, both `md5 9d0c6533a32a7678ff6953d648d29c51`).
  2. Current build, full navigation history: dashboard → click `Search` → query
     `RunContext` → `results: 30`, url `/search`. Press **Back** → url `/` and
     `h2: Repository dashboard`, i.e. Back leaves the route entirely rather than undoing
     the search. Press **Forward** → url `/search` but `results: 0` and the query input is
     `""` — the search is gone (`search-back-forward-loses-results.png`).
  3. Grep of the `c122529` client for `useSearchParams|router` returns nothing.
- Probable cause + diagnostic confidence: high — query and mode live only in `useState`.
- Smallest safe next step: mirror `q` and `mode` into the query string on submit and seed
  state from `useSearchParams` on mount.
- Affected data/migrations/providers/cost: none. Note that re-running a query from a URL
  must stay provider-free unless the mode is `semantic`.
- Recommended tests + acceptance criteria: E2E — search, copy the URL, open in a fresh
  context, assert the same results; assert Back/Forward restores query, mode and results.
- Fix status: report-only

### REV-807

- ID: REV-807
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: browser E2E verified (both builds)
- Applies to: both
- Impact: The product's stated top-level user decision (§2, "Workspace auswählen oder
  anlegen") has no UI at all, so the intended navigation cannot be started, and the
  workspace API/data model is unreachable from the browser. Combined with zero rows in
  `workspaces`, no workspace behaviour can be acceptance-tested through the product.
- Evidence: the sidebar contains exactly four links — `Dashboard`, `Search`,
  `Code graph`, `AI Chat` (ARIA snapshot of the `complementary` landmark, identical on
  both builds; `dashboard-main.png`). There is no workspace switcher, no create control,
  and no membership or dependency management on any of the four routes.
  `/workspaces` → clean 404 (`negative-workspaces-route-404.png`).
  `GET /api/workspaces` → `[]`. The dashboard's only entry action is "Connect a
  repository", which takes a name and a clone URL and no workspace.
- Probable cause + diagnostic confidence: high, and consistent with §2's own
  "Aktueller, nachweisbarer Stand" — workspace CRUD exists in the API only.
- Smallest safe next step: as §11 suggests, a read-only workspace shell first — list
  workspaces, show `Unassigned` repositories, and make the current repository scope
  visible — before any create/assign flow.
- Affected data/migrations/providers/cost: none for a read-only shell. Membership writes
  need the atomicity and exclusivity questions in §5.C settled first.
- Recommended tests + acceptance criteria: E2E for the §5.G path as far as the UI allows,
  with an explicit assertion that an unassigned repository is labelled as such rather than
  silently shown as global.
- Fix status: report-only

### REV-808

- ID: REV-808
- Category: BUG_CONFIRMED
- Severity: medium
- Evidence level: browser E2E verified (main lineage); `dashboard-client.tsx` is
  byte-identical on `stash@{0}` and `c122529` (`ee0185ba`) → both.
- Applies to: both
- Impact: The confirmation dialog for the **destructive** delete action fails three basic
  modal requirements (§5.A: "Fokus, Tastatur, Dialog Escape/Restore"). A keyboard user
  tabs straight out of the dialog into the page behind it while the dialog is still open
  and modal — including onto the very `Delete` button that opened it — and cannot dismiss
  with Escape.
- Evidence: dashboard → `Delete` on the `pydanticAI` card. Dialog opened correctly with
  `role="dialog" aria-modal="true"` and a clear, well-written body ("This removes the
  repository and all of its indexed files, chunks, and graph data. The remote Git
  repository will not be changed."). Then:

  | Check | Expected | Actual |
  |---|---|---|
  | Focus moved into dialog on open | first control focused | `activeElement` = the `Delete` **trigger** button, outside the dialog |
  | Focus trapped | Tab cycles Cancel ↔ Delete repository | escapes after 2 stops: `Cancel → Delete repository → BODY → Dashboard → Search → Code graph → AI Chat → Repository name → Clone URL → Add repository → Sync → Reindex` |
  | Escape closes | dialog closes | `dialog still open after Escape? true` |
  | Focus restored on close | back to the trigger | after `Cancel`, `activeElement` = `BODY` |

  Screenshot `dashboard-delete-dialog-focus-not-trapped.png`. I closed the dialog with
  `Cancel` and **never pressed `Delete repository`**.
- Probable cause + diagnostic confidence: high. `dashboard-client.tsx:92-96` renders a
  hand-rolled `div.dialog-backdrop` + `section[role=dialog]`; there is no focus move, no
  key handler, no focus restore, and no inertness for the background content.
- Smallest safe next step: use the native `<dialog>` element with `showModal()`, which
  provides focus containment, Escape and backdrop inertness for free; or add a focus trap
  plus `onKeyDown` Escape and restore focus to the trigger on close.
- Affected data/migrations/providers/cost: none — but note this guards the only control
  that destroys the indexed repository.
- Recommended tests + acceptance criteria: E2E asserting focus enters the dialog, Tab
  cycles only within it, Escape closes without deleting, and focus returns to the trigger.
- Fix status: report-only

### REV-809

- ID: REV-809
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: browser E2E verified (both builds)
- Applies to: both
- Impact: The graph — the surface carrying most of the product's value — is entirely
  unavailable to keyboard and screen-reader users, and the one honest thing it says about
  data completeness ("truncated") is never announced.
- Evidence:
  1. Main-lineage canvas:
     `{"role":null,"ariaLabel":null,"tabIndex":-1,"title":null,"text":""}` — no role, no
     name, no text alternative, not focusable. Wrapper is a bare
     `<div class="graph-canvas"><div><div class="force-graph-container">`.
  2. Current build canvas: `{"role":null,"ariaLabel":null,"tabIndex":-1,"text":""}` —
     unchanged.
  3. There is no table, list or textual summary of nodes/edges anywhere as an alternative
     representation. The only textual output is the node-details panel, which requires a
     **mouse click on a canvas node** to populate.
  4. Truncation is visual only: the summary bar carries
     `{"role":null,"ariaLive":null}`, so `truncated at the node cap` is never announced.
     (Credit where due: the current build's symbol hit list *does* have
     `aria-live="polite"`.)
  5. `prefers-reduced-motion` is not handled — see REV-820.
- Probable cause + diagnostic confidence: high — `graph-canvas.tsx` renders
  `<ForceGraph2D>` with no accessibility props, and no alternative view exists.
- Smallest safe next step: give the canvas `role="img"` with an `aria-label` summarising
  root symbol, node/edge counts and truncation, and add `role="status"` to the summary bar
  so counts and truncation are announced. A keyboard-navigable node list beside the canvas
  is the durable fix and doubles as the text alternative.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: automated axe scan of `/graph` with zero
  serious violations; E2E asserting the canvas has an accessible name that includes the
  node count and any truncation, and that every node reachable by mouse is also reachable
  by keyboard.
- Fix status: report-only

### REV-810

- ID: REV-810
- Category: PERFORMANCE_RISK
- Severity: medium
- Evidence level: browser E2E verified (current build); file byte-identical on both refs
  → both.
- Applies to: both
- Impact: Opening a large indexed file builds a DOM proportional to its line count. This
  is the destination of every search result and every chat citation, so it is a hot path.
- Evidence: `/files/13bad800-…` (`tests/test_temporal.py`) →
  `lines: 11554`, `DOM nodes: 23140`, load `699 ms` on a warm localhost with no network
  latency (`files-view-large-file.png`). `page.tsx` maps every line to
  `<div id={"L"+n}><span/>{text}</div>`, i.e. two elements per line, with no windowing and
  no syntax highlighting to justify the cost. The full file content is also transferred in
  the server-rendered payload regardless of which line the anchor targets.
- Probable cause + diagnostic confidence: high for the mechanism (measured). The *user
  impact* on a real workstation was not measured beyond load time — I did not profile
  scroll jank, so no claim is made there.
- Smallest safe next step: measure first, then window the rendering (or render a plain
  `<pre>` with a CSS-counter gutter, which removes the per-line elements entirely and keeps
  anchors via a single scroll target).
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: performance budget test on the largest indexed
  file asserting DOM element count below an agreed ceiling and time-to-interactive under a
  measured baseline.
- Fix status: report-only

### REV-811

- ID: REV-811
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: browser E2E verified (current build) + API measurement; `symbol_out`
  identical at `c122529` (`main.py:53`) and on the main-lineage runtime → both.
- Applies to: both
- Impact: Every graph response ships the **full source text** of every symbol node, and
  the user-facing node panel then dumps it verbatim together with internal byte offsets
  and force-layout state. This inflates payloads by an order of magnitude and leaks
  implementation detail into a surface a user reads.
- Evidence:
  1. `symbol_out` includes `source_text` (and `start_byte`/`end_byte`).
  2. Symbol subgraph, `Agent` depth 1: total `342 259` bytes of which **`247 194` chars are
     `source_text`** (72 %).
  3. Repository map: **`1 244 277` chars** of `source_text` across just 54 nodes that carry
     it, inside a 3.61 MB response. A single node —
     `test_groq_model_thinking_part_iter` — carries **235 824 chars** of source on its own.
  4. Node-details panel, current build, real symbol clicked: 959 characters rendered, keys
     `Label, ID, Kind, repository_id, file_id, name, qualified_name, type, language,
     start_line, end_line, start_byte, end_byte, parent_symbol_id, signature, source_text,
     isRoot, degree, fx, fy` — including the raw `source_text` and the force simulation's
     own `fx`/`fy` pinning coordinates (`current-build-node-detail-source-text.png`).
     The fixture path shows the same leak of layout state:
     `Label | SearchClient | ID | search-client | Kind | symbol | fx | undefined | fy |
     undefined` (`current-build-fixture-node-detail.png`).
- Probable cause + diagnostic confidence: high. The graph endpoints reuse the
  single-symbol `symbol_out` projection, and the panel renders `Object.entries(selected)`
  minus a small deny-list that omits `fx`/`fy`/`isRoot`/`degree`/`source_text`.
- Smallest safe next step: give graph endpoints a slim node projection (identity, name,
  kind, path, line range) and let the detail panel fetch the full symbol on demand; render
  an explicit field allow-list in the panel rather than a deny-list.
- Affected data/migrations/providers/cost: no migration; a response-shape change, so it
  needs the versioned-schema treatment §5.B asks for. Large bandwidth saving.
- Recommended tests + acceptance criteria: API test asserting graph node objects contain
  no `source_text` and that payload size for a 100-node graph stays under an agreed budget;
  UI test asserting the panel shows only allow-listed fields.
- Fix status: report-only

### REV-812

- ID: REV-812
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: browser E2E verified (main lineage) + source-reviewed (`c122529`)
- Applies to: main (running, pre-14:28) only — **fixed** at `c122529`.
- Impact: §3 invariant 6 requires every hit to retain repository, path, line range **and
  indexed commit**. On the main-lineage build the commit was missing from search results,
  so a copied result could not be tied to a revision.
- Evidence: result card innerHTML on the main-lineage build carried
  `<b>pydanticAI</b> <span class="muted">docs/mcp/client.md:477-680 · markdown ·
  chunk</span>` — repository, path, line range, language, type, and **no commit**
  (`search-RunContext.png`). The commit only appears one hop later on the file view
  (`markdown · commit 640d5171fe57`, `files-view-from-search-navigation.png`).
  At `c122529` the card appends
  `{result.indexed_commit_sha ? ' · ' + result.indexed_commit_sha.slice(0,12) : ''}` and the
  result type carries `indexed_commit_sha`, so the gap is closed there. The current build's
  chat surface likewise shows `pydanticAI · 640d5171fe57`
  (`current-build-chat-with-scope-selector.png`).
- Probable cause + diagnostic confidence: high — the field was simply absent from the
  main-lineage result type and card.
- Smallest safe next step: none needed on the review target; keep the `c122529` behaviour
  and add a regression test so it cannot be lost again.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: E2E asserting every result card shows a 12-char
  commit prefix, and that it equals the repository's `indexed_commit_sha`.
- Fix status: report-only

### REV-813

- ID: REV-813
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: browser E2E verified (current build) + source-reviewed (`c122529`)
- Applies to: `c122529` and the current build. The main-lineage build was **correct** here,
  so this is a regression.
- Impact: A first-time visitor to `/graph` is told their filters excluded everything,
  before they have loaded anything or touched a filter. It misdirects the user into
  fiddling with filters instead of loading data, and conflates "nothing loaded" with
  "everything filtered out" — two of the states §5.A requires to be distinguishable.
- Evidence: fresh `/graph` on the current build, no interaction:
  summary `No graph loaded · 0 nodes · 0 relationships` but the body reads
  **`No graph data to display.` / `The selected filters returned no connected nodes.
  Adjust filters or load the fixture demo.`** (`current-build-graph-wrong-empty-state.png`).
  The main-lineage build in the same situation correctly read
  `No graph loaded yet.` / `Search for a symbol above and choose one to anchor the graph,
  or load the fixture demo.` (`graph-initial-empty-state.png`).
  Source: `c122529` `graph-explorer.tsx:112` is a two-way ternary
  (`loading ? … : nodes.length > 0 ? <GraphCanvas/> : <no-graph-data/>`) with no
  "nothing loaded yet" branch, whereas the main-lineage version had a three-way ternary
  with `!filteredGraph` handled first.
- Probable cause + diagnostic confidence: high — the `!graph` branch was dropped when
  `graph` stopped being nullable.
- Smallest safe next step: restore the third branch keyed on "no graph has been requested
  yet" rather than on node count.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: E2E asserting three distinct texts for
  pristine, loaded-but-filtered-empty, and loading.
- Fix status: report-only

### REV-814

- ID: REV-814
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: browser E2E verified (main lineage) + source-reviewed (`c122529`)
- Applies to: both — neither version labels these controls or announces results.
- Impact: The search form is unusable with confidence via screen reader: the query field
  has no label, the mode selector has no accessible name at all, and results appear with no
  announcement.
- Evidence: ARIA snapshot of `/search` on the main-lineage build:

  ```text
  - textbox "auth repo:backend lang:python"      ← name is the placeholder, no <label>
  - combobox:                                    ← NO accessible name
    - option "hybrid" [selected] / "text" / "symbols" / "semantic"
  - button "Search"
  ```

  No `role="status"` / `aria-live` anywhere on the route, so neither `Searching…` nor the
  arrival of 30 results is announced. At `c122529` the same two controls remain unlabelled
  (only an `error` div gained `role="alert"`), and a new
  `Reranker verwenden` checkbox introduces an untranslated German label into an otherwise
  English UI.
  For contrast, the dashboard form is done correctly — both inputs have real labels
  (`textbox "Repository name"`, `textbox "Clone URL"`), and the graph picker's controls are
  named (`combobox "Repository"`, `textbox "Symbol"`, `spinbutton "Depth"`).
- Probable cause + diagnostic confidence: high — placeholder-only inputs and a bare
  `<select>`.
- Smallest safe next step: wrap both controls in `<label>` like the dashboard already
  does, and add `role="status"` to a results-count line.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: axe scan of `/search` with zero serious
  violations; E2E asserting every form control has a non-placeholder accessible name and
  that the result count is exposed in a live region.
- Fix status: report-only

### REV-815

- ID: REV-815
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: browser E2E verified (current build); file identical on both refs → both.
- Applies to: both
- Impact: The file view is where every search result and every chat citation lands, and it
  offers no way onward — breaking the §2 chain `Datei → Symbol → fokussierter Graph`. The
  user must go back and start again.
- Evidence: after navigating from a search result to `/files/0b38559c-…#L142`, the page
  contains a heading, a provenance line and the source listing, and
  `[...document.querySelectorAll('main a')]` returns **`[]`** — no links at all
  (`files-view-from-search-navigation.png`). There is also no `Files` entry in the sidebar,
  so the route is reachable *only* via a search result or a chat citation.
  Mitigating, on the review target only: `c122529`'s search card adds
  `View symbol →` and `Open graph →` links, so the graph becomes reachable from a search
  hit — but the file page itself is still a dead end in both refs.
- Probable cause + diagnostic confidence: high — `files/[id]/page.tsx` renders no links,
  and `GET /api/files/{id}/symbols` (which exists and is already used by the graph picker)
  is not consulted here.
- Smallest safe next step: list the file's symbols from the existing endpoint and link each
  to the focused graph, plus a breadcrumb to the repository.
- Affected data/migrations/providers/cost: none — the endpoint already exists.
- Recommended tests + acceptance criteria: E2E completing `search → file → symbol → focused
  graph` entirely by clicking, with no typed URL and no UUID entry.
- Fix status: report-only

### REV-816

- ID: REV-816
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: browser E2E verified (both builds)
- Applies to: both
- Impact: §5.D requires that a fixture can never be mistaken for real workspace data. The
  fixture is one click away, sits in the same canvas, and the only distinguishing signal is
  the phrase "Fixture demo" in small muted text — while the repository selector continues
  to display the real repository as selected. It also displays relationship types
  (`renders`, `handles`) and graded confidences (`0.94`, `0.87`) that **no real edge in this
  system has**, which trains users to expect evidence the platform cannot produce.
- Evidence: `/graph` → `Fixture` (current build). Summary:
  `Repository Directory File Symbol` + `Fixture demo · 8 nodes · 7 relationships`.
  `warning banner? []` — no banner, no dialog, no colour change. The repository
  `<select>` still reads `21ffa409-9e13-493a-b919-7bb6a5b80bb9` / `pydanticAI`
  (`current-build-fixture-demo.png`). Clicking a fixture node yields
  `Label | SearchClient | ID | search-client | Kind | symbol`, i.e. a non-UUID id in the
  same panel that otherwise shows real symbol UUIDs
  (`current-build-fixture-node-detail.png`). Same on the main-lineage build, whose fixture
  button is labelled `Use fixture demo`.
  The fixture's own content describes a *different* repository (`knowledge-way`, `apps`,
  `web`, `api`, `search/page.tsx`), which is the only real cue — and only to someone who
  already knows the product.
- Probable cause + diagnostic confidence: high — `fixture` is a module constant rendered
  through the identical code path as API data, with `source` state as the only marker.
- Smallest safe next step: either remove the fixture from the production surface, or render
  it behind a persistent, high-contrast "demo data — not from your repositories" banner and
  clear the repository selection while it is shown.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: E2E asserting a visible non-muted demo warning
  whenever fixture data is displayed, and that no real repository appears selected.
- Fix status: report-only

### REV-817

- ID: REV-817
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: **split** — `browser E2E verified` for the URL never changing;
  `source-reviewed` for the deep-link rejection (see below); source-reviewed for `c122529`.
- Applies to: main (running, pre-14:28) only — **addressed** at `c122529`.
- Impact: On the main-lineage build no graph state was addressable, so a loaded graph could
  not be shared or restored, and Back navigated away from the page entirely rather than
  undoing a step.
- Evidence:
  - `browser E2E verified`: after loading a 100-node subgraph the URL was still
    `http://localhost:3000/graph` with no query string
    (`url (unchanged?): http://localhost:3000/graph`).
  - `source-reviewed`: the running main-lineage `graph-explorer.tsx` (= `stash@{0}`,
    extracted from the container) contains **zero** occurrences of
    `useSearchParams`/`searchParams`, and all of `repositoryId`, `symbolQuery`, `symbol`,
    `depth`, `graph`, `relationship` and `minimumConfidence` are plain `useState`. A
    `?repository=&symbol=` URL therefore cannot be honoured. I must be explicit that I did
    **not** observe this rejection in the browser: the scripted step that would have done so
    sat after a step that crashed, and the retry straddled the 14:28:14 rebuild, so
    `graph-deep-link-ignored.png` was never captured (see §7).
  - `c122529` adds `useSearchParams()` with `?repository=` / `?symbol=` seeding
    (`graph-explorer.tsx:59-62`), which closes this on the review target.
- Probable cause + diagnostic confidence: high — the main-lineage component held all state
  in `useState` with no router integration.
- Smallest safe next step: none on the review target; add a regression test.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: E2E asserting a deep link reproduces the same
  graph, and that Back/Forward moves between graph states rather than off the route.
- Fix status: report-only

### REV-818

- ID: REV-818
- Category: DESIGN_GAP
- Severity: low
- Evidence level: browser E2E verified (both builds)
- Applies to: both, with opposite symptoms.
- Impact: Two surfaces querying the same index disagree about the minimum useful query,
  and neither behaviour matches the backend's actual tokenisation. Users get either a
  refusal or a page of meaningless substring matches.
- Evidence:
  1. Main-lineage `/graph`, query `Ag` → clean, well-worded refusal:
     `Enter at least 3 characters — the symbol index ignores shorter words.`
     (`graph-short-query-rejected.png`).
  2. Same-build `/search`, query `ab` → **30 result cards**, top hit
     `docs/capabilities/third-party.md:1-51`, matching `ab` inside words such as
     "available" and "table" (`search-ab.png`). No warning that the query is degenerate.
  3. Current build `/graph`: the 3-character guard is **gone** —
     `after 2 chars, Find symbol disabled? false`. The minimum is no longer enforced on
     either surface.
- Probable cause + diagnostic confidence: high. `search.py`'s `query_terms()` only keeps
  tokens of 3+ characters, but the lexical branch runs a raw
  `source_text ILIKE '%ab%'` first, which has no length floor. The main-lineage graph
  component encoded the 3-char rule client-side (`MIN_QUERY_LENGTH = 3`); the current build
  dropped it.
- Smallest safe next step: enforce one minimum in the API and return a structured
  "query too short" response both surfaces can render.
- Affected data/migrations/providers/cost: none, and it removes needless full-corpus
  `ILIKE` scans.
- Recommended tests + acceptance criteria: API test asserting a consistent documented
  response for 1–2 character queries; E2E asserting both surfaces show the same message.
- Fix status: report-only

### REV-819

- ID: REV-819
- Category: DESIGN_GAP
- Severity: low
- Evidence level: browser E2E verified (main lineage); `dashboard-client.tsx` identical on
  both refs → both.
- Applies to: both
- Impact: A repository that finished indexing 40 minutes earlier still advertises an
  in-progress phase, so a user cannot trust the dashboard's freshness signals — one of the
  state distinctions §5.A calls for.
- Evidence: the `pydanticAI` card shows badge `ready` and, at the same time,
  `Progress: finalizing · 2284 files` (`dashboard-main.png`). The API confirms both:
  `"indexing_status": "ready"` with `"indexing_progress": {"files": 2284, "phase":
  "finalizing"}` and `last_indexed_at: 2026-08-10T11:49:38`.
- Probable cause + diagnostic confidence: high. `progressLabel()`
  (`lib/repositories.ts`) renders whatever `indexing_progress` holds, and the ingestion
  writer leaves the final phase in place rather than clearing it on success. `Progress`
  is unconditional in the card markup.
- Smallest safe next step: when status is `ready`, show `last_indexed_at` and the indexed
  commit instead of the residual progress phase.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: E2E asserting a `ready` card shows no
  in-progress phase wording, and that `indexing`/`failed` cards do show theirs.
- Fix status: report-only

### REV-820

- ID: REV-820
- Category: DESIGN_GAP
- Severity: low
- Evidence level: browser E2E verified (current build) + source-reviewed (both refs)
- Applies to: both
- Impact: Users who have asked the operating system to reduce motion still get a
  continuously animating force simulation, which is a recognised vestibular-discomfort
  trigger and burns CPU indefinitely.
- Evidence: a browser context with `reducedMotion: 'reduce'` loaded `/graph` and requested
  the repository map. `matchMedia('(prefers-reduced-motion: reduce)').matches` → `true`,
  and two canvas screenshots taken 900 ms apart still differ →
  `canvas still animating under reduced motion? true`
  (`graph-reduced-motion-still-animates.png`). `grep -c prefers-reduced-motion` over
  `globals.css` returns **0** on the running main-lineage build and **0** at `c122529`, and
  `graph-canvas.tsx` passes no cooldown or freeze props to `ForceGraph2D`.
- Probable cause + diagnostic confidence: high — the preference is simply not consulted
  anywhere.
- Smallest safe next step: read the preference and stop the simulation once settled — e.g.
  a short `cooldownTime`/`cooldownTicks` and no re-heat, or pre-computed static positions
  under reduce.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: E2E in a reduced-motion context asserting the
  canvas is pixel-stable after settling; a CSS assertion that a reduced-motion block
  exists.
- Fix status: report-only

### REV-821

- ID: REV-821
- Category: PERFORMANCE_RISK
- Severity: low
- Evidence level: browser E2E verified (current build)
- Applies to: current build; the 760 px breakpoint exists on both refs, so the layout
  mechanics apply to both, but the repository-map volume is current-build only.
- Impact: The mobile layout claims in the CSS mostly hold, but the graph route is not
  usable at 390 px: the canvas sits far below the fold and is asked to draw thousands of
  edges into a postcard.
- Evidence: at 390×844 with `isMobile`, three of four routes are clean —
  `/`, `/search` and `/chat` all report `docW 390, winW 390, horizontalOverflow false`
  (`mobile-390-dashboard.png`, `mobile-390-search.png`, `mobile-390-chat.png`). The stacked
  single-column form and full-width sidebar behave as the `@media (max-width: 760px)` block
  intends. `/graph` is the exception: `docW 398 > winW 390` (8 px horizontal overflow), and
  after `Repository map` the canvas bounding box is
  `{"x":21,"y":1376,"width":348,"height":632}` — **1 376 px below the top** — while the
  summary reports `100 nodes · 7952 relationships`
  (`mobile-390-graph-loaded.png`).
- Probable cause + diagnostic confidence: medium-high. The overflow source was not
  isolated to a specific element, so that part is a measurement, not a diagnosis. The
  offscreen canvas is straightforward: the picker form, legend, edge key and two filter
  selects all stack above it at this width.
- Smallest safe next step: identify the 8 px overflow with a per-element scroll-width check;
  consider collapsing the picker into a disclosure on narrow viewports so the canvas is
  visible without scrolling.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: E2E at 390 px asserting no horizontal overflow
  on every route and that the graph canvas is at least partly within the initial viewport.
- Fix status: report-only

### REV-822

- ID: REV-822
- Category: DESIGN_GAP
- Severity: info
- Evidence level: browser E2E verified (both builds)
- Applies to: both
- Impact: Cosmetic, but it means the browser console is never clean, so a real error has to
  be spotted among permanent noise. Worth fixing precisely because it costs nothing.
- Evidence: every single page load on every route of both builds logs
  `Failed to load resource: the server responded with a status of 404 (Not Found)`.
  Confirmed as the icon request: `curl -w %{http_code} localhost:3000/favicon.ico` → `404`
  (`/apple-touch-icon.png` likewise). No other console errors, and **no hydration errors
  and no repeated polling 404s were observed anywhere** — which is worth recording as a
  positive result of this pass.
- Probable cause + diagnostic confidence: high — no `favicon.ico` or `app/icon.*` exists in
  `apps/web`.
- Smallest safe next step: add an icon, or a `metadata.icons` entry.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: E2E asserting zero console errors on each route.
- Fix status: report-only

### REV-823

- ID: REV-823
- Category: DESIGN_GAP
- Severity: low
- Evidence level: browser E2E verified (main lineage)
- Applies to: main (running, pre-14:28) only — **fixed** at `c122529`.
- Impact: The legend promised a richer graph than the endpoint could ever return, implying
  a structural graph (repositories, directories, files) that the symbol subgraph does not
  contain.
- Evidence: the main-lineage summary bar always rendered four fixed legend entries —
  `Repository`, `Directory`, `File`, `Symbol` — while `GET …/subgraph` returns only symbol
  nodes (`rel types ['call']`, all nodes from `symbol_out`). So three of the four legend
  keys could never appear (`graph-truncated-at-100-nodes.png`). `c122529` computes
  `presentKinds` from the loaded data instead, which is why the current build correctly
  shows `Repository Directory File Function Class` for the repository map and only
  `Class Function` for a symbol subgraph.
- Probable cause + diagnostic confidence: high — hard-coded legend markup.
- Smallest safe next step: none on the review target; keep the derived legend.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: UI test asserting the legend contains exactly
  the kinds present in the loaded graph.
- Fix status: report-only

### REV-824

- ID: REV-824
- Category: TEST_GAP
- Severity: medium
- Evidence level: browser E2E verified (this pass is the evidence) + manual live acceptance
- Applies to: both
- Impact: Every defect in this report was reachable within minutes of a first real browser
  session, which indicates the absence of browser coverage rather than unusual bugs. Two of
  them — REV-800 and REV-802 — are on the primary happy path. Separately, the live target
  was rebuilt **twice** during this pass, which is itself a reproducibility problem for the
  review and for any future E2E suite.
- Evidence:
  1. No browser/component test tooling exists in `apps/web` (no Playwright, Cypress or
     Testing Library config or spec files); the `@playwright/mcp` plugin was introduced for
     this review only, and could not even launch (§1.1).
  2. REV-800 reproduces with two clicks on the main surface; REV-802 with one navigation.
  3. Target instability, verified from container metadata and the schema: the runtime moved
     from `main` lineage / DB `20260808_0004` to integration + in-flight edits / DB
     `20260809_0008` at 14:28:14, mid-pass — after which the `main`-lineage runtime could no
     longer be reproduced without rebuilding, which an analysis-only mandate forbids.
     The `evidence/` directory is also shared with another agent session, which wrote
     `graph-filter-recheck-current-build.png`, `graph-subgraph-truncated.png` and
     `graph-symbol-picker-hits.png` there; those are **not** mine and are excluded from §6.
- Probable cause + diagnostic confidence: high.
- Smallest safe next step: add Playwright with a pinned browser download (do **not** rely
  on the `chrome` channel, per §1.1) and encode the §5.G happy path plus the negative cases
  in §5 as the first specs. Pin the reviewed commit and schema head for any E2E run.
- Affected data/migrations/providers/cost: CI time only; keep specs provider-free by
  asserting `embedding_provider = none`, as this pass did.
- Recommended tests + acceptance criteria: the §5.G path as far as the UI supports it, plus
  regressions for REV-800, REV-802, REV-805, REV-808 and REV-813. Acceptance: the suite
  fails on today's build for each of those five.
- Fix status: report-only

---

## 5. Controls I found and deliberately did not press

All of these are reachable in the running UI. Each was located and inspected — via the
DOM, the source, and in two cases the OpenAPI document — and then left alone.

| Control | Route | Why not pressed | Verified reachable by |
|---|---|---|---|
| `Add repository` (submit) | `/` | creates a repository and queues an 11 m 37 s index | filled both fields with an invalid URL to inspect validation, never submitted (`dashboard-add-form-invalid-url-not-submitted.png`) |
| `Sync` | `/` repo card | `POST /repositories/{id}/sync` — enqueues indexing work | button present and enabled in the ARIA tree |
| `Reindex` | `/` repo card | `POST /repositories/{id}/reindex` — full re-index | idem |
| `Delete` → `Delete repository` | `/` dialog | `DELETE /repositories/{id}` — destroys the only indexed repository | opened the dialog to test focus/Escape (REV-808), then closed it with `Cancel`; confirmed the dialog's own copy, never the destructive button |
| `semantic` option in the mode select | `/search` | instructed not to run semantic search | option enumerated in the ARIA tree; `hybrid` left selected. Note it is provably free here (§1.4) — `embedding_provider()` returns `None` — so the mode would return an empty list rather than bill |
| `Ask codebase` | `/chat` | `POST /api/chat` (main) / `POST /api/explanations` (current) — provider cost | surface inspected on both builds, textarea left empty, never submitted |
| `Reranker verwenden` checkbox | `/search` at `c122529` | paid reranking path | source-reviewed only; not present on the builds I drove |
| `POST /documentation/generate` | symbol page at `c122529` | provider generation triggered from a symbol page | found while checking whether viewing a symbol could spend money; I never navigated to that page |

I also confirmed by source that one GET is **safe** before using anything near it:
`GET /repositories/{id}/symbols/{id}/code-card` (`main.py:186-191`) only reads a stored
row and raises 404 when absent — it does not generate. And `Repository map` calls
`GET /repositories/{id}/graph`, confirmed a read-only GET in the live OpenAPI document
before I clicked it.

**No application state was mutated.** Post-pass verification against the values recorded
in `01-runtime-and-provenance.md`:

```text
repositories=1        workspaces=0        files=2284      symbols=21324
symbol_edges=136566   indexing_jobs=4     conversations=0 messages=0
pydanticAI  ready  640d5171fe57  last_indexed 2026-08-10T11:49:38.119422
```

Every count is unchanged, `indexing_jobs` is still 4 (no index was queued), and
`conversations=0 / messages=0` is positive proof that no chat message was ever submitted —
`POST /api/chat` unconditionally inserts a `Conversation` and two `Message` rows
(`main.py:238-240`), so a single submission would be visible here.

The only writes I made anywhere were the screenshots in §6, this report, and driver
scripts in the session scratchpad.

---

## 6. Screenshot index

All under `docs/reviews/2026-08-10-comprehensive-review/evidence/`. `Build` column as in
§2. Timestamps establish which build each shot belongs to (boundary 14:28:14).

### Main lineage (14:14–14:20)

| File | Finding | What it shows |
|---|---|---|
| `dashboard-main.png` | REV-807, REV-819 | dashboard with `ready` badge yet `finalizing · 2284 files`; four-item sidebar, no workspace UI |
| `dashboard-add-form-invalid-url-not-submitted.png` | §5 | add-repository form with an invalid URL, not submitted |
| `dashboard-delete-dialog-focus-not-trapped.png` | REV-808 | delete confirmation dialog open, focus not contained |
| `search-empty-state.png` | REV-805, REV-814 | pristine `/search` |
| `search-no-results-indistinguishable-from-empty.png` | REV-805 | `zzqqxxnothingmatches` — byte-identical to the shot above |
| `search-zzqqxxnothingm.png` | REV-805 | original filename of the same capture |
| `search-Agent.png` | REV-801 | `Agent` results led by `AgentRetries` |
| `search-RunContext.png` | REV-812 | result card provenance without a commit |
| `search-toolset.png` | REV-801 | `toolset` results |
| `search-ab.png` | REV-818 | 2-character query returning 30 substring hits |
| `search-state-lost-on-reload.png` | REV-806 | results gone after reload; byte-identical to `search-empty-state.png` |
| `graph-initial-empty-state.png` | REV-813 | correct `No graph loaded yet.` state (contrast for the regression) |
| `graph-short-query-rejected.png` | REV-818 | the 3-character guard that later disappeared |
| `graph-symbol-search-Agent-all-from-one-test-file.png` | REV-801 | 15 hits, no `Agent`, three test files |
| `graph-symbol-resolved-uuid-shown.png` | REV-801 | resolved symbol and its UUID |
| `graph-truncated-at-100-nodes.png` | REV-800, REV-823 | working graph, honest truncation notice, fixed 4-kind legend |
| `graph-relationship-filter-empties-canvas.png` | REV-800 | `0 nodes · 112 relationships` after a no-op filter |
| `graph-relationship-filter-all-types-restored.png` | REV-800 | still `0 nodes` after reverting to `All types` |
| `graph-confidence-filter-noop.png` | REV-800, REV-804 | confidence thresholds change nothing |

### Current build (from 14:28:14 — integration + in-flight edits)

| File | Finding | What it shows |
|---|---|---|
| `current-build-graph-wrong-empty-state.png` | REV-813 | "filters returned no connected nodes" before anything is loaded |
| `current-build-repository-map.png` | REV-803 | `100 nodes · 7952 relationships · truncated at the node cap` |
| `current-build-symbol-search-picker.png` | REV-801 | `RunContext` picker working, hit list with `aria-live` |
| `current-build-symbol-search-Agent-still-unreachable.png` | REV-801 | `Agent` still absent, from a different arbitrary file set |
| `current-build-focus-symbol-truncated.png` | REV-803, REV-809 | focused subgraph, truncation shown but not announced |
| `current-build-filters.png` | REV-800, REV-804 | filters retain 100 nodes (in-flight fix) yet confidence still filters nothing |
| `current-build-node-detail-source-text.png` | REV-811 | node panel dumping `source_text`, byte offsets, `fx`/`fy` |
| `current-build-fixture-demo.png` | REV-816 | fixture with no warning while the real repository stays selected |
| `current-build-fixture-node-detail.png` | REV-811, REV-816 | fixture node showing a non-UUID id and layout state |
| `search-back-forward-loses-results.png` | REV-806 | Forward returns to `/search` with 0 results and an empty query |
| `current-build-chat-with-scope-selector.png` | REV-812 | chat with required repository scope and commit |
| `chat-integration-build-with-scope-selector.png` | REV-812 | same surface, earlier capture |
| `files-view-from-search-navigation.png` | REV-815, REV-812 | file view reached by clicking a result; commit shown; no onward links |
| `files-view-large-file.png` | REV-810 | 11 554 lines → 23 140 DOM elements |
| `negative-files-nonexistent-uuid.png` | REV-802 | raw 500 page for an absent file id |
| `negative-files-malformed-uuid.png` | REV-802 | raw 500 page for a malformed id |
| `negative-workspaces-route-404.png` | REV-807 | clean 404 for `/workspaces` |
| `graph-reduced-motion-still-animates.png` | REV-820 | canvas animating with reduce honoured by the browser |
| `mobile-390-dashboard.png` | REV-821 | mobile dashboard, no overflow |
| `mobile-390-search.png` | REV-821 | mobile search, no overflow |
| `mobile-390-chat.png` | REV-821 | mobile chat, no overflow |
| `mobile-390-graph.png` | REV-821 | mobile graph route, 8 px overflow |
| `mobile-390-graph-loaded.png` | REV-803, REV-821 | 7 952 edges in a 348×632 canvas, 1 376 px below the fold |

Not written by me, present in the same directory from another agent session and excluded
from this report: `graph-filter-recheck-current-build.png`, `graph-subgraph-truncated.png`,
`graph-symbol-picker-hits.png`.

No screenshot contains a token, key or credential. The only secret-adjacent value on
screen anywhere is the public clone URL `https://github.com/pydantic/pydantic-ai`, which
carries no credentials.

---

## 7. Not assessed

- **The `main`-lineage graph node-details panel, fixture demo, deep-link rejection,
  Back/Forward behaviour and reduced-motion behaviour.** These were mid-run when the stack
  was rebuilt at 14:28:14; the run straddled the restart and its output was discarded
  rather than reported. Reason: the `main`-lineage runtime could not be restored without
  rebuilding containers, which the analysis-only mandate forbids. Each was subsequently
  measured on the **current** build and is reported there (REV-811, REV-816, REV-820), and
  the `main`-lineage deep-link gap is carried as REV-817 on the strength of the URL
  observation made before the restart plus the source. `graph-deep-link-ignored.png` was
  therefore never captured.
- **Node click on the `main`-lineage build.** Never landed: my first attempt ran after the
  filter bug (REV-800) had already removed the canvas, and the retry straddled the restart.
  The node-panel evidence in REV-811 is current-build only.
- **The link tooltip rendering `Math.round(confidence * 100)` as `10000%`.** A hover sweep
  of 361 canvas points captured no link tooltip, so this remains `source-reviewed`
  (REV-804, item 7). Hovering a specific force-graph edge is not reliably scriptable.
- **`semantic` search mode, chat submission, reranking, and any provider path.** Not
  exercised, per instruction and §4. Note the deployment could not have billed anyway
  (§1.4), so this is a scope decision, not a cost finding.
- **Workspace behaviour of any kind.** Zero workspaces exist, there is no UI to create one
  and `/workspaces` 404s (REV-807), so no workspace switching, scope isolation, membership
  or dependency behaviour could be exercised in a browser. This is the single largest
  untested area of the product and cannot be closed by browser testing until a UI exists.
- **Multi-repository behaviour**, including graph and search scope isolation on repository
  switch (§3 invariant 7). One repository exists; adding another triggers long indexing
  work. The repository `<select>` on `/graph` therefore had exactly one option, so
  switching could not be tested.
- **Cross-browser and real assistive technology.** Chromium only, headless, no
  screen-reader transcript (§1.2). All accessibility findings are ARIA/DOM-level.
- **`c122529` runtime as such.** The post-14:28 build is `c122529` **plus unreviewed
  in-flight edits**, so no browser observation in this report is presented as evidence
  about the pristine review target. Where it mattered I cross-checked the clean ref by
  source and labelled it `source-reviewed`.
- **The 8 px mobile overflow source** on `/graph` (REV-821) was measured but not isolated
  to an element.
- **Scroll/interaction profiling of the large file view** (REV-810). Load time and DOM size
  were measured; jank was not.
