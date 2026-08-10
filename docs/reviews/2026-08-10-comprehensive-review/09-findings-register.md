# 09 — Findings Register

> Generated from the workstream reports; the authoritative wording for each finding stays in
> its own report. One row per finding ID, most severe first. Clusters below group IDs that are
> the **same underlying defect** found independently by different workstreams — read those
> first, because the register's raw count overstates how many distinct problems exist.

**213 findings** across 9 workstreams.

| Severity | Count |
|---|---|
| blocker | 4 |
| critical | 16 |
| high | 70 |
| medium | 87 |
| low | 29 |
| info | 7 |

| Category | Count |
|---|---|
| `DESIGN_GAP` | 65 |
| `CORRECTNESS_RISK` | 36 |
| `BUG_CONFIRMED` | 33 |
| `TEST_GAP` | 27 |
| `PERFORMANCE_RISK` | 16 |
| `DOCUMENTATION_GAP` | 13 |
| `SECURITY_RISK` | 11 |
| `OPTIMIZATION_OPPORTUNITY` | 6 |
| `BUG_SUSPECTED` | 3 |
| `info` | 2 |
| `INFO` | 1 |

| Evidence level | Count |
|---|---|
| source-reviewed | 83 |
| postgresql integration-tested | 46 |
| manual live acceptance | 30 |
| unit/api-tested | 28 |
| browser e2e verified | 25 |
| documented only | 1 |

Note the evidence profile: the largest bucket is `source-reviewed`. Per §7 those are reasoned
claims about code, not observed behaviour, and must not be reported as verified.

| Workstream | Findings |
|---|---|
| A Product & UX | 39 |
| B API & scope | 27 |
| Browser E2E | 25 |
| G Tests & E2E | 23 |
| D Graph & evidence | 23 |
| E Indexing & providers | 21 |
| F Security & ops | 20 |
| C Data & migrations | 20 |
| Concept & efficiency | 15 |

---

## Duplicate clusters — the same defect seen from several angles

13 clusters absorb 68 of the 213 IDs.

### C1 — Repository scope is a Python post-filter applied after the SQL LIMIT

*Worst severity in cluster:* **critical** · *IDs:* `REV-200`, `REV-502`, `REV-907`, `REV-208`, `REV-217`, `REV-515`, `REV-514`, `REV-220`

Every retrieval modality truncates candidates in SQL, then filters by repository in Python. Silently under-returns; invisible at one repository, a wrong-answer generator at two. Blocks any workspace-scoped search.

### C2 — `confidence` is a bare-name uniqueness artefact rendered as verified evidence

*Worst severity in cluster:* **critical** · *IDs:* `REV-401`, `REV-901`, `REV-415`, `REV-910`, `REV-904`, `REV-914`

Edge resolution matches a bare callee name across the whole repository with no import, scope or receiver information, then stamps confidence=100. Builtin calls bind to unrelated methods. Already baked into the 22 900 embedded chunks, so a correct fix implies a billable re-embed.

### C3 — A failed index job commits its own destructive rewrite

*Worst severity in cluster:* **blocker** · *IDs:* `REV-500`, `REV-407`, `REV-520`, `REV-703`

No rollback() before the except block's bookkeeping commit, so the common failure path publishes a half-deleted index under a `failed` status. SIGKILL is the only safe failure mode.

### C4 — Unindexed foreign keys make every re-index 12.7x slower than a first index

*Worst severity in cluster:* **critical** · *IDs:* `REV-503`, `REV-902`, `REV-311`

Four columns referencing symbols.id have no index, so each symbol delete triggers four sequential scans. This is the entire 55s -> 11m37s regression; statement batching recovers nothing.

### C5 — Graph routes load the entire edge table into Python per request

*Worst severity in cluster:* **critical** · *IDs:* `REV-406`, `REV-517`, `REV-911`, `REV-203`, `REV-604`, `REV-102`

All 136 566 edges are fetched and sorted in process to return at most 100 nodes.

### C6 — Truncation is reported as a bare boolean, or not at all

*Worst severity in cluster:* **critical** · *IDs:* `REV-402`, `REV-101`, `REV-405`, `REV-419`, `REV-423`, `REV-719`, `REV-421`

No cause, no counts, and no edge budget: a 100-node response can carry 7 952 edges while 97% of the neighbourhood is dropped, so the shape the user reads is an artefact of the cap.

### C7 — Workspace-first exists in the data model and nowhere else

*Worst severity in cluster:* **blocker** · *IDs:* `REV-100`, `REV-909`, `REV-201`, `REV-306`, `REV-722`, `REV-206`, `REV-707`

13 workspace operations, zero clients: `grep -rin workspace apps/web/` returns nothing. No Unassigned state, no atomic create-in-workspace, no workspace-scoped read path.

### C8 — The platform is unauthenticated and published on all interfaces

*Worst severity in cluster:* **blocker** · *IDs:* `REV-600`, `REV-601`, `REV-602`, `REV-603`, `REV-605`, `REV-619`

Redis without password plus RQ's pickle serializer is LAN-reachable RCE as root; Postgres superuser on 0.0.0.0 with hardcoded credentials; 15 state-mutating routes anonymous.

### C9 — Semantic retrieval cannot use an index and scores the whole corpus in Python

*Worst severity in cluster:* **critical** · *IDs:* `REV-505`, `REV-903`, `REV-309`, `REV-508`, `REV-504`

Vector() is declared without a dimension, so no pgvector ANN index can be created at all; the query then fetches every embedded chunk with no LIMIT and no repository predicate.

### C10 — No text index anywhere; lexical search sequentially scans file contents

*Worst severity in cluster:* **high** · *IDs:* `REV-506`, `REV-906`

ILIKE '%term%' over 165 MB; zero-result queries are the slowest.

### C11 — Symbol identity is uuid4() regenerated on every index run

*Worst severity in cluster:* **high** · *IDs:* `REV-404`, `REV-507`, `REV-905`

Deep links rot, capped node sets change between re-indexes, and no durable citation is possible.

### C12 — Nothing enforces any of this: no CI, and tests cannot see production semantics

*Worst severity in cluster:* **blocker** · *IDs:* `REV-700`, `REV-702`, `REV-317`, `REV-701`, `REV-709`

No CI on either branch. Every DB test is SQLite with foreign keys off, so all 12 ON DELETE CASCADE declarations are inert and the destructive delete path is untestable as configured.

### C13 — Documentation asserts capabilities and abstractions that do not exist

*Worst severity in cluster:* **high** · *IDs:* `REV-512`, `REV-908`, `REV-609`, `REV-610`, `REV-513`, `REV-613`, `REV-905`

Incremental git sync, full-text search, a prompt-injection defence, enforced authorization, and ADR-0001's three storage contracts are all documented and absent.

---

## Full register

| ID | Sev | Category | Evidence | Applies to | Workstream | Claim |
|---|---|---|---|---|---|---|
| `REV-100` | blocker | `DESIGN_GAP` | source-reviewed | both | A Product & UX | The top-level user decision described in §2 ("Workspace auswählen oder anlegen") does not exist. A human cannot create, name, select, switch, describe or… |
| `REV-500` | blocker | `CORRECTNESS_RISK` | unit/api-tested | both | E Indexing & providers | A failed indexing job commits the destructive rewrite it was in the middle of. The repository is flagged failed and its indexed_commit_sha is left at the… |
| `REV-600` | blocker | `SECURITY_RISK` | manual live acceptance | both | F Security & ops | Any host on the same layer-2 network as the docker host obtains arbitrary code execution as root inside the worker container, with no credential of any ki… |
| `REV-700` | blocker | `TEST_GAP` | source-reviewed | both | G Tests & E2E | Every other finding in this report is unenforceable. A contributor can push code that breaks all 50 tests and nothing objects. The 42-route API, the migra… |
| `REV-101` | critical | `CORRECTNESS_RISK` | manual live acceptance | both (integration exp… | A Product & UX | The user is shown a heavily truncated graph and told it is "API result · N nodes · M relationships". There is no indication that the graph is a fraction o… |
| `REV-102` | critical | `PERFORMANCE_RISK` | manual live acceptance | both | A Product & UX | A single "focus symbol" action transfers 2.35 MB and takes 3.5 s, then asks a force-directed canvas to lay out 5 296 edges over 100 nodes. §3.3 requires h… |
| `REV-103` | critical | `CORRECTNESS_RISK` | source-reviewed | integration (main's g… | A Product & UX | Direct §3.7 violation. Old graph answers are neither discarded nor isolated on scope change, so the user can read a graph belonging to repository A while… |
| `REV-200` | critical | `BUG_CONFIRMED` | unit/api-tested | both (defect is in se… | B API & scope | The only repository-scope filter the retrieval layer offers is applied after the SQL row limit. In a corpus with more than one repository, a scoped query… |
| `REV-201` | critical | `DESIGN_GAP` | unit/api-tested | both | B API & scope | Invariant §3.1 ("scope comes from the server") is honoured by exactly one function. Every read route that returns code, symbols, edges, graphs, jobs or co… |
| `REV-401` | critical | `BUG_CONFIRMED` | postgresql integration-tested | both | D Graph & evidence | The graph presents fabricated relationships as verified, 100 %-confidence code evidence. A human or coding agent that trusts the graph will conclude that… |
| `REV-402` | critical | `CORRECTNESS_RISK` | postgresql integration-tested | both | D Graph & evidence | truncated: true is the only signal that a graph is incomplete. It states neither the cause (node cap) nor the magnitude. For Agent the response looks like… |
| `REV-501` | critical | `BUG_CONFIRMED` | postgresql integration-tested | main (working tree) a… | E Indexing & providers | As observed live, a PostgreSQL backend was stuck idle in transaction for over 20 minutes with an open xid. It held RowExclusiveLock on symbols, code_chunk… |
| `REV-601` | critical | `SECURITY_RISK` | postgresql integration-tested | both | F Security & ops | Any host on the LAN reads and writes the entire corpus — 2 284 files with full content, 21 324 symbols, 136 566 edges — using a credential pair that is wr… |
| `REV-602` | critical | `SECURITY_RISK` | manual live acceptance | both | F Security & ops | Every operation is anonymous. There is no principal, no session, no API key, no bearer verification, no reverse proxy in the compose file, and nothing in… |
| `REV-701` | critical | `TEST_GAP` | source-reviewed | both | G Tests & E2E | The entire user-facing surface — every state the mandate §5.A asks about (Empty, Loading, Indexing, Failed, Stale, Truncated, No-results), every accessibi… |
| `REV-702` | critical | `TEST_GAP` | postgresql integration-tested | both | G Tests & E2E | This is the central finding of the workstream. Production is PostgreSQL 16 + pgvector; every database-backed test is SQLite in-memory with foreign keys di… |
| `REV-703` | critical | `TEST_GAP` | manual live acceptance | both — the job_timeou… | G Tests & E2E | The indexing-job lifecycle — the one subsystem that demonstrably broke twice in one session and left a repository stuck in indexing forever — has no test… |
| `REV-901` | critical | `CORRECTNESS_RISK` | postgresql integration-tested | both | Concept & efficiency | The product's central promise is evidence. Its most confident relationship claims are its least justified. A user or agent asking "who calls this?" receiv… |
| `REV-902` | critical | `PERFORMANCE_RISK` | postgresql integration-tested | both | Concept & efficiency | Re-indexing an unchanged repository takes 11 m 37 s instead of 55 s for byte-identical output. This is the defect that produced the original RQ job_timeou… |
| `REV-903` | critical | `PERFORMANCE_RISK` | postgresql integration-tested | both | Concept & efficiency | The first user who configures an embedding provider gets an API that transfers 5.5 GB and performs 22 900 Python dot products per semantic query, on a sin… |
| `REV-104` | high | `BUG_CONFIRMED` | source-reviewed | both (dashboard-clien… | A Product & UX | Failed operations are announced as if they had succeeded. A failed sync, reindex or delete renders in the same neutral .form-message with role="status" us… |
| `REV-105` | high | `BUG_CONFIRMED` | manual live acceptance | both (dashboard-clien… | A Product & UX | A fully indexed repository permanently displays an in-progress phase. The status pill says ready while the Progress field beneath it says finalizing · 228… |
| `REV-106` | high | `DESIGN_GAP` | source-reviewed | integration (the main… | A Product & UX | Direct §3.2 violation at the primary graph entry point. To open a focused symbol subgraph from /graph, a human must obtain a 36-character UUID and type or… |
| `REV-107` | high | `BUG_CONFIRMED` | source-reviewed | both (app/page.tsx is… | A Product & UX | When the API is unreachable the dashboard renders the *empty* state — "No repositories yet. Connect one above to begin indexing." — with metric tiles read… |
| `REV-108` | high | `BUG_CONFIRMED` | manual live acceptance | both (app/files/[id]/… | A Product & UX | Any failure in a server component produces a bare HTTP 500 with the generic app shell — no message, no retry, no way back. A stale or mistyped file link,… |
| `REV-109` | high | `DESIGN_GAP` | source-reviewed | both | A Product & UX | The §2 chain Workspace → "Alle Repositories" → Repository → Tree/Search/File → Symbol → Graph is broken in four places. Only the middle segment (Search →… |
| `REV-110` | high | `CORRECTNESS_RISK` | postgresql integration-tested | both | A Product & UX | The UI presents confidence as a calibrated percentage in three places, but the stored value is a two-valued heuristic marker. Users are shown "20 % confid… |
| `REV-111` | high | `CORRECTNESS_RISK` | postgresql integration-tested | both | A Product & UX | 45.5 % of extracted relationships are invisible in every graph view, with no indicator. The user sees a call graph that appears complete and reads it as "… |
| `REV-112` | high | `CORRECTNESS_RISK` | source-reviewed | both | A Product & UX | The fixture demo is designed to look exactly like this product's own real output, and its only disclosure is one muted inline phrase. A user who clicks "F… |
| `REV-113` | high | `BUG_CONFIRMED` | source-reviewed | both | A Product & UX | There is no client-side routing in the product. Every internal link triggers a full document load, so all client state is destroyed on every navigation an… |
| `REV-114` | high | `DESIGN_GAP` | source-reviewed | both (chat-client.tsx… | A Product & UX | The "AI Chat" page has no history. Answers exist only in React state, are lost on any navigation or refresh (REV-113), and are never persisted server-side… |
| `REV-115` | high | `DESIGN_GAP` | source-reviewed | both (graph-canvas.ts… | A Product & UX | The graph — the product's flagship surface — is completely unavailable to keyboard and screen-reader users, and has no reduced-motion path. There is no te… |
| `REV-116` | high | `DESIGN_GAP` | source-reviewed | both (dashboard-clien… | A Product & UX | The only modal in the product — the one guarding a destructive, irreversible action — implements none of the required dialog behaviours. Keyboard focus st… |
| `REV-117` | high | `BUG_CONFIRMED` | source-reviewed | integration (search-c… | A Product & UX | Search has no no-results state and no result-count disclosure. A query returning zero hits renders a page visually identical to the never-searched state,… |
| `REV-118` | high | `BUG_SUSPECTED` | source-reviewed | both | A Product & UX | No request is ever cancelled or sequenced, so overlapping requests can resolve out of order and render results belonging to a superseded query or scope. I… |
| `REV-119` | high | `DESIGN_GAP` | source-reviewed | both | A Product & UX | Two related failures of scope communication. (a) Search is globally unscoped from the UI even though the API supports repository scoping, so there is no w… |
| `REV-120` | high | `BUG_CONFIRMED` | source-reviewed | integration (search-c… | A Product & UX | The API reports provider capability and whether reranking was actually applied; the client discards all of it. Consequences: a user ticks "Reranker verwen… |
| `REV-121` | high | `DESIGN_GAP` | source-reviewed | both | A Product & UX | Repository creation cannot assign a workspace, so every repository in the system is permanently unassigned unless a second, separate API call is made by h… |
| `REV-122` | high | `TEST_GAP` | source-reviewed | both | A Product & UX | The web app has no automated test coverage of any kind, so every finding in this report describes behaviour that no test would have caught and no test wil… |
| `REV-202` | high | `BUG_CONFIRMED` | unit/api-tested | both | B API & scope | POST /api/chat is the only body-taking route that never checks that repository_id exists. It is written straight into Conversation.repository_id, which is… |
| `REV-203` | high | `PERFORMANCE_RISK` | manual live acceptance | both | B API & scope | scoped_edges materialises every edge row of the repository into Python and sorts it, on every graph-family request, regardless of how few edges the answer… |
| `REV-204` | high | `BUG_CONFIRMED` | manual live acceptance | both (search.py:68,73… | B API & scope | Every candidate SELECT applies LIMIT without ORDER BY. PostgreSQL is free to return any rows, so the candidate set — and therefore the final result set —… |
| `REV-205` | high | `DESIGN_GAP` | manual live acceptance | both | B API & scope | No route declares response_model. Every response is a hand-built dict assembled by repo_out / workspace_out / symbol_out / edge_out / citation or inline l… |
| `REV-206` | high | `DESIGN_GAP` | unit/api-tested | both | B API & scope | There is no atomic "create repository in workspace" operation. RepositoryIn has no workspace_id field, so POST /api/repositories always produces an unassi… |
| `REV-207` | high | `BUG_CONFIRMED` | unit/api-tested | both | B API & scope | enqueue() catches Exception and returns None. All three enqueueing routes then answer 202 Accepted with job_id: null. For POST /api/repositories the repos… |
| `REV-208` | high | `BUG_CONFIRMED` | unit/api-tested | main working tree (un… | B API & scope | The new symbol picker — the fix for "no human UUID entry" (§3.2) — relies on a server-side narrowing that does not exist, and its inline code comment asse… |
| `REV-220` | high | `TEST_GAP` | unit/api-tested | both | B API & scope | The suite passes and is genuinely useful, but it does not cover the contract this workstream is about. No test anywhere passes repository_id to search, so… |
| `REV-300` | high | `BUG_CONFIRMED` | postgresql integration-tested | both | C Data & migrations | DELETE /api/repositories/{repo_id} raises an unhandled IntegrityError and returns 500 for any repository that has ever been used in POST /api/chat. The re… |
| `REV-301` | high | `BUG_CONFIRMED` | postgresql integration-tested | both | C Data & migrations | POST /api/workspaces/{id}/dependencies can be called repeatedly with the same source_repository_id / target_repository_id and no package_name / import_pat… |
| `REV-302` | high | `CORRECTNESS_RISK` | postgresql integration-tested | integration | C Data & migrations | 0008 cannot be rolled back once the parser has written a single target_name longer than 512 characters — which is the entire reason the revision exists ("… |
| `REV-303` | high | `CORRECTNESS_RISK` | postgresql integration-tested | integration | C Data & migrations | 0008 removed the varchar(512) bound but left ix_symbol_edges_target_name as a plain btree. A btree entry cannot exceed ~2 704 bytes, so a sufficiently lon… |
| `REV-304` | high | `DESIGN_GAP` | postgresql integration-tested | both | C Data & migrations | the two stated invariants of a dependency declaration — source ≠ target, and both endpoints members of the *same* workspace — exist only in validate_depen… |
| `REV-306` | high | `DESIGN_GAP` | manual live acceptance | both | C Data & migrations | §5.C asks for "a clear Unassigned status or a documented, safeguarded backfill". Neither exists. Workspace membership is the presence or absence of a work… |
| `REV-307` | high | `CORRECTNESS_RISK` | postgresql integration-tested | both (structural); ac… | C Data & migrations | the migration-head guard protects the API and not the worker. The API refuses to start against a stale database — verified — but worker.py never calls ver… |
| `REV-309` | high | `DESIGN_GAP` | postgresql integration-tested | both | C Data & migrations | code_chunks.embedding was created as Vector() with no dimension. pgvector refuses to build any ANN index on a dimensionless vector column, so ivfflat and… |
| `REV-403` | high | `BUG_CONFIRMED` | source-reviewed | both (identical text… | D Graph & evidence | The first use of the "Relationship" or "Minimum confidence" filter replaces the rendered graph with No graph data to display. The selected filters returne… |
| `REV-404` | high | `BUG_CONFIRMED` | postgresql integration-tested | both | D Graph & evidence | Under the node cap, *which* nodes come back is decided by comparing random UUIDs. symbols.id defaults to uuid.uuid4() and every index run recreates symbol… |
| `REV-405` | high | `DESIGN_GAP` | postgresql integration-tested | both (/graph verified… | D Graph & evidence | §3.3 asks for "one global hard budget". Only nodes are budgeted, and the consequence is no longer hypothetical. The bounded repository overview returns 3.… |
| `REV-406` | high | `PERFORMANCE_RISK` | postgresql integration-tested | both | D Graph & evidence | Every graph and neighbour request costs ~2.5–3.6 s on a single 21 k-symbol repository, independent of how much data is asked for. The cause is isolated, n… |
| `REV-407` | high | `CORRECTNESS_RISK` | postgresql integration-tested | both | D Graph & evidence | §3.6 requires every graph context to retain repository, file/path, line range and indexed commit. A graph node carries repository_id, file_id, start_line,… |
| `REV-419` | high | `DESIGN_GAP` | postgresql integration-tested | both | D Graph & evidence | When the cap bites, the surviving neighbours are chosen by Python codepoint order on qualified_name — uppercase before lowercase, no relevance signal at a… |
| `REV-423` | high | `CORRECTNESS_RISK` | postgresql integration-tested | integration (the /gra… | D Graph & evidence | Two defects compound into a third. symbol_edges stores one row per *call site* with no aggregation, and the overview ranks symbols by raw edge count — so… |
| `REV-502` | high | `BUG_CONFIRMED` | unit/api-tested | both | E Indexing & providers | Scoping a search to a repository can return zero results for a repository that demonstrably contains matches. The SQL LIMIT is applied without any reposit… |
| `REV-503` | high | `PERFORMANCE_RISK` | postgresql integration-tested | both (schema-level; m… | E Indexing & providers | This is the measured 12.7× re-index regression. symbols has four incoming foreign keys and none of the referencing columns is indexed, so PostgreSQL fires… |
| `REV-504` | high | `BUG_CONFIRMED` | unit/api-tested | integration only (mai… | E Indexing & providers | The embedding-reuse cache can never hit. Every full re-index re-embeds every chunk from scratch, including chunks whose source has not changed by one byte… |
| `REV-505` | high | `PERFORMANCE_RISK` | unit/api-tested | both | E Indexing & providers | Semantic search is O(entire corpus) per query, in one Python process, inside the request. No LIMIT, no repository predicate, no pgvector operator, and no… |
| `REV-506` | high | `PERFORMANCE_RISK` | postgresql integration-tested | both (the lexical SQL… | E Indexing & providers | Lexical search has no index behind it. Every query is a sequential scan of code_chunks (165 MB, 22 900 rows) with ILIKE '%…%', which no btree can serve. M… |
| `REV-507` | high | `DESIGN_GAP` | source-reviewed | integration (regressi… | E Indexing & providers | The integration branch removed the only code that avoided work for unchanged files, so every index — sync as well as full — is now a complete destructive… |
| `REV-508` | high | `CORRECTNESS_RISK` | postgresql integration-tested | both | E Indexing & providers | Chunk text is sent to the embedding provider with no truncation and no token budget. On the live corpus 879 chunks (3.8 %) exceed the ~8 000-character / 2… |
| `REV-603` | high | `SECURITY_RISK` | manual live acceptance | both | F Security & ops | Any web page the operator visits while the stack is running can trigger cost-bearing and state-changing operations on it. CORSMiddleware only decides whet… |
| `REV-604` | high | `PERFORMANCE_RISK` | manual live acceptance | both | F Security & ops | Several anonymous GETs perform work proportional to the *whole repository* rather than to the requested result, giving a ~2 400× request-to-work amplifica… |
| `REV-605` | high | `SECURITY_RISK` | source-reviewed | both | F Security & ops | Two anonymous routes destroy the platform's entire value, and one of them leaks disk permanently. DELETE /api/repositories/{id} cascades away 2 284 files,… |
| `REV-704` | high | `TEST_GAP` | source-reviewed | both (42 routes on in… | G Tests & E2E | 24 of 42 routes have no test. The uncovered set is not random — it is exactly the mutating and retrieval halves of the API: repository create/delete/sync/… |
| `REV-705` | high | `TEST_GAP` | source-reviewed | both | G Tests & E2E | The §5.G target path is the product. Not one of its eight steps is automated end to end, and no test spans even two consecutive steps. Every step boundary… |
| `REV-706` | high | `TEST_GAP` | source-reviewed | both | G Tests & E2E | add_workspace_repository (main.py:127-140) is written defensively against a race — it pre-checks membership, inserts, and then catches IntegrityError to r… |
| `REV-707` | high | `TEST_GAP` | postgresql integration-tested | both | G Tests & E2E | Mandate invariant §3.8 states plainly: removing membership ≠ deleting the repository, and deleting a workspace ≠ deleting the repositories. No test assert… |
| `REV-708` | high | `TEST_GAP` | source-reviewed | both | G Tests & E2E | Retrieval is the product's core read path and its SQL is never executed by a test. Four routes (/api/search, /api/search/symbols, /api/search/semantic, an… |
| `REV-710` | high | `CORRECTNESS_RISK` | manual live acceptance | both | G Tests & E2E | The one documented way to run the tests validates a stale artefact. Anyone following docs/HANDOFF.md:66 gets a green result about code that may be arbitra… |
| `REV-722` | high | `TEST_GAP` | source-reviewed | both | G Tests & E2E | Mandate invariant §3.1 — "Scope kommt vom Server": for every workspace-scoped operation the permitted repository set is derived server-side, and a client-… |
| `REV-800` | high | `BUG_CONFIRMED` | browser e2e verified | main (running, pre-14… | Browser E2E | The two filter controls on the primary analysis surface destroy the graph on first use. Recovery requires re-running the whole symbol search and reloading… |
| `REV-801` | high | `CORRECTNESS_RISK` | browser e2e verified | main (running) and cu… | Browser E2E | The symbol picker is the only UUID-free route to a focused graph, and it cannot reach Agent — the single most important symbol in pydantic-ai. Worse, the… |
| `REV-802` | high | `BUG_CONFIRMED` | browser e2e verified | both | Browser E2E | Any stale, mistyped or shared link to a file yields a raw server-error page with an opaque incident number and no way back — no message, no "file not foun… |
| `REV-803` | high | `CORRECTNESS_RISK` | browser e2e verified | current build; the en… | Browser E2E | The "Repository map" — the bounded workspace/repository overview §3 invariant 3 demands — enforces a node budget while letting edges run unbounded. The br… |
| `REV-804` | high | `CORRECTNESS_RISK` | browser e2e verified | both, with different… | Browser E2E | confidence is presented to users as a filterable evidence measure, but the same field carries two different scales in one response, so the control cannot… |
| `REV-904` | high | `DESIGN_GAP` | postgresql integration-tested | both | Concept & efficiency | The resolution rule cannot express the relationships users most want. Any symbol sharing a bare name with any other symbol anywhere in the repository is p… |
| `REV-905` | high | `CORRECTNESS_RISK` | source-reviewed | integration (regressi… | Concept & efficiency | Integration deleted the only incremental short-circuit that existed. On main, a sync (full=False) skipped files whose content_hash matched. On integration… |
| `REV-906` | high | `PERFORMANCE_RISK` | postgresql integration-tested | both | Concept & efficiency | Search latency is inversely proportional to term rarity — the opposite of what a code search tool needs, since rare identifiers are the valuable queries.… |
| `REV-907` | high | `DESIGN_GAP` | source-reviewed | both | Concept & efficiency | search.py cannot express scope. The repository filter runs in Python after the SQL LIMIT, so with more than one repository a scoped query silently returns… |
| `REV-908` | high | `DOCUMENTATION_GAP` | source-reviewed | both | Concept & efficiency | Four capability claims and four named abstractions do not exist, and two sibling docs contradict each other on the same facts. Planning and this review bo… |
| `REV-909` | high | `DESIGN_GAP` | source-reviewed | both | Concept & efficiency | Workspace-first is the stated top-level user decision (§2) and has no UI surface whatsoever — the string "workspace" does not occur anywhere in apps/web.… |
| `REV-123` | medium | `DESIGN_GAP` | source-reviewed | both (dashboard-clien… | A Product & UX | The Indexing state never resolves. After clicking Sync or Reindex the card shows indexing and then stays that way forever, because nothing polls. The user… |
| `REV-124` | medium | `DESIGN_GAP` | source-reviewed | both (both branches'… | A Product & UX | Two problems from one line of logic, repeated in two files. (a) Both surfaces silently drop every repository that is not ready, with no note — so a reposi… |
| `REV-125` | medium | `DESIGN_GAP` | source-reviewed | both | A Product & UX | Stale-index detection is impossible in the UI even though the server already computes it. The dashboard cannot tell the user "the remote has moved on sinc… |
| `REV-126` | medium | `DESIGN_GAP` | source-reviewed | both (dashboard-clien… | A Product & UX | §3.8 requires that "Mitgliedschaft entfernen ≠ Repository löschen; Workspace löschen ≠ Repository löschen" be understood identically by UI, API, database… |
| `REV-127` | medium | `CORRECTNESS_RISK` | source-reviewed | both | A Product & UX | The graph and the symbol page — the two surfaces whose entire purpose is structural evidence — display no indexed commit. §3.6 requires that "Treffer und… |
| `REV-128` | medium | `DESIGN_GAP` | source-reviewed | integration for the s… | A Product & UX | Three form controls have no accessible name, so screen-reader users hear only a role ("edit text", "combo box") with no indication of purpose, and voice-c… |
| `REV-129` | medium | `DESIGN_GAP` | source-reviewed | both | A Product & UX | Keyboard users get no visible focus indication beyond the browser default, and the one interactive element that *is* styled for the mouse — the navigation… |
| `REV-130` | medium | `DESIGN_GAP` | source-reviewed | both | A Product & UX | Application state is never written to the URL, so deep links are read-only and one-way. The graph honours ?repository=&symbol= once on mount and then dive… |
| `REV-131` | medium | `DOCUMENTATION_GAP` | source-reviewed | both (documentation i… | A Product & UX | The product vision document instructs the UI to display something the review mandate explicitly forbids claiming. Anyone building the workspace UI from HO… |
| `REV-132` | medium | `DOCUMENTATION_GAP` | source-reviewed | both | A Product & UX | The documented "Repository operations" surface is almost entirely unbuilt, so the vision document overstates the product's operational capability. Anyone… |
| `REV-133` | medium | `DESIGN_GAP` | source-reviewed | both (files/[id]/page… | A Product & UX | The file view is a terminal, context-free page. It shows a path and a commit and nothing else: no repository name, no breadcrumb, no link back to the repo… |
| `REV-209` | medium | `BUG_CONFIRMED` | manual live acceptance | both (git diff --stat… | B API & scope | The MCP bridge validates a search mode vocabulary that does not match the API's. lexical passes MCP validation and is accepted by the API with 200, but fa… |
| `REV-210` | medium | `CORRECTNESS_RISK` | manual live acceptance | both | B API & scope | /api/files/{file_id} returns full file content addressed by a bare id, with no repository or workspace predicate — the only route returning source text th… |
| `REV-211` | medium | `BUG_CONFIRMED` | manual live acceptance | both | B API & scope | The path query parameter is interpolated into a SQL LIKE pattern without escaping % or _. This is not SQL injection — the value is bound — but it *is* LIK… |
| `REV-212` | medium | `CORRECTNESS_RISK` | unit/api-tested | both | B API & scope | DELETE /api/repositories/{id} performs no state check. Deleting a repository while its indexing job is running removes the rows the worker is about to wri… |
| `REV-213` | medium | `CORRECTNESS_RISK` | unit/api-tested | integration (route ab… | B API & scope | /graph returns one edges array containing two mutually incompatible object shapes, and one nodes array containing two more. A client must sniff which keys… |
| `REV-214` | medium | `CORRECTNESS_RISK` | unit/api-tested | both | B API & scope | POST /api/chat loads a conversation by client-supplied id and never checks that it belongs to the requested repository. Messages and citations from reposi… |
| `REV-215` | medium | `DESIGN_GAP` | unit/api-tested | both | B API & scope | mode is a free-form str. An unknown value is accepted, echoed back, and produces an empty result set indistinguishable from "no matches" — which is precis… |
| `REV-216` | medium | `DESIGN_GAP` | manual live acceptance | both | B API & scope | POST /api/search/semantic accepts an untyped dict. A misspelled key yields body.get('query','') = '' and a 200 with an empty result set — no 422, no signa… |
| `REV-217` | medium | `DESIGN_GAP` | unit/api-tested | both | B API & scope | GET /api/search/symbols exposes only q. There is no repository_id, no limit and no mode; the limit is the search() default of 30, which becomes a limit *… |
| `REV-218` | medium | `BUG_CONFIRMED` | unit/api-tested | both | B API & scope | The fusion key is a location, not an identity. Two distinct symbols or chunks that share (type, file_id, start_line, end_line) collapse into one result, a… |
| `REV-219` | medium | `DESIGN_GAP` | unit/api-tested | both | B API & scope | The good news first: no internal detail leaks to clients. There is no custom exception handler, so Starlette's default converts any unhandled exception in… |
| `REV-221` | medium | `CORRECTNESS_RISK` | source-reviewed | both | B API & scope | POST /api/workspaces/{ws}/dependencies promises 409 'Dependency declaration already exists' on IntegrityError. The backing unique constraint spans two nul… |
| `REV-222` | medium | `DESIGN_GAP` | manual live acceptance | both | B API & scope | The three clients do not share one scope-and-provenance contract; they share a base URL. The web client has no concept of a workspace at all, the MCP clie… |
| `REV-223` | medium | `PERFORMANCE_RISK` | postgresql integration-tested | both | B API & scope | GET /api/repositories/{id}/tree selects the full File entity — including the content column — for every file under the requested prefix, uses only id and… |
| `REV-305` | medium | `CORRECTNESS_RISK` | postgresql integration-tested | both | C Data & migrations | removing a repository from a workspace at database level leaves every workspace_dependencies row that references it intact, because those rows have foreig… |
| `REV-308` | medium | `BUG_CONFIRMED` | postgresql integration-tested | integration (the thre… | C Data & migrations | alembic check fails against a database at head, which means models.py and the migration history do not agree. Today the practical consequence is mild — ev… |
| `REV-310` | medium | `CORRECTNESS_RISK` | postgresql integration-tested | both | C Data & migrations | two different state machines share one vocabulary with neither a CHECK constraint nor an enum on either column, and they disagree. repositories.indexing_s… |
| `REV-311` | medium | `PERFORMANCE_RISK` | postgresql integration-tested | integration | C Data & migrations | 0008's ALTER TABLE symbol_edges requires ACCESS EXCLUSIVE. The DDL itself is cheap — measured 10.360 ms on 136 566 rows — but lock *acquisition* is unboun… |
| `REV-312` | medium | `DESIGN_GAP` | postgresql integration-tested | both | C Data & migrations | two related gaps in first-boot behaviour. verify_migration_ready reads alembic_version before checking that it exists, so on a database that has never bee… |
| `REV-317` | medium | `TEST_GAP` | unit/api-tested | both | C Data & migrations | every finding in this report that is graded PostgreSQL integration-tested was invisible to the existing suite, because the suite has no PostgreSQL. All 50… |
| `REV-408` | medium | `BUG_CONFIRMED` | postgresql integration-tested | integration | D Graph & evidence | /api/repositories/{id}/graph returns a single edges array containing two mutually incompatible object shapes and two different confidence scales. Any cons… |
| `REV-409` | medium | `BUG_CONFIRMED` | postgresql integration-tested | integration | D Graph & evidence | The /graph overview's edges array order changes between API processes, so two identical requests can return byte-different bodies. That defeats ETag/cachi… |
| `REV-410` | medium | `DESIGN_GAP` | source-reviewed | both | D Graph & evidence | §3.2 forbids human UUID entry as the normal entry point. The graph page's own entry point *is* a UUID text field, and a node click cannot open a focused g… |
| `REV-411` | medium | `CORRECTNESS_RISK` | source-reviewed | both | D Graph & evidence | §3.7 requires that a repository switch discards or isolates stale answers. Changing the "Repository" dropdown updates only the form state; the canvas keep… |
| `REV-412` | medium | `CORRECTNESS_RISK` | source-reviewed | both | D Graph & evidence | The fixture demo is visually indistinguishable from real data and teaches wrong semantics. It claims a repository named knowledge-way — the product's own… |
| `REV-413` | medium | `BUG_CONFIRMED` | source-reviewed | both | D Graph & evidence | Following a second Open graph → link (or any client-side navigation that changes ?symbol=) reloads the canvas for the new symbol but leaves the form input… |
| `REV-414` | medium | `DESIGN_GAP` | postgresql integration-tested | both | D Graph & evidence | §5.D asks whether the canvas is comprehensible at many nodes. Three concrete reasons it is not, at the default 100-node cap: (a) labels are gated behind a… |
| `REV-415` | medium | `CORRECTNESS_RISK` | postgresql integration-tested | both | D Graph & evidence | confidence exists in the schema, so this is not "confidence displayed when it is not stored" — it is worse in a subtler way. The stored value is a two-val… |
| `REV-416` | medium | `BUG_CONFIRMED` | manual live acceptance | main (running deploym… | D Graph & evidence | The "Repository map" button on the running deployment cannot work. The served web bundle calls /api/repositories/{id}/graph, a route that exists only on t… |
| `REV-418` | medium | `TEST_GAP` | unit/api-tested | integration (the test… | D Graph & evidence | The three graph tests pass and cover the happy path, but they run against a fake session whose scalars() ignores every WHERE clause, so no test exercises… |
| `REV-509` | medium | `CORRECTNESS_RISK` | source-reviewed | integration (code_car… | E Indexing & providers | Provider work that was requested, billed and successfully returned is thrown away. _post_batch issues code_card_request_concurrency (default 8) requests c… |
| `REV-510` | medium | `DESIGN_GAP` | source-reviewed | integration (the Cohe… | E Indexing & providers | The reranker has no rate-limit handling of any kind. Cohere's 429 becomes an immediate exception; search.py:114-116 swallows it and degrades the response… |
| `REV-511` | medium | `DESIGN_GAP` | source-reviewed | integration for the c… | E Indexing & providers | §3.10 requires provider work to be "kostenbeobachtbar" — cost-observable. It is not. Token counts are stored per card and readable only one symbol at a ti… |
| `REV-512` | medium | `DOCUMENTATION_GAP` | source-reviewed | both | E Indexing & providers | README.md's MVP capability list makes two claims the code does not support, and both are in the areas §7 explicitly guards. A reader — or an agent — plann… |
| `REV-513` | medium | `DESIGN_GAP` | documented only | both | E Indexing & providers | ADR 0001 is "Accepted" and specifies three storage contracts as the mechanism by which alternative backends stay adapters. None exists. Retrieval strategy… |
| `REV-514` | medium | `TEST_GAP` | unit/api-tested | both | E Indexing & providers | The 50-test suite passes in 1.24 s and covers parser facts, provider selection, retry behaviour and graph shape well. Two gaps let this workstream's most… |
| `REV-515` | medium | `DESIGN_GAP` | manual live acceptance | both | E Indexing & providers | Two of the four retrieval modalities cannot be scoped at all. GET /api/search/symbols and POST /api/search/semantic accept no repository_id on either bran… |
| `REV-516` | medium | `CORRECTNESS_RISK` | manual live acceptance | main for search (reso… | E Indexing & providers | §3.6 requires every hit and every piece of graph context to carry repository, file/path, line range and indexed commit. On the live target, search results… |
| `REV-517` | medium | `PERFORMANCE_RISK` | manual live acceptance | both (graph semantics… | E Indexing & providers | Every graph request loads all 136 566 edges of the repository into Python, sorts them, and re-scans the list once per traversal hop. Measured 3.2–3.4 s fo… |
| `REV-606` | medium | `SECURITY_RISK` | manual live acceptance | both for root + read-… | F Security & ops | Both containers run as uid=0 with the host's ./data bind-mounted read-write, so any code execution inside them (REV-600) writes to the host filesystem as… |
| `REV-607` | medium | `SECURITY_RISK` | source-reviewed | both | F Security & ops | The redaction layer is applied at exactly one place and every other exception path bypasses it. ingestion.py:240 persists str(e) verbatim into two databas… |
| `REV-608` | medium | `SECURITY_RISK` | source-reviewed | both | F Security & ops | README.md states "secrets are excluded by default and are never logged". The actual exclusion is a four-name denylist plus two suffixes. Index a repositor… |
| `REV-609` | medium | `DOCUMENTATION_GAP` | source-reviewed | both | F Security & ops | The section of README.md titled "Security model" asserts a prompt-injection control that does not exist. A reader — or a coding agent — takes it as an imp… |
| `REV-610` | medium | `DOCUMENTATION_GAP` | source-reviewed | both | F Security & ops | Directly implicates §3.9 and §7. Two documents state in the present tense that authorization is enforced. The code does not implement it (see REV-602), so… |
| `REV-611` | medium | `SECURITY_RISK` | source-reviewed | both | F Security & ops | No request-body ceiling exists at any layer — uvicorn does not impose one, and there is no proxy in the compose file. POST /api/search/semantic is the wor… |
| `REV-612` | medium | `DESIGN_GAP` | source-reviewed | both | F Security & ops | validate_clone_url proves the URL is a *well-formed, credential-free network git URL* but says nothing about *which host*. An anonymous POST /api/reposito… |
| `REV-619` | medium | `TEST_GAP` | source-reviewed | both | F Security & ops | Every finding above is un-regression-tested. Because no test asserts a boundary, nothing fails when a boundary is removed — the loopback rebind of REV-600… |
| `REV-709` | medium | `TEST_GAP` | manual live acceptance | both | G Tests & E2E | With no conftest.py and no pytest configuration, the suite runs under exactly one undocumented invocation per package and fails under the obvious ones. Wo… |
| `REV-711` | medium | `TEST_GAP` | unit/api-tested | both | G Tests & E2E | test_migrations.py is three assertions, none of which runs a migration. Its head test is a pure tripwire that must be hand-edited on every migration — whi… |
| `REV-712` | medium | `TEST_GAP` | unit/api-tested | both | G Tests & E2E | MCP is the agent-facing contract (§5.B: API, web client and MCP must share the same scope/provenance contract). The client's 10 tests are good, but they a… |
| `REV-713` | medium | `TEST_GAP` | manual live acceptance | both | G Tests & E2E | Summary finding for the §5.G negative-test list. 0 of 9 fully covered, 6 partially, 3 absent. Negative behaviour is where scope leaks, misleading evidence… |
| `REV-714` | medium | `TEST_GAP` | source-reviewed | both | G Tests & E2E | All 42 routes return loose hand-built dicts and zero declare a response_model. Nothing — no schema, no test, no OpenAPI snapshot — pins the response shape… |
| `REV-716` | medium | `BUG_CONFIRMED` | manual live acceptance | integration (the scri… | G Tests & E2E | benchmarks/scripts/verify_live_queries.py is the only artefact in the repository that asserts real product behaviour against real indexed data — the close… |
| `REV-717` | medium | `CORRECTNESS_RISK` | manual live acceptance | both (test_manifests.… | G Tests & E2E | A test that passes natively and fails in a container is the classic CI adoption blocker — and it fails for a reason unrelated to what it tests, which will… |
| `REV-718` | medium | `TEST_GAP` | unit/api-tested | both | G Tests & E2E | test_workspaces_api.py is one test function covering 11 routes with ~20 sequential assertions against shared mutable state. The first failure aborts every… |
| `REV-719` | medium | `TEST_GAP` | unit/api-tested | both | G Tests & E2E | Mandate §3.3 requires one global hard budget and §5.D requires hard node and edge budgets with an honest truncated flag carrying cause and count. Testing… |
| `REV-720` | medium | `TEST_GAP` | source-reviewed | integration (code_car… | G Tests & E2E | Provider coverage is entirely mock-based, which per §7 forbids any claim of provider E2E verification — correct, and this report makes none. The gap that… |
| `REV-805` | medium | `DESIGN_GAP` | browser e2e verified | both — neither search… | Browser E2E | A user cannot tell "your query matched nothing" from "you have not searched yet", or from "the request failed". §5.A requires these states to be distingui… |
| `REV-806` | medium | `DESIGN_GAP` | browser e2e verified | both — neither versio… | Browser E2E | Search results cannot be shared, bookmarked or restored. Reload, Back and Forward all silently discard them, which is exactly the Back/Forward/refresh con… |
| `REV-807` | medium | `DESIGN_GAP` | browser e2e verified | both | Browser E2E | The product's stated top-level user decision (§2, "Workspace auswählen oder anlegen") has no UI at all, so the intended navigation cannot be started, and… |
| `REV-808` | medium | `BUG_CONFIRMED` | browser e2e verified | both | Browser E2E | The confirmation dialog for the destructive delete action fails three basic modal requirements (§5.A: "Fokus, Tastatur, Dialog Escape/Restore"). A keyboar… |
| `REV-809` | medium | `DESIGN_GAP` | browser e2e verified | both | Browser E2E | The graph — the surface carrying most of the product's value — is entirely unavailable to keyboard and screen-reader users, and the one honest thing it sa… |
| `REV-810` | medium | `PERFORMANCE_RISK` | browser e2e verified | both | Browser E2E | Opening a large indexed file builds a DOM proportional to its line count. This is the destination of every search result and every chat citation, so it is… |
| `REV-811` | medium | `CORRECTNESS_RISK` | browser e2e verified | both | Browser E2E | Every graph response ships the full source text of every symbol node, and the user-facing node panel then dumps it verbatim together with internal byte of… |
| `REV-812` | medium | `DESIGN_GAP` | browser e2e verified | main (running, pre-14… | Browser E2E | §3 invariant 6 requires every hit to retain repository, path, line range and indexed commit. On the main-lineage build the commit was missing from search… |
| `REV-813` | medium | `DESIGN_GAP` | browser e2e verified | c122529 and the curre… | Browser E2E | A first-time visitor to /graph is told their filters excluded everything, before they have loaded anything or touched a filter. It misdirects the user int… |
| `REV-814` | medium | `DESIGN_GAP` | browser e2e verified | both — neither versio… | Browser E2E | The search form is unusable with confidence via screen reader: the query field has no label, the mode selector has no accessible name at all, and results… |
| `REV-815` | medium | `DESIGN_GAP` | browser e2e verified | both | Browser E2E | The file view is where every search result and every chat citation lands, and it offers no way onward — breaking the §2 chain Datei → Symbol → fokussierte… |
| `REV-816` | medium | `DESIGN_GAP` | browser e2e verified | both | Browser E2E | §5.D requires that a fixture can never be mistaken for real workspace data. The fixture is one click away, sits in the same canvas, and the only distingui… |
| `REV-817` | medium | `DESIGN_GAP` | browser e2e verified | main (running, pre-14… | Browser E2E | On the main-lineage build no graph state was addressable, so a loaded graph could not be shared or restored, and Back navigated away from the page entirel… |
| `REV-824` | medium | `TEST_GAP` | browser e2e verified | both | Browser E2E | Every defect in this report was reachable within minutes of a first real browser session, which indicates the absence of browser coverage rather than unus… |
| `REV-910` | medium | `DESIGN_GAP` | source-reviewed | both | Concept & efficiency | SymbolEdge cannot record *how* an edge was derived. A single confidence integer with two values (100/20) is carrying the whole evidence model, which is wh… |
| `REV-911` | medium | `OPTIMIZATION_OPPORTUNITY` | postgresql integration-tested | both | Concept & efficiency | Every graph, caller, callee and documentation request hydrates the entire repository into Python to return at most 100 nodes. Measured row-data volume ≈11… |
| `REV-912` | medium | `PERFORMANCE_RISK` | source-reviewed | integration | Concept & efficiency | Integration adds an unconditional pass over the edge table once per structural card to every index run, on both the full and sync paths. Estimated +30 to… |
| `REV-913` | medium | `DESIGN_GAP` | source-reviewed | integration | Concept & efficiency | 424 LOC, two tables, four migrations and two provider integrations exist for a capability no user or agent can reach, while workspace-first (§2) has no UI… |
| `REV-914` | medium | `TEST_GAP` | source-reviewed | both | Concept & efficiency | The test suite validates the resolution rule only where it succeeds, so REV-901's false positives are not merely unfixed — they are *protected*. Any futur… |
| `REV-134` | low | `DESIGN_GAP` | source-reviewed | integration (graph-ex… | A Product & UX | The Node details panel is one large aria-live="polite" region whose entire contents are replaced on every node click. Screen-reader users therefore hear t… |
| `REV-135` | low | `BUG_CONFIRMED` | source-reviewed | integration (graph-ex… | A Product & UX | Pressing Enter while focus is in the graph page's Repository select or Depth field submits the form and triggers "Focus symbol" — the *secondary* action —… |
| `REV-136` | low | `BUG_SUSPECTED` | source-reviewed | integration (graph-ex… | A Product & UX | Confidence normalisation guesses the input's scale from its magnitude, so the two scales it supports are not distinguishable at their boundary. A stored c… |
| `REV-137` | low | `BUG_SUSPECTED` | source-reviewed | integration (graph-ex… | A Product & UX | The displayed node count changes meaning depending on whether the graph has any links, and isolated nodes are silently hidden whenever it does. A user fil… |
| `REV-138` | low | `DOCUMENTATION_GAP` | source-reviewed | both (search-client.t… | A Product & UX | A single German control label sits in an otherwise entirely English UI, and it is not a slip — the vision document specifies it verbatim, so it will be re… |
| `REV-224` | low | `DESIGN_GAP` | unit/api-tested | integration (both rou… | B API & scope | Two routes skip the repository existence check that their siblings perform, so a request against a nonexistent repository is answered with a 404 about the… |
| `REV-225` | low | `OPTIMIZATION_OPPORTUNITY` | source-reviewed | integration (route is… | B API & scope | structural_cards gets the filter/limit ordering right — the path-prefix filter runs before the slice, and truncated is computed against the filtered count… |
| `REV-313` | low | `DOCUMENTATION_GAP` | postgresql integration-tested | both | C Data & migrations | docs/migrations.md overstates two things. It claims both the API *and* the worker check their migration head at startup — the worker does not (REV-307) —… |
| `REV-314` | low | `OPTIMIZATION_OPPORTUNITY` | postgresql integration-tested | both | C Data & migrations | workspace_repositories carries three btree indexes although its logical key is repository_id alone — which is precisely what uq_workspace_repositories_rep… |
| `REV-315` | low | `OPTIMIZATION_OPPORTUNITY` | postgresql integration-tested | both | C Data & migrations | all six JSON columns materialise as PostgreSQL json, not jsonb. json stores the original text and re-parses on every access, supports no containment or pa… |
| `REV-316` | low | `CORRECTNESS_RISK` | postgresql integration-tested | both | C Data & migrations | every timestamp column is timestamp without time zone, populated by datetime.utcnow() — a naive datetime that carries no offset — and serialised by FastAP… |
| `REV-417` | low | `DESIGN_GAP` | source-reviewed | both | D Graph & evidence | §3.4 forbids rendering declared dependencies as verified calls / references / imports. Today the invariant is not violated in fact — no endpoint emits dec… |
| `REV-420` | low | `DESIGN_GAP` | manual live acceptance | both | D Graph & evidence | GET /api/files/{file_id}/symbols — the route the graph workflow depends on to turn a file into symbol ids — performs no repository scope check and no exis… |
| `REV-422` | low | `OPTIMIZATION_OPPORTUNITY` | source-reviewed | both | D Graph & evidence | The companion to REV-414(a). Auto-fit exists but is wired to fire exactly once, and the force simulation has no collision or charge tuning, so a 100-node… |
| `REV-518` | low | `DESIGN_GAP` | source-reviewed | integration | E Indexing & providers | The code-card module obtains its Google ADC token by calling a private static method on the embeddings adapter. Disabling, replacing or moving the Vertex… |
| `REV-519` | low | `DESIGN_GAP` | source-reviewed | both | E Indexing & providers | ChatProvider is declared but never implemented, and openai_api_key / openai_chat_model are never read by any code path. /api/chat returns a canned string… |
| `REV-613` | low | `DOCUMENTATION_GAP` | source-reviewed | both | F Security & ops | The file an operator opens for security guidance answers a narrower question than the one they asked. docs/security.md is titled "Git credential security"… |
| `REV-614` | low | `SECURITY_RISK` | source-reviewed | both | F Security & ops | The MCP bridge accepts KW_API_BEARER_TOKEN and sends it as Authorization: Bearer …. Nothing on the server verifies it — there is no security scheme, no de… |
| `REV-615` | low | `CORRECTNESS_RISK` | source-reviewed | both | F Security & ops | Two config footguns on one line. (1) cors_origins.split(',') does not strip whitespace, and Starlette compares origins by exact string equality, so CORS_O… |
| `REV-616` | low | `DOCUMENTATION_GAP` | source-reviewed | both | F Security & ops | compose.git-secrets.example.yml mounts the deploy key and known_hosts but never sets GIT_SSH_KEY_PATH / GIT_SSH_KNOWN_HOSTS_PATH, which is what actually m… |
| `REV-617` | low | `SECURITY_RISK` | source-reviewed | both | F Security & ops | git_environment() builds a deliberately minimal, allowlisted environment — GIT_TERMINAL_PROMPT=0, GIT_CONFIG_NOSYSTEM=1, GIT_CONFIG_GLOBAL=/dev/null, GIT_… |
| `REV-715` | low | `DOCUMENTATION_GAP` | manual live acceptance | both | G Tests & E2E | The documented test evidence is stale and understated, so a reader cannot tell what is actually covered. docs/HANDOFF.md records a pass count matching nei… |
| `REV-721` | low | `TEST_GAP` | unit/api-tested | both | G Tests & E2E | test_normal_startup_has_no_create_all_ddl guards a real invariant (§5.C: no start-up DDL in API/worker) with a substring search over source text. It passe… |
| `REV-818` | low | `DESIGN_GAP` | browser e2e verified | both, with opposite s… | Browser E2E | Two surfaces querying the same index disagree about the minimum useful query, and neither behaviour matches the backend's actual tokenisation. Users get e… |
| `REV-819` | low | `DESIGN_GAP` | browser e2e verified | both | Browser E2E | A repository that finished indexing 40 minutes earlier still advertises an in-progress phase, so a user cannot trust the dashboard's freshness signals — o… |
| `REV-820` | low | `DESIGN_GAP` | browser e2e verified | both | Browser E2E | Users who have asked the operating system to reduce motion still get a continuously animating force simulation, which is a recognised vestibular-discomfor… |
| `REV-821` | low | `PERFORMANCE_RISK` | browser e2e verified | current build; the 76… | Browser E2E | The mobile layout claims in the CSS mostly hold, but the graph route is not usable at 390 px: the canvas sits far below the fold and is asked to draw thou… |
| `REV-823` | low | `DESIGN_GAP` | browser e2e verified | main (running, pre-14… | Browser E2E | The legend promised a richer graph than the endpoint could ever return, implying a structural graph (repositories, directories, files) that the symbol sub… |
| `REV-915` | low | `DOCUMENTATION_GAP` | source-reviewed | both | Concept & efficiency | The graph fixture teaches capabilities the product does not have. It is correctly labelled "Fixture demo" in the summary line, so §5D's "fixture must neve… |
| `REV-226` | info | `INFO` | unit/api-tested | both | B API & scope | None — this records a verified non-finding, because §5.B explicitly asks whether error responses leak internal detail. The one route that puts a dynamic s… |
| `REV-318` | info | `info` | postgresql integration-tested | both | C Data & migrations | none — this is the finding that a claimed invariant genuinely holds, recorded so it is not re-litigated. UniqueConstraint('repository_id') does guarantee… |
| `REV-319` | info | `info` | postgresql integration-tested | integration | C Data & migrations | none for the upgrade direction. 0005–0008 are safe with respect to existing data; the risks that do exist are the *downgrade* of 0008 (REV-302), the new i… |
| `REV-421` | info | `DOCUMENTATION_GAP` | source-reviewed | integration | D Graph & evidence | The structural-cards routes are the best-behaved part of this workstream and are worth recording as the pattern to copy, with two small blemishes. |
| `REV-520` | info | `DESIGN_GAP` | source-reviewed | both | E Indexing & providers | The design answer to §5.E's "atomic, published index generations" question: there are none. The index is a single transaction that mutates live rows in pl… |
| `REV-618` | info | `OPTIMIZATION_OPPORTUNITY` | source-reviewed | both | F Security & ops | Recording what is already correct, so that a later refactor cannot regress it silently and so that the workstream's negative results are on the record rat… |
| `REV-822` | info | `DESIGN_GAP` | browser e2e verified | both | Browser E2E | Cosmetic, but it means the browser console is never clean, so a real error has to be spotted among permanent noise. Worth fixing precisely because it cost… |

