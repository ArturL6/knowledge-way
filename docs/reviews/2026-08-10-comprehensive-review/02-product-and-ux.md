# 02 — Product, UX and Information Architecture (Workstream §5.A)

> Builds on `01-runtime-and-provenance.md`. Static review target: read-only worktree at
> `c122529` = `origin/integration/consolidated-verified`. All 17 files under `apps/web/`
> were read in full (no sampling), plus the backing routes in `apps/api/app/main.py`,
> `apps/api/app/search.py`, `apps/api/app/models.py`.

## Summary

The shipped web UI is a **five-page repository tool, not a workspace product**. The string
`workspace` does not occur once in any file under `apps/web/` (verified: `grep -rnic workspace
apps/web/app apps/web/lib` returns `0` for all 16 source files). Fourteen workspace routes
exist on the API and the web client calls **none** of them. Workspace-first is therefore not
"partially implemented in the UI" — it is absent, and §2's intended navigation cannot begin.

The web client calls **9 distinct API paths out of 42**. The unused ones are not incidental:
`/api/repositories/{id}/tree` (no file browser exists), `/api/search/symbols` (no symbol
picker), `/api/files/{id}/symbols` (file view has no symbol links), `/api/repositories/{id}/status`
and `/api/jobs/{job_id}` (no progress polling), `/api/chat` + `/api/conversations` (no
conversation history). The features the mandate asks about mostly exist server-side and are
simply not reachable by a human.

Three cross-cutting defect classes dominate:

1. **Provenance and honesty gaps.** Both graph endpoints return `truncated`; the client
   discards it. A measured live call returns `truncated: true` with 100 nodes selected from
   21 324 symbols, and the UI renders "API result · 100 nodes" with no caveat. 62 151 of
   136 566 edges have a NULL target and are silently dropped from every graph. `confidence`
   is displayed as a percentage but only two values exist in the database (20 and 100).
2. **State-transition unsafety (§3.7).** Nothing is discarded on scope change. Switching the
   repository dropdown, or a failed request, leaves the previous graph on screen still
   labelled "API result". No `AbortController` or request sequencing anywhere.
3. **No client-side routing at all.** Zero `next/link`, zero `useRouter`, zero `router.push`
   in the whole app. Every internal link is a plain `<a href>`, so every navigation is a full
   document load that destroys search results, graph state and the entire chat history.

Accessibility is materially broken in two specific places: the delete confirmation dialog has
no focus management, escape handler or focus restore, and the force-graph canvas has no role,
no accessible name, no text alternative and no keyboard path to any node.

Browser E2E was **not possible** — Playwright reports no Chromium at `/opt/google/chrome/chrome`.
Live evidence in this report is `curl`/HTTP/SQL only, and applies to `main` lineage. Thirteen web
files are byte-identical between `main` and integration (`Dockerfile`, `chat/page.tsx`,
`dashboard-client.tsx`, `files/[id]/page.tsx`, `layout.tsx`, `page.tsx`, `search/page.tsx`,
`lib/api.ts`, `lib/repositories.ts`, `next.config.ts`, `next-env.d.ts`, `package.json`,
`tsconfig.json` — verified by `git rev-parse` blob comparison), so live evidence about those
transfers to both branches and is marked accordingly.

### Runtime change during this workstream (recorded, not incorporated)

At approximately 14:34, after this review's evidence was collected, a non-review session added a
`migrate` service to `docker-compose.yml`, migrated the live database `20260808_0004` →
`20260809_0008`, and rebuilt the stack so that `api`, `worker` and `web` now run
integration-lineage code. Data was preserved (1 repository, 2 284 files, 21 324 symbols,
136 566 edges) and `workspaces` is **still empty with no UI able to create one**, so REV-100 is
unaffected. Two findings in this report were subsequently addressed on that working branch and are
annotated in place so the roadmap does not double-count them: **REV-101** (`truncated` now shown in
the graph summary bar) and **REV-106** (symbol UUID input replaced by a symbol search field). Both
remain valid as filed against the pinned target `c122529` and against `main`; neither was
re-verified here. All source citations in this report continue to reference the pinned read-only
worktree at `c122529`, because the working tree now carries in-flight edits from two sessions and
is not a stable reference. Every live measurement quoted below (`truncated: true`, 2.35 MB / 3.5 s
subgraph, `finalizing · 2284 files` on a `ready` repository, HTTP 500 on `/files/<unknown>`, the
edge-confidence distribution, the 62 151 NULL-target edges) was taken **before** this restart,
against `main`-lineage containers, and is labelled accordingly.

### State-distinguishability matrix

`✓` distinguishable · `~` present but wrong or misleading · `✗` absent · `–` not applicable

| Surface | Empty | Loading | Indexing | Failed | Stale | Truncated | No-results |
|---|---|---|---|---|---|---|---|
| Dashboard | `~` REV-107 | `✗` | `~` REV-105/123 | `~` REV-104 | `✗` REV-125 | `✗` | `–` |
| Search | `✗` REV-117 | `~` REV-118 | `✗` | `~` REV-104 | `✓` | `✗` REV-117 | `✗` REV-117 |
| File view | `✗` REV-108 | `✗` REV-108 | `–` | `✗` REV-108 | `✓` | `✗` | `–` |
| Chat | `~` REV-124 | `✓` | `✗` | `~` REV-104 | `✓` | `✗` | `✓` |
| Graph | `~` REV-119 | `✓` | `✗` REV-124 | `~` REV-103 | `✗` REV-127 | `✗` REV-101 | `~` REV-119 |

### Every place a human meets a raw UUID (§3.2)

| # | Location | Nature |
|---|---|---|
| 1 | `graph-explorer.tsx:104` — `<input placeholder="symbol UUID for local graph">` | **Typed UUID required.** The only way to open a focused subgraph from the graph page. Direct §3.2 violation. |
| 2 | `graph-explorer.tsx:78` — "Enter both a repository ID and a symbol ID to load the API graph" | Error copy instructing UUID entry; also factually wrong (repository is a `<select>`). |
| 3 | `graph-explorer.tsx:114` — Node details `<dt>ID</dt>` rendered in `.citation` monospace, plus `repository_id`, `file_id`, `parent_symbol_id` | UUIDs presented as the inspectable identity of a node, in the same monospace style used elsewhere for real citations. This panel is the copy-source that feeds #1. |
| 4 | `/files/[id]` route | Deep-link only; no path-addressable file route exists, so a human cannot construct or recover this URL. |
| 5 | `/repositories/[repositoryId]/symbols/[symbolId]` | Deep-link only — permitted by §3.2 — but orphaned: no `/repositories/[repositoryId]` page exists (`HTTP 404`), so the URL hierarchy implies a parent that does not exist. |
| 6 | All workspace and dependency operations | No UI whatsoever, so the *only* entry point is hand-written `curl` with workspace/repository/dependency UUIDs — i.e. 100 % UUID-first. |

## Findings table

| ID | Category | Severity | One-line |
|---|---|---|---|
| REV-100 | DESIGN_GAP | blocker | Workspace-first is absent from the UI: zero `workspace` references, 14 unused API routes, no creation/switch/membership/dependency surface. |
| REV-101 | CORRECTNESS_RISK | critical | `truncated` is returned by both graph endpoints and discarded by the client; 100-of-21 324 nodes shown as an unqualified "API result". |
| REV-102 | PERFORMANCE_RISK | critical | No edge budget and full `source_text` per node: measured 2.35 MB / 3.5 s for one 100-node subgraph with 5 296 edges. |
| REV-103 | CORRECTNESS_RISK | critical | Graph is never reset on scope change or request failure — a previous repository's graph stays on screen labelled "API result" (§3.7). |
| REV-104 | BUG_CONFIRMED | high | Failed sync/reindex/delete render as neutral `role="status"` notices; a failed delete shows its error *behind* the modal backdrop. |
| REV-105 | BUG_CONFIRMED | high | `indexing_progress` is never cleared, so a `ready` repository permanently displays "finalizing · 2284 files". |
| REV-106 | DESIGN_GAP | high | A typed raw symbol UUID is the only route to a focused subgraph; clicking a graph node is a dead end that exists to supply that UUID. |
| REV-107 | BUG_CONFIRMED | high | Dashboard swallows the API error and renders "No repositories yet", making a dead API indistinguishable from an empty install. |
| REV-108 | BUG_CONFIRMED | high | No `error.tsx` / `not-found.tsx` / `loading.tsx` anywhere: `GET /files/<unknown>` returns HTTP 500. |
| REV-109 | DESIGN_GAP | high | Navigation chain has four breaks: no workspace layer, no repository page, no tree browser, no graph→symbol link. |
| REV-110 | CORRECTNESS_RISK | high | `confidence` is rendered as a percentage but only two values exist (20, 100); three of the four filter thresholds are behaviourally identical. |
| REV-111 | CORRECTNESS_RISK | high | 62 151 of 136 566 edges have a NULL target and are dropped from every graph with no "unresolved" indicator. |
| REV-112 | CORRECTNESS_RISK | high | Fixture demo is mistakable for real data: named `knowledge-way`, real-looking paths, invented relationship types, fabricated confidences. |
| REV-113 | BUG_CONFIRMED | high | No `next/link` / `useRouter` anywhere: every navigation is a full page load that destroys search results, graph state and chat history. |
| REV-114 | DESIGN_GAP | high | Chat has no persisted conversation: it calls `/explanations`, never `/chat` or `/conversations`. |
| REV-115 | DESIGN_GAP | high | The graph canvas is unreachable by keyboard and unnameable to screen readers; no text alternative, no reduced-motion handling. |
| REV-116 | DESIGN_GAP | high | Delete dialog has no focus move, focus trap, Escape handler, focus restore or background inerting. |
| REV-117 | BUG_CONFIRMED | high | Search has no no-results state and no result-count/limit disclosure; 0 hits looks identical to "not searched yet". |
| REV-118 | BUG_SUSPECTED | high | No request sequencing in search or graph: overlapping requests can resolve out of order and render the wrong result set. |
| REV-119 | DESIGN_GAP | high | Search is globally unscoped in the UI even though `/api/search` accepts `repository_id`; graph empty-state blames filters when nothing was ever loaded. |
| REV-120 | BUG_CONFIRMED | high | The `semantic` capability object (state/reason, `reranking.applied`) is dropped by the client, so degraded providers and a silently-ignored reranker are invisible. |
| REV-121 | DESIGN_GAP | high | Repository creation cannot assign a workspace; every repository is permanently unassigned and the UI has no `Unassigned` concept. |
| REV-122 | TEST_GAP | high | No web test infrastructure at all — no runner, no test files; `mapApiGraph` and `isSafeCloneUrl` are exported, pure and untested. |
| REV-123 | DESIGN_GAP | medium | No indexing progress polling: the Indexing state never resolves to Ready or Failed without a manual reload. |
| REV-124 | DESIGN_GAP | medium | Chat and graph silently filter to `ready` repositories and auto-select an arbitrary one; with none ready, both surfaces are silent dead ends. |
| REV-125 | DESIGN_GAP | medium | Stale detection is impossible in the UI: `latest_detected_commit_sha` is returned by the API and omitted from the web `Repository` type. |
| REV-126 | DESIGN_GAP | medium | Delete-repository copy omits the workspace membership and dependency declarations that the API does in fact delete (§3.8). |
| REV-127 | CORRECTNESS_RISK | medium | Graph and symbol pages show no indexed commit, so graph evidence has no commit provenance (§3.6). |
| REV-128 | DESIGN_GAP | medium | Missing accessible names: search input, search-mode select and chat textarea have only placeholders. |
| REV-129 | DESIGN_GAP | medium | No `:focus` styling anywhere, no skip link, no `aria-current` on nav; `a:hover` is styled but `a:focus` is not. |
| REV-130 | DESIGN_GAP | medium | Graph state is never written to the URL, so a deep link works once and Refresh or Back silently discards everything the user did. |
| REV-131 | DOCUMENTATION_GAP | medium | `HOSTED_PRODUCT_AND_UI_VISION.md` promises dependency "evidence origin and confidence", which §7 explicitly forbids claiming. |
| REV-132 | DOCUMENTATION_GAP | medium | Documented repository-operations surface (branch selection, job timeline, counts, model identity, cost) is entirely unbuilt. |
| REV-133 | DESIGN_GAP | medium | File view has no symbol overlay, no repository context and no breadcrumb; line numbers sit inside the copyable region. |
| REV-134 | DESIGN_GAP | low | `aria-live="polite"` on the whole Node details panel announces every field including full symbol source text. |
| REV-135 | BUG_CONFIRMED | low | Pressing Enter in the graph Repository select or Depth field submits "Focus symbol" and produces a UUID-entry error. |
| REV-136 | BUG_SUSPECTED | low | Confidence normalisation is ambiguous: a stored value of `1` (1 %) would be rendered as 100 %. |
| REV-137 | BUG_SUSPECTED | low | `filteredGraph` drops isolated nodes whenever any link exists, so the displayed node count changes meaning under filtering. |
| REV-138 | DOCUMENTATION_GAP | low | The German label `Reranker verwenden` in an otherwise English UI is prescribed verbatim by the vision document. |

## Findings

### Blocker

- ID: REV-100
- Category: DESIGN_GAP
- Severity: blocker
- Evidence level: source-reviewed
- Applies to: both
- Impact: The top-level user decision described in §2 ("Workspace auswählen oder anlegen") does not exist. A human cannot create, name, select, switch, describe or delete a workspace; cannot add or remove repository membership; cannot declare, view or maintain a dependency. Every one of §2's eight expected workspace behaviours is unreachable from the browser. The live database confirms the consequence: `workspaces` has 0 rows after a full session of use, because no code path in the UI can produce one.
- Evidence:
  - `grep -rnic "workspace" apps/web/app apps/web/lib` → `0` for all 16 source files. There is no workspace identifier, type, route, component, label or fetch anywhere in the web app.
  - Route inventory: `find apps/web -type f` yields exactly six addressable pages — `app/page.tsx`, `app/search/page.tsx`, `app/chat/page.tsx`, `app/graph/page.tsx`, `app/files/[id]/page.tsx`, `app/repositories/[repositoryId]/symbols/[symbolId]/page.tsx`. No `/workspaces` segment exists.
  - Live corroboration on `main`: `curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/workspaces` → `404`.
  - The API side is complete and unused: `apps/api/app/main.py:74-146` defines 14 workspace routes (`GET/POST /api/workspaces`, `GET/PATCH/DELETE /api/workspaces/{id}`, 4 dependency routes, `GET /api/workspaces/{id}/repositories`, `PUT`+`POST`+`DELETE .../repositories/{repo_id}`). The complete set of paths the web client requests is nine: `/repositories`, `/repositories/{id}`, `/repositories/{id}/sync`, `/repositories/{id}/reindex`, `/repositories/{id}/graph`, `/repositories/{id}/symbols/{sid}/subgraph`, `/repositories/{id}/symbols/{sid}[/callers|/callees]`, `/files/{id}`, `/search`, `/explanations`, `/documentation/generate`. Zero workspace paths.
  - `apps/web/app/layout.tsx:3` — the global navigation is a flat four-item list (`Dashboard`, `Search`, `Code graph`, `AI Chat`) with no workspace switcher slot and no hierarchy.
- Probable cause + diagnostic confidence: Deliberate build order — the API/data model was delivered first and the UI slice was never started. High confidence; this is a straightforward absence, not a malfunction.
- Smallest safe next step: Decide the Unassigned-repository policy (§11.2) before writing UI. Then a single read-only slice: a `GET /api/workspaces` -backed switcher in `layout.tsx` plus a `/workspaces` list page with a create form. No ingestion, provider or migration change required.
- Affected data/migrations/providers/cost: None. `workspaces`, `workspace_repositories` and `workspace_dependencies` already exist at head `20260809_0008`; the live database is at `20260808_0004` and already has all three tables.
- Recommended tests + acceptance criteria: API test that a created workspace appears in `GET /api/workspaces`; browser E2E for create → appears in switcher → select → repository list scoped to members; negative test that a non-member repository ID is rejected server-side. Acceptance: a human completes §2 steps 1–2 with no UUID typing.
- Fix status: report-only

### Critical

- ID: REV-101
- Category: CORRECTNESS_RISK
- Severity: critical
- Evidence level: source-reviewed + manual live acceptance (truncation flag confirmed live on `main`'s subgraph route)
- Applies to: both (integration exposes it on two endpoints; `main` has no `/graph` route at all, so only the subgraph path is affected there)
- Impact: The user is shown a heavily truncated graph and told it is "API result · N nodes · M relationships". There is no indication that the graph is a fraction of the data, no cause, and no count of what was omitted. This is precisely the misleading-evidence class §3.3/§5.D exist to prevent: a bounded budget is honest only if the boundary is visible.
- Evidence:
  - Both endpoints return the flag. `apps/api/app/main.py:261` — `return {'root_symbol_id':symbol_id,'depth':depth,'max_nodes':max_nodes,'truncated':truncated,'nodes':[...],'edges':[...]}`. `apps/api/app/main.py:295` — `return {'repository_id':repo.id,'max_nodes':max_nodes,'truncated':len(selected)<len(symbols),'nodes':graph_nodes,'edges':graph_edges}`.
  - The client throws it away. `apps/web/app/graph/graph-explorer.tsx:32-54` (`mapApiGraph`) reads only `nodes`, `edges`/`links` and `root_symbol_id`, and returns `{ nodes, links }`. `truncated` and `max_nodes` are never referenced anywhere in `apps/web` (`grep -rn "truncated" apps/web` → no match).
  - The summary line that should carry it: `graph-explorer.tsx:110` — `{source === 'fixture' ? 'Fixture demo' : source === 'api' ? 'API result' : 'No graph loaded'} · {filteredGraph.nodes.length} nodes · {filteredGraph.links.length} relationships`.
  - Live magnitude, reproducible:
    ```
    SID=ac72c484-621c-4f6f-996c-c4cc8a2870bc
    curl -s "http://localhost:8000/api/repositories/21ffa409-9e13-493a-b919-7bb6a5b80bb9/symbols/$SID/subgraph?depth=2" | python3 -c "import sys,json;d=json.load(sys.stdin);print({k:v for k,v in d.items() if k not in ('nodes','edges')})"
    → {'root_symbol_id': 'ac72c484-...', 'depth': 2, 'max_nodes': 100, 'truncated': True}
    ```
  - The repository overview is worse: `graph-explorer.tsx:94` hardcodes `?max_nodes=100`, and `MAX_GRAPH_NODES=100` (`main.py:52`) is also the hard server ceiling, so the budget cannot be raised. Against the live repository's 21 324 symbols and 2 284 files, the overview is guaranteed `truncated: true` and shows well under 0.5 % of the symbol population, ranked by degree (`main.py:274`), with no disclosure.
- Probable cause + diagnostic confidence: `mapApiGraph` was written as a shape-normaliser for node/link rendering and metadata was out of its remit; no caller compensates. High confidence — the flag is produced and demonstrably never read.
- Smallest safe next step: Return `truncated` and `max_nodes` from `mapApiGraph` and render them in the existing summary strip (`graph-explorer.tsx:110`), e.g. `Showing 100 of 21 324 symbols (node budget reached)`. Server already supplies everything except the total, which `repository_graph` has in `len(symbols)` and could add as `total_nodes`.
- Affected data/migrations/providers/cost: None. Read-only response-shape addition.
- Recommended tests + acceptance criteria: unit test on `mapApiGraph` asserting `truncated` survives both response shapes; API test asserting `truncated is True` when `max_nodes` is below the reachable set; browser E2E asserting the truncation notice is present for the live repository overview. Acceptance: no graph can be displayed without either "complete" or an explicit omission count.
- Fix status: report-only. **Addressed on the current working branch after this review began** — the coordinator reports `truncated` is now surfaced in the graph summary bar. The finding stands as filed against the pinned target `c122529` and against `main`; the roadmap should not double-count it. Not re-verified by this workstream, and the node/edge-count disclosure (REV-102) and the "total available" figure are separate and may remain open.

- ID: REV-102
- Category: PERFORMANCE_RISK
- Severity: critical
- Evidence level: manual live acceptance (measured against live `main` API) + source-reviewed (cause identical on integration)
- Applies to: both
- Impact: A single "focus symbol" action transfers 2.35 MB and takes 3.5 s, then asks a force-directed canvas to lay out 5 296 edges over 100 nodes. §3.3 requires hard node **and edge** budgets; only a node budget exists. The visual result cannot be comprehensible at that density, and clicking any node dumps the full source text of that symbol into a definition list.
- Evidence:
  - Measured, reproducible (single repository, warm containers; not a synthetic benchmark):
    ```
    SID=ac72c484-621c-4f6f-996c-c4cc8a2870bc
    curl -s -o /dev/null -w "%{size_download} bytes %{time_total}s\n" ".../symbols/$SID/subgraph?depth=2"
    → 2352734 bytes 3.492733s
    curl ... "?depth=1"  → 1935076 bytes 3.429538s
    ```
    Node/edge counts for the same call: `nodes= 100 edges= 5296`.
  - No edge budget exists in either endpoint. `main.py:260` — `graph_edges=[e for e in edges if e.source_symbol_id in selected and e.target_symbol_id in selected]` — unbounded once the node set is fixed. `main.py:294` likewise. The `max_nodes` query parameter is the only budget.
  - Root cause of the payload size: `main.py:261` emits `symbol_out(...)` per node, and `symbol_out` (`main.py:53`) includes `'source_text':s.source_text` and `'signature'`. The graph needs a label and a kind; it receives every symbol's entire body.
  - The client propagates it into React state and into the DOM: `graph-explorer.tsx:41` spreads `...item` into each node, and `graph-explorer.tsx:114` renders **every** remaining key — `Object.entries(selected).filter(([key]) => !['id','label','kind','x','y','vx','vy','index','__indexColor'].includes(key)).map(...)` — so `source_text`, `signature`, `start_byte`, `end_byte`, `parent_symbol_id`, `degree` and `isRoot` are all written into `<dd>` elements on node click. The stylesheet's `.graph-detail dd { overflow-wrap: anywhere; }` (`globals.css:9`) is a symptom of this.
- Probable cause + diagnostic confidence: The graph endpoints reuse the symbol-detail serialiser rather than a projection. High confidence for the cause of payload size (directly attributable); the rendering-comprehensibility claim is reasoned from the measured 5 296/100 ratio, not from a browser observation, since Chromium was unavailable.
- Smallest safe next step: Add a graph-node projection (`id`, `qualified_name`, `kind`, `file_id`, `start_line`, `end_line`) instead of `symbol_out` in the two graph routes; add an explicit `max_edges` budget with `truncated_reason`. Client-side, replace the "dump every key" loop with an allow-list.
- Affected data/migrations/providers/cost: None. No provider or schema involvement. Reduces load on Postgres and the browser.
- Recommended tests + acceptance criteria: API test asserting graph node payloads contain no `source_text`; API test asserting `len(edges) <= max_edges` and that `truncated` reports the edge cause; a recorded payload-size assertion (e.g. < 200 KB for `max_nodes=100`). Acceptance: measured payload and latency re-recorded after the change, per §7 no performance claim without measurement.
- Fix status: report-only

- ID: REV-103
- Category: CORRECTNESS_RISK
- Severity: critical
- Evidence level: source-reviewed
- Applies to: integration (main's graph-explorer is the divergent working-tree version; the same reset omission should be re-checked there separately)
- Impact: Direct §3.7 violation. Old graph answers are neither discarded nor isolated on scope change, so the user can read a graph belonging to repository A while the controls say repository B, with the summary strip still asserting "API result". Combined with REV-127 (no commit shown), there is no way for the user to detect the mismatch.
- Evidence:
  - Changing the repository never clears the graph: `graph-explorer.tsx:103` — `<select value={repositoryId} onChange={(event) => setRepositoryId(event.target.value)} required>`. The handler sets the ID only. `graph`, `source`, `selected`, `relationship` and `minimumConfidence` are untouched. Same for the symbol input, `graph-explorer.tsx:104`.
  - Failure leaves stale data on screen: `graph-explorer.tsx:84-85` — `catch (cause) { setError(...) } finally { setLoading(false) }`. No `setGraph({nodes:[],links:[]})`, no `setSource('empty')`. Identical omission in `requestOverview`, `graph-explorer.tsx:95-96`.
  - Consequence chain, source-traceable: click "Repository map" for A → `source='api'`, graph = A. Select B in the dropdown → nothing changes on screen. Click "Repository map" → if the request fails, the error banner (`graph-explorer.tsx:108`) appears **above** a canvas still rendering A, and the summary (`:110`) still reads "API result · N nodes". If it succeeds, the transition is silent with no indication which repository is displayed.
  - The same class of omission also survives a fixture → API failure transition: after `loadFixture()` (`:98`) sets `source='fixture'`, a failed API request leaves the fixture rendered while the error implies a real request was attempted.
  - Contrast: the symbol page does this correctly — `apps/web/app/repositories/[repositoryId]/symbols/[symbolId]/page.tsx:15` uses an `active` flag (`let active = true; ... if (!active) return; ... return () => { active = false; }`). The pattern exists in the codebase and was not applied to the graph.
- Probable cause + diagnostic confidence: Missing reset on the controlled inputs' change handlers plus missing reset in the error path. High confidence; the state transitions are fully visible in 40 lines.
- Smallest safe next step: In the two `onChange` handlers and both `catch` blocks, reset `graph`/`source`/`selected`. Cheapest correct version: derive a `scopeKey = repositoryId + '|' + symbolId` and clear whenever it changes, so no handler can be forgotten.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: component test — load graph for A, change repository to B, assert the canvas is empty and the summary reads "No graph loaded"; second test — force a rejected fetch and assert the graph is cleared alongside the error. Acceptance: no rendered graph can outlive the scope it was fetched for.
- Fix status: report-only

### High

- ID: REV-104
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: source-reviewed
- Applies to: both (`dashboard-client.tsx` is byte-identical on `main` and integration)
- Impact: Failed operations are announced as if they had succeeded. A failed sync, reindex or delete renders in the same neutral `.form-message` with `role="status"` used for success notices — not `.form-error`, not `role="alert"`. Worse, a failed delete leaves the modal open with the error message rendered *behind* the full-screen backdrop, so the user sees a dialog that appears to hang.
- Evidence:
  - `apps/web/app/dashboard-client.tsx:37-45` — `runAction` writes both outcomes to the same state: success `setNotice(\`${action === 'sync' ? 'Sync' : 'Reindex'} queued for ${repo.name}.\`)` (line 41) and failure `catch (error) { setNotice(apiErrorMessage(error)); }` (line 43).
  - The single render site has no error styling: `dashboard-client.tsx:77` — `{notice && <p className="form-message" role="status">{notice}</p>}`. The codebase *has* the error variant (`.form-error`, used at `:74` and `:82`) and simply does not use it here.
  - Failed delete keeps the dialog open and hides the message: `dashboard-client.tsx:47-57` — on success `setDeleting(null)` (line 54) runs, but the `catch` (line 55) only calls `setNotice(...)`, leaving `deleting` set. Since `deleting` is truthy the backdrop renders (`:92`) with `position: fixed; inset: 0; z-index: 10; background: rgb(0 0 0 / .65)` (`globals.css:10`), and the notice at `:77` is part of the underlying page, so it is behind the overlay. The confirm button label also reverts from "Deleting…" to "Delete repository" because `busy` is cleared in `finally`, giving no trace that anything failed.
  - Inconsistent error formatting across the app: the dashboard normalises errors through `apiErrorMessage` (`lib/repositories.ts:33-41`, which unwraps a JSON `detail`), but `search-client.tsx:38`, `chat-client.tsx:18`, `graph-explorer.tsx:84`/`:95` and the symbol page `:15`/`:16` all use `cause.message` directly. Since `lib/api.ts:10` throws `new Error(await response.text())`, those four surfaces display the raw response body — e.g. the literal string `{"detail":"Repository not found"}`.
- Probable cause + diagnostic confidence: One notice channel reused for two outcomes, plus a missing dialog-close/error-placement in the delete path. High confidence — both branches are visible in the same function.
- Smallest safe next step: Add an `isError` flag alongside `notice` (or store `{text, kind}`) and pick `.form-error` + `role="alert"` for failures; render the delete error *inside* `.confirm-dialog`. Route the other four surfaces through the existing `apiErrorMessage` helper — it is already exported and unused by them.
- Affected data/migrations/providers/cost: None. Note that a failed `sync`/`reindex` currently leaves no visible trace, which can lead a user to re-click and enqueue duplicate indexing work — an indirect cost path.
- Recommended tests + acceptance criteria: component test — reject the sync request, assert the message carries `role="alert"` and the error class; reject the delete request, assert the dialog stays open **and** contains the error text. Acceptance: no failure path renders through `role="status"`.
- Fix status: report-only

- ID: REV-105
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: manual live acceptance (live API payload) + source-reviewed
- Applies to: both (`dashboard-client.tsx` and `lib/repositories.ts` are byte-identical across branches)
- Impact: A fully indexed repository permanently displays an in-progress phase. The status pill says `ready` while the Progress field beneath it says `finalizing · 2284 files`, so the Indexing and Ready states are not distinguishable from the progress readout, and the user cannot tell a genuinely running index from a finished one without reading the pill.
- Evidence:
  - Live payload for the only repository, which has `indexing_status = ready` and `last_indexed_at = 2026-08-10T11:49:38`:
    ```
    curl -s http://localhost:8000/api/repositories | python3 -c "import sys,json;d=json.load(sys.stdin)[0];print(d['indexing_status'], json.dumps(d['indexing_progress']))"
    → ready {"files": 2284, "phase": "finalizing"}
    ```
  - `apps/web/lib/repositories.ts:26-31` — `progressLabel` renders `${phase}${files}` with no reference to `indexing_status`, so it produces `finalizing · 2284 files` for a ready repository.
  - Rendered unconditionally next to the status pill: `dashboard-client.tsx:81` — `<div><dt>Progress</dt><dd>{progressLabel(repo.indexing_progress)}</dd></div>`.
  - The inverse defect is present too: for a `pending` repository with an empty progress object the label is the hardcoded `'Waiting to start'` (`repositories.ts:27`), which is also what a `failed` repository shows if its progress was never written — so Pending and Failed collapse onto the same progress text.
- Probable cause + diagnostic confidence: The ingestion path never clears or finalises `indexing_progress` on completion, and `progressLabel` is status-blind. High confidence for the UI half (directly observed); the ingestion half belongs to workstream E and is inferred from the persisted value.
- Smallest safe next step: UI-only and safe — make `progressLabel` take `indexing_status` and return `''`/`Indexed 2 284 files` for `ready`, `Failed` for `failed`. Do not change ingestion as part of a UX fix (§4 boundary: `ingestion.py` is do-not-touch without a separate gate).
- Affected data/migrations/providers/cost: None for the UI fix. Clearing `indexing_progress` server-side would touch ingestion and is out of scope here.
- Recommended tests + acceptance criteria: unit test on `progressLabel` covering `ready`+stale phase, `pending`+empty, `indexing`+phase, `failed`. Acceptance: the Progress field never contradicts the status pill.
- Fix status: report-only

- ID: REV-106
- Category: DESIGN_GAP
- Severity: high
- Evidence level: source-reviewed
- Applies to: integration (the `main` working tree has an uncommitted symbol-search picker that addresses this; that fix is not on the review target)
- Impact: Direct §3.2 violation at the primary graph entry point. To open a focused symbol subgraph from `/graph`, a human must obtain a 36-character UUID and type or paste it into a text field. §2 requirement 8 ("nie Repository- oder Symbol-UUIDs manuell eingeben müssen") is unmet. The design compounds it: the one place that surfaces a symbol UUID is the Node details panel, so the intended workflow is literally "click a node, copy the UUID, paste it into the input" — the UI teaches the anti-pattern.
- Evidence:
  - The input: `graph-explorer.tsx:104` — `<label>Symbol (optional for overview)<input value={symbolId} onChange={...} placeholder="symbol UUID for local graph" autoComplete="off" /></label>`.
  - The submit path uses it verbatim: `graph-explorer.tsx:82` — `\`/repositories/${encodeURIComponent(repository.trim())}/symbols/${encodeURIComponent(symbol.trim())}/subgraph?depth=${boundedDepth}\``.
  - The error copy instructs UUID entry and is also inaccurate about the repository control: `graph-explorer.tsx:78` — `'Enter both a repository ID and a symbol ID to load the API graph, or use the fixture demo.'` The repository is a `<select>` (`:103`), not an entry field.
  - The UUID source is the adjacent panel: `graph-explorer.tsx:114` — `<dt>ID</dt><dd className="citation">{selected.id}</dd>`, prefaced by `Click a node to inspect its identifier and metadata.`
  - Graph nodes are not links, so there is no alternative: `graph-canvas.tsx:77` — `onNodeClick={(node) => onNodeClick(node as GraphNode)}` — and `onNodeClick` is `setSelected` (`graph-explorer.tsx:112`). Clicking a node changes local state only; it never navigates, never refocuses the graph, and never reaches `/repositories/{r}/symbols/{s}`.
  - A symbol picker is buildable from existing pieces but was not: `/api/search/symbols` exists (`main.py:301`) and on integration `result()` does include `symbol_id` (`apps/api/app/search.py:35` — `'symbol_id': item.id if kind == 'symbol' else getattr(item, 'symbol_id', None)`). Live confirmation that this is integration-only: `curl -s "http://localhost:8000/api/search/symbols?q=Agent"` on `main` returns result keys with **no** `symbol_id`.
  - The indirect path that does work: Search → "Open graph →" (`search-client.tsx:57`) and Symbol page → "Open graph →" (symbol page `:19`) both build `?repository=&symbol=`, and the deep link is honoured (`graph-explorer.tsx:60-61`, `:89`). So a human can reach a focused graph without typing a UUID — but only by starting in Search, never from the graph page itself.
- Probable cause + diagnostic confidence: The graph page was built before search carried `symbol_id`, and the text input was never replaced. High confidence.
- Smallest safe next step: Replace the input with a debounced symbol search against `/api/search/symbols` scoped by the already-selected `repositoryId`, selecting `symbol_id` from the result. The working-tree implementation on `main` is a reference; note its comment that `main`'s `/search/symbols` omits `symbol_id` and needs a file lookup — on integration that detour is unnecessary.
- Affected data/migrations/providers/cost: None. `/api/search/symbols` is lexical only (`search(db,q,'symbols')`), no provider call, no embedding cost.
- Recommended tests + acceptance criteria: browser E2E — from `/graph`, type a symbol name, pick a suggestion, assert a subgraph loads and no UUID was typed. Acceptance: no text input in the product accepts a UUID as its primary value.
- Fix status: report-only. **Addressed on the current working branch after this review began** — the coordinator reports the raw symbol-UUID input has been replaced with a symbol search field (type a name, pick a hit, focus the graph). The finding stands as filed against the pinned target `c122529` and against `main`; the roadmap should not double-count it. Not re-verified by this workstream. The five remaining raw-UUID exposures in the table above (notably #3, the Node details panel, and #6, workspace operations having no client at all) are **not** covered by that change.

- ID: REV-107
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: source-reviewed
- Applies to: both (`app/page.tsx` is byte-identical across branches)
- Impact: When the API is unreachable the dashboard renders the *empty* state — "No repositories yet. Connect one above to begin indexing." — with metric tiles reading 0/0/0. A user whose backend is down is told their data does not exist, and is invited to re-add a repository they already have. Empty and Failed are indistinguishable on the application's landing page.
- Evidence:
  - `apps/web/app/page.tsx:5-12`:
    ```tsx
    let repos: Repository[] = [];
    try { repos = await api<Repository[]>('/repositories'); } catch { /* The client can still connect once the API is available. */ }
    ```
    The error is swallowed with no state to distinguish it, and `repos` stays `[]`.
  - The empty branch that then renders: `dashboard-client.tsx:89` — `{!repos.length && <div className="card">No repositories yet. Connect one above to begin indexing.</div>}`.
  - The metrics are computed from the same empty array: `dashboard-client.tsx:61-63` — three tiles reading `repos.length`, ready count and indexing count, all `0`.
  - There is no boundary to catch it either: no `error.tsx` or `global-error.tsx` exists anywhere under `apps/web` (verified: `find apps/web -name error.tsx -o -name global-error.tsx` → 0 results), so removing the `try/catch` would surface REV-108's raw 500 instead.
  - The comment shows the intent was resilience, but the client-side `refresh()` (`dashboard-client.tsx:19-21`) is only ever called after a user action, so nothing recovers automatically.
- Probable cause + diagnostic confidence: Deliberate swallow to keep the shell rendering during startup, without a distinct "backend unavailable" state. High confidence.
- Smallest safe next step: Pass the failure down — `const unreachable = ...` in the catch, and render a distinct card ("Cannot reach the indexing service") instead of the empty-state card. Two lines plus a conditional.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: component test rendering `DashboardClient` with an explicit `unreachable` prop asserting the empty-state copy is *not* shown; browser E2E with the API container stopped. Acceptance: "no repositories" is only ever shown after a successful empty response.
- Fix status: report-only

- ID: REV-108
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: manual live acceptance + source-reviewed
- Applies to: both (`app/files/[id]/page.tsx` is byte-identical across branches, and no boundary files exist on either)
- Impact: Any failure in a server component produces a bare HTTP 500 with the generic app shell — no message, no retry, no way back. A stale or mistyped file link, a deleted file, or a transient API error all yield the same dead page. There is also no route-level loading state anywhere, so navigating to a large file gives no feedback until the whole document arrives.
- Evidence:
  - Live, reproducible: `curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/files/does-not-exist` → `500`. The response body carries only `<title>knowledge-way</title>`, i.e. the layout shell with no error content.
  - Cause: `apps/web/app/files/[id]/page.tsx:1` awaits `api<...>(\`/files/${id}\`)` with no `try`/`catch` and no `notFound()`. `lib/api.ts:10` throws on any non-2xx (`if (!response.ok) throw new Error(await response.text())`), and the API returns 404 for an unknown file (`main.py:219` — `raise HTTPException(404,'File not found')`), so the throw propagates out of the server component.
  - No Next.js boundaries exist at all — verified on the static target:
    ```
    error.tsx: 0   global-error.tsx: 0   not-found.tsx: 0
    loading.tsx: 0   template.tsx: 0     middleware.ts: 0
    ```
  - The same exposure applies to the dashboard route were its `try/catch` (REV-107) removed, and to any future server component.
  - Related dead ends confirmed live on `main`: `/repositories` → 404, `/repositories/21ffa409-…` → 404, `/repositories/21ffa409-…/symbols` → 404, `/workspaces` → 404. On integration the third of those resolves one level deeper only (`…/symbols/{symbolId}`), so the intermediate segments remain 404 on both branches by route-file structure.
- Probable cause + diagnostic confidence: Next.js boundary files were never added. High confidence — verified by both file absence and a live 500.
- Smallest safe next step: Add one `app/error.tsx` and one `app/not-found.tsx` (native platform feature, no dependency), and call `notFound()` in the file page when the API returns 404. Add `app/loading.tsx` for route-level feedback.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: browser E2E asserting `/files/<bogus>` renders a readable not-found page with a link back, and that the HTTP status is 404 rather than 500. Acceptance: no user-reachable URL returns a bare 500.
- Fix status: report-only

- ID: REV-109
- Category: DESIGN_GAP
- Severity: high
- Evidence level: source-reviewed (route-existence corroborated live on `main`)
- Applies to: both
- Impact: The §2 chain `Workspace → "Alle Repositories" → Repository → Tree/Search/File → Symbol → Graph` is broken in four places. Only the middle segment (Search → Symbol → Graph) is complete.
- Evidence — link-by-link, with the exact missing element:
  | Link | Status | Exact missing element |
  |---|---|---|
  | Workspace → anything | **missing** | No workspace UI at all (REV-100). |
  | Workspace overview ("Alle Repositories") | **missing** | No bounded workspace-level graph or list exists; `graph-explorer.tsx:94` only ever fetches a *single* repository's `/graph`. §3.3's "one deterministic bounded graph" has no UI counterpart. |
  | Dashboard → Repository | **missing** | `dashboard-client.tsx:79-88` renders each repository as an `<article>` whose only interactive children are the Sync/Reindex/Delete buttons (`:84-86`). The repository name at `:80` is a plain `<b>`, not a link. There is no `/repositories/[repositoryId]/page.tsx` on either branch, so `/repositories/<uuid>` → 404 (verified live on `main`). |
  | Repository → Tree | **missing** | `GET /api/repositories/{repo_id}/tree` exists (`main.py:207-215`) and is called by nothing: `grep -rn "tree" apps/web` → no match. There is no file-browser surface anywhere in the product. |
  | Repository → Search | **partial** | Search exists but is not repository-scoped from the UI (REV-119), so this is a global escape hatch rather than a scoped drill-down. |
  | Search → File | works | `search-client.tsx:62` — `<a href={\`/files/${encodeURIComponent(result.file_id)}#L${result.start_line}\`}>Open source →</a>`. |
  | File → Symbol | **missing** | `GET /api/files/{file_id}/symbols` exists (`main.py:221`) and is unused. `files/[id]/page.tsx` renders raw lines only; no symbol is clickable, and there is no link back to the repository (REV-133). |
  | Search → Symbol | works (integration only) | `search-client.tsx:55-56`, gated on `result.symbol_id && result.repository_id`. Requires integration's `search.py:35`. |
  | Symbol → Graph | works | symbol page `:19` — `\`/graph?repository=…&symbol=…\``, honoured at `graph-explorer.tsx:60-61,89`. |
  | Symbol → Symbol | works | symbol page `:20` — callers/callees render as links to sibling symbol pages. |
  | **Graph → Symbol** | **missing** | `graph-canvas.tsx:77` routes clicks to `setSelected` only. No node is a link, nothing navigates to `/repositories/{r}/symbols/{s}`, and the graph cannot re-focus itself on a clicked node. The graph is a terminal surface (REV-106). |
  - Coverage of the chain in the shipped nav: `layout.tsx:3` offers four flat destinations with no notion of a current repository or workspace.
- Probable cause + diagnostic confidence: Vertical slices were delivered per page rather than per journey; the API grew ahead of the UI. High confidence — every claim is an absent route file or an uncalled endpoint.
- Smallest safe next step: Add `/repositories/[repositoryId]/page.tsx` as the missing hub — it needs only `GET /api/repositories/{id}` plus `GET /api/repositories/{id}/tree`, both existing and free — and make the dashboard repository name link to it. That single page closes three of the broken links (Dashboard→Repository, Repository→Tree, and gives Graph→Symbol somewhere to land).
- Affected data/migrations/providers/cost: None; both endpoints are read-only Postgres queries with no provider involvement.
- Recommended tests + acceptance criteria: browser E2E walking dashboard → repository → tree → file → symbol → graph without ever editing the URL bar. Acceptance: every step is reachable by clicking, and no step requires knowing an ID.
- Fix status: report-only

- ID: REV-110
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: PostgreSQL integration-tested (value distribution) + source-reviewed (rendering)
- Applies to: both
- Impact: The UI presents `confidence` as a calibrated percentage in three places, but the stored value is a two-valued heuristic marker. Users are shown "20 % confidence" and "94 %"-style precision that does not exist, and given a four-option confidence filter in which three options are behaviourally identical. This is the false-precision case §7 forbids ("Evidenzursprung oder Confidence … darf kein Report oder UI behaupten") and §5.D restricts.
- Evidence:
  - The entire live distribution — only two values exist across 136 566 edges:
    ```
    docker compose exec -T postgres psql -U knowledgeway -d knowledgeway \
      -c "SELECT relationship_type, confidence, count(*) FROM symbol_edges GROUP BY 1,2 ORDER BY 3 DESC;"
     relationship_type | confidence | count
     call              |        100 | 67792
     call              |         20 | 54439
     import            |         20 |  7712
     import            |        100 |  6623
    ```
  - The schema makes it a constant-defaulted integer, not a measurement: `apps/api/app/models.py:37` — `confidence:Mapped[int]=mapped_column(Integer,default=50)`. Note the default (50) does not even occur in the data, so the default is dead and the two real values are set explicitly by extraction.
  - Rendered as a percentage in three places:
    1. `graph-canvas.tsx:66` — `linkLabel={(link) => ... \`${item.relationship} (${Math.round(item.confidence * 100)}%)\`}` → hover shows `call (20%)`.
    2. symbol page `:20` — `${confidencePercent(edge.confidence)}% confidence` in the callers/callees lists.
    3. `graph-canvas.tsx:12` — edge thickness `(link.confidence ?? 0) >= 0.9 ? 2.2 : 1.4`, i.e. a binary visual encoding dressed as a threshold.
  - Three of four filter options are equivalent. `graph-explorer.tsx:111` offers `Any confidence` / `50% or higher` / `75% or higher` / `90% or higher`; the filter is `graph-explorer.tsx:71` — `(link.confidence == null || link.confidence >= minimum)`. With only `0.2` and `1.0` present after normalisation (`graph-explorer.tsx:48`), the thresholds `0.5`, `0.75` and `0.9` all select exactly the same set. A user changing 50 %→90 % sees no change and reasonably concludes the filter is broken.
  - The fixture is what makes the filter *look* meaningful, which is why the defect is easy to miss: its fabricated confidences are `0.94` and `0.87` (`graph-explorer.tsx:22-23`), deliberately straddling the 0.9 threshold (REV-112).
- Probable cause + diagnostic confidence: `confidence` encodes "target symbol resolved" (100) vs "name-matched only" (20); the UI treats the column as a probability. High confidence — the distribution query is definitive.
- Smallest safe next step: Stop rendering a percentage for values that are not probabilities. Cheapest honest version: map `100 → "resolved"` and `20 → "unresolved name match"` in the link label and the callers/callees list, and replace the four-option confidence filter with a two-state "resolved only" toggle. No schema change needed.
- Affected data/migrations/providers/cost: None. A later real confidence model would be a separate, versioned change and must not reuse this column's semantics silently.
- Recommended tests + acceptance criteria: API test asserting the documented confidence vocabulary is closed and enumerated; component test asserting the graph filter offers only states the data can distinguish. Acceptance: no percentage is shown for a value that is not a measured probability, per §7.
- Fix status: report-only

- ID: REV-111
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: PostgreSQL integration-tested + source-reviewed
- Applies to: both
- Impact: 45.5 % of extracted relationships are invisible in every graph view, with no indicator. The user sees a call graph that appears complete and reads it as "these are the callers/callees", when nearly half the references the indexer found were dropped because their target could not be resolved to a symbol. This is a misleading-completeness claim about evidence — the highest-priority class in §8.5.
- Evidence:
  - Live counts:
    ```
    docker compose exec -T postgres psql -U knowledgeway -d knowledgeway \
      -c "SELECT count(*) FROM symbol_edges WHERE target_symbol_id IS NULL;"
    → 62151      (of 136566 total = 45.5 %)
    ```
  - Server-side drop, both graph endpoints: `main.py:245` — `edges=[e for e in scoped_edges(db,repo_id) if e.source_symbol_id and e.target_symbol_id]`; `main.py:267` — the same predicate for the repository overview. Neither response reports how many were excluded; `truncated` covers only the node budget (`main.py:261`, `:295`).
  - The callers/callees routes drop them too: `main.py:230` filters on the resolved endpoint, so the symbol page's "Callers"/"Callees" lists silently exclude unresolved references and can render the reassuring `None found.` (symbol page `:20`) for a symbol that in fact has many unresolved inbound references.
  - Client-side second drop: `graph-explorer.tsx:46` — `if (!source || !target || !nodeIds.has(source) || !nodeIds.has(target)) return null;` — so any edge whose endpoint fell outside the node budget is discarded silently as well, on top of REV-101.
  - The data needed for an honest indicator is already stored: `models.py:37` keeps `target_name:Mapped[str]=mapped_column(Text,index=True)` for exactly these edges, and `edge_out` (`main.py:54`) already returns `target_name`. Nothing surfaces it.
- Probable cause + diagnostic confidence: The graph model requires both endpoints to be node IDs, and unresolved references have no node to attach to. High confidence for the drop and its magnitude; the user-interpretation consequence is a design judgement.
- Smallest safe next step: Report the count without changing the graph shape — add `unresolved_edge_count` to both graph responses and render it in the existing summary strip ("… · 143 unresolved references not shown"). On the symbol page, replace `None found.` with a statement that distinguishes "no references" from "no *resolved* references".
- Affected data/migrations/providers/cost: None. Rendering unresolved targets as pseudo-nodes later would be a larger change and must not be presented as verified edges (§3.4, §7).
- Recommended tests + acceptance criteria: API test on a fixture with a deliberately unresolvable reference asserting the count is reported; component test asserting the notice renders. Acceptance: no graph or neighbour list implies completeness it does not have.
- Fix status: report-only

- ID: REV-112
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: source-reviewed (relationship vocabulary corroborated by SQL)
- Applies to: both
- Impact: The fixture demo is designed to look exactly like this product's own real output, and its only disclosure is one muted inline phrase. A user who clicks "Fixture" — or who arrives at a screen someone else left in that state — can reasonably believe they are looking at indexed data about knowledge-way itself. Worse, the fixture teaches a relationship vocabulary and a confidence range that the indexer never produces, so it actively miscalibrates the user's expectations for the real graph.
- Evidence:
  - The fixture impersonates this repository. `graph-explorer.tsx:12-25`: the repository node is `label: 'knowledge-way'`, and the file/directory nodes are `apps`, `web`, `api`, `search/page.tsx`, `app/main.py` — all real paths in this codebase. If a user connects knowledge-way as a repository (the demo playbook's natural first move), the fixture is indistinguishable from a genuine 8-node overview of it.
  - Its relationship types do not exist in reality. Fixture links use `renders` and `handles` (`graph-explorer.tsx:22-23`); the database contains only `call` and `import` (see REV-110's distribution query). Because the filter dropdown is populated from the loaded graph — `graph-explorer.tsx:67` — `relationshipTypes = [...new Set(graph.links.map((link) => link.relationship))].sort()` — clicking "Fixture" populates the Relationship filter with two invented types.
  - Its confidences are fabricated at a precision the data never has: `0.94` and `0.87`. Real values are only `0.2` and `1.0` (REV-110). These two numbers straddle the `0.9` filter threshold, so on the fixture the confidence filter appears to work and on real data it does not.
  - Its edge styling maps to nothing: `graph-canvas.tsx:9-13` styles `contains` and `defines` specially and falls through to the "calls/references" style for everything else, so fixture `renders`/`handles` edges render with the same solid arrows as real verified calls — violating §3.4's requirement that visual semantics distinguish relationship classes.
  - Disclosure is weak and easy to miss: the only label is inside the summary strip at `graph-explorer.tsx:110`, positioned *after* the legend dots, as `<span className="muted">Fixture demo · 8 nodes · 7 relationships</span>` — i.e. `.muted { color: #9babca }` (`globals.css:8`) at 13 px (`globals.css:9`). There is no banner, no canvas watermark, no colour change, and no confirmation when entering fixture mode.
  - Fixture IDs are presented in the citation style used for real provenance: clicking a fixture node renders `<dt>ID</dt><dd className="citation">repo</dd>` (`graph-explorer.tsx:114`), where `.citation` is the monospace style used for genuine file citations in search and chat (`globals.css:8`).
  - Fixture state survives a failed real request (REV-103), so the sequence "click Fixture → select a repository → Repository map fails" leaves a fixture on screen next to an error about a real repository.
- Probable cause + diagnostic confidence: The fixture was built as a rendering harness for the canvas before the API existed, then kept as a demo affordance without a provenance boundary. High confidence.
- Smallest safe next step: Two cheap, independent mitigations. (a) Rename the fixture's content so it cannot be mistaken for real data — `Example repository`, `example/module.py`, and relationship types drawn only from the real vocabulary (`call`, `import`, `contains`, `defines`). (b) Promote the disclosure from a muted span to a persistent, non-muted banner above the canvas whenever `source === 'fixture'`. Strongly consider whether the fixture needs to ship at all now that a real repository graph endpoint exists — deleting it removes the whole risk class.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: component test asserting a fixture-mode banner is rendered and that no fixture relationship type falls outside the real vocabulary; browser E2E asserting the banner is visible without hovering or scrolling. Acceptance: a screenshot of any graph state makes its provenance unambiguous, per §5.D ("Fixture/Demo kann nie als echte Workspace-Daten fehlinterpretiert werden").
- Fix status: report-only

- ID: REV-113
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: source-reviewed
- Applies to: both
- Impact: There is no client-side routing in the product. Every internal link triggers a full document load, so all client state is destroyed on every navigation and on every Back. Concretely: following "Open source →" from a search result discards the query and the entire result set; returning with Back re-mounts `SearchClient` with `q=''` and `results=[]`, showing the initial state. Clicking a citation in a chat answer destroys the whole conversation (REV-114). Leaving the graph discards the loaded graph, filters and selection. The evidence-first workflow the product exists for — search, open a source line, come back, open the next hit — cannot be completed without re-typing the query each time.
- Evidence:
  - Verified absence across the whole app: `grep -rn "next/link\|useRouter\|router\.\|<Link" apps/web/app apps/web/lib` → **no matches**.
  - Every navigation is therefore a raw anchor. Global nav: `layout.tsx:3` — `<a href="/">Dashboard</a><a href="/search">Search</a><a href="/graph">Code graph</a><a href="/chat">AI Chat</a>`. Search results: `search-client.tsx:62` — three `<a href=…>` (source, symbol, graph). Chat citations: `chat-client.tsx:24` — `<a className="citation" href={\`/files/${citation.file_id}#L${citation.start_line}\`}>`. Symbol page: `:19-21` — source, graph and neighbour links, all `<a href>`.
  - The state that is lost is entirely client-held and never persisted or reflected in the URL: `search-client.tsx:22-27` (`q`, `mode`, `rerank`, `results`), `chat-client.tsx:11-12` (`items` — the conversation), `graph-explorer.tsx:62-66` (`graph`, `source`, `selected`, `relationship`, `minimumConfidence`, `symbolId`).
  - Only one URL-addressable piece of state exists in the app: the graph's `?repository=`/`?symbol=` deep link (`graph-explorer.tsx:60-61`), and even that is read once and never written back (REV-130).
  - `lib/api.ts:8` sets `cache: 'no-store'` on every request, so the full reload also re-fetches everything; there is no cached-navigation mitigation.
- Probable cause + diagnostic confidence: `next/link` was simply never adopted; the pages were written as standalone documents. High confidence — the absence is absolute and mechanically verified.
- Smallest safe next step: Replace `<a href>` with `next/link` in `layout.tsx` and `search-client.tsx` first — those two files cover the highest-traffic paths and the change is mechanical. That alone preserves search results across a source-view round trip, because Next keeps the client component mounted in the router cache. Pair it with REV-130 (put `q` in the URL) so state survives a hard refresh too.
- Affected data/migrations/providers/cost: None directly, but note the cost coupling for chat: each `/explanations` answer is a provider call (`main.py:307`), and losing the conversation on navigation means users re-ask questions they have already paid for.
- Recommended tests + acceptance criteria: browser E2E — search, open a result, press Back, assert the query and results are still present; ask a chat question, click a citation, press Back, assert the answer is still present. Acceptance: no user-visible work is lost by following a link and returning.
- Fix status: report-only

- ID: REV-114
- Category: DESIGN_GAP
- Severity: high
- Evidence level: source-reviewed (route absence corroborated live)
- Applies to: both (`chat-client.tsx` is divergent between branches, but neither version calls the conversation routes)
- Impact: The "AI Chat" page has no history. Answers exist only in React state, are lost on any navigation or refresh (REV-113), and are never persisted server-side even though the schema and routes for conversations exist. Each question is also independent — no prior turn is sent — so it is a one-shot Q&A form labelled as a chat. This directly contradicts the documented intent that the UI provides "Verlauf" (`docs/USER_AND_AGENT_EXPERIENCE.md:73`).
- Evidence:
  - The client uses the stateless endpoint: `chat-client.tsx:17` — `api<Answer>('/explanations', { method: 'POST', body: JSON.stringify({ question: q, repository_id: repositoryId }) })`. The request carries no conversation ID and no prior turns.
  - The conversational endpoints are unused: `POST /api/chat` (`main.py:328`), `GET /api/conversations` (`main.py:342`), `GET /api/conversations/{conversation_id}` (`main.py:344`). `grep -rn "conversation\|'/chat'" apps/web` → no match. Both routes are also present on the live `main` API (confirmed in the live path list), so this is not a branch artifact.
  - The tables exist and are empty: `conversations` and `messages` are two of the twelve live tables (per `01-runtime-and-provenance.md`), and nothing in the web app can write to them.
  - History is purely local and append-only in memory: `chat-client.tsx:12` — `const [items, setItems] = useState<Answer[]>([])`; `:17` — `setItems((current) => [...current, result])`. No `localStorage`, no URL state, no fetch on mount for prior turns (the only `useEffect`, `:13`, loads repositories).
  - The user's own questions are not even retained in the transcript: `:24` renders only `item.answer` in a `.message.assistant` div. The `.message.user` style exists in the stylesheet (`globals.css:8`) and is never used, so the rendered transcript is a list of answers with no visible questions.
- Probable cause + diagnostic confidence: `/explanations` was the grounded single-shot endpoint and the chat UI was built against it before `/chat` existed; the surfaces were never reconciled. High confidence.
- Smallest safe next step: Do not build persistence yet — first decide whether this page is "grounded Q&A" or "chat", because the label and the endpoint disagree. The zero-cost interim fix is to render the user's question alongside each answer using the existing `.message.user` style, so the transcript is at least readable. Persistence via `/api/chat` + `/api/conversations` is a separate slice and must be costed, since every turn is a provider call.
- Affected data/migrations/providers/cost: `conversations`/`messages` already exist; no migration needed. Provider cost: each turn is one `/explanations` call. Multi-turn context would increase tokens per turn and needs an explicit budget (§3.10).
- Recommended tests + acceptance criteria: API test that a chat turn persists a conversation and its messages; browser E2E asserting a reload restores the transcript. Acceptance: either the page is renamed to reflect single-shot behaviour, or history survives a refresh.
- Fix status: report-only

- ID: REV-115
- Category: DESIGN_GAP
- Severity: high
- Evidence level: source-reviewed
- Applies to: both (`graph-canvas.tsx` is divergent; the accessibility omissions are present in the integration version reviewed here)
- Impact: The graph — the product's flagship surface — is completely unavailable to keyboard and screen-reader users, and has no reduced-motion path. There is no text alternative to the canvas, no way to reach a node without a pointing device, and the only textual detail panel requires a mouse click to populate. A keyboard user can operate every control on the page and then reach nothing.
- Evidence, element by element:
  - **Canvas has no accessible identity.** `graph-canvas.tsx:31-32` renders `<div className="graph-canvas" ref={containerRef}><ForceGraph2D … /></div>`. No `role`, no `aria-label`, no `aria-describedby`, no `<figcaption>`, no fallback children. `react-force-graph-2d` renders a bare `<canvas>`; nothing in this file supplies a name or description for it.
  - **No keyboard path to a node.** The only interaction handlers are pointer-based: `graph-canvas.tsx:76` `onNodeHover`, `:77` `onNodeClick`. There is no `tabIndex`, no `onKeyDown`, and no focusable representation of any node. `nodePointerAreaPaint` (`:61-65`) is a hit-testing routine for the mouse only.
  - **The text alternative is gated behind a mouse click.** `graph-explorer.tsx:114` — the Node details `<aside>` shows `Click a node to inspect its identifier and metadata.` until `selected` is set, and `selected` can only be set by `onNodeClick`. So the one accessible representation of graph content is unreachable by the users who need it.
  - **The legend conveys the only key to canvas colour, which is unavailable anyway.** `graph-explorer.tsx:110-111` renders `<i className="legend-dot" style={{background: …}} />` plus text; the text labels are present (good), but they describe colours a non-visual user cannot perceive, and there is no equivalent structural listing of what the graph contains.
  - **No reduced-motion handling anywhere.** The force simulation animates for `cooldownTicks={180}` (`graph-canvas.tsx:74`) with `d3AlphaDecay={0.035}` (`:72`), then animates a zoom on settle — `onEngineStop={() => graphRef.current?.zoomToFit(350, 70)}` (`:75`), a 350 ms transition. `grep -c "prefers-reduced-motion" apps/web/app/globals.css` → `0`; the string does not appear anywhere in `apps/web`.
  - **The summary is the only machine-readable content**, and it is a single muted sentence: `graph-explorer.tsx:110`.
- Probable cause + diagnostic confidence: Canvas-based visualisation with no parallel accessible representation — a well-known omission class, not a subtle bug. High confidence for every listed omission (each is a verifiable absence in a 80-line file). Not verified with a screen reader; Chromium was unavailable, so no assistive-technology observation was made.
- Smallest safe next step: Add the accessible parallel that the data already supports, without touching the canvas library: (a) give the canvas container `role="img"` and an `aria-label` built from the existing summary ("Repository graph, 100 nodes, 5296 relationships, truncated"); (b) render a keyboard-reachable node list — a `<ul>` of the same `filteredGraph.nodes`, each an item that sets `selected` on activation, which makes the existing detail panel reachable and gives a text alternative for free; (c) wrap the animation in a `prefers-reduced-motion` check and set `cooldownTicks={0}` when it matches. The mandate's own rule applies here — accessibility basics are not a candidate for simplification.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: automated axe scan of `/graph` with zero critical violations; browser E2E asserting every node is reachable and selectable by keyboard alone; a manual screen-reader pass recorded in the report. Acceptance: the graph's content is fully obtainable without a pointing device and without sight.
- Fix status: report-only

- ID: REV-116
- Category: DESIGN_GAP
- Severity: high
- Evidence level: source-reviewed
- Applies to: both (`dashboard-client.tsx` is byte-identical across branches)
- Impact: The only modal in the product — the one guarding a destructive, irreversible action — implements none of the required dialog behaviours. Keyboard focus stays on the page behind the overlay, Escape does nothing, Tab walks into content the user cannot see, and dismissing the dialog leaves focus nowhere useful. A screen-reader user is told a dialog opened (`aria-modal="true"`) but is not moved into it, and can continue to operate the Sync/Reindex/Delete buttons of other repositories behind a visually blocking overlay.
- Evidence — the whole dialog is `dashboard-client.tsx:92-96`:
  ```tsx
  {deleting && <div className="dialog-backdrop" role="presentation"><section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-title">
    <h3 id="delete-title">Delete {deleting.name}?</h3>
    …
  ```
  - **No focus move in.** There is no `ref`, no `useEffect` that calls `focus()`, and no `autoFocus` on either button. Focus remains on the "Delete" card button that opened it (`:86`), which is behind the backdrop and still enabled (`disabled={busy !== null}` with `busy === null`).
  - **No Escape handler.** No `onKeyDown` on the backdrop or the section, no document-level key listener, no `useEffect` registering one. `grep -n "Escape\|keydown\|onKeyDown" apps/web/app/dashboard-client.tsx` → no match.
  - **No focus trap and no background inerting.** Nothing sets `inert` or `aria-hidden` on the rest of the document, so Tab order continues through the dashboard form and every repository card behind the overlay.
  - **No focus restore.** `setDeleting(null)` is called from Cancel (`:95`) and from the success path (`:54`) with no stored trigger element to return focus to.
  - **No click-outside dismissal.** The backdrop has `role="presentation"` and no `onClick`.
  - **Failure keeps it open with an invisible error** — see REV-104; the two defects compound into a dialog that appears frozen.
  - The stylesheet confirms the overlay genuinely blocks the page: `globals.css:10` — `.dialog-backdrop { position: fixed; inset: 0; z-index: 10; … background: rgb(0 0 0 / .65); }`.
  - Positives worth preserving: `role="dialog"`, `aria-modal="true"` and `aria-labelledby="delete-title"` are all correct, and the accessible name is specific ("Delete pydanticAI?").
- Probable cause + diagnostic confidence: A hand-rolled overlay instead of the platform `<dialog>` element. High confidence — every behaviour is a verifiable absence.
- Smallest safe next step: Replace the hand-rolled overlay with the native `<dialog>` element and `showModal()`. That single change supplies Escape-to-close, the top-layer focus trap, background inerting and focus restore from the platform, and removes the `.dialog-backdrop` CSS along with it — a net deletion rather than added code.
- Affected data/migrations/providers/cost: None. Note the action being guarded is `DELETE /api/repositories/{id}`, which cascades to files, chunks, symbols, edges, workspace membership and dependency declarations (`main.py:163`), so the guard's correctness matters.
- Recommended tests + acceptance criteria: browser E2E — open the dialog, assert focus is inside it, assert Tab cannot escape, press Escape and assert it closes with focus back on the triggering button; axe scan with zero violations. Acceptance: the dialog satisfies keyboard dismissal, focus containment and focus restoration.
- Fix status: report-only

- ID: REV-117
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: source-reviewed
- Applies to: integration (`search-client.tsx` is divergent; the same absence should be re-checked on `main`'s smaller version)
- Impact: Search has no no-results state and no result-count disclosure. A query returning zero hits renders a page visually identical to the never-searched state, so the user cannot tell "no matches" from "nothing happened" from "the request silently failed". Separately, the server caps results at 30 and the UI never says so, so a user seeing 30 results has no way to know whether that is all of them or the first page of thousands — and there is no pagination.
- Evidence:
  - No empty branch exists. `search-client.tsx:54` goes straight from the filter hint to the list: `{results.map((result, index) => {…})}`. There is no `results.length === 0` conditional anywhere in the file, and no "searched yet" flag distinct from `loading`.
  - Consequence traced through the state: after a zero-hit query, `results` is `[]` (set at `:35` — `setResults(response.results ?? [])`), `loading` is `false`, `error` is `''`. Every conditional render in the component is therefore false, so the page shows exactly the heading, the form and the filter hint — byte-identical to first load.
  - No count or limit disclosure. The server default is `limit:int=30` (`main.py:297`), clamped to `min(max(limit,1),100)` (`:299`). The client never sends `limit` (`search-client.tsx:34` sends only `q`, `mode`, `rerank`) and never renders `results.length` or any total. `/api/search` does not return a total either, so the honest disclosure would currently have to be "showing up to 30 matches".
  - The API does return the query echo and mode (`main.py:300` — `{'query':q,'mode':mode,'results':results,'semantic':semantic}`) which could anchor a "no matches for X" message; the client discards all three non-`results` fields.
  - The same conflation exists in the graph, with an added inaccuracy — see REV-119.
- Probable cause + diagnostic confidence: The list render was written as a bare `.map` with no empty branch. High confidence.
- Smallest safe next step: One conditional. Track whether a search has completed (the component already has everything needed: a `submitted` query string set in `go`), and render "No matches for `<q>`" when `results.length === 0`. Add "showing up to 30 matches" beside the result list.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: component test — mock a zero-result response, assert a no-matches message is rendered and that it names the query; assert the initial render shows neither the message nor results. Acceptance: Empty, No-results and Failed are three visually distinct states on the search page.
- Fix status: report-only

- ID: REV-118
- Category: BUG_SUSPECTED
- Severity: high
- Evidence level: source-reviewed
- Applies to: both
- Impact: No request is ever cancelled or sequenced, so overlapping requests can resolve out of order and render results belonging to a superseded query or scope. In search, results also stay on screen unchanged during a new request, so stale results are displayed as if current. This is the §3.7 "stale async response" case, and the mandate's §5.G negative-test list names it explicitly.
- Evidence:
  - No cancellation primitive exists anywhere in the app: `grep -rn "AbortController\|signal" apps/web` → no match. `lib/api.ts:4-13` accepts an `init` but no caller passes a `signal`.
  - **Search.** `search-client.tsx:29-42` — `go` sets `loading`, awaits, then unconditionally `setResults(response.results ?? [])` (`:35`). There is no request ID, no generation counter, no abort of the in-flight request. Two submissions in quick succession both call `setResults`; the last to *resolve* wins, which need not be the last submitted. During the overlap the previous results remain rendered with no dimming or replacement — the only loading affordance is the button label (`:50` — `{loading ? 'Searching…' : 'Search'}`).
  - **Graph.** `graph-explorer.tsx:76-97` — `requestGraph` and `requestOverview` share `graph`, `source`, `loading` and `error` state and neither guards against the other. The two are triggered by adjacent buttons (`:106` — "Repository map" and "Focus symbol"), so an impatient user can easily have both in flight; whichever resolves last sets `graph` and `source`. Combined with REV-103 (no reset on scope change) and REV-127 (no commit or repository shown on the canvas), a wrong-scope render is undetectable by the user.
  - Contrast — the pattern is already used correctly elsewhere in the codebase: the symbol page guards its effect with an `active` flag (`repositories/[repositoryId]/symbols/[symbolId]/page.tsx:15` — `let active = true; … if (!active) return; … return () => { active = false; };`). Nothing equivalent exists in search or graph.
  - Marked `BUG_SUSPECTED` rather than confirmed: the race is unambiguous in the source, but it was not reproduced. Reproduction requires a browser, which was unavailable, and the live search path returns in well under the window that would make it easy to trigger by hand.
- Probable cause + diagnostic confidence: Fire-and-forget `async` handlers writing directly to shared state. High confidence in the hazard; medium confidence in real-world frequency, which depends on latency and user behaviour and was not measured.
- Smallest safe next step: A generation counter is smaller than an `AbortController` and fixes the visible symptom: keep a `useRef` counter, increment on each submit, capture it in the closure, and drop the `setResults`/`setGraph` if the captured value is stale. Four lines per surface, no new dependency.
- Affected data/migrations/providers/cost: None for search/graph. Note the same pattern in chat is currently single-flighted only by the disabled button, and each chat turn is a billable provider call, so an abort path there has a cost dimension.
- Recommended tests + acceptance criteria: component test issuing two searches with the first response delayed, asserting the second query's results are the ones rendered; equivalent test for overview-vs-subgraph. Acceptance: a superseded response can never overwrite a newer one.
- Fix status: report-only

- ID: REV-119
- Category: DESIGN_GAP
- Severity: high
- Evidence level: source-reviewed
- Applies to: both
- Impact: Two related failures of scope communication. (a) Search is globally unscoped from the UI even though the API supports repository scoping, so there is no way to search "within this repository", let alone within a workspace — the page is even titled "Global code search", making the gap a stated feature. (b) The graph's empty state tells the user their filters are wrong even when nothing has ever been loaded, actively misdirecting a first-time user.
- Evidence:
  - **(a) Unscoped search.** `/api/search` accepts and validates `repository_id` (`main.py:297-298` — `repository_id:str|None=None`, with `if repository_id and not db.get(Repository,repository_id): raise HTTPException(404,…)`), and threads it into the candidate filter *before* limits (`apps/api/app/search.py:61` — `def allowed(repo): return repo and (not repository_id or repo.id == repository_id) and …`). The client never sends it: `search-client.tsx:34` — `\`/search?q=${…}&mode=${…}&rerank=${rerank}\``. There is no repository selector on the search page at all.
  - The only scoping offered is a free-text convention the user must know and type: `search-client.tsx:52` — `<p className="muted">Filters: <code>repo:</code> <code>lang:</code> <code>path:</code></p>`, and `repo:` is matched by substring against the repository *name* (`search.py:61` — `q.repo.lower() in repo.name.lower()`), not by identity. So "scoping" is a fuzzy name match typed into a query box, which cannot express workspace membership and will silently match multiple repositories whose names share a substring.
  - Page title asserts the behaviour: `search-client.tsx:45` — `<h2>Global code search</h2>`. Contrast `docs/USER_AND_AGENT_EXPERIENCE.md:99`, which specifies the delivery order as "UI vertikal schließen: **Repository wählen → suchen** → Symbol/Graph öffnen": the intended flow is scoped search, and the shipped flow inverts it.
  - **(b) Misleading graph empty state.** `graph-explorer.tsx:112` uses one branch for two very different conditions: `filteredGraph.nodes.length > 0 ? <GraphCanvas …/> : <div className="graph-state"><strong>No graph data to display.</strong><p className="muted">The selected filters returned no connected nodes. Adjust filters or load the fixture demo.</p></div>`. On first visit `source === 'empty'` and no request has been made, yet the user is told their filters returned nothing and advised to adjust them — there are no filters to adjust. The component already has the information to distinguish the cases (`source` is `'empty' | 'api' | 'fixture'`, `graph.links.length` is known) and does not use it.
  - The same strip does label the state correctly a few lines earlier — `graph-explorer.tsx:110` renders `'No graph loaded'` when `source === 'empty'` — so the page simultaneously says "No graph loaded" and "The selected filters returned no connected nodes".
- Probable cause + diagnostic confidence: (a) search was built as the first page, before repositories were selectable anywhere; (b) one empty-state string reused for two causes. High confidence for both.
- Smallest safe next step: (b) is a two-line fix: branch the empty-state copy on `source === 'empty'`. (a) is a small slice: add the repository `<select>` that `chat-client.tsx:22` and `graph-explorer.tsx:103` already implement, and pass `repository_id` through — the server-side filtering is already correct and applies before limits, so no API change is required. Do not add workspace scoping to search until REV-100/REV-121 settle what a workspace scope means.
- Affected data/migrations/providers/cost: None. Scoping *reduces* semantic-search work, since `allowed()` gates candidates.
- Recommended tests + acceptance criteria: API test asserting `repository_id` excludes other repositories' hits before the limit is applied; component test asserting the graph's initial empty copy does not mention filters. Acceptance: a user can restrict search to one repository without typing a query operator, and no empty state misattributes its own cause.
- Fix status: report-only

- ID: REV-120
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: source-reviewed (capability payload confirmed live)
- Applies to: integration (`search-client.tsx` divergent)
- Impact: The API reports provider capability and whether reranking was actually applied; the client discards all of it. Consequences: a user ticks "Reranker verwenden" and cannot tell whether the reranker ran, was unconfigured, or failed; selecting `semantic` mode with no embedding provider yields a blank page indistinguishable from "no matches" (REV-117); and a degraded embedding provider is invisible. `docs/HOSTED_PRODUCT_AND_UI_VISION.md:28` explicitly requires the opposite — "Visible provider/capability state: disabled, configured, active, degraded" — so this is a shipped contradiction of a stated requirement, and it undermines §3.10's "kostenbeobachtbar" intent.
- Evidence:
  - The API returns it. `main.py:300` — `return {'query':q,'mode':mode,'results':results,'semantic':semantic}`, where `semantic` is the `capability` object built in `search.py`: `capability['indexed_candidates']` (`search.py:93`), and on failure `capability['state'] = 'degraded'`, `capability['enabled'] = False`, `capability['reason'] = 'embedding_request_failed'` (`search.py:95-97`). Reranking status is tracked explicitly: `capability['reranking']['requested'] = rerank` and `capability['reranking']['applied'] = False` (`search.py:105-106`), set to applied only inside the success path (`search.py:107+`).
  - Live confirmation that the field is populated on the wire: `curl -s "http://localhost:8000/api/search?q=Agent&mode=hybrid&rerank=false"` returns top-level keys `['query', 'mode', 'semantic']` alongside `results`.
  - The client reads one field and drops the rest: `search-client.tsx:34-35` — `const response = await api<{ results: Result[] }>(…); setResults(response.results ?? []);`. The response type declares only `results`, so `semantic` is not even in the TypeScript surface. `grep -rn "capability\|semantic'" apps/web` finds only the mode `<option>semantic</option>` at `:48`.
  - The reranker checkbox therefore has no feedback loop: `search-client.tsx:49` — `<input type="checkbox" checked={rerank} disabled={mode !== 'hybrid'} …/> Reranker verwenden`. Server-side the reranker is skipped silently when unconfigured — `search.py:104` — `reranker = rerank_provider() if rerank and mode == 'hybrid' else None`, then `if rerank and reranker is not None and results:` — so an unconfigured reranker produces the same UI as a successful rerank.
  - Semantic mode fails silently to empty: `search.py:83` requires `provider is not None`; with no provider `semantic` stays `[]`, and `search.py:98` — `if mode == 'semantic': results = semantic[:limit]` — returns zero results with HTTP 200. The client renders nothing (REV-117).
- Probable cause + diagnostic confidence: The capability object was added to the API contract and the client type was never extended. High confidence — the field is demonstrably on the wire and absent from the client type.
- Smallest safe next step: Widen the client response type to include `semantic` and render a single line beneath the form: the capability `state`, and `reranking.applied` when `requested`. No API change. This is also the cheapest fix for the blank-semantic-page symptom, because `reason` explains it.
- Affected data/migrations/providers/cost: No new provider calls. Directly improves cost observability, which §3.10 requires: today a user cannot tell whether a ticked reranker box is spending anything.
- Recommended tests + acceptance criteria: API test asserting `semantic.state == 'degraded'` and a `reason` when the embedding provider raises; component test asserting the capability line renders `disabled`/`degraded`/`active` and that a requested-but-not-applied rerank is stated. Acceptance: the UI never implies a provider ran when it did not.
- Fix status: report-only

- ID: REV-121
- Category: DESIGN_GAP
- Severity: high
- Evidence level: source-reviewed
- Applies to: both
- Impact: Repository creation cannot assign a workspace, so every repository in the system is permanently unassigned unless a second, separate API call is made by hand. There is no `Unassigned` concept in the UI, no indication that a repository belongs to no workspace, and no way to attach one. Combined with REV-100 this makes workspace-first structurally unreachable rather than merely unbuilt: even if a workspace existed, nothing in the product could put a repository into it. §2 requirement 2 is unmet, and §5.B's atomicity concern has a direct UX consequence.
- Evidence:
  - The creation contract has no workspace field: `main.py:21-22` — `class RepositoryIn(BaseModel): name:str=…; clone_url:str=…; requested_revision:str|None=…`. The handler creates the row and enqueues indexing with no membership write: `main.py:153` — `r=Repository(name=body.name,clone_url=body.clone_url,requested_revision=body.requested_revision,indexing_status='pending');db.add(r);db.commit();db.refresh(r); return {'repository':repo_out(r),'job_id':enqueue(r.id,True)}`.
  - Membership is only settable through a separate route — `PUT`/`POST /api/workspaces/{workspace_id}/repositories/{repo_id}` (`main.py:125-140`) — which the web app never calls, so the two-step sequence is not merely non-atomic, it is never completed.
  - The client sends exactly the two fields: `dashboard-client.tsx:30` — `api('/repositories', {method: 'POST', body: JSON.stringify({name: name.trim(), clone_url: cloneUrl.trim()})})`.
  - Nothing surfaces membership state. `repo_out` (`main.py:42`) returns no workspace identifier, and the web `Repository` type (`lib/repositories.ts:1-10`) has no workspace field. So even a repository that *was* attached out-of-band would look identical to an unassigned one on the dashboard.
  - Live corroboration of the end state: 1 repository, 0 workspaces, 0 memberships — reachable only because creation ignores workspaces entirely.
  - The success copy reinforces a workspace-free mental model: `dashboard-client.tsx:31` — `'Repository added. Its first index has been queued.'`
- Probable cause + diagnostic confidence: The workspace layer was added alongside, not above, the pre-existing repository model, and the creation path was never migrated. High confidence.
- Smallest safe next step: This needs the product decision named in §11.2 before code — whether an unassigned repository is legal, or whether every repository must have a workspace. Once decided, the minimal implementation is a `workspace_id` on `RepositoryIn` handled in the same transaction as the insert, plus an explicit `Unassigned` grouping on the dashboard for the existing row. Do not backfill the live repository into a synthetic workspace without a documented policy.
- Affected data/migrations/providers/cost: No migration needed to *read* membership; a mandatory-workspace policy would require a backfill for the one existing unassigned repository and a nullability decision on `workspace_repositories`. Flagged for the data-model workstream.
- Recommended tests + acceptance criteria: API test that creating a repository with a workspace produces both rows or neither (atomicity); API test that a foreign `workspace_id` is rejected; browser E2E that a newly added repository appears under the selected workspace. Acceptance: no repository can be created into an undefined scope, or `Unassigned` is a first-class, visible state.
- Fix status: report-only

- ID: REV-122
- Category: TEST_GAP
- Severity: high
- Evidence level: source-reviewed
- Applies to: both
- Impact: The web app has no automated test coverage of any kind, so every finding in this report describes behaviour that no test would have caught and no test will prevent from regressing. Two pure, exported, logic-bearing functions are the cheapest possible test targets and have no tests, and they are precisely the ones carrying correctness risk (`mapApiGraph` is where `truncated` is lost — REV-101 — and where confidence is normalised — REV-136).
- Evidence:
  - No test runner is installed. `apps/web/package.json` (single line) declares scripts `dev`, `build`, `start`, `lint` and devDependencies `@types/node`, `@types/react`, `typescript` only. No `vitest`, `jest`, `@testing-library/*`, `playwright` or `@playwright/test`.
  - No test files exist. `find . -path ./data -prune -o -name '*.test.*' -print -o -name '*.spec.*' -print -o -name 'playwright*' -print` → no results anywhere in the repository.
  - The two obvious unit targets are exported and pure:
    - `export function mapApiGraph(payload: unknown): GraphData` (`graph-explorer.tsx:32`) — exported from a `'use client'` component specifically so it can be tested, and never is. It handles four alternative response shapes (`root.nodes`/`body.nodes`, `root.edges`/`root.links`/`body.edges`/`body.links`, `:35-36`), three ID aliases (`:39`), five label fallbacks (`:41`), three endpoint aliases (`:45`), dangling-edge rejection (`:46`), confidence coercion from string and percent forms (`:47-48`) and degree computation (`:51-52`). Every one of those branches is untested.
    - `export function isSafeCloneUrl(value: string): boolean` (`lib/repositories.ts:13`) — three regexes gating what gets sent to a Git clone. Untested, despite being the client half of a trust boundary (the server re-validates at `main.py:151`, which is the control that actually matters — but the client rule silently diverging from the server rule is a real UX failure mode).
    - `progressLabel` (`lib/repositories.ts:26`) and `apiErrorMessage` (`:33`) — both pure, both untested, both implicated in findings (REV-105, REV-104).
  - `next lint` is the only automated check, and lint cannot detect any of: a dropped `truncated` flag, a missing empty state, an unreset graph, or a dialog without focus management.
- Probable cause + diagnostic confidence: No frontend test tooling was ever set up. High confidence — verified by absence of both runner and files.
- Smallest safe next step: Do not stand up a browser E2E harness first — start with the cheapest thing that would have caught real bugs. Add one dev dependency (a test runner) and one file of plain assertions over `mapApiGraph`, `progressLabel`, `isSafeCloneUrl` and `apiErrorMessage`. That covers four findings' regression surface with no rendering infrastructure. Component and browser E2E come after, and per §8.7 the chosen plugin's version, permissions and limits should be recorded when it lands.
- Affected data/migrations/providers/cost: None. Tests must run without provider access (§3.10) — all four targets are pure and satisfy that trivially.
- Recommended tests + acceptance criteria: `mapApiGraph` — asserts `truncated` and `max_nodes` survive; asserts a dangling edge is dropped; asserts `confidence: 100` normalises to `1` and `20` to `0.2`; asserts both `nodes/edges` and `data.nodes/data.links` shapes parse. `progressLabel` — asserts a `ready` repository never shows an in-progress phase. Acceptance: every finding in this report that has a pure-function cause has a failing test written before the fix.
- Fix status: report-only

### Medium

- ID: REV-123
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both (`dashboard-client.tsx` byte-identical)
- Impact: The Indexing state never resolves. After clicking Sync or Reindex the card shows `indexing` and then stays that way forever, because nothing polls. The user has no way to learn that the job finished, failed, or is still running short of reloading the page and guessing. For the measured 11 m 37 s full re-index on this repository, that is a long silent window, and it makes the failure modes documented in `01-runtime-and-provenance.md` (a job killed by a timeout, an orphaned job) invisible in the product.
- Evidence:
  - Status is refreshed only as a side effect of user actions: `dashboard-client.tsx:19-21` — `async function refresh() { setRepos(await api<Repository[]>('/repositories')); }` — called once at the end of `addRepository` (`:32`) and once at the end of `runAction` (`:42`). There is no `setInterval`, no `setTimeout`, no polling `useEffect`; the file's only React hooks are `useState` (`:11-17`).
  - Because `refresh()` runs immediately after the enqueue returns, the fetched status is whatever it was milliseconds after the job was queued — typically `pending` or `indexing` — and that snapshot is then frozen.
  - Two purpose-built endpoints are unused: `GET /api/repositories/{repo_id}/status` (`main.py:174-178`), which returns exactly `{status, progress, error, indexed_commit_sha}`, and `GET /api/jobs/{job_id}` (`main.py:337`). `grep -rn "/status\|/jobs" apps/web` → no match. The enqueue responses even hand the client a job ID it discards: `main.py:167` — `return {'job_id':enqueue(repo_id,False)}`.
  - Compounding: because `indexing_progress` is never cleared (REV-105), the frozen snapshot shown after a completed index reads `finalizing · 2284 files` — an in-progress phase on a finished repository, which is the worst possible frozen value.
  - `docs/HOSTED_PRODUCT_AND_UI_VISION.md:20` specifies the intended surface: "Show job timeline: queued, clone, parse, embed, code-card generation, complete/failed." None of it exists.
- Probable cause + diagnostic confidence: Polling was never added; the action-triggered refresh was assumed sufficient. High confidence.
- Smallest safe next step: One `useEffect` with an interval that calls the existing `refresh()` only while some repository is in a non-terminal status (`pending`/`indexing`), and stops otherwise. That reuses the function already present, adds no dependency, and self-limits so it does not poll a fully idle dashboard.
- Affected data/migrations/providers/cost: None — `GET /api/repositories` is a single unfiltered Postgres select. Note it is also unbounded (no limit or pagination, `main.py:148`), so a polling interval should be revisited if the repository count grows.
- Recommended tests + acceptance criteria: component test with a fake timer asserting the status transitions from `indexing` to `ready` without user interaction, and that polling stops once no repository is non-terminal. Acceptance: a user who triggers an index learns its outcome without reloading.
- Fix status: report-only

- ID: REV-124
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both (both branches' chat and graph clients filter identically)
- Impact: Two problems from one line of logic, repeated in two files. (a) Both surfaces silently drop every repository that is not `ready`, with no note — so a repository that is currently indexing simply is not in the dropdown, and the user cannot tell whether it is missing because it is indexing, failed, or was never added. (b) Both then auto-select the first remaining repository, so a user can ask a grounded question, or read a graph, scoped to a repository they never chose. With zero ready repositories, both pages become silent dead ends: the chat's submit button is permanently disabled with no explanation.
- Evidence:
  - Chat: `chat-client.tsx:13` — `api<Repository[]>('/repositories').then((items) => { const ready = items.filter((item) => item.indexing_status === 'ready'); setRepositories(ready); if (ready[0]) setRepositoryId(ready[0].id); })`. Graph: `graph-explorer.tsx:88` — the same filter and the same `if (!repositoryId && ready[0]) setRepositoryId(ready[0].id)`.
  - The selection is arbitrary from the user's perspective: `GET /api/repositories` orders by `Repository.created_at.desc()` (`main.py:148`), so `ready[0]` is the most recently created ready repository. Nothing in the UI says which one was chosen or why.
  - Dead-end chat with nothing ready: `repositories` is `[]`, so the `<select>` (`chat-client.tsx:22`) contains only the `Choose an indexed repository` placeholder, `repositoryId` stays `''`, and the button is `disabled={loading || !repositoryId}` — permanently disabled with no message. `ask` also returns early on `!repositoryId` (`:15`). There is no empty state anywhere in the file.
  - The graph degrades slightly better but still misdirects: `requestOverview` reports `'Choose an indexed repository first.'` (`graph-explorer.tsx:92`) — which is not actionable when the dropdown is empty because none are ready.
  - Silent filtering hides real states the user needs: a `failed` repository is absent rather than shown as unavailable-and-why, so the failure surfaced correctly on the dashboard (`.status-failed` + `error_message`) disappears entirely on the two pages where the user is trying to use it.
  - The `indexing_status` values in play are `pending`, `indexing`, `ready`, `failed` (per `main.py:153` and the dashboard's status classes at `globals.css:10`).
- Probable cause + diagnostic confidence: `filter(ready)` is a correct guard implemented without the corresponding user-facing explanation. High confidence.
- Smallest safe next step: Keep the filter, add the explanation. Show non-ready repositories as `<option disabled>` with their status appended (`my-service · indexing`), and render one line when nothing is ready ("No repository has finished indexing yet"). Remove the auto-select, or label it explicitly — with one repository auto-select is a convenience, with five it is a scope hazard.
- Affected data/migrations/providers/cost: Provider cost relevance: chat auto-select means a billable `/explanations` call can be issued against an unintended repository.
- Recommended tests + acceptance criteria: component tests for zero-ready (message shown, submit disabled with a reason), one-ready, and mixed statuses (non-ready shown as disabled with status). Acceptance: the repository a question or graph is scoped to is always a deliberate, visible choice.
- Fix status: report-only

- ID: REV-125
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: source-reviewed (field presence confirmed live)
- Applies to: both
- Impact: Stale-index detection is impossible in the UI even though the server already computes it. The dashboard cannot tell the user "the remote has moved on since you indexed", so a user reading search results, graph edges or generated documentation has no signal that the underlying index is behind the repository's current head. §3.6 makes commit provenance a first-class requirement and the Stale state is the one that tells a user their evidence is out of date.
- Evidence:
  - The API returns both commits. `main.py:42` — `repo_out` includes `'indexed_commit_sha':r.indexed_commit_sha` **and** `'latest_detected_commit_sha':r.latest_detected_commit_sha`. Live confirmation of both keys on the wire, and of their equality at review time:
    ```
    curl -s http://localhost:8000/api/repositories | python3 -c "…"
    → indexed: 640d5171fe57  latest: 640d5171fe57  status: ready
    ```
    (They match because a sync ran; nothing in the UI would have shown it if they had not.)
  - The web type discards it: `apps/web/lib/repositories.ts:1-10` declares `id`, `name`, `clone_url`, `indexing_status`, `indexing_progress`, `indexed_commit_sha`, `error_message`, `last_indexed_at` — and omits `latest_detected_commit_sha`, `default_branch`, `indexed_branch`, `last_sync_at` and `requested_revision`, all of which the API returns.
  - Consequently the card renders one commit with no comparison: `dashboard-client.tsx:81` — `<div><dt>Current commit</dt><dd><code>{repo.indexed_commit_sha?.slice(0, 12) || 'Not indexed'}</code></dd></div>`.
  - Branch is also absent from the UI despite being available and specifically required by `docs/HOSTED_PRODUCT_AND_UI_VISION.md:12` ("Repository cards with latest indexed commit, **branch**, health and indexing status").
  - Downstream surfaces inherit the gap: search results and chat citations show `indexed_commit_sha` (good — `search-client.tsx:59`, `chat-client.tsx:24`) but nothing anywhere compares it to the latest detected commit, so a commit shown as provenance may be arbitrarily old with no indication.
- Probable cause + diagnostic confidence: The web type was written narrowly and never widened as the API grew. High confidence — a direct field-by-field comparison.
- Smallest safe next step: Add the two fields to the `Repository` type and render a `Stale` badge when `latest_detected_commit_sha` is set, non-empty and different from `indexed_commit_sha`, next to the existing status pill. The `.status` badge styles already exist (`globals.css:10`). No API change.
- Affected data/migrations/providers/cost: None. A visible Stale badge is what makes the existing Sync button meaningful, so it may reduce blind re-indexing (each full index measured at 11 m 37 s on this repository).
- Recommended tests + acceptance criteria: component test asserting a Stale badge appears when the two commits differ and not when they match or when `latest_detected_commit_sha` is null; unit test that `Not indexed` is still shown when `indexed_commit_sha` is null. Acceptance: a user can see at a glance whether the index is current.
- Fix status: report-only

- ID: REV-126
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both (`dashboard-client.tsx` byte-identical)
- Impact: §3.8 requires that "Mitgliedschaft entfernen ≠ Repository löschen; Workspace löschen ≠ Repository löschen" be understood identically by UI, API, database and tests. The UI expresses only one of the three operations, and its copy under-states what that operation destroys: deleting a repository also deletes its workspace membership and every dependency declaration referencing it, and the dialog does not say so. The other two operations have no copy at all because they have no UI, so the distinction §3.8 protects cannot be conveyed to a user.
- Evidence:
  - What the dialog promises: `dashboard-client.tsx:94` — "This removes the repository and all of its indexed files, chunks, and graph data. The remote Git repository will not be changed."
  - What the API actually does: `main.py:163` — `db.execute(delete(WorkspaceDependency).where((WorkspaceDependency.source_repository_id==repo_id)|(WorkspaceDependency.target_repository_id==repo_id))); db.execute(delete(WorkspaceRepository).where(WorkspaceRepository.repository_id==repo_id)); db.delete(r); db.commit()`. Workspace membership and *both directions* of every dependency declaration are deleted. Dependency declarations are hand-authored data (§2: "manuelle Deklarationen") and therefore not reconstructible by re-indexing — unlike the files, chunks and graph data the copy does mention.
  - The success notice repeats the narrow framing: `dashboard-client.tsx:53` — `${deleting.name} and its indexed data were removed.`
  - Membership removal has UI-independent, materially different semantics that no copy expresses: `DELETE /api/workspaces/{workspace_id}/repositories/{repo_id}` (`main.py:141-146`) deletes the membership and the workspace's dependencies touching that repository, and leaves the repository and its entire index intact. Workspace deletion (`main.py:90-94`) deletes dependencies and memberships and leaves every repository intact. Three operations, three outcomes, one of which is reachable and mislabelled.
  - Positives worth keeping: the dialog title is specific (`Delete {deleting.name}?`, `:93`), the remote-repository disclaimer is correct and valuable, and the card button ("Delete") versus the confirm button ("Delete repository", `:95`) escalate appropriately.
- Probable cause + diagnostic confidence: The copy was written before workspace cascades were added to the delete handler and never revisited. High confidence — the mismatch is between two quotable lines.
- Smallest safe next step: One sentence in the existing dialog naming the two additional casualties ("Any workspace membership and dependency declarations that reference it are also removed"). When workspace UI lands, the two other operations need their own distinct copy, and the three should be reviewed together rather than one at a time.
- Affected data/migrations/providers/cost: No migration. Data consequence is real and irreversible for hand-authored dependency declarations.
- Recommended tests + acceptance criteria: API tests asserting each of the three operations affects exactly the intended rows (repository delete removes membership+dependencies+index; membership removal preserves the repository and its index; workspace delete preserves all repositories). Acceptance: the UI copy for each destructive action enumerates every row class it destroys, and a test pins the copy to the handler's behaviour.
- Fix status: report-only

- ID: REV-127
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both
- Impact: The graph and the symbol page — the two surfaces whose entire purpose is structural evidence — display no indexed commit. §3.6 requires that "Treffer und Graph-Kontext … Repository, Datei/Pfad, Zeilenbereich und indexierten Commit" be retained, and §5.D forbids mixing commits without a visible commit vector. A user cannot tell which commit a graph or a symbol's callers/callees were derived from, and combined with REV-103 (stale graphs survive scope changes) there is no provenance anchor that would let them detect a wrong or outdated view.
- Evidence:
  - The graph responses carry no commit at all. `main.py:295` returns `repository_id`, `max_nodes`, `truncated`, `nodes`, `edges`; `main.py:261` returns `root_symbol_id`, `depth`, `max_nodes`, `truncated`, `nodes`, `edges`. Node payloads come from `symbol_out` (`main.py:53`), which has no commit field, and the synthesized structural nodes (`main.py:281-284`) carry none either. So the UI could not display a commit even if it tried.
  - The symbol page has the same gap: `detail` is a `symbol_out` payload, and the header renders only type, language and line range — `repositories/[repositoryId]/symbols/[symbolId]/page.tsx:21` — `<p className="muted">{detail.type} · {detail.language ?? 'unknown language'} · lines {detail.start_line}–{detail.end_line}</p>`.
  - Callers/callees likewise: `main.py:238`/`:239` return `{symbol_id, callers|callees}` built from `symbol_out` + `edge_out` (`main.py:54`), neither of which carries a commit.
  - The rest of the product does this correctly, which makes the gap an inconsistency rather than an oversight of principle: search results show it (`search-client.tsx:59` — `result.indexed_commit_sha.slice(0, 12)`), chat answers show it (`chat-client.tsx:24`), the file view shows it (`files/[id]/page.tsx:1` — `{f.language} · commit {f.indexed_commit_sha?.slice(0, 12)}`), and generated documentation shows it (symbol page `:21` — `Commit {documentation.scope.indexed_commit_sha?.slice(0, 12) ?? 'unknown'}`).
  - Note the underlying data exists: `files.indexed_commit_sha` and `code_chunks.indexed_commit_sha` are populated (that is what search and the file view read), and `repositories.indexed_commit_sha` is available on every graph request since the handler already loads the repository (`main.py:265` — `repo=db.get(Repository,repo_id)`).
- Probable cause + diagnostic confidence: The graph serialisers were built from the symbol model, which has no commit column, and the repository's commit was never attached at the response level. High confidence.
- Smallest safe next step: Add `indexed_commit_sha` (from the already-loaded `repo`) to both graph responses and to the symbol-detail response, and render it in the graph summary strip (`graph-explorer.tsx:110`) and the symbol page header. One field, three call sites, no schema change. This is also a precondition for the multi-repository case, where §3.6's "Commit-Vektor pro Repository" will require per-repository commits rather than one.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: API test asserting both graph responses and the symbol detail include the repository's indexed commit; component test asserting the graph summary renders it. Acceptance: no evidence surface displays structural claims without the commit they were derived from.
- Fix status: report-only

- ID: REV-128
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: integration for the search page (`search-client.tsx` divergent); both for chat (`chat-client.tsx` divergent but the textarea omission is present on both) — re-verify per branch before fixing
- Impact: Three form controls have no accessible name, so screen-reader users hear only a role ("edit text", "combo box") with no indication of purpose, and voice-control users cannot address them. Two of the three are the primary input of their page. Placeholders are not accessible names and disappear as soon as the user types, so they also fail sighted users with short-term memory or attention constraints.
- Evidence — exact elements:
  - **Search query input, no name at all.** `search-client.tsx:47` — `<input value={q} onChange={…} placeholder="auth repo:backend lang:python" />`. No wrapping `<label>`, no `aria-label`, no `aria-labelledby`, no `id`+`for`. This is the main input of the search page. The placeholder is additionally used to teach query syntax, which is a second reason it should not be the only naming mechanism.
  - **Search mode select, no name at all.** `search-client.tsx:48` — `<select value={mode} onChange={…}><option>hybrid</option><option>text</option><option>symbols</option><option>semantic</option></select>`. Unlabelled, and the option values are bare lowercase tokens with no explanation of what "hybrid" versus "text" means.
  - **Chat question textarea, no name.** `chat-client.tsx:22` — `<textarea rows={4} value={q} onChange={…} placeholder="Where is authentication implemented?"/>`. The repository `<select>` immediately before it *is* correctly wrapped (`<label>Repository<select …>`), so the omission is inconsistent within a single line of JSX.
  - The correct pattern is used throughout the rest of the app, which is why these three stand out: `dashboard-client.tsx:70-71` (`<label>Repository name<input …/></label>`, `<label>Clone URL<input …/></label>`), `graph-explorer.tsx:103-105` (Repository, Symbol, Depth all wrapped), `graph-explorer.tsx:111` (Relationship, Minimum confidence both wrapped). The stylesheet already supports it (`globals.css:9` — `.graph-controls label { display: grid; gap: 6px; … }`).
  - The rerank checkbox is named correctly (`search-client.tsx:49`, wrapped in a `<label>`), though its text is German — see REV-138.
- Probable cause + diagnostic confidence: The search page was the first surface built, with a compact single-row form and placeholders instead of labels; the pattern was corrected later elsewhere and not retrofitted. High confidence — an accessible name is either present in the markup or it is not.
- Smallest safe next step: Wrap the three controls in `<label>` exactly as the four other forms in this codebase already do. Visually hide the label text if the compact one-row layout must be preserved, but do not substitute `aria-label` where a real label works — a visible label also helps sighted users. Accessibility basics are explicitly out of scope for simplification.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: axe scan of `/search` and `/chat` with zero violations of the "form elements must have labels" rule; component test querying each control by its accessible name rather than by placeholder. Acceptance: every interactive control in the product has a programmatically determinable name.
- Fix status: report-only

- ID: REV-129
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both
- Impact: Keyboard users get no visible focus indication beyond the browser default, and the one interactive element that *is* styled for the mouse — the navigation links — has no focus equivalent, so a keyboard user traversing the sidebar sees a much weaker signal than a mouse user hovering it. There is also no skip link past the sidebar, so every keyboard visit to every page starts by tabbing through four navigation links, and no current-page indication, so a screen-reader user cannot tell which of the four they are on.
- Evidence:
  - No focus styling exists anywhere: `grep -c "prefers-reduced-motion\|focus-visible\|:focus" apps/web/app/globals.css` → `0`. The stylesheet is the app's only CSS (imported at `layout.tsx:1`), so this is exhaustive.
  - The asymmetry is explicit in one line: `globals.css:5` — `a { color: #b9c8ed; text-decoration: none; padding: 9px; border-radius: 7px; } a:hover { background: #1c2945; color: #fff; }`. A hover state is defined; no focus state is. Note `text-decoration: none` removes the one indicator that would otherwise survive.
  - Buttons are also unstyled for focus and the disabled state degrades contrast: `globals.css:8` — `button:disabled { cursor: wait; opacity: .7; }`. Every disabled button in the app is also given `cursor: wait`, including ones that are disabled for reasons other than waiting — e.g. the delete dialog's Cancel button (`dashboard-client.tsx:95`, `disabled={busy !== null}`) and the graph's "Focus symbol" button (`graph-explorer.tsx:106`, `disabled={loading || !symbolId.trim()}`), which is disabled simply because the field is empty. That misreports the reason for the disabled state.
  - No skip link: `layout.tsx:3` renders `<aside>` (with `<h1>`, a paragraph, `<nav>` with four links, and a `<small>`) before `<main>{children}</main>`, with nothing to bypass it.
  - Navigation lacks both a landmark name and a current-page indicator: `<nav>` has no `aria-label`, and none of the four `<a>` elements carries `aria-current="page"` — the app cannot set it anyway, since it has no router and each page is a separate document (REV-113).
  - Contrast ratios were checked and are adequate, so this finding is specifically about focus and orientation, not colour: `.muted` `#9babca` on the card `#131d34` ≈ 7:1; `aside small` `#789` on `#10182d` ≈ 5:1. Both pass AA for body text.
- Probable cause + diagnostic confidence: A hand-written stylesheet with hover states and no focus states — a common omission. High confidence for the absences (mechanically verified); the assessment that the browser default ring is insufficient against this dark palette is a judgement, not a measurement, and was not verified in a browser.
- Smallest safe next step: Two rules in the existing stylesheet — a single `:focus-visible` outline applied to `a, button, input, select, textarea`, and a skip link before the `<aside>`. Native CSS, no dependency, no component changes. `aria-current` follows naturally once client-side routing lands (REV-113).
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: browser E2E tabbing through each page asserting the focused element always has a visible outline; axe scan for landmark and link-name rules. Acceptance: the keyboard focus position is visible on every interactive element in the product.
- Fix status: report-only

- ID: REV-130
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both
- Impact: Application state is never written to the URL, so deep links are read-only and one-way. The graph honours `?repository=&symbol=` once on mount and then diverges silently: everything the user does afterwards — loading a repository overview, focusing a different symbol, changing filters, selecting a node — leaves the URL unchanged. A refresh therefore silently reverts to the original deep link rather than the current view, Back leaves the page entirely instead of undoing the last graph action, and no view a user reaches by interaction can be shared or bookmarked. Search is worse: `q`, `mode` and `rerank` never appear in the URL at all, so no result set is addressable.
- Evidence:
  - The deep link is read exactly once and never written: `graph-explorer.tsx:59-61` — `const searchParams = useSearchParams(); const initialRepositoryId = searchParams.get('repository') ?? ''; const initialSymbolId = searchParams.get('symbol') ?? '';` — used to seed state (`:62`) and to drive the mount effect (`:89` — `useEffect(() => { if (initialRepositoryId && initialSymbolId) void requestGraph(…); else if (initialRepositoryId) void requestOverview(); }, [initialRepositoryId, initialSymbolId]);`).
  - Nothing writes back. `grep -rn "useRouter\|router\.\|replaceState\|pushState\|history\." apps/web` → no matches, so there is no `router.replace`, no `history.replaceState`, and no `<Link>`. This is the same absence as REV-113 seen from the state-persistence side.
  - The divergence is concrete: arriving at `/graph?repository=A&symbol=S` loads S's subgraph; clicking "Repository map" (`:106`) replaces it with A's overview while the URL still says `symbol=S`. A refresh at that point re-runs the mount effect and returns to S's subgraph — the user's last action is silently undone, and the URL was actively misleading in between.
  - Search state is entirely unaddressable: `search-client.tsx:22-24` holds `q`, `mode`, `rerank` in `useState` with no URL synchronisation, and `go` (`:29`) never touches the URL. Since navigating away is a full page load (REV-113), leaving and returning loses the query with no recovery path.
  - Filter state is likewise local-only: `graph-explorer.tsx:66` (`relationship`, `minimumConfidence`) and `:65` (`selected`).
  - `useSearchParams()` requires the Suspense boundary that `graph/page.tsx:5` provides, so the read side is implemented correctly — only the write side is missing.
- Probable cause + diagnostic confidence: Deep-link support was added as an entry point for the search→graph handoff (REV-106) rather than as URL-as-state. High confidence.
- Smallest safe next step: Do REV-113 first (adopt `next/link`), because with client-side routing the router cache alone preserves state across in-app navigation and Back. Then a single `router.replace` on each successful graph load and each search submit makes the URL authoritative. Keep it to the fields that identify a view (`repository`, `symbol`, `q`, `mode`) — filters can stay local.
- Affected data/migrations/providers/cost: None. Shareable graph and search links are a stated product benefit (`docs/USER_AND_AGENT_EXPERIENCE.md:55`, clickable, citable source locations).
- Recommended tests + acceptance criteria: browser E2E — load a deep link, change the view, assert the URL updated, refresh, assert the changed view is restored; assert Back returns to the previous graph view rather than leaving the page. Acceptance: the URL always describes what is on screen.
- Fix status: report-only

- ID: REV-131
- Category: DOCUMENTATION_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both (documentation is identical on both branches for this file)
- Impact: The product vision document instructs the UI to display something the review mandate explicitly forbids claiming. Anyone building the workspace UI from `HOSTED_PRODUCT_AND_UI_VISION.md` would implement a dependency view asserting evidence origin and confidence for declarations that have neither, creating exactly the misleading-evidence class §3.4 and §7 exist to prevent. Because the workspace UI is unbuilt (REV-100), this is currently a latent instruction rather than a shipped defect — which makes it cheap to fix now and expensive to fix after implementation.
- Evidence:
  - The instruction: `docs/HOSTED_PRODUCT_AND_UI_VISION.md:13` — "Explicit cross-repository dependency view, **with evidence origin and confidence**."
  - The prohibition: §7 of the mandate forbids any report or UI claiming "Evidenzursprung oder Confidence für heutige deklarierte Dependencies", and §3.4 requires that initial workspace overviews "dürfen deklarierte Abhängigkeiten nicht als verifizierte `calls`, `references` oder `imports` darstellen".
  - The data supports the prohibition, not the vision. `workspace_dependencies` rows carry `package_name`, `import_path`, `reason` and `note` (`main.py:44` — `workspace_dependency_out`) and **no** confidence field and no evidence provenance. §2 states plainly that these are "manuelle Deklarationen, keine automatisch belegten, cross-repository Code-Kanten".
  - The risk of conflation is concrete because the graph client would happily render them as verified edges: `graph-explorer.tsx:49` defaults any unrecognised relationship to `'related'`, and `graph-canvas.tsx:9-13` falls through to the solid-arrow "calls/references" style for every relationship that is not `contains` or `defines`. A `declared_dependency` edge fed into today's canvas would be drawn identically to a verified call — see also the fixture's invented types (REV-112).
  - Related, smaller mismatch in the same document: `HOSTED_PRODUCT_AND_UI_VISION.md:30` — "Graph exploration with verified versus unresolved relationships clearly distinguished" — is unmet today for a different reason (REV-111: unresolved relationships are not distinguished, they are deleted).
- Probable cause + diagnostic confidence: The vision document predates the decision that dependencies are manual declarations, and was not revised when that constraint was set. High confidence — the two documents are in direct textual conflict.
- Smallest safe next step: Amend line 13 to say what is true and buildable: "Explicit cross-repository dependency view, labelled as manual declarations, visually distinct from verified code relationships." Add the `declared_dependency` relationship to `graph-canvas.tsx`'s style map with its own non-arrow treatment *before* any workspace graph ships, so the default fall-through cannot mislabel it.
- Affected data/migrations/providers/cost: None. A confidence column for declarations should not be added merely to satisfy the sentence.
- Recommended tests + acceptance criteria: a rendering test asserting a `declared_dependency` edge is visually and textually distinguishable from a `call` edge; a documentation review gate asserting no UI copy attributes confidence or evidence origin to a declaration. Acceptance: §7's non-claims hold for the workspace UI when it lands.
- Fix status: report-only

- ID: REV-132
- Category: DOCUMENTATION_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both
- Impact: The documented "Repository operations" surface is almost entirely unbuilt, so the vision document overstates the product's operational capability. Anyone reading it — including a future agent planning work — would assume branch selection, a job timeline, index statistics, model identity and cost/usage reporting exist. None do. The cost/usage gap is the material one: §3.10 requires provider spend to be "kostenbeobachtbar", and the UI reports no tokens, no cost and no model identity anywhere.
- Evidence — `docs/HOSTED_PRODUCT_AND_UI_VISION.md:16-22` item by item:
  | Documented (line) | Shipped |
  |---|---|
  | "Add Git URL and **select branch**" (18) | Only name + clone URL: `dashboard-client.tsx:70-71`. `RepositoryIn` has no branch field (`main.py:22`), only an optional 40-hex `requested_revision`, which the UI never sends. `repo_out` returns `default_branch` and `indexed_branch` (`main.py:42`) and neither is displayed. |
  | "Start full index, incremental sync, or **bounded Code Card run**" (19) | Sync and Reindex exist as two unexplained adjacent buttons (`dashboard-client.tsx:84-85`) with no copy, tooltip or `title` distinguishing them — a user cannot tell which to press. `POST /api/repositories/{id}/code-cards` exists on integration (`main.py:179`) with no UI at all. |
  | "Show job timeline: queued, clone, parse, embed, code-card generation, complete/failed" (20) | Nothing. No timeline, no history, no polling (REV-123). `indexing_jobs` has four rows in the live database and no UI can read them; there is no list endpoint for them either. |
  | "Display file/symbol/chunk counts, indexed commit, model identity, and cost/usage metadata" (21) | Only the indexed commit (`dashboard-client.tsx:81`). No counts (the live repository has 2 284 files / 21 324 symbols / 22 900 chunks, none shown), no model identity, no token or cost figures. `code_cards` stores `input_tokens`/`output_tokens`/`model`/`prompt_version` (`models.py:32`) and nothing surfaces them. |
  | "Credentials are never entered or displayed as raw secrets in the UI" (22) | **Holds.** No credential input exists; the clone-URL validator rejects embedded credentials patterns via `isSafeCloneUrl` (`lib/repositories.ts:13-20`) and the server re-validates (`main.py:151`). |
  - The dashboard metrics that do exist are repository-level counts only: `dashboard-client.tsx:61-63` — total, ready, indexing.
- Probable cause + diagnostic confidence: The vision document describes the target state and is not marked as aspirational, while `CURRENT_STATUS.md` and `ENGINEERING_BACKLOG.md` exist alongside it. High confidence in the gap list; each row is a checked absence.
- Smallest safe next step: Do not build the timeline first. Mark the unbuilt items in the vision document as target-state with a pointer to the backlog, so the document stops reading as a description of the product. Then the cheapest genuinely useful slice is the counts and branch on the repository card — the branch fields are already in `repo_out`, and counts would need one small aggregate endpoint.
- Affected data/migrations/providers/cost: None for the documentation change. Surfacing Code Card runs in the UI would expose a billable path and must not ship without the explicit opt-in and budget §3.10 requires.
- Recommended tests + acceptance criteria: none for the doc fix beyond review. For the counts slice: API test asserting the aggregate matches direct table counts; component test asserting the card renders them. Acceptance: no line in the vision document describes an unbuilt capability without saying so.
- Fix status: report-only

- ID: REV-133
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both (`files/[id]/page.tsx` byte-identical)
- Impact: The file view is a terminal, context-free page. It shows a path and a commit and nothing else: no repository name, no breadcrumb, no link back to the repository or to the search that produced it, and no way to reach any symbol defined in the file — so the natural "read this file, now jump to the function" step is impossible. It is also the end of every navigation path in the product (search, chat citation, symbol page all lead here), which makes it the worst place for a dead end.
- Evidence — the whole page is one line, `apps/web/app/files/[id]/page.tsx:1`:
  - Context shown: `<h2>{f.path}</h2><p className="muted">{f.language} · commit {f.indexed_commit_sha?.slice(0, 12)}</p>`. The response includes `repository_id` (`main.py:220`) and it is not rendered, so the user does not learn which repository the file belongs to — significant once more than one repository exists.
  - No symbol overlay. `GET /api/files/{file_id}/symbols` exists (`main.py:221`) and returns `id`, `name`, `qualified_name`, `type`, `start_line`, `end_line` for every symbol in the file — exactly what a gutter or sidebar would need — and is called by nothing (`grep -rn "/symbols'" apps/web` → no match). No line is clickable and no symbol is linked.
  - No outbound links at all: the page renders no `<a>` elements, so the only way out is the sidebar or the browser Back button (which, per REV-113, discards the search that led here).
  - Line numbers are inside the copyable region: `{f.content.split('\n').map((x,i)=><div id={\`L${i+1}\`} key={i}><span className="muted">{String(i+1).padStart(4)} </span>{x}</div>)}` — the number `<span>` is a sibling of the code text inside the same `<div>`, so selecting and copying a range copies the line numbers with it. Deep-link anchors (`#L{n}`) work, which is the mechanism search and chat rely on.
  - The `<pre>` is not keyboard-scrollable: `globals.css:8` sets `pre { white-space: pre-wrap; overflow: auto; … }`, and no `tabindex="0"` is applied, so a scrollable code region cannot be scrolled by keyboard alone.
  - Whole-file rendering with no bound: `main.py:220` returns `f.content` in full and the page renders two DOM elements per line with no virtualisation or truncation notice. For the largest files in a 2 284-file repository this is the least efficient possible rendering, though no specific file was measured, so no performance claim is made here (§7).
  - Contrast with `docs/USER_AND_AGENT_EXPERIENCE.md:55` ("Suchergebnisse, Symboldetail und **klickbare Quellstellen**") and the Sourcegraph pattern cited at `HOSTED_PRODUCT_AND_UI_VISION.md:40` ("code citations, symbol/relationship navigation").
- Probable cause + diagnostic confidence: Built as a minimal source viewer to make citations clickable, and never developed into a navigation surface. High confidence.
- Smallest safe next step: Two small, independent additions. (a) Render the repository name and a link back to it (needs REV-109's repository page to land, or link to the dashboard in the interim) — the `repository_id` is already in the response. (b) Fetch `/files/{id}/symbols` and render a symbol list beside the source, each item linking to the existing symbol page. Move the line numbers out of the copyable flow using CSS counters rather than text nodes.
- Affected data/migrations/providers/cost: None; both endpoints are existing read-only queries.
- Recommended tests + acceptance criteria: component test asserting the repository is named and linked, and that each symbol in the file is a link to its symbol page; browser E2E asserting a copied selection contains no line numbers. Acceptance: the file view is a navigation hub, not a leaf.
- Fix status: report-only

### Low

- ID: REV-134
- Category: DESIGN_GAP
- Severity: low
- Evidence level: source-reviewed
- Applies to: integration (`graph-explorer.tsx` divergent)
- Impact: The Node details panel is one large `aria-live="polite"` region whose entire contents are replaced on every node click. Screen-reader users therefore hear the whole panel re-announced each time — heading, label, a 36-character UUID read character-group by character-group, kind, and then every remaining metadata field including the symbol's complete source text (REV-102). A single click can produce a very long unwanted announcement, which in practice trains users to ignore the region.
- Evidence:
  - The live region wraps everything: `graph-explorer.tsx:114` — `<aside className="graph-detail" aria-live="polite"><h3>Node details</h3>{selected ? <dl>…</dl> : <p className="muted">Click a node…</p>}</aside>`.
  - What gets announced includes the raw source text, because the metadata loop excludes only layout keys: `Object.entries(selected).filter(([key]) => !['id','label','kind','x','y','vx','vy','index','__indexColor'].includes(key)).map(([key, value]) => <span key={key}><dt>{key}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></span>)`. For an API-sourced node that is `repository_id`, `file_id`, `name`, `qualified_name`, `type`, `language`, `start_line`, `end_line`, `start_byte`, `end_byte`, `parent_symbol_id`, `signature`, `source_text`, `degree`, `isRoot`.
  - The `<dt>` labels are raw field names (`qualified_name`, `start_byte`, `parent_symbol_id`), so the announcement is also not human-phrased.
  - The `<span style="display: contents">` wrapper used to keep the `dl` grid intact (`globals.css:9` — `.graph-detail dl span { display: contents; }`) is a presentational workaround that does not affect the announcement but does mean the `dt`/`dd` pairing depends on a CSS property; if `display: contents` is unsupported the definition list structure breaks visually.
- Probable cause + diagnostic confidence: `aria-live` was added to the container to announce selection changes, without narrowing what changes. High confidence in the markup; the severity of the announcement is reasoned, not observed with a screen reader (none was available).
- Smallest safe next step: Move `aria-live` off the container onto a small dedicated status line that announces only the selected node's label and kind, and let the detail list be read on demand. Cap or omit `source_text` from the panel with an allow-list of displayed fields — which also fixes the rendering half of REV-102.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: manual screen-reader pass asserting a node selection produces a short announcement; component test asserting `source_text` is not rendered into the detail list. Acceptance: selecting a node announces an identification, not a data dump.
- Fix status: report-only

- ID: REV-135
- Category: BUG_CONFIRMED
- Severity: low
- Evidence level: source-reviewed
- Applies to: integration (`graph-explorer.tsx` divergent; re-check on `main`'s working-tree version)
- Impact: Pressing Enter while focus is in the graph page's Repository select or Depth field submits the form and triggers "Focus symbol" — the *secondary* action — which then fails with the UUID-entry error message if no symbol is set. The visually primary action ("Repository map") is not the default, so the most natural keyboard gesture produces a confusing error instead of the obvious result.
- Evidence:
  - The form's submit handler is the symbol path: `graph-explorer.tsx:102` — `<form className="card graph-controls" onSubmit={loadGraph}>`, and `:87` — `function loadGraph(event: FormEvent) { event.preventDefault(); void requestGraph(); }`.
  - Button roles are inverted relative to their styling: `graph-explorer.tsx:106` — "Repository map" is `<button type="button" …>` with the default (primary) style, while "Focus symbol" is `<button type="submit" className="secondary-button" …>`. In HTML the submit button is the implicit default for Enter, so the secondary-styled button is the keyboard default.
  - The resulting failure path: `requestGraph` with an empty symbol hits `graph-explorer.tsx:78` — `if (!repository.trim() || !symbol.trim()) { setError('Enter both a repository ID and a symbol ID to load the API graph, or use the fixture demo.'); return; }` — so the user is told to enter IDs after pressing Enter on a dropdown (see also REV-106 on that copy).
  - Partial mitigation that makes it inconsistent rather than always broken: "Focus symbol" is `disabled={loading || !symbolId.trim()}`, and a disabled submit button suppresses implicit submission in current browsers — so Enter does nothing at all when the symbol field is empty, and misfires only once a symbol has been entered but the user intends an overview. Either way, Enter never performs the primary action.
- Probable cause + diagnostic confidence: The form was wired for the symbol flow first and the overview button was added later as `type="button"`. High confidence in the markup; the exact browser behaviour for the disabled-submit case is standard but was not verified in a browser.
- Smallest safe next step: Make the primary action the submit button and the secondary one `type="button"` — i.e. swap the two `type` attributes and the two class names so that role, styling and keyboard default agree. Zero new code.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: browser E2E asserting Enter in the Repository select loads the repository overview. Acceptance: the visually primary action is the keyboard default on every form in the product.
- Fix status: report-only

- ID: REV-136
- Category: BUG_SUSPECTED
- Severity: low
- Evidence level: source-reviewed
- Applies to: integration (`graph-explorer.tsx` divergent)
- Impact: Confidence normalisation guesses the input's scale from its magnitude, so the two scales it supports are not distinguishable at their boundary. A stored confidence of `1` meaning "1 %" would be rendered as 100 % — the maximum instead of the minimum. Latent today because the live data contains only `20` and `100` (REV-110), but it is a silent, wrong-direction misreport of evidence quality if the vocabulary ever changes.
- Evidence:
  - The heuristic: `graph-explorer.tsx:47-48` — `const confidence = typeof confidenceValue === 'number' ? confidenceValue : typeof confidenceValue === 'string' && confidenceValue.trim() !== '' ? Number(confidenceValue) : null; const normalizedConfidence = Number.isFinite(confidence) ? Math.max(0, Math.min(1, confidence! > 1 ? confidence! / 100 : confidence!)) : null;` — anything `> 1` is treated as a percentage, anything `<= 1` as a fraction. The value `1` falls on the fraction side and becomes `1.0` = 100 %.
  - The same ambiguity is implemented independently on the symbol page, with the boundary on the other side: `repositories/[repositoryId]/symbols/[symbolId]/page.tsx:11` — `Math.round(Math.max(0, Math.min(100, number <= 1 ? number * 100 : number)))`. So `1` becomes 100 there too, but the two functions duplicate the same guess in two places and could drift.
  - The server's own synthetic structural edges rely on the ambiguity resolving the "1 means certain" way: `main.py:288`, `:291`, `:293` all emit `'confidence':1` for `contains`/`defines` edges, which the client reads as 100 % — correct by intent, but only because the heuristic happens to break that way.
  - The database column is an integer with a percentage-like range (`models.py:37`, `default=50`), so the mixed-scale handling exists to accommodate the synthetic `1` values, not real data. The clean alternative is already available: the server knows which scale it is emitting.
  - Marked `BUG_SUSPECTED`: no current input triggers the wrong branch, so it was not reproduced.
- Probable cause + diagnostic confidence: A defensive coercion written to accept both API shapes, duplicated in two components. High confidence in the code path; the impact is conditional on future data.
- Smallest safe next step: Fix the source of the ambiguity rather than the guess — have the API emit one scale for all edges (percent integers, since that is what the column stores) and delete the magnitude heuristic from both client functions. If REV-110's recommendation is adopted and confidence stops being a percentage, this finding disappears entirely, which is the preferable outcome.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: unit test on the normalisation asserting each documented input value maps to exactly one output, including the boundary value `1`. Acceptance: no confidence value's meaning depends on its magnitude.
- Fix status: report-only

- ID: REV-137
- Category: BUG_SUSPECTED
- Severity: low
- Evidence level: source-reviewed
- Applies to: integration (`graph-explorer.tsx` divergent)
- Impact: The displayed node count changes meaning depending on whether the graph has any links, and isolated nodes are silently hidden whenever it does. A user filtering by relationship type sees the node count drop by more than the filter implies, because nodes that lost all their edges are removed rather than shown as isolated — so the summary's "N nodes" is not the number of nodes in the requested scope. Minor in effect but it makes the one honest number on the graph page unreliable, which matters given REV-101.
- Evidence:
  - `graph-explorer.tsx:69-74`:
    ```ts
    const links = graph.links.filter((link) => (relationship === 'all' || link.relationship === relationship) && (link.confidence == null || link.confidence >= minimum));
    const connected = new Set(links.flatMap((link) => [link.source, link.target]));
    return { links, nodes: graph.nodes.filter((node) => connected.has(node.id) || graph.links.length === 0) };
    ```
    The predicate keeps a node only if it survives in the *filtered* link set, with a single escape hatch: `graph.links.length === 0`, which tests the **unfiltered** list. So when a graph has links, isolated nodes are dropped; when it has none, all nodes are kept. Two different definitions of "nodes to display".
  - The count rendered from it is the one the user reads as the graph's size: `graph-explorer.tsx:110` — `{filteredGraph.nodes.length} nodes · {filteredGraph.links.length} relationships`.
  - The effect compounds with the confidence filter's coarseness (REV-110): switching from "Any confidence" to "50 % or higher" drops all `0.2` edges at once, which can silently remove a large number of nodes from the count with no explanation.
  - It also interacts with REV-111: nodes whose only edges were unresolved are already absent server-side, so the count under-reports twice for different reasons.
  - Marked `BUG_SUSPECTED` because the intended behaviour is not documented — hiding isolated nodes may well be deliberate; the defect is that the count is presented as the scope size regardless.
- Probable cause + diagnostic confidence: The `|| graph.links.length === 0` clause was added so that a link-less graph still renders its nodes, and the inconsistency with the filtered case was not noticed. High confidence in the behaviour; medium in whether it is unintended.
- Smallest safe next step: Decide and state one rule. Either always keep all nodes in scope and render isolated ones (simplest, and consistent with "N nodes" meaning the scope size), or keep the hiding and label the count accordingly ("N of M nodes shown"). Either way the escape hatch should test the same list as the filter.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: unit test on `filteredGraph` covering a graph with links where a filter isolates a node, asserting the documented rule; assert the summary count matches the rule. Acceptance: the node count has one definition that holds under every filter combination.
- Fix status: report-only

- ID: REV-138
- Category: DOCUMENTATION_GAP
- Severity: low
- Evidence level: source-reviewed
- Applies to: both (`search-client.tsx` is divergent, but the label is present on both branches and is prescribed by the document)
- Impact: A single German control label sits in an otherwise entirely English UI, and it is not a slip — the vision document specifies it verbatim, so it will be re-introduced by anyone implementing from the document. Beyond inconsistency it is an accessibility issue: the document is declared `lang="en"`, so a screen reader applies English pronunciation to German words. It also happens to label the one control with a cost implication, which is the worst candidate for ambiguity.
- Evidence:
  - Shipped: `search-client.tsx:49` — `<label className="muted"><input type="checkbox" checked={rerank} disabled={mode !== 'hybrid'} onChange={…} /> Reranker verwenden</label>`.
  - Prescribed: `docs/HOSTED_PRODUCT_AND_UI_VISION.md:27` — "Per-query checkbox: `Reranker verwenden`; it only controls ranking for that request." The document is otherwise written in English, so the German string is deliberate and quoted as the intended label.
  - Language declaration: `layout.tsx:3` — `<html lang="en">`, with no `lang` attribute on the German text. Every other user-facing string in the app is English (verified across all five page surfaces).
  - The wider repository is bilingual by design — `docs/USER_AND_AGENT_EXPERIENCE.md` and the review mandate are German, `HOSTED_PRODUCT_AND_UI_VISION.md` is English — so the underlying question is whether the *product* has a language policy. It currently does not, and this label is the only place the ambiguity has reached the UI.
  - No i18n mechanism exists: no locale files, no `next-intl`/`react-i18next` dependency in `package.json`, no `[locale]` route segment.
- Probable cause + diagnostic confidence: The vision document was drafted bilingually and this label was copied verbatim into the implementation. High confidence — both texts are quotable and identical.
- Smallest safe next step: Decide the UI language (English, given every other string and `lang="en"`), change the label to "Use reranker", and correct the vision document so the German string is not re-introduced. If the intent is genuinely a German UI, that is a much larger decision and should be recorded as one rather than expressed through one checkbox. Do not add an i18n framework for a single string.
- Affected data/migrations/providers/cost: None directly, but this checkbox gates a billable reranking call (`search.py:104-110`), and its effect is currently invisible to the user (REV-120) — so a label the user may not understand controls spend they cannot observe.
- Recommended tests + acceptance criteria: component test querying the control by its English accessible name; a review check that all user-facing strings match the declared `lang`. Acceptance: one UI language, consistently applied, matching the `lang` attribute.
- Fix status: report-only

## Not assessed

Each entry states what was not established and why, per the mandate's preference for a stated
gap over a guess (§10, §7).

- **Browser E2E of any surface.** Playwright could not launch: `Chromium distribution 'chrome' is
  not found at /opt/google/chrome/chrome`. No finding in this report carries the
  `browser E2E verified` level. Specifically **not** verified in a browser, and therefore reasoned
  from source: keyboard tab order and focus visibility (REV-129), delete-dialog focus behaviour
  and Escape handling (REV-116), graph canvas keyboard reachability (REV-115), Back/forward and
  refresh behaviour (REV-113, REV-130), the out-of-order response races (REV-118), and rendering
  legibility of a 100-node / 5 296-edge graph (REV-102). Each of these is marked
  `source-reviewed` and names the exact absent code, but none was observed as user behaviour.
- **Screen-reader behaviour.** No assistive technology was available, so the accessibility
  findings describe missing markup and missing focus management rather than observed
  announcements. The announcement-verbosity severity in REV-134 in particular is reasoned, not
  measured.
- **Colour-contrast audit beyond spot checks.** Three ratios were computed by hand (`.muted` on
  card background ≈ 7:1, `aside small` on sidebar ≈ 5:1, both passing AA); the `button:disabled`
  `opacity: .7` case and the status-pill palette were **not** measured. No contrast finding is
  filed because no failure was established.
- **Multi-repository and multi-workspace UX.** One repository and zero workspaces exist, and
  creating more would have triggered billable or long-running indexing (§4). So the behaviours
  most at risk were reasoned from source only: whether the auto-selected `ready[0]` repository
  (REV-124) is confusing in practice, whether the `repo:` substring filter (REV-119) matches
  multiple repositories, whether scope-switch staleness (REV-103) is noticed by users, and
  whether the unbounded `GET /api/repositories` list degrades. §3.6's per-repository commit
  vector could not be exercised at all.
- **The integration branch at runtime, as of when evidence was collected.** All live
  measurements quoted here were taken against `main`-lineage containers before the 14:34 restart
  described above. `main`'s live API exposes 26 paths versus integration's 42; notably
  `GET /api/repositories/{repo_id}/graph` returned `404 Not Found` on the live stack at
  measurement time, so the repository-overview path (`graph-explorer.tsx:94`) could not be
  exercised end to end at all. Findings touching it are `source-reviewed`.
- **Provider-backed surfaces.** No `POST` to `/explanations`, `/documentation/generate`, `/chat`
  or `/search/semantic` was made (§4 cost gate, no approval). So the chat page's rendered answer
  and citation layout, the grounded/ungrounded distinction (`chat-client.tsx:24`), the generated
  documentation panel (symbol page `:21`) and semantic-mode result rendering were read but never
  rendered with real data. REV-120's claim about the dropped capability object rests on the API
  contract and one free `GET /api/search`, not on a degraded-provider observation.
- **Whether the documentation staleness marker works.** `docs/USER_AND_AGENT_EXPERIENCE.md:82`
  requires generated documents to be flagged as potentially outdated after a reindex or commit
  change. The symbol page renders the generating commit (`:21`) but never compares it to the
  repository's current indexed commit, and generated documentation is not persisted, so it cannot
  become stale in the current implementation. This was **not** filed as a finding because the
  feature it would regress against does not exist yet; it is recorded here as a precondition for
  whoever implements persistence.
- **Actual file-view rendering cost.** REV-133 notes two DOM elements per line with no
  virtualisation, but no file was measured, so no performance claim is made (§7). The largest
  file in the indexed repository was not identified.
- **`next lint` and TypeScript results.** Neither was run against the static target; the worktree
  has no `node_modules` and installing dependencies would have written to it, which the read-only
  constraint forbids. So it is not established whether the app currently type-checks or lints
  clean. REV-122's claim is only that no *test* tooling exists, which is verified from
  `package.json` and the absence of test files.
- **MCP and CLI surfaces.** Out of scope for this workstream (§5.A covers the human UI). The
  claim in `docs/USER_AND_AGENT_EXPERIENCE.md:7` that humans and agents share one fact base was
  not verified across clients; that belongs to the API/contract workstream.
- **Whether the two working-branch fixes reported by the coordinator are correct.** REV-101 and
  REV-106 are annotated as addressed on the working branch on the coordinator's report. Neither
  fix was read or executed by this workstream, because source evidence is pinned to `c122529`.
  They should be verified independently before either finding is closed.
