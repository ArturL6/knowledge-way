# 09b — Concept Coherence and Efficiency Critique

> Workstream: challenge the premise, not just the implementation. Builds on
> `01-runtime-and-provenance.md` (targets, safety gates, live DB state, exclusions) — that
> brief is not restated here. Mandate reference: `docs/CODING_AGENT_COMPREHENSIVE_REVIEW_PROGRAM.md`
> §1 (thesis), §2 (workspace-first), §3 (invariants), §6 (taxonomy), §7 (forbidden claims).
>
> Static target: `c122529` = `origin/integration/consolidated-verified`, read-only worktree.
> Live target: `main` + working tree, as described in the shared brief. Every finding states
> which. `data/` is excluded as source and cited only as indexed input.

---

## Summary

The concept is sound in its *ambition* and honest in its *primary documents*. The
`REPOSITORY_KNOWLEDGE_CONCEPT.md` layered-graph model is a good design, and it explicitly
disclaims full static analysis. The problem is not that the idea is wrong. The problem is a
**three-way mismatch between the concept documents, the data model, and what the numbers in
the database actually say** — and that mismatch lands precisely on the thesis: evidence.

Three things are genuinely concept-level, not implementation slips:

1. **The graph is a name-collision index presented as a call graph.** Edge resolution is
   "the bare identifier is unique in this repository" (`ingestion.py:120-146`). 41.5 % of
   this repository's symbols (8 842 of 21 324) can therefore *never* be an edge target,
   while 8 321 call edges resolve to a *method* whose receiver was thrown away. The stored
   value for that guess is `confidence = 100`, and the UI renders it as `call (100%)`.
   A `list.append(...)` call becomes 1 962 edges into `EnqueueGuard.append`. The evidence
   thesis is not weakened here, it is inverted: the system's most confident claims are its
   most fabricated ones.
2. **There is no evidence-origin field.** The project's own concept doc requires every edge
   to retain "resolver type" (`REPOSITORY_KNOWLEDGE_CONCEPT.md` §3). `SymbolEdge`
   (`models.py:36-37`) has a single `confidence` integer with exactly two possible values.
   The whole layered-confidence roadmap — `manifest_dependency`, `cross_repo_import`,
   `api_contract` — needs that column before any of it can be built. Adding it later is a
   migration over 136 566 rows whose provenance is unrecoverable.
3. **Retrieval has no scope pushdown, so workspace-first cannot be built on it.** The
   repository filter is applied in Python *after* the SQL `LIMIT` (`search.py:61, 68-80`).
   Workspace-scoped search — the stated top-level product primitive — is not a feature that
   can be added to this function; it is a rewrite of it.

On efficiency, the headline 12.7× re-index regression has a single, measured, boring cause
that is neither the parser nor the provider: **four foreign-key columns pointing at
`symbols.id` have no index**, so every one of the 21 324 symbol deletions triggers two full
sequential scans. 25.7 ms measured per row × 21 324 rows = 548 s, i.e. ≥85 % of the observed
642 s delta, fixable with two `CREATE INDEX` statements. The most alarming number in this
report, though, is latent: a single semantic query as written fetches **5 477.8 MB** of row
data (measured) for a 30-result answer.

Where effort has gone versus where value is: `code_cards.py` (213 LOC) and
`structural_cards.py` (52 LOC) plus 4 migrations and 159 LOC of tests have **zero
consumers** — `grep -c "code-card\|structural-cards" apps/web apps/mcp` returns nothing.
`grep -c workspace apps/web` returns nothing either. The interesting layer was built before
the necessary one. That is a judgement, and I state my confidence below.

---

## 1. Does the architecture deliver the thesis? — the real data path

Thesis (§1): *every claim traces to repository / file / line / commit.* Walking the path on
the static target, marking where provenance is created, preserved, weakened, or invented.

```
git clone --depth 1                              ingestion.py:193-200
  → rglob + read_text + size/secret filters      ingestion.py:203-207
  → File rows (content, content_hash, sha)        ingestion.py:221-224
  → tree-sitter analyze_source                   parser_facts.py:163-198
  → DeclarationFact / ImportFact / ReferenceFact  (each carries SourceRange)
  → Symbol + CodeChunk rows                      ingestion.py:82-109
  → _persist_edges: name-collision resolution    ingestion.py:120-146   ← P1, P2, P3
  → refresh_structural_cards                     structural_cards.py:19-52
  → optional embeddings                          ingestion.py:161-175
  → retrieval (lexical / symbol / semantic)      search.py:57-117       ← P4, P5
  → API responses + citations                    main.py:63-71, 227-295 ← P6
  → UI / MCP rendering                           graph-canvas.tsx:8-12  ← P7
```

**Provenance is created well.** `parser_facts.py` is the best module in the repository. Every
fact is a frozen dataclass carrying a `SourceRange` with byte offsets *and* line numbers
(`parser_facts.py:19-24`), the module refuses unknown languages rather than guessing a
grammar (`parser_facts.py:171-172`), signatures are explicitly cut at the body boundary so a
signature is never a whole function (`parser_facts.py:107-109`), and syntax errors are
retained as `DiagnosticFact` instead of silently dropping a file. The docstring even states
the correct boundary: *"References intentionally have no resolved target: resolution belongs
to the graph layer."* This module upholds the thesis.

### P1 — Resolution discards the evidence the parser bothered to collect

`_call_reference` (`parser_facts.py:149-160`) captures the receiver for attribute calls:
`x.append()` yields `ReferenceFact(kind='call', target_name='append', qualifier='x', ...)`.
`_persist_edges` reads `reference.target_name` and `reference.scope_qualified_name` and
**never reads `reference.qualifier`** (`ingestion.py:137-140`). The single most
discriminating piece of evidence available — the receiver expression — is parsed, stored in
memory, and thrown away one function call later.

### P2 — Resolution is bare-name uniqueness, and it is called confidence 100

```python
# ingestion.py:122-135
all_symbols = db.scalars(select(Symbol).where(Symbol.repository_id == repo_id)).all()
candidates = {}
for symbol in all_symbols:
 candidates.setdefault(symbol.name, []).append(symbol)      # keyed on BARE name

def edge(source_file, source_symbol, target_name, relationship_type, line):
 matches = candidates.get(target_name, [])
 target = matches[0] if len(matches) == 1 else None          # unique-name → "resolved"
 ...  confidence=RESOLVED_CONFIDENCE if target else UNRESOLVED_CONFIDENCE
```

`RESOLVED_CONFIDENCE = 100` (`ingestion.py:19`). Measured consequences on the live corpus
(one Python repository, `pydantic-ai` @ `640d517`):

| Measured | Value |
|---|---|
| `call` edges at confidence 100 | 67 792 |
| `call` edges at confidence 20 | 54 439 |
| `import` edges (100 / 20) | 6 623 / 7 712 |
| Symbols whose bare name is **not** unique | **8 842 of 21 324 (41.5 %)** |
| Distinct ambiguous names | 1 426 |
| Symbols named `__init__` | 380 |
| Confidence-100 `call` edges resolving to a **method** (`qualified_name LIKE '%.%'`) | **8 321** |

The false-positive profile, from the top confidence-100 call targets:

| `target_name` | edges | resolved to | defined in |
|---|---|---|---|
| `append` | **1 962** | `EnqueueGuard.append` | `pydantic_ai_slim/.../durable_exec/_toolset.py` |
| `raises` | **1 193** | `raises` | `tests/_inline_snapshot.py` |
| `set` | **550** | `TestEnv.set` | `tests/conftest.py` |
| `any` | **491** | `SpanTree.any` | `pydantic_evals/.../otel/span_tree.py` |
| `edge_from` | 444 | `GraphBuilder.edge_from` | `pydantic_graph/.../graph_builder.py` |
| `list` | **312** | `AnalysisStore.list` | `examples/.../slack_lead_qualifier/store.py` |
| `IsStr` | 6 227 | `IsStr` | `tests/conftest.py` |
| `snapshot` | 3 848 | `snapshot` | `tests/_inline_snapshot.py` |

`list.append`, `set(...)`, `any(...)`, `list(...)` are Python builtins and list methods.
`pytest.raises` is a third-party import. Every one of those ~4 508 edges (from a 15-name
probe, so a floor, not a total) asserts a call relationship that does not exist, at maximum
confidence, with a real file path and line number attached. **Fabricated provenance is worse
than absent provenance**, because the citation is checkable and looks correct: the line
number *does* contain a call to something named `append`.

The reciprocal loss is just as damaging: because `run`, `execute`, `__init__` and every other
common method name is ambiguous, 41.5 % of symbols are structurally excluded from the graph.
The symbols a developer most wants to trace are exactly the ones the rule cannot reach.

### P3 — 19 806 edges have no source symbol

`select count(*) from symbol_edges where source_symbol_id is null` → **19 806**. All 14 335
`import` edges pass `source_symbol=None` by construction (`ingestion.py:146`), and a further
5 471 are module-level calls, because `visit()` passes the *enclosing declaration* as scope
(`parser_facts.py:191`) and module-level code has none. These rows are half-edges: they carry
a file and a line, so the provenance is intact, but they cannot participate in
`callers`/`callees`/`subgraph`, all of which require both endpoints
(`main.py:230, 245, 267`). Not a defect — but it means the effective graph is 116 760 edges,
not 136 566, and the row count is not a measure of graph richness.

### P4 — Retrieval scope is applied after the SQL limit

```python
# search.py:61, 68
def allowed(repo): return repo and (not repository_id or repo.id == repository_id) and ...
for chunk, file in db.execute(chunk_stmt().where(CodeChunk.source_text.ilike(...)).limit(limit * 2)):
    repo = repos.get(chunk.repository_id)
    if allowed(repo): lexical.append(...)
```

`repository_id` never enters the SQL. With one repository this is invisible. With five, a
repository-scoped query for a term common in repository A returns *fewer or zero* results
for repository B, non-deterministically, because the `LIMIT 60` was consumed before the
Python filter ran. Invariant §3.1 ("Scope kommt vom Server") is satisfied in the sense that
the client cannot widen scope — but scope is not *applied*, it is *post-filtered*, and the
result set is silently wrong. This is a concept issue rather than a typo: `search_with_capability`
has no place to put a workspace's repository set, and the fusion in `_fuse` operates on
whatever survived. Workspace-scoped search means rewriting this function around SQL-side
scope predicates.

### P5 — Semantic retrieval abandons bounded retrieval entirely

```python
# search.py:88  (identical on main:search.py:85 — verified)
for chunk, file in db.execute(chunk_stmt().where(CodeChunk.embedding_model == provider.model)
                                          .where(CodeChunk.embedding.is_not(None))):
```

No `LIMIT`, no `ORDER BY`, no pgvector operator; `_cosine` is pure Python
(`search.py:40-43`). `chunk_stmt()` is `select(CodeChunk, File).join(File, ...)`, so every
row carries the joined `File` **including `File.content`**. Measured on the live corpus:

```sql
select round(sum(length(c.source_text)+length(f.content))/1024.0/1024.0,1)
from code_chunks c join files f on f.id=c.file_id;
-- 5477.8   (MB, 22 900 rows)
```

**5.5 GB of row data per semantic query**, of which ~5.3 GB is the same 76 MB of file content
re-sent once per chunk. Then 22 900 Python dot products. This is the exact scenario §5E of
the mandate names ("Ob Vollkorpus-Vektoren in Python geladen werden") and the answer is yes,
plus the entire corpus text alongside them. Currently dormant — `embedding_provider = "none"`
by default (`config.py:12`) and the live DB has zero embeddings — which is why it has never
been observed. It is not a hypothetical: it is what the code does the moment a provider is
configured.

### P6 — Citations are honest; the citation *helper* is the strongest evidence code

`citation()` (`main.py:63-65`) clamps line ranges to the file's actual line count and falls
back through `item.indexed_commit_sha → file.indexed_commit_sha → repo.indexed_commit_sha`.
That is careful, correct provenance work and it deserves saying. `/api/explanations`
(`main.py:307-313`) returns `answer_mode: "retrieval_only"` and `grounded: bool(results)`
rather than pretending to synthesise. Good. Provenance is *not* lost at the API boundary —
it is lost upstream, at P2, and the API faithfully reports the fabricated edge.

### P7 — The UI converts a heuristic into a percentage

```tsx
// graph-canvas.tsx:11 — the wide branch, i.e. calls/references
return { color: '#6386bd', width: (link.confidence ?? 0) >= 0.9 ? 2.2 : 1.4, dash: [], arrow: 5 };
// graph-canvas.tsx (linkLabel)
return item.confidence == null ? item.relationship : `${item.relationship} (${Math.round(item.confidence * 100)}%)`;
```

`graph-explorer.tsx` normalises `confidence > 1 ? confidence/100 : confidence`, so a stored
`100` becomes `1.0` becomes the label **`call (100%)`** and the thickest stroke. The filter
dropdown offers "90 % or higher". A user filtering for high-confidence relationships gets
*exactly* the name-collision guesses. §7 forbids claiming "Evidenzursprung oder Confidence"
that is not there; this is the clearest overstep in the product, and it is in the UI rather
than the docs.

**Verdict on Q1.** The path preserves file/line/commit provenance end to end — that part of
the thesis holds. What it does not preserve is *relationship truth*, and it labels the
weakest inference in the pipeline with the strongest number the schema can express.

---

## 2. Claims versus reality

| Documented claim | Actual state | Evidence |
|---|---|---|
| "Incremental Git synchronization with content-hash deduplication" (`README.md`) | **False on integration.** `main` had `if f and f.content_hash==digest and not full: continue`; integration replaced it with `if f and f.content_hash==digest: f.indexed_commit_sha=sha` — **no `continue`**. Every index of every kind now deletes and re-parses every file. | `ingestion.py:222`; `git diff main:…/ingestion.py c122529:…/ingestion.py` |
| "PostgreSQL … full-text search" (`README.md`); "PostgreSQL full-text/trigram candidate retrieval" (`architecture.md`) | **False.** Zero GIN/GiST indexes exist on any user table; retrieval is `ILIKE '%term%'`. | `select … from pg_indexes where indexdef like '%gin%' or '%gist%'` → 2 rows, both `pg_catalog`; `search.py:68,73,77` |
| "The `SearchEngine`, `EmbeddingProvider`, `ChatProvider`, and parser interfaces…" (`architecture.md`) | `EmbeddingProvider`/`ChatProvider` exist (`providers.py:14-25`). **`SearchEngine` does not exist anywhere.** | `grep -rl SearchEngine apps packages` → no hits |
| ADR 0001 "Initial Contracts": `CodeGraphStore`, `VectorSearchIndex`, `ProvenanceStore` | **None exist.** Route handlers write SQLAlchemy directly (`main.py` imports 13 model classes). ADR decision 2 ("services use storage contracts, not backend-specific calls") is contradicted by the code it governs. | `grep -rl CodeGraphStore\|VectorSearchIndex\|ProvenanceStore apps packages` → no hits |
| "Grounded chat answers with verified, clickable file-and-line citations" (`README.md`) | Citations are real; the *answer* is a constant string, and it names `OPENAI_API_KEY` while the live provider stack is Vertex/OpenRouter. | `main.py:332` |
| "embeddings are not yet persisted or queried with pgvector"; "the first indexer uses conservative declaration-aware regex extraction" (`CURRENT_STATUS.md`) | **Stale and contradicted by a sibling doc.** `NEXT_STEPS.md` states Vertex embeddings are live and tree-sitter symbols persist; `models.py:29` has a `Vector()` column. | `CURRENT_STATUS.md` vs `NEXT_STEPS.md` "Verified baseline" |
| "Resolution rule: a target becomes a resolved symbol only when its declaration name is unique inside the same repository … resolved local edges are confidence 100" (`REPOSITORY_KNOWLEDGE_CONCEPT.md`) | **Accurate.** This doc is honest about the mechanism. It omits that the mechanism produces confidently-wrong edges for builtins and methods, and the UI then renders 100 as 100 %. | `ingestion.py:127-135`; measured table in §1/P2 |
| "An edge should retain: source, target …, **resolver type**, confidence, and index commit" (`REPOSITORY_KNOWLEDGE_CONCEPT.md` §3) | **Not implemented.** `SymbolEdge` has no resolver/origin column. | `models.py:36-37` |
| "Workspace membership and explicit repository-to-repository dependency declarations are available" (`NEXT_STEPS.md` "Verified baseline") | API/DB only. **Zero occurrences of "workspace" in `apps/web`.** Zero rows in the live DB. | `grep -rn workspace apps/web` → no hits; shared brief |
| "It must not be represented as complete cross-language static analysis" (`architecture.md`) | The *docs* comply. The **UI does not** — `call (100%)`. | `graph-canvas.tsx` `linkLabel` |
| "Static references are advisory and always carry a confidence level" (`PRODUCT_DECISIONS.md`) | Literally true, and the reason the problem is invisible: "advisory" is stated in a doc no user reads, while "100 %" is printed on the graph. | `PRODUCT_DECISIONS.md`; `graph-canvas.tsx` |

Docs that are *good* and should be protected: `REPOSITORY_KNOWLEDGE_CONCEPT.md` (the layered
model with evidence types per layer is the right target architecture), ADR 0001's
"Validation Gate for Any Future Adapter" (five concrete criteria before adding Neo4j/FAISS —
this is what stops the project adding a graph DB it does not need), and `backlog/README.md`
"Product boundaries" ("do not add Neo4j/FalkorDB yet").

---

## 3. Efficiency analysis, ranked by evidence strength

### Rank 1 — Unindexed foreign keys on `symbols.id` cause the 12.7× re-index regression
*(`PostgreSQL integration-tested`, measured cause)*

Ground truth from `indexing_jobs`, both `kind='full'`, same repo, same commit, byte-identical
output:

```
8c6ddf6e  ready  11:29:07 → 11:30:02   00:00:54.87   (empty DB)
cf074b18  ready  11:38:00 → 11:49:38   00:11:37.27   (2 284 files already present)
                                        delta = 642.4 s
```

The only structural difference is that the second run takes the delete branch
(`ingestion.py:223`): `delete(Symbol).where(Symbol.file_id==f.id)` then
`delete(CodeChunk).where(...)`, once per file. `\d symbols` shows four FK constraints
referencing `symbols.id`, and **not one of the referencing columns is indexed**:

```
Referenced by:
  code_chunks.symbol_id     ON DELETE SET NULL   -- no index
  symbol_edges.source_symbol_id  (NO ACTION)     -- no index
  symbol_edges.target_symbol_id  (NO ACTION)     -- no index
  symbols.parent_symbol_id       (NO ACTION)     -- no index, self-referential
```

Every deleted `symbols` row therefore fires referential-integrity triggers that sequential-scan
the referencing tables. Measured, on the live database:

```
Seq Scan on symbols       WHERE parent_symbol_id = $1   → 11.759 ms  (21 324 rows filtered)
Seq Scan on code_chunks   WHERE symbol_id        = $1   → 13.964 ms  (22 900 rows filtered)
Seq Scan on symbol_edges  WHERE source_symbol_id = $1   → 21.991 ms  (136 566 rows filtered)
```

Arithmetic: (11.759 + 13.964) ms × 21 324 rows = **548 519 ms ≈ 548 s**, i.e. **85.4 % of the
observed 642 s delta from these two triggers alone.** The two `symbol_edges` triggers add
more — the edges are deleted at `ingestion.py:212` before the file loop, so the table holds
no live rows, but 136 566 dead tuples still occupy pages that each check must read, and no
`VACUUM` can run inside the transaction. Counting them at full measured cost would over-shoot
the observed delta (1 493 s), so the honest statement is: **the measured per-row trigger cost
brackets the observed regression, with the two live-table scans alone accounting for ≥85 % of
it.** No other candidate mechanism in the diff comes within an order of magnitude.

*Predicted effect of the fix (labelled reasoning, high confidence):* four B-tree indexes turn
each ~13 ms scan into a ~0.05 ms index probe, collapsing ~548 s to under 2 s. Additionally
`ON DELETE CASCADE`/`SET NULL` on those constraints would let PostgreSQL batch the work.

### Rank 2 — A semantic query fetches 5 477.8 MB of row data
*(`PostgreSQL integration-tested` for the volume; `source-reviewed` for the call site; not observed end to end)*

`search.py:88` (and `main:search.py:85`) issues an unbounded `select(CodeChunk, File)` join
filtered only on `embedding_model`. Measured payload for the current corpus: **5 477.8 MB
across 22 900 rows**, ~5.3 GB of which is `File.content` duplicated once per chunk. Then
22 900 pure-Python cosine computations at 768 dimensions each. The comment defending it —
*"Python cosine is portable to SQLite tests and pgvector production"* — trades production
scalability for test-harness convenience, on the one query path where scalability is the
entire point. pgvector is already installed and the column is already `Vector()`.

### Rank 3 — Lexical search has no text index; worst case 594 ms per scan, up to 3 per query
*(`PostgreSQL integration-tested`)*

```
EXPLAIN ANALYZE … WHERE c.source_text ILIKE '%zzzznotpresent%' LIMIT 60;
  Seq Scan on code_chunks  Rows Removed by Filter: 22900
  Buffers: shared hit=4766 read=13423
  Execution Time: 593.756 ms
```

A hybrid query runs the exact `ILIKE` (`limit*2`), then — when it returns nothing — a
term-OR `ILIKE` with N clauses (`limit*8`), then a symbol `ILIKE` scan (measured 4 ms, the
one cheap path). A no-hit hybrid query therefore costs ≈1.2 s of sequential scanning **on one
2 284-file repository**, and grows linearly with corpus size. A matching query is fast
(10.5 ms) only because `LIMIT` short-circuits; the cost is a function of term rarity, which
is exactly backwards for a code search tool where rare identifiers are the valuable queries.
No GIN/`pg_trgm` index exists to fix it (confirmed: zero GIN/GiST indexes on user tables).

### Rank 4 — Every graph request hydrates the whole repository
*(`PostgreSQL integration-tested` for volumes; `source-reviewed` for the code path; end-to-end latency not measured)*

`scoped_edges` (`main.py:60`) loads **all** `SymbolEdge` rows for a repository into ORM
objects and sorts them in Python, on every call to `/graph`, `/subgraph`, `/callers`,
`/callees`, and `/documentation/generate`. `repository_graph` (`main.py:262-295`) additionally
loads all `File` entities (`scoped_files`, full `content`) and all `Symbol` entities (full
`source_text`). Measured row-data volumes for one request that returns **at most 100 nodes**:

| Loaded | Rows | Row data |
|---|---|---|
| `files` (incl. `content`) | 2 284 | 76.0 MB |
| `symbols` (incl. `source_text`) | 21 324 | 22.0 MB |
| `symbol_edges` | 136 566 | ~15 MB field bytes (84 MB table) |

≈113 MB transferred and hydrated into ~160 000 Python objects per graph page load. Raw
server-side scan of the edges alone measures 30.9 ms; ORM hydration of 136 566 instances
dominates that by an order of magnitude (reasoning, high confidence). All of it is discarded
except ≤100 nodes and their incident edges. The degree computation, the budget walk, and the
BFS are all Python loops over the full set (`main.py:270-280`, `248-259`).

### Rank 5 — `refresh_structural_cards` is O(cards × edges), added on integration, never measured
*(`source-reviewed` + arithmetic; `documented only / pending` for the runtime effect — integration only)*

```python
# structural_cards.py:30-39
for kind,path in [("directory",p) for p in paths]+[("package",p) for p in package_paths]:
 direct=[f for f in files if …]                       # O(files) per card
 owned={f.id for f in files if …}                     # O(files) per card
 for edge in edges:                                   # O(136 566) per card
  …
```

Measured card count inputs on the live corpus: 162 distinct directories (`paths` also
includes pure-container directories and `""`, so ≥163) plus 45 package paths ≈ **210+ cards ×
136 566 edges ≈ 28.7 M inner iterations**, each building a 4-tuple and two dict lookups, plus
a `sorted(boundary)` per card and ~1.4 M `PurePosixPath` allocations. My estimate is **+30 to
+90 s per index** on integration; this is *reasoning from measured cardinalities*, medium
confidence, and it has never been observed because the live stack does not run this code
(migration head `0004`, no `structural_cards` table). Commit `0413f2f` ("perf: avoid quadratic
symbol lookup in structural cards") already fixed the symbol lookup; the edge loop remains.

### Rank 6 — Per-symbol `flush()` and unbounded session growth
*(`source-reviewed`)*

`ingestion.py:97` flushes once per declaration — 21 324 round-trips per index, present in
both branches and in both measured runs. `_persist_edges` then accumulates 136 566 ORM
objects in one session before a single flush. Neither is the load-bearing cost (they are in
the 55 s baseline too), so they rank below everything above; `bulk_insert_mappings` or
`insert().values([...])` would remove them but should not be prioritised over ranks 1-3.

---

## 4. Simplicity audit

### On the density itself

`models.py` is 43 LOC for 12 tables, one semicolon-separated line per model.
`main.py` is 347 LOC for 42 routes. My honest read: **this is dense but mostly fine, and it
is not the project's problem.** The density is uniform, mechanical, and reversible — a
formatter run would expand it in seconds without changing behaviour. It genuinely helps in
one respect the mandate cares about: the whole API is reviewable exhaustively rather than by
sampling. I am not going to convert a style preference into a finding.

Where density crosses into *dangerous*, it is because it hides a real defect rather than
because it is ugly:

- `main.py:57` — `scoped_symbol` runs a SQL `WHERE repository_id=… AND id=…`, then re-checks
  both conditions in a Python `next(...)` generator over the result. The redundancy reads as
  belt-and-braces scope enforcement but is dead code; the same pattern recurs in
  `scoped_edges`, `scoped_symbols`, `scoped_files` (`main.py:60-62`). It makes a reviewer
  believe there are two independent scope checks where there is one.
- `ingestion.py:238` — a single line performs 11 assignments including two `datetime.utcnow()`
  calls and a subprocess (`run('git','branch','--show-current',…)`). A failure inside the
  subprocess aborts mid-commit-block.
- `search.py:58` — `parse_query(raw)` is called **twice** on the same line to build `q` and
  `terms`.
- `structural_cards.py:41` — `__import__('itertools').groupby(...)` inline, to avoid an
  import line. This is density for its own sake in the middle of the hottest loop in the
  module.

### Cut list — genuine over-engineering, in cut order

1. **`code_cards.py` (213 LOC) + `structural_cards.py` (52 LOC) + migrations `0005`/`0006` +
   `test_code_cards.py` (114) + `test_incremental_structural_cards.py` (45).** 424 LOC and two
   tables with **no consumer**: no UI reads them (`grep -rn "code-card\|structural-cards"
   apps/web` → nothing) and no MCP tool exposes them (`apps/mcp` is 181 LOC of client+server;
   nothing references cards). Code cards additionally gate on `code_cards_enabled=False`.
   16 % of the API's source is billable-provider machinery no user can reach.
   *Cut = stop investing, not delete*: the code is written and tested; leave it dormant, but
   it should not receive another commit until something reads it.
2. **ADR 0001 "Initial Contracts" (`CodeGraphStore` / `VectorSearchIndex` / `ProvenanceStore`).**
   Nine method signatures for three abstractions with zero implementations, over a backend
   the ADR itself says will not be migrated. The *decision* (Postgres is the source of truth;
   adapters must earn their place via the five-point validation gate) is excellent and costs
   nothing. The contract inventory is speculative API design that will be wrong by the time
   anything needs it. Delete the contract block, keep the decision and the gate.
3. **`SearchEngine` (`architecture.md`) and `CodeCardProvider` / `RerankProvider` protocol
   plans (`NEXT_STEPS.md` §3).** `RerankProvider` already exists as a `Protocol` with exactly
   one implementation (`providers.py:22-25, 28-49`) and `rerank_provider = "none"` by default —
   an interface for one product. Harmless (5 LOC), but the plan to add two more protocols
   before either has a second implementation is the rung-1 question unanswered.
4. **The graph fixture (`graph-explorer.tsx:11-24`).** Invents relationship types `renders`
   (0.94) and `handles` (0.87) that the backend cannot produce and fractional confidences the
   schema cannot store. It teaches the user a capability that does not exist. Replace with a
   real bounded subgraph from an indexed repository, or drop it.
5. **`deterministic_embedding` (`providers.py`, 8 LOC).** Docstring says "Test-only … never
   used by production indexing" — it belongs in `tests/`, not in the production module.

Deliberately **not** on the cut list, because they earn their keep: `verify_migration_ready`
(`db.py:18-30`) fails fast when the DB is behind head and directly implements the "no
start-time DDL" invariant (§5C); the `git_auth` / `git_askpass` split (95 + 16 LOC) keeps
tokens out of URLs and process arguments; `_snapshot_code_cards` / `_restore_code_cards`
keying cards on `(path, qualified_name, source_hash)` rather than symbol IDs is exactly right
and directly avoids billable regeneration.

### "Too thin" list — where laziness cut a corner that matters

1. **No index on four FK columns.** Rank-1 efficiency finding. Not a style issue; 548 s.
2. **`SymbolEdge` has no `resolver_type` / evidence-origin column** (`models.py:36-37`), while
   the concept doc requires one. Two integer values (100/20) are being asked to carry the
   entire evidence model.
3. **No test asserts the *absence* of a wrong edge.** `test_ingestion_graph.py:65-67` asserts
   a unique name resolves at 100 and a missing name at 20. Nothing asserts that an *ambiguous*
   name stays unresolved, and nothing asserts that a builtin-named call is not bound to an
   unrelated same-named symbol. The tests validate the happy path of the rule that produces
   the false positives.
4. **`POST /api/search/semantic` takes `body: dict`** (`main.py:303-306`) — no Pydantic model,
   no length bound on `query`, and it ignores `repository_id` entirely, so it is the one
   retrieval route with no scope parameter at all. Every other route has a typed model; this
   one was skipped.
5. **`text_search` has no `Query(...)` bounds** — `limit:int=30` is clamped in Python
   (`main.py:299`) rather than declared, so OpenAPI advertises an unbounded integer while
   sibling routes use `Query(50,ge=1,le=100)` (`main.py:193`). Contract and implementation
   disagree.
6. **`enqueue()` swallows every exception and returns `None`** (`main.py:49-51`), so
   `POST /api/repositories` returns `202` with `job_id: null` when Redis is down. The caller
   cannot distinguish "queued" from "silently dropped".
7. **`except Exception` swallowing in `search.py:94-97` and `114-116`** downgrades capability
   state without logging *what* failed — correct user-facing behaviour, but there is no
   `logger` in `search.py` at all, so provider failures are unobservable.
8. **`ingestion.py:240` writes `str(e)` into `repo.error_message` and `job.error_message`**
   for *any* exception. Git errors are redacted (`git_auth.redact_git_error`), but a Vertex
   error is not — `providers.py` interpolates `response.text` into a `RuntimeError`
   (`providers.py`, Vertex 400 branch), which then lands in a DB column served by
   `GET /api/repositories/{id}/status`. Flagged for the security workstream; noted here
   because it is the same "one line does eleven things" pattern.

---

## 5. Where the effort went versus where the value is

*This section is judgement. Confidence: high on the facts, medium-high on the priority call.*

`git diff --stat 5aedeb3 c122529` — 15 commits, 3 340 insertions across 52 files:

| Area | Insertions | Has a user-reachable consumer? |
|---|---|---|
| Docs (11 new/changed `.md`) | **1 393** | n/a |
| `code_cards.py` + `structural_cards.py` + 4 migrations | 362 | **No** |
| `benchmarks/` (scripts, manifests, results) | 386 | Internal only |
| `providers.py` (Vertex, Cohere rerank) | 162 | Rerank: `"none"` by default |
| API tests | 424 | n/a |
| `apps/web` (7 files incl. new symbol route) | 306 | Yes |
| `scripts/knowledge-way-transfer` | 82 | Yes |

Against that, the unfinished basics on the same branch:

- **No workspace UI at all.** `grep -rn workspace apps/web` → zero hits, while workspace-first
  is §2 of the mandate and the top-level product primitive. Zero workspaces have ever existed
  in the deployment.
- **Raw symbol UUID typed into a text input** (`graph-explorer.tsx`,
  `placeholder="symbol UUID for local graph"`), violating invariant §3.2.
- **No auth.** Not one route has an auth dependency; the only `Depends` in `main.py` is
  `get_db` (42 occurrences).
- **No browser E2E.** 890 LOC of Python tests, zero component or browser tests, for 543 LOC
  of web app.
- **Both P0 items in `ENGINEERING_BACKLOG.md`** ("Incremental sync correctness: use
  `git diff --name-status`", "Web repository management") remain unchecked, and `KW-004` is
  still open — while integration *removed* the one content-hash short-circuit that existed.

My read: the project is building the interesting layer before the necessary one, and the
docs-to-code ratio on this branch (1 393 doc lines to 1 947 code lines, with 424 of the code
lines unreachable) is the clearest signal. To be fair to the other side: the documents are
genuinely high quality and several are *load-bearing* for a review-first mandate — this very
review is only possible because `REPOSITORY_KNOWLEDGE_CONCEPT.md` states the resolution rule
precisely enough to be falsified. Writing down the concept honestly, then measuring against
it, is the right order. The failure is not that the docs exist; it is that the *measured*
gaps they name (incremental indexing, workspace UI, FTS) stayed open while two card systems
with no consumer were built, tested, and migrated.

---

## 6. Findings

| ID | Category | Severity | One-line |
|---|---|---|---|
| REV-901 | CORRECTNESS_RISK | critical | `confidence=100` means "bare name unique in repo"; ≥4 508 measurably fabricated call edges rendered as `call (100%)` |
| REV-902 | PERFORMANCE_RISK | critical | Four unindexed FK columns on `symbols.id` cause ≥85 % of the measured 12.7× re-index regression |
| REV-903 | PERFORMANCE_RISK | critical | Semantic retrieval fetches 5 477.8 MB of row data per query, unbounded, with Python cosine |
| REV-904 | DESIGN_GAP | high | Name-uniqueness resolution structurally excludes 41.5 % of symbols; the parser's `qualifier` evidence is discarded |
| REV-905 | CORRECTNESS_RISK | high | Integration removed the content-hash short-circuit: every index is now a full teardown; "incremental sync" is false |
| REV-906 | PERFORMANCE_RISK | high | No FTS/trigram index; measured 594 ms per worst-case `ILIKE` scan, up to 3 scans per hybrid query |
| REV-907 | DESIGN_GAP | high | Repository scope is post-filtered in Python after the SQL `LIMIT`; workspace-scoped search cannot be built on `search.py` |
| REV-908 | DOCUMENTATION_GAP | high | README/`architecture.md`/`CURRENT_STATUS.md`/ADR-0001 claim four capabilities and four abstractions that do not exist |
| REV-909 | DESIGN_GAP | high | Workspace-first has zero UI surface; exclusive membership + manual dependencies will need rework at cross-repo resolution |
| REV-910 | DESIGN_GAP | medium | `SymbolEdge` has no resolver/evidence-origin column, contradicting the project's own concept doc and blocking the layered roadmap |
| REV-911 | OPTIMIZATION_OPPORTUNITY | medium | Every graph request hydrates ~113 MB / 160 000 ORM objects to return ≤100 nodes |
| REV-912 | PERFORMANCE_RISK | medium | `refresh_structural_cards` is O(cards × edges) ≈ 28.7 M iterations, added on integration, never measured |
| REV-913 | DESIGN_GAP | medium | Code cards and structural cards (424 LOC, 2 tables, 4 migrations) have no UI or MCP consumer |
| REV-914 | TEST_GAP | medium | No test asserts the *absence* of a wrong edge; the false-positive rule is only tested on its happy path |
| REV-915 | DOCUMENTATION_GAP | low | Graph fixture invents relationship types and fractional confidences the product cannot produce |

---

### REV-901

- ID: REV-901
- Category: CORRECTNESS_RISK
- Severity: critical
- Evidence level: PostgreSQL integration-tested
- Applies to: both
- Concept or implementation: concept
- Impact: The product's central promise is evidence. Its most confident relationship claims
  are its least justified. A user or agent asking "who calls this?" receives 1 962 assertions
  that ordinary `list.append(...)` calls invoke `EnqueueGuard.append`, each with a real path
  and line number, labelled `call (100%)` and drawn with the thickest stroke. Filtering for
  "90 % or higher confidence" selects *precisely* the fabricated set. An agent acting on an
  impact analysis derived from this graph will edit the wrong code. This is the §7 forbidden
  claim ("Evidenzursprung oder Confidence") realised in the UI.
- Evidence:
  - `apps/api/app/ingestion.py:19-20` — `RESOLVED_CONFIDENCE=100`, `UNRESOLVED_CONFIDENCE=20`.
  - `apps/api/app/ingestion.py:122-135` — `candidates.setdefault(symbol.name, ...)` keyed on
    the **bare** name; `target = matches[0] if len(matches) == 1 else None`; confidence set
    from that boolean alone.
  - `apps/web/app/graph/graph-explorer.tsx` — `confidence! > 1 ? confidence!/100 : confidence!`.
  - `apps/web/app/graph/graph-canvas.tsx` — `linkLabel` → `` `${relationship} (${Math.round(confidence*100)}%)` ``;
    `relationshipStyle` → `width: (link.confidence ?? 0) >= 0.9 ? 2.2 : 1.4`.
  - Measured:
    ```sql
    select e.target_name, s.qualified_name, f.path, count(*) from symbol_edges e
      join symbols s on s.id=e.target_symbol_id join files f on f.id=s.file_id
     where e.relationship_type='call' and e.target_name in ('append','set','list','any','raises')
     group by 1,2,3 order by 4 desc;
    -- append 1962 → EnqueueGuard.append   (pydantic_ai_slim/.../durable_exec/_toolset.py)
    -- raises 1193 → raises                (tests/_inline_snapshot.py)
    -- set     550 → TestEnv.set            (tests/conftest.py)
    -- any     491 → SpanTree.any           (pydantic_evals/.../otel/span_tree.py)
    -- list    312 → AnalysisStore.list     (examples/.../slack_lead_qualifier/store.py)
    ```
    ≥4 508 wrong confidence-100 edges from a 15-name probe; 8 321 confidence-100 `call` edges
    resolve to a method (`qualified_name LIKE '%.%'`) with the receiver discarded.
- Probable cause + diagnostic confidence: **Certain.** The mechanism is three lines and the
  measurement is direct. `parser_facts.py:149-160` captures `ReferenceFact.qualifier`;
  `ingestion.py:137-140` never reads it, so `x.append()` and `append()` are indistinguishable
  at resolution time.
- Smallest safe next step: **Do not change resolution yet — change the label.** Stop emitting
  a percentage for `call`/`import` edges in the UI: render `resolved (name-unique)` /
  `unresolved` instead of `100%` / `20%`, and relabel the filter from "Minimum confidence" to
  "Resolution". Zero backend change, zero migration, removes the false claim immediately.
  Then, separately: in `_persist_edges`, refuse to resolve when `reference.qualifier is not
  None` and the qualifier cannot be tied to an in-repository declaration — a two-line guard
  that would drop most of the 8 321 method-name matches.
- Affected data/migrations/providers/cost: No migration for the UI fix. The resolution guard
  changes `symbol_edges` content on next index and would require a re-index to take effect
  (cost: one index run, no provider spend while `embedding_provider="none"`). Code cards are
  keyed on source hash and survive (`ingestion.py:39-79`).
- Recommended tests + acceptance criteria: (1) a fixture where a repo defines
  `class A: def run(self)` and `class B: def run(self)` and calls `a.run()` — assert the edge
  stays unresolved; (2) a fixture calling `items.append(x)` where the repo defines exactly one
  `append` method — assert **no** confidence-100 edge is created; (3) a UI/component test
  asserting no rendered edge label matches `/\d+%/` for a `call` relationship.
- Fix status: report-only

### REV-902

- ID: REV-902
- Category: PERFORMANCE_RISK
- Severity: critical
- Evidence level: PostgreSQL integration-tested
- Applies to: both
- Concept or implementation: implementation
- Impact: Re-indexing an unchanged repository takes 11 m 37 s instead of 55 s for
  byte-identical output. This is the defect that produced the original RQ `job_timeout` kill
  (`5767f63f`, failed at 453 s against a 180 s ceiling) and it is why both branches carry
  independent timeout workarounds (1 800 s on integration, 3 600 s on `main`'s working tree)
  instead of a fix. Cost scales with symbol count, so a repository 5× larger will not fit
  under either ceiling.
- Evidence:
  - `indexing_jobs`: `8c6ddf6e` full/ready 54.87 s (empty DB) vs `cf074b18` full/ready
    697.27 s (2 284 files present). Delta 642.4 s.
  - `apps/api/app/ingestion.py:223` — per file:
    `db.execute(delete(Symbol).where(Symbol.file_id==f.id)); db.execute(delete(CodeChunk).where(CodeChunk.file_id==f.id))`.
    Reached only when `existing` is non-empty, i.e. only on re-index. 21 324 symbol rows are
    deleted across 2 284 statements.
  - `docker compose exec -T postgres psql … -c "\d symbols"` — `Referenced by:`
    `code_chunks.symbol_id` (SET NULL), `symbol_edges.source_symbol_id`,
    `symbol_edges.target_symbol_id`, `symbols.parent_symbol_id`; `Indexes:` lists
    `symbols_pkey`, `ix_symbols_file_id`, `ix_symbols_name`, `ix_symbols_qualified_name`,
    `ix_symbols_repo_name`, `ix_symbols_repository_id` — **none of the four referencing
    columns is indexed.**
  - Measured per-row trigger cost:
    ```
    Seq Scan on symbols     WHERE parent_symbol_id=$1 → 11.759 ms (21 324 rows filtered)
    Seq Scan on code_chunks WHERE symbol_id=$1        → 13.964 ms (22 900 rows filtered)
    Seq Scan on symbol_edges WHERE source_symbol_id=$1 → 21.991 ms (136 566 rows filtered)
    ```
    (11.759+13.964) × 21 324 = 548 519 ms = **548 s = 85.4 % of the 642 s delta**. 10 862 of
    21 324 symbols have a non-null `parent_symbol_id`, so the self-FK is live, not vestigial.
- Probable cause + diagnostic confidence: **High.** PostgreSQL's RI triggers must locate
  referencing rows for every deleted referenced row; with no index that is a sequential scan
  per row. The arithmetic brackets the observed delta and no other mechanism in the delete
  branch is within an order of magnitude. Residual uncertainty: buffer-cache warmth and
  accumulating dead tuples inside the single long transaction move the true figure within the
  bracket, they do not change the cause.
- Smallest safe next step: one migration adding
  `ix_symbols_parent_symbol_id`, `ix_code_chunks_symbol_id`,
  `ix_symbol_edges_source_symbol_id`, `ix_symbol_edges_target_symbol_id` — ideally
  `CREATE INDEX CONCURRENTLY`. Four statements, no data change, trivially reversible.
  Separately (and better, per REV-905): stop deleting unchanged files at all.
- Affected data/migrations/providers/cost: New Alembic revision; ~5-10 MB of index; no data
  rewrite; no provider cost. Must not be applied while an index job is running.
- Recommended tests + acceptance criteria: `test_migrations.py` extension asserting the four
  indexes exist at head. Acceptance: a second full index of an unchanged repository completes
  within 2× the initial index time (target <110 s for this corpus), recorded in
  `indexing_jobs`. Add the duration assertion to `benchmarks/scripts/run_fork_e2e_nightly.py`
  so the regression cannot silently return.
- Fix status: report-only

### REV-903

- ID: REV-903
- Category: PERFORMANCE_RISK
- Severity: critical
- Evidence level: PostgreSQL integration-tested (volume); source-reviewed (call site)
- Applies to: both
- Concept or implementation: implementation (with a concept consequence: bounded retrieval is
  claimed as a design principle and is absent on this path)
- Impact: The first user who configures an embedding provider gets an API that transfers
  5.5 GB and performs 22 900 Python dot products per semantic query, on a single small
  repository. It will appear as an API timeout or an OOM in the API container, not as a slow
  query. It also breaks the mandate's own retrieval design ("lexical + symbol + vector
  retrieval (30-50 candidates)" — `REPOSITORY_KNOWLEDGE_CONCEPT.md`), because this path has
  no candidate bound at all.
- Evidence:
  - `apps/api/app/search.py:88` (and `main:apps/api/app/search.py:85`, verified identical
    shape): `db.execute(chunk_stmt().where(CodeChunk.embedding_model == provider.model).where(CodeChunk.embedding.is_not(None)))`
    — no `.limit()`, no `ORDER BY`.
  - `apps/api/app/search.py:62-66` — `chunk_stmt()` is `select(CodeChunk, File).join(File, …)`,
    so `File.content` is fetched per row.
  - `apps/api/app/search.py:40-43` — `_cosine` in pure Python.
  - Measured:
    ```sql
    select round(sum(length(c.source_text)+length(f.content))/1024.0/1024.0,1), count(*)
      from code_chunks c join files f on f.id=c.file_id;
    -- 5477.8 MB, 22 900 rows      (files.content total is only 76.0 MB → ~5.3 GB duplicated)
    ```
  - `apps/api/app/config.py:12` — `embedding_provider: str = "none"`, and the live DB has zero
    embeddings, which is why this has never been observed.
- Probable cause + diagnostic confidence: **Certain** as to the query shape and the volume;
  the end-to-end latency is unmeasured because no provider is configured (§4 cost gate). The
  in-code justification — *"Python cosine is portable to SQLite tests and pgvector
  production"* — indicates the cause is a deliberate test-portability choice.
- Smallest safe next step: two changes, both local to `search.py`. (1) Drop `File` from the
  semantic statement and fetch paths for the surviving top-N only. (2) Replace the Python
  cosine with pgvector's `<=>` operator plus `ORDER BY … LIMIT settings.rerank_candidate_limit`,
  keeping the Python path behind a branch used only by the SQLite unit tests. The
  `Vector()` column already exists (`models.py:29`).
- Affected data/migrations/providers/cost: No migration required for correctness, but an
  HNSW/IVFFlat index on `code_chunks.embedding` should follow, and it must be built per
  embedding model/dimension. No provider spend to fix or to test with
  `deterministic_embedding`.
- Recommended tests + acceptance criteria: a PostgreSQL integration test that inserts >5 000
  chunks with deterministic vectors and asserts the semantic path issues one statement with a
  `LIMIT` and returns in <200 ms. Acceptance: semantic query cost is O(limit), not O(corpus),
  verified by `EXPLAIN ANALYZE` showing an index scan and a bounded row count.
- Fix status: report-only

### REV-904

- ID: REV-904
- Category: DESIGN_GAP
- Severity: high
- Evidence level: PostgreSQL integration-tested
- Applies to: both
- Concept or implementation: concept
- Impact: The resolution rule cannot express the relationships users most want. Any symbol
  sharing a bare name with any other symbol anywhere in the repository is permanently
  unreachable as an edge target — 8 842 of 21 324 symbols (41.5 %), including all 380
  `__init__` methods, so no constructor call is ever traceable. "Navigate structural
  relationships" is therefore supportable only for uniquely-named top-level declarations. The
  measured 136 566-row edge table conveys richness it does not have: 19 806 rows lack a source
  endpoint and cannot appear in any subgraph, and of the remainder the confident half is
  contaminated per REV-901. §7 forbids claiming a complete call graph; the docs comply, but
  the *product* offers "Callers"/"Callees"/"Impact" views built on this.
- Evidence:
  - `apps/api/app/ingestion.py:122-129` — resolution keyed on `Symbol.name`, single-match only.
  - `apps/api/app/parser_facts.py:149-160` — `ReferenceFact.qualifier` computed for attribute
    calls; `apps/api/app/ingestion.py:137-140` never reads it.
  - Measured:
    ```sql
    with n as (select name, count(*) c from symbols group by 1)
    select count(*) filter (where c=1), count(*) filter (where c>1),
           sum(c) filter (where c>1), sum(c) from n;
    -- unique_names 12482 | ambiguous_names 1426 | symbols_unreachable 8842 | total 21324
    select count(*) from symbols where name='__init__';   -- 380
    select count(*) from symbol_edges where source_symbol_id is null;  -- 19 806
    ```
  - `apps/api/app/main.py:230, 245, 267` — `callers`/`callees`/`subgraph`/`graph` all require
    both endpoints, so the 19 806 half-edges are invisible to every graph view.
- Probable cause + diagnostic confidence: **Certain.** This is the documented, intentional
  rule (`REPOSITORY_KNOWLEDGE_CONCEPT.md`: "Resolution rule: … unique inside the same
  repository"), chosen for conservatism. My judgement — stated as judgement, high confidence —
  is that it is the *wrong* conservative rule: bare-name uniqueness is simultaneously too
  permissive (binds builtins) and too restrictive (drops every method). Scope-aware
  resolution — same-file declarations, then imported names via the already-parsed `ImportFact`
  set, then unresolved — would be both safer and more useful, and the facts it needs are
  already collected.
- Smallest safe next step: raise the qualifier guard from REV-901 first (removes false
  positives without adding machinery). Then, as one bounded change, resolve calls against
  (a) declarations in the same file, then (b) names the file actually imports, per
  `facts.imports` — and leave everything else unresolved. No new tables.
- Affected data/migrations/providers/cost: `symbol_edges` content changes; a re-index is
  required. Adding `resolver_type` (REV-910) should land in the same migration so the new
  edges record how they were resolved.
- Recommended tests + acceptance criteria: a multi-class fixture asserting (1) same-name
  methods in different classes never cross-resolve, (2) an imported name resolves only when
  the import is present in that file, (3) resolved-edge count and unresolved-edge count are
  both asserted, so a future change that "improves" recall by re-adding false positives fails.
  Acceptance: on the pydantic-ai corpus, zero confidence-100 edges target `append`, `list`,
  `set`, or `any`.
- Fix status: report-only

### REV-905

- ID: REV-905
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: source-reviewed
- Applies to: integration (regression relative to `main`)
- Concept or implementation: implementation, with a documented-claim consequence
- Impact: Integration deleted the only incremental short-circuit that existed. On `main`, a
  `sync` (`full=False`) skipped files whose `content_hash` matched. On integration, *every*
  index of *every* kind deletes and re-parses every file, so a no-op sync costs the full
  697 s and rewrites 21 324 symbol rows and 22 900 chunk rows for no change. This amplifies
  REV-902 from "slow re-index" to "slow every sync", makes `README.md`'s "Incremental Git
  synchronization with content-hash deduplication" false, and violates `KW-004`'s own
  acceptance criterion "No-op sync does not generate vectors or mutate graph cardinality."
- Evidence:
  - `main:apps/api/app/ingestion.py` — `if f and f.content_hash==digest and not full: continue`
  - `apps/api/app/ingestion.py:222` (integration) —
    `if f and f.content_hash==digest: f.indexed_commit_sha=sha` — **the `continue` is gone**,
    so line 223's delete-and-reparse executes unconditionally.
  - `git diff main:apps/api/app/ingestion.py c122529:apps/api/app/ingestion.py` shows the
    replacement directly.
  - `README.md` "MVP capabilities" bullet 2; `docs/ENGINEERING_BACKLOG.md` P0 "Incremental
    sync correctness: use `git diff --name-status <indexed SHA>..<HEAD>`" — still unchecked;
    `backlog/KW-004-incremental-git-indexing.md` — still open.
  - `ingestion.py:203-207` — the file walk is still a full `rglob` with `read_text` of every
    file; no `git diff` is ever invoked.
- Probable cause + diagnostic confidence: **High.** The rewrite's evident intent was to make
  `indexed_commit_sha` advance on unchanged files (a real bug on `main`: an unchanged file
  kept a stale commit SHA, weakening exactly the provenance the thesis needs). The fix
  addressed that by falling through to the rebuild instead of updating the SHA and then
  continuing. The correct form is one line: set the SHA **and** `continue`. Residual
  uncertainty: whether structural cards need the symbols re-created (they read from the DB,
  so no).
- Smallest safe next step: restore the short-circuit *including* the SHA update —
  `if f and f.content_hash==digest: f.indexed_commit_sha=sha; continue` — being careful that
  `existing.pop(path)` has already removed it from the deletion set (it has, line 221).
- Affected data/migrations/providers/cost: No migration. Directly avoids re-embedding
  unchanged chunks, so it is also a provider-cost fix once embeddings are enabled.
- Recommended tests + acceptance criteria: extend
  `apps/api/tests/test_incremental_structural_cards.py` with a no-op re-index asserting
  (1) `symbols.id` values are unchanged for untouched files, (2) `indexed_commit_sha` is
  advanced, (3) edge and chunk cardinality is identical. This is the `KW-004` acceptance
  criterion, testable today without `git diff` support.
- Fix status: report-only

### REV-906

- ID: REV-906
- Category: PERFORMANCE_RISK
- Severity: high
- Evidence level: PostgreSQL integration-tested
- Applies to: both
- Concept or implementation: implementation
- Impact: Search latency is inversely proportional to term rarity — the opposite of what a
  code search tool needs, since rare identifiers are the valuable queries. A miss costs
  ~1.2 s of sequential scanning on one 2 284-file repository and scales linearly with corpus
  size. Two documents claim this is already indexed, so the gap is invisible to planning.
- Evidence:
  - Measured worst case:
    ```
    EXPLAIN ANALYZE … WHERE c.source_text ILIKE '%zzzznotpresent%' LIMIT 60;
      Seq Scan on code_chunks   Rows Removed by Filter: 22900
      Buffers: shared hit=4766 read=13423     Execution Time: 593.756 ms
    ```
    Matching term for contrast: `ILIKE '%retry%'` → 10.511 ms (LIMIT short-circuits after 725
    rows). Symbol scan: 4.088 ms.
  - `apps/api/app/search.py:68` (exact, `limit*2`), `:73` (term-OR, `limit*8`), `:78` (symbols,
    `limit*3`) — up to three scans per hybrid query; the term-OR path runs only when the exact
    path returns nothing, i.e. exactly in the miss case.
  - `select count(*) from pg_indexes where indexdef like '%gin%' or indexdef like '%gist%'`
    → 2, both in `pg_catalog`. No text index exists on any user table.
  - `README.md` claims "full-text search"; `docs/architecture.md` claims "PostgreSQL
    full-text/trigram candidate retrieval".
- Probable cause + diagnostic confidence: **Certain.** `ILIKE '%…%'` is unindexable without
  `pg_trgm`; the extension is not enabled and no index exists.
- Smallest safe next step: `CREATE EXTENSION pg_trgm` plus a GIN trigram index on
  `code_chunks.source_text` and `symbols.name`/`qualified_name` in one migration. No
  application change is needed — the planner will use it for `ILIKE '%…%'`. Correct the two
  documentation claims in the same change so they describe the state after it.
- Affected data/migrations/providers/cost: One migration; a trigram GIN index over 176 MB of
  chunk text is substantial (expect 50-150 MB) and slows inserts, which matters given
  REV-902/905 rewrite everything on each index — so land REV-905 first. No provider cost.
- Recommended tests + acceptance criteria: `test_migrations.py` asserts the extension and
  indexes at head. Acceptance: `EXPLAIN ANALYZE` for a non-matching `ILIKE` shows a Bitmap
  Index Scan and completes in <20 ms; add a query-latency assertion to
  `benchmarks/scripts/verify_live_queries.py`.
- Fix status: report-only

### REV-907

- ID: REV-907
- Category: DESIGN_GAP
- Severity: high
- Evidence level: source-reviewed
- Applies to: both
- Concept or implementation: concept
- Impact: `search.py` cannot express scope. The repository filter runs in Python after the SQL
  `LIMIT`, so with more than one repository a scoped query silently returns fewer or zero
  results depending on which rows the unscoped `LIMIT` happened to take. Workspace-scoped
  search — invariant §2.5 and the top-level product primitive — cannot be added to this
  function; it requires re-founding it on SQL-side scope predicates. Building the workspace UI
  on top of it first would ship a workspace that appears to filter and does not.
- Evidence:
  - `apps/api/app/search.py:61` — `def allowed(repo): return repo and (not repository_id or repo.id == repository_id) …`
  - `apps/api/app/search.py:68` — `.limit(limit * 2)` with no `repository_id` predicate; the
    filter is applied in the Python loop body immediately after.
  - Same shape at `:73` (`limit*8`) and `:78` (`limit*3`).
  - `apps/api/app/search.py:59` — `repos = {r.id: r for r in db.scalars(select(Repository)).all()}`
    loads every repository unconditionally.
  - `apps/api/app/main.py:303-306` — `POST /api/search/semantic` accepts `body: dict` and
    never passes `repository_id`, so it has no scope parameter at all.
  - Not currently observable: the live DB has one repository, so the post-filter is a no-op.
- Probable cause + diagnostic confidence: **Certain** as to the code shape; **high** on the
  consequence (single-repository deployment masks it entirely). This is a design shortcut that
  was correct for one repository and is load-bearing wrong for the stated product.
- Smallest safe next step: thread an explicit `repository_ids: set[str] | None` through
  `search_with_capability` and add `.where(CodeChunk.repository_id.in_(ids))` /
  `Symbol.repository_id.in_(ids)` to all three statements *before* `.limit()`. Derive the set
  server-side from workspace membership (§3.1). Keep the Python `allowed()` only for the
  `repo:` text filter, which is a name substring match and genuinely post-hoc.
- Affected data/migrations/providers/cost: No migration. Changes result sets in multi-repo
  deployments — which is the point.
- Recommended tests + acceptance criteria: a two-repository fixture where repo A contains
  `limit*8 + 1` matches for a term and repo B contains exactly one; assert a scoped query for
  repo B returns that one result. This test fails today and is the acceptance gate for any
  workspace-scoped search work.
- Fix status: report-only

### REV-908

- ID: REV-908
- Category: DOCUMENTATION_GAP
- Severity: high
- Evidence level: source-reviewed
- Applies to: both
- Concept or implementation: implementation (docs), with concept consequence
- Impact: Four capability claims and four named abstractions do not exist, and two sibling
  docs contradict each other on the same facts. Planning and this review both had to
  re-derive the truth from code. The mandate's §10 acceptance criterion — no unsupported
  claims about performance, snapshots, or E2E — is currently failed by the repository's own
  documentation. `CURRENT_STATUS.md` in particular is worse than no document: it understates
  the product (claims regex extraction and no persisted embeddings) while `NEXT_STEPS.md`
  overstates it (claims workspace dependencies are a "verified baseline" with no UI).
- Evidence:
  - "full-text search" — `README.md`; "PostgreSQL full-text/trigram candidate retrieval" —
    `docs/architecture.md`. Contradicted by `search.py:68,73,77` and zero GIN/GiST indexes.
  - "Incremental Git synchronization with content-hash deduplication" — `README.md`.
    Contradicted by `ingestion.py:222` (REV-905).
  - "Grounded chat answers" — `README.md`. `main.py:332` returns a constant string naming
    `OPENAI_API_KEY` while the provider stack is Vertex/OpenRouter (`providers.py`).
  - `SearchEngine` — `docs/architecture.md`. `grep -rl SearchEngine apps packages` → no hits.
  - `CodeGraphStore`, `VectorSearchIndex`, `ProvenanceStore`, `get_bounded_subgraph`,
    `find_impact` — `docs/adr/0001-storage-backend-adapters.md` "Initial Contracts".
    `grep -rl` for each → no hits. ADR decision 2 ("services use storage contracts, not
    backend-specific calls") is contradicted by `main.py:14` importing 13 model classes into
    route handlers.
  - `CodeCardProvider` — `docs/NEXT_STEPS.md` §3. No hits.
  - `docs/CURRENT_STATUS.md` ("embeddings are not yet persisted", "conservative
    declaration-aware regex extraction") vs `docs/NEXT_STEPS.md` "Verified baseline"
    ("Tree-sitter symbols", "Vertex AI is live") and `models.py:29` (`Vector()` column).
  - `README.md` contains a duplicated paragraph (the demo-playbook sentence appears twice).
- Probable cause + diagnostic confidence: **Certain.** Documents were written aspirationally
  and at different times, and `CURRENT_STATUS.md` was never updated after the tree-sitter and
  embedding work landed.
- Smallest safe next step: delete `docs/CURRENT_STATUS.md` (it is superseded by
  `NEXT_STEPS.md` and `HANDOFF.md`, and a wrong status doc is a liability); remove the
  "Initial Contracts" block from ADR 0001 while keeping the decision and the validation gate;
  correct the four `README.md`/`architecture.md` claims to describe `ILIKE`, full re-parse,
  and retrieval-only answers.
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: a docs check in CI that greps every backticked
  identifier in `docs/architecture.md` and `docs/adr/` against the source tree and fails on a
  name with no definition. Cheap, and it is the only mechanical defence against this class.
- Fix status: report-only

### REV-909

- ID: REV-909
- Category: DESIGN_GAP
- Severity: high
- Evidence level: source-reviewed
- Applies to: both
- Concept or implementation: concept
- Impact: Workspace-first is the stated top-level user decision (§2) and has **no UI surface
  whatsoever** — the string "workspace" does not occur anywhere in `apps/web`. It cannot be
  exercised in a browser, and no workspace has ever existed in this deployment. Beyond the
  missing UI, two modelling choices will need rework once real cross-repo resolution arrives:
  (a) **exclusive membership** (`UniqueConstraint('repository_id')`) means a shared SDK
  repository cannot belong to two products' workspaces without being indexed twice, which is
  the common multi-repo case the feature exists to serve; (b) **manually declared
  dependencies** live in a separate table from verified edges, which is correct today per
  §3.4 — but the moment `manifest_dependency` and `cross_repo_import` arrive there will be two
  parallel dependency representations to reconcile, and `REPOSITORY_KNOWLEDGE_CONCEPT.md`
  already lists five relation types that all need the origin/confidence fields
  `WorkspaceDependency` lacks.
  My judgement, medium-high confidence: the manual/verified distinction **is** sustainable in
  the data model but **will** be misread in the product, because the only place a user can see
  a dependency is a graph whose other edges are labelled `100%`. A `declared_dependency`
  rendered next to a `call (100%)` edge will read as the weaker claim of the two, when it is
  in fact the better-evidenced one (a human asserted it; the other was a name collision).
- Evidence:
  - `grep -rn workspace apps/web --include='*.tsx' --include='*.ts'` → **no hits**.
  - `apps/api/app/main.py:74-146` — 13 workspace routes exist (CRUD, membership, dependencies).
  - `apps/api/app/models.py:16` —
    `UniqueConstraint('repository_id', name='uq_workspace_repositories_repository_id')`.
  - `apps/api/app/models.py:18-20` — `WorkspaceDependency` has `package_name`, `import_path`,
    `reason`, `note` but **no** `origin`/`evidence_type`/`confidence` column, while
    `REPOSITORY_KNOWLEDGE_CONCEPT.md` §1 requires "`declared_dependency` | `manifest_dependency`
    | `workspace_reference` | `api_contract` | `runtime_endpoint`" each with "its evidence and
    confidence in the UI/MCP response".
  - No workspace-scoped graph or search endpoint exists (`main.py` has no
    `/api/workspaces/{id}/graph` and `search.py` takes only `repository_id`).
  - Live DB: `workspaces` 0 rows.
- Probable cause + diagnostic confidence: **Certain** on the missing UI and the constraint;
  the rework prediction is **judgement, medium-high confidence**, grounded in the fact that
  the project's own concept doc already specifies five relation types the table cannot store.
- Smallest safe next step: before any workspace UI, add `origin`
  (`manual|manifest|configuration`) to `WorkspaceDependency` — one nullable column defaulting
  to `'manual'`, cheap now, and it is the field every later relation type needs. Then decide
  the exclusive-membership question explicitly (it is a product decision, §11.2), because the
  UI shape depends on the answer. Do not build the switcher until REV-907 gives scope a
  server-side home.
- Affected data/migrations/providers/cost: One additive nullable column; zero rows to
  backfill (0 workspaces exist), so this is the cheapest it will ever be.
- Recommended tests + acceptance criteria: existing `test_workspaces_api.py` (67 LOC) covers
  membership rules; add (1) a test that a `declared_dependency` is never serialised with a
  `confidence` field or a `calls`/`imports` relationship type (invariant §3.4), and (2) the
  two-repository scope-isolation test from REV-907. Acceptance: the mandate's E2E path
  (create workspace → add repo → scoped search → switch workspace → verify isolation) is
  executable in a browser.
- Fix status: report-only

### REV-910

- ID: REV-910
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both
- Concept or implementation: concept
- Impact: `SymbolEdge` cannot record *how* an edge was derived. A single `confidence` integer
  with two values (100/20) is carrying the whole evidence model, which is why REV-901 was
  possible: there is no field in which "unique bare name in repository" could have been
  written, so it was encoded as certainty. Every item on the cross-repo roadmap
  (`manifest_dependency`, `cross_repo_import`, `api_contract`, `runtime_endpoint`) and every
  future resolver (same-file, import-scoped, SCIP/LSP) needs this column to coexist with the
  current one. Adding it after another N repositories are indexed means a migration over rows
  whose provenance is unrecoverable — the current 136 566 rows already cannot be classified
  retroactively.
- Evidence:
  - `apps/api/app/models.py:36-37` — `SymbolEdge` columns: `repository_id`,
    `source_symbol_id`, `target_symbol_id`, `target_name`, `relationship_type`,
    `source_file_id`, `line_number`, `confidence`. No resolver, origin, or parser-version
    column, despite `parser_facts.py:14` defining `PARSER_VERSION = "kw-003-tree-sitter-v1"`
    and never persisting it.
  - `docs/REPOSITORY_KNOWLEDGE_CONCEPT.md` §3 — "An edge should retain: source, target (or
    unresolved target spelling), source location, **resolver type**, confidence, and index
    commit." Four of six are present.
  - `select distinct confidence from symbol_edges` → exactly `{20, 100}`.
  - `docs/ideas/hierarchical-code-cards.md` — the folder-facts design depends on "Resolver-
    und Parser-Version, Confidence" per relationship, which the schema cannot supply.
- Probable cause + diagnostic confidence: **Certain** as to the absence; **high** confidence
  that it is the enabling condition for REV-901 rather than an independent gap.
- Smallest safe next step: one additive migration adding
  `resolver: str` (e.g. `unique_name`, `same_file`, `imported`, `unresolved`) and
  `parser_version: str`, populated at insert in `_persist_edges`. Land it together with
  REV-902's indexes and REV-904's resolution change so there is exactly one `symbol_edges`
  migration and one re-index.
- Affected data/migrations/providers/cost: Additive columns; existing 136 566 rows can only
  be backfilled to `unique_name`/`kw-003-tree-sitter-v1`, which is accurate for them. One
  re-index. No provider cost.
- Recommended tests + acceptance criteria: assert every persisted edge has a non-null
  `resolver`, and that the API serialises `resolver` alongside `confidence` so the UI can
  label rather than percentage-ise. Acceptance: `GET …/subgraph` response includes a resolver
  string per edge.
- Fix status: report-only

### REV-911

- ID: REV-911
- Category: OPTIMIZATION_OPPORTUNITY
- Severity: medium
- Evidence level: PostgreSQL integration-tested (volumes); source-reviewed (path)
- Applies to: both
- Concept or implementation: implementation
- Impact: Every graph, caller, callee and documentation request hydrates the entire
  repository into Python to return at most 100 nodes. Measured row-data volume ≈113 MB and
  ≈160 000 ORM instances per `/api/repositories/{id}/graph` call. The endpoint is correct and
  deterministically bounded in its *output* — the budget walk and tie-breaking at
  `main.py:273-280` are careful work — but its *input* is unbounded, so response time and API
  memory grow with repository size while the answer stays the same size. This is the most
  likely cause of a slow or OOM graph page on a large repository.
- Evidence:
  - `apps/api/app/main.py:60` — `scoped_edges` loads all `SymbolEdge` rows for the repository
    and Python-sorts them. Called from `neighbors` (`:230`), `subgraph` (`:245`),
    `repository_graph` (`:267`), `documentation` (`:320`).
  - `apps/api/app/main.py:62` — `scoped_files` loads full `File` entities including `content`.
  - `apps/api/app/main.py:268` — all `Symbol` entities including `source_text`.
  - Measured:
    ```
    files      2 284 rows,   76.0 MB content
    symbols   21 324 rows,   22.0 MB source_text
    symbol_edges 136 566 rows (84 MB table; raw scan 30.9 ms server-side)
    ```
  - `apps/api/app/main.py:270-280` — degree computation and budget walk are Python loops over
    the full symbol and edge sets.
- Probable cause + diagnostic confidence: **High** on the mechanism and volumes; the
  end-to-end request latency was not measured (the live `main` graph endpoint differs from
  integration's, and I did not want to attribute a `main` measurement to `c122529`). ORM
  hydration dominating the 30.9 ms raw scan by an order of magnitude is reasoning, high
  confidence.
- Smallest safe next step: two narrow changes with no behaviour change. (1) In
  `scoped_files`/`scoped_symbols`/`repository_graph`, use `load_only(...)` to exclude
  `File.content` and `Symbol.source_text` — the graph response never returns file content, and
  `symbol_out` includes `source_text` only for node payloads that could be fetched per node.
  (2) Push `source_symbol_id IS NOT NULL AND target_symbol_id IS NOT NULL` into SQL, since
  every caller filters on it in Python immediately after (`:230, :245, :267`) — that alone
  removes 19 806 rows (14.5 %) from every graph request.
- Affected data/migrations/providers/cost: No migration. Combines well with REV-902's edge
  indexes, which would additionally allow `neighbors` to query by endpoint instead of scanning.
- Recommended tests + acceptance criteria: assert `GET …/graph?max_nodes=100` issues no query
  selecting `files.content`, and completes within a fixed budget against the 2 284-file
  fixture. Acceptance: request cost is a function of `max_nodes`, not repository size.
- Fix status: report-only

### REV-912

- ID: REV-912
- Category: PERFORMANCE_RISK
- Severity: medium
- Evidence level: source-reviewed (runtime effect: documented only / pending)
- Applies to: integration
- Concept or implementation: implementation
- Impact: Integration adds an unconditional pass over the edge table once per structural card
  to every index run, on both the `full` and `sync` paths. Estimated +30 to +90 s per index on
  the current corpus, on top of REV-902 and REV-905. It has never been measured because the
  live stack is at migration `0004` and has no `structural_cards` table, so this cost is
  invisible to the only timing data that exists.
- Evidence:
  - `apps/api/app/structural_cards.py:30-39` — outer loop over
    `[("directory",p) for p in paths] + [("package",p) for p in package_paths]`; inner
    `for edge in edges` over all repository edges; `direct`, `child_paths` and `owned` each
    iterate all files per card.
  - `apps/api/app/structural_cards.py:41` — `sorted(boundary)` per card, plus
    `__import__('itertools').groupby` inline in the hot loop.
  - `apps/api/app/ingestion.py:235` — `refresh_structural_cards(db, repo_id, sha)` called
    unconditionally, i.e. also on `sync`.
  - Measured cardinalities on the live corpus (same repo/commit): 162 distinct directories
    (`paths` also includes container-only directories and `""`), 45 package directories,
    2 284 files, 136 566 edges → **≥210 cards × 136 566 = ≈28.7 M inner iterations**, plus
    ≈480 K file iterations and ≈1.4 M `PurePosixPath` allocations.
  - `git log --oneline 5aedeb3..c122529` — `0413f2f perf: avoid quadratic symbol lookup in
    structural cards` already addressed the symbol lookup; the edge loop was not changed.
- Probable cause + diagnostic confidence: **Certain** on the complexity class and the
  cardinalities; the 30-90 s estimate is **reasoning from measured counts, medium
  confidence** — it has not been executed. Labelling it precisely: the *cost class* is
  source-reviewed fact, the *seconds* are an estimate.
- Smallest safe next step: invert the loop — iterate edges **once**, computing each edge's
  source and target directory, and accumulate boundary aggregates into a
  `dict[path, list]` keyed by the ancestor directories of both endpoints. Single pass over
  edges, same output. Roughly the same line count as the current version.
- Affected data/migrations/providers/cost: None; `structural_cards` content must be
  byte-identical, which the existing `content_fingerprint` makes directly assertable.
- Recommended tests + acceptance criteria: `test_incremental_structural_cards.py` already
  checks fingerprint stability — extend it to assert identical `content_fingerprint` values
  before and after the loop inversion, and add a timing assertion against a fixture with
  >10 000 edges. Acceptance: card generation time is O(edges + cards), not O(edges × cards).
- Fix status: report-only

### REV-913

- ID: REV-913
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: integration
- Concept or implementation: concept (prioritisation)
- Impact: 424 LOC, two tables, four migrations and two provider integrations exist for a
  capability no user or agent can reach, while workspace-first (§2) has no UI and the graph
  still demands a raw UUID (§3.2). This is the clearest instance of the interesting layer
  preceding the necessary one. Concretely it also raises risk: code cards are the only
  billable path in the system, and `_snapshot_code_cards`/`_restore_code_cards` add complexity
  to `index_repository` — the hottest, most defect-prone function in the codebase — to protect
  data nothing displays.
- Evidence:
  - `apps/api/app/code_cards.py` (213 LOC), `apps/api/app/structural_cards.py` (52 LOC),
    migrations `20260809_0005_code_cards.py`, `20260809_0006_structural_cards.py`,
    `apps/api/tests/test_code_cards.py` (114 LOC),
    `apps/api/tests/test_incremental_structural_cards.py` (45 LOC).
  - `grep -rln "structural-cards\|code-card" apps/web apps/mcp` → **no hits.** No UI view and
    no MCP tool reads either table. `apps/mcp` is 181 LOC (server 57, client 124).
  - `apps/api/app/config.py` — `code_cards_enabled: bool = False`; live DB has no
    `code_cards` table at all (head `0004`).
  - `grep -rn workspace apps/web` → no hits; `graph-explorer.tsx` still has
    `placeholder="symbol UUID for local graph"`.
  - `docs/ENGINEERING_BACKLOG.md` P0 "Web repository management" and "Incremental sync
    correctness" — both unchecked.
  - `git diff --stat 5aedeb3 c122529` — 3 340 insertions, of which 1 393 are documentation and
    424 are unreachable card code.
- Probable cause + diagnostic confidence: **Certain** on the absence of consumers. The
  prioritisation criticism is **my judgement, medium-high confidence**; the counter-argument I
  accept is that the card work is genuinely well built (bounded concurrency, `extra="forbid"`
  response validation, source-hash keying, 429/`Retry-After` handling) and that structural
  cards are the deterministic foundation `docs/ideas/hierarchical-code-cards.md` needs.
- Smallest safe next step: nothing to delete. **Freeze**: no further commits to
  `code_cards.py` or `structural_cards.py` until one consumer exists. The cheapest consumer
  that would justify the structural-cards table is a single MCP tool
  (`get_structural_card(repository_id, path)`) — the endpoint already exists at
  `main.py:192-206`, so this is a few lines in `apps/mcp`.
- Affected data/migrations/providers/cost: None if frozen. Code cards remain the only billable
  path and stay behind `code_cards_enabled=False`.
- Recommended tests + acceptance criteria: n/a for a freeze. If a consumer is added, the
  acceptance criterion is the mandate's: an agent answers a repository question citing a
  structural card *and* the source evidence behind it.
- Fix status: report-only

### REV-914

- ID: REV-914
- Category: TEST_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both
- Concept or implementation: implementation
- Impact: The test suite validates the resolution rule only where it succeeds, so REV-901's
  false positives are not merely unfixed — they are *protected*. Any future change that
  reduces over-resolution will look like a regression against the current assertions, and any
  change that increases it will pass. For a product whose thesis is evidence, the missing test
  is the one that asserts the system declines to claim.
- Evidence:
  - `apps/api/tests/test_ingestion_graph.py:65` —
    `assert by_target["shared"].confidence == ingestion.RESOLVED_CONFIDENCE`
  - `apps/api/tests/test_ingestion_graph.py:67` —
    `assert by_target["missing"].confidence == ingestion.UNRESOLVED_CONFIDENCE`
  - No test in the file constructs two symbols with the same bare name and asserts a call
    stays unresolved; no test asserts a builtin-named call is not bound. Test names in the
    file: `…parser_graph_with_safe_resolution_and_source_provenance`,
    `…clears_old_edges_before_rebuilding`, `…preserves_unchanged_code_cards`,
    `…prunes_empty_structural_chunks`, `…checks_out_requested_immutable_revision`.
  - No test asserts re-index duration or edge cardinality stability (REV-902, REV-905).
  - 890 LOC of Python tests, 0 browser/component tests for 543 LOC of web app, so the
    `call (100%)` label has no test at all.
- Probable cause + diagnostic confidence: **Certain.** Tests were written to demonstrate the
  feature works, which is the normal and understandable failure mode; the adversarial cases
  were never added.
- Smallest safe next step: add two assertions to the existing fixture in
  `test_ingestion_graph.py` — one ambiguous name stays unresolved, one builtin-named call
  produces no confidence-100 edge. Both are a few lines in a file that already builds the
  fixture repository.
- Affected data/migrations/providers/cost: None. Both tests run on SQLite with no provider.
- Recommended tests + acceptance criteria: as above, plus a cardinality snapshot test
  (resolved/unresolved counts per relationship type) so any resolution change must state its
  effect explicitly. Acceptance: the new tests fail against current `_persist_edges` and pass
  after REV-901/REV-904.
- Fix status: report-only

### REV-915

- ID: REV-915
- Category: DOCUMENTATION_GAP
- Severity: low
- Evidence level: source-reviewed
- Applies to: both
- Concept or implementation: implementation
- Impact: The graph fixture teaches capabilities the product does not have. It is correctly
  labelled "Fixture demo" in the summary line, so §5D's "fixture must never be mistaken for
  real data" is met — but it displays relationship types (`renders`, `handles`) that no
  resolver can produce and fractional confidences (0.94, 0.87) that the schema cannot store.
  A demo audience will reasonably conclude the system infers render and route-handler
  relationships with 94 % confidence.
- Evidence:
  - `apps/web/app/graph/graph-explorer.tsx:11-24` — fixture nodes/links, including
    `{ source: 'search-page', target: 'search-client', relationship: 'renders', confidence: 0.94 }`
    and `{ source: 'search-client', target: 'search-route', relationship: 'handles', confidence: 0.87 }`.
  - `select distinct relationship_type from symbol_edges` → `{call, import}` only;
    `select distinct confidence` → `{20, 100}` only.
  - `apps/api/app/main.py:288-293` — the only other relationship strings the API emits are
    `contains` and `defines`, both at `confidence: 1`.
  - `docs/HANDOFF.md` states "initial keine Fake-Daten; Fixture-Demo bleibt nur über den
    expliziten Button verfügbar" — the labelling intent is deliberate and honoured.
- Probable cause + diagnostic confidence: **Certain.** The fixture predates the real graph
  endpoint and was kept as an offline demo without being brought in line with the schema.
- Smallest safe next step: restrict the fixture's relationships to `contains`, `defines`,
  `call`, `import` and its confidences to `1`, `100`, `20`. Three edited lines. Better: delete
  the fixture, since `requestOverview()` now provides a real bounded repository map
  (`graph-explorer.tsx`, `/graph?max_nodes=100`).
- Affected data/migrations/providers/cost: None.
- Recommended tests + acceptance criteria: a component test asserting every fixture
  relationship string is a member of the API's emitted set. Acceptance: no rendered
  relationship label can exist that the backend cannot produce.
- Fix status: report-only

---

## 7. Single highest-leverage change

*This is my opinion, stated as such, with the reasoning visible.*

**Delete the percentage. Stop rendering `confidence` as a percentage anywhere in the UI, and
replace it with a resolution label (`resolved (name-unique)` / `unresolved`).**

Reasoning, in the order I weighed it:

1. **It is the only change that repairs the thesis rather than the plumbing.** Every other
   finding here is about speed, missing UI, or stale docs. REV-901 is about the product
   telling users something false, confidently, with a citation attached. A code-intelligence
   platform whose distinguishing claim is evidence cannot ship a view where its weakest
   inference is drawn as its strongest edge. Nothing else on this list threatens the premise;
   this does.
2. **It is the smallest diff on the list.** Two expressions in
   `apps/web/app/graph/graph-canvas.tsx` (the `linkLabel` template and the
   `>= 0.9 ? 2.2 : 1.4` stroke) plus one `<select>` relabel in `graph-explorer.tsx`. No
   migration, no re-index, no provider call, no backend change, no data touched. It is
   reversible in one commit.
3. **It does not require deciding the hard question first.** Fixing *resolution* (REV-904)
   needs a product decision about which conservative rule to adopt and costs a re-index of
   every repository. Fixing the *label* is orthogonal and can ship today; it also makes the
   resolution work safe to do incrementally afterwards, because improving recall will no
   longer change a number users read as certainty.
4. **It converts a correctness risk into a known limitation.** "Resolved by unique name" is a
   defensible, useful, honest thing to show a developer — they can immediately judge whether
   to trust it. "100 %" is not.

The risk, stated plainly: **the graph will look less impressive.** The percentage and the
thick strokes are what make the visualisation feel like real static analysis, and removing
them removes that impression. That impression is currently unearned, so I consider the cost
acceptable — but it is a genuine product cost and it is a human's call, not mine.

If I could make a second change, it would be REV-902's four `CREATE INDEX` statements: four
lines of migration to remove ~548 measured seconds and the timeout defect that has already
cost two failed jobs and two divergent workarounds. It is the highest ratio of value to risk
in the entire report — but it makes the product faster, not truer, which is why it is second.

**What I would cut:** stop investing in code cards, structural cards, benchmarks and the
provider-protocol expansion (`NEXT_STEPS.md` §3) until each has a consumer — 424 LOC of the
card systems is currently unreachable, and adding `CodeCardProvider` and `RerankProvider`
adapters before either has a second implementation is an interface for one product. Delete
`docs/CURRENT_STATUS.md`, the ADR-0001 "Initial Contracts" block, and the graph fixture. Keep
every line of `parser_facts.py`, the `citation()` helper, `verify_migration_ready`, the
`git_auth`/`git_askpass` split, the source-hash card keying, and ADR-0001's validation gate —
those are the parts of this codebase that are doing the thesis's work.

---

## Not assessed

- **Integration-branch runtime.** Not built or run. Every efficiency measurement here was
  taken against the live database on the `main` lineage (migration head `0004`). Where a
  finding depends on integration-only code (`structural_cards.py`, REV-912), I have labelled
  the runtime effect as estimated and the cost class as source-reviewed. Migrating the live DB
  to `0008` would have been an irreversible schema change under an analysis-only mandate.
- **Provider-backed paths.** Zero provider calls (§4). REV-903's end-to-end semantic latency,
  the code-card generation pipeline's telemetry (`context_s`/`provider_s`/`parse_s`), Vertex
  429/`Retry-After` behaviour, and reranker effect on ranking quality are all
  `source-reviewed` only. No spend was incurred.
- **Multi-repository and multi-workspace behaviour.** One repository, zero workspaces. REV-907
  and REV-909's most damaging consequences are therefore structurally unobservable in this
  deployment — they are read off the code, not reproduced. Adding a second repository would
  have triggered a billable/long index run.
- **Browser verification of the `call (100%)` label.** Read from
  `graph-canvas.tsx`/`graph-explorer.tsx` source, not observed in a browser; the live stack
  runs `main`'s graph components, which differ. A browser pass is a separate workstream in
  this review — the label logic should be confirmed there.
- **Security, auth, CORS, secret redaction, SSRF policy.** Out of this workstream's remit
  (§5F). Noted only where it intersects density (`ingestion.py:240` writing unredacted
  provider errors into a column served by `GET …/status`); not analysed.
- **Alembic upgrade/downgrade behaviour, data-model integrity, unique-constraint NULL
  semantics, cascade behaviour, API contract/OpenAPI fidelity, accessibility.** Owned by the
  data-model, API and UX workstreams; deliberately not duplicated here beyond the schema facts
  needed for the efficiency findings.
- **Per-request end-to-end API latency.** I measured Postgres-side cost with
  `EXPLAIN (ANALYZE, BUFFERS)` and row-data volumes with SQL. I did not benchmark HTTP
  responses, so REV-911's ORM-hydration dominance is reasoning from measured volumes, not a
  timed request. §7 forbids performance claims without representative measurement; the
  measured parts are labelled measured and the inferred parts are labelled inferred.
