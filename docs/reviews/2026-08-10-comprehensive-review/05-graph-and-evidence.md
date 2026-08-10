# 05 — Graph and Evidence Analysis (Workstream §5.D)

> Builds on `01-runtime-and-provenance.md`. Static target `c122529`
> (`origin/integration/consolidated-verified`, pinned read-only worktree); live target the
> running containers on the `main` lineage. Read-only review by this workstream: no code
> changed, no migration run, no billable endpoint called. `data/` excluded throughout.
> See "Target-drift caveat" below — the main working directory changed mid-review and is not
> a source of evidence here.

## Summary

The graph layer's *mechanics* are better than expected and its *evidence claims* are worse.

Verified-good, with live evidence: repository scope holds (double-filtered in SQL and in
Python), no edge in any observed response has a dangling endpoint, the subgraph node cap is
enforced exactly, repeated identical requests are byte-identical, and a symbol with no
resolved edges honestly returns one node and `truncated: false`.

The problems are all about what the graph *asserts*:

1. **Edges are not evidence.** Reference resolution matches a bare identifier against
   symbol names that happen to be unique in the whole repository, ignoring imports, scope
   and receiver type, and then stamps the result `confidence = 100`. `assert any(...)`
   becomes a 100 %-confidence `call` edge to `SpanTree.any` in a different package. 4 360
   such edges exist in the live database (REV-401).
2. **`truncated: true` is the whole truth budget.** `Agent`'s real depth-1 neighbourhood is
   3 220 symbols and the 100 returned nodes have 3 549 incident edges in the database; the
   response shows 100 nodes and 103 edges and reports no cause and no count (REV-402).
   Worse, selection is codepoint-alphabetical, so 97 of those 100 nodes are pytest test
   methods (REV-419).
3. **There is no edge budget at all**, and every node ships its full `source_text`. The
   "bounded repository overview" returns **3.6 MB, 100 nodes and 7 952 edges** (REV-405) —
   of which only **152 edges are distinct relationships**, because degree ranking selects the
   symbols whose edges are most duplicated (REV-423; one pair appears 2 485 times).
4. **Order at the cap boundary is decided by `uuid4()`**, which is regenerated on every
   re-index, so the same query against the same commit returns a different node set after a
   re-index (REV-404). Proven live.
5. **The relationship / confidence filters break the canvas** the first time they are used,
   because `d3-force-3d` mutates the link objects the filter re-reads (REV-403).
6. **No commit vector anywhere** in any graph response (REV-407).

Findings apply to `both` targets unless stated. `/api/repositories/{id}/graph` and
`/structural-cards` exist only on `integration` — they returned 404 live for most of this
review and became reachable at 14:34 when the stack was migrated to `0008` and rebuilt from
integration (see the next section). That swap is a net gain for this workstream: the two
integration-only routes now have real-data evidence instead of container-probe evidence, and
`subgraph` is proven byte-identical across both builds.

### Which live evidence transfers

`subgraph`, `callers`, `callees`, `scoped_edges`, `scoped_symbols`, `edge_key`, `edge_out`
and `MAX_GRAPH_NODES` are **textually identical** on `main` and `integration`:

```bash
for f in edge_key edge_out scoped_edges scoped_symbols; do
  diff <(git show main:apps/api/app/main.py            | grep -n "$f=") \
       <(git show origin/integration/consolidated-verified:apps/api/app/main.py | grep -n "$f=")
done            # → no output for all four
git show main:apps/api/app/main.py | sed -n '193,213p'   # == integration main.py:241-261
```

So live subgraph/callers/callees evidence is evidence about **both** targets.
`/api/repositories/{id}/graph` is integration-only and was probed in a throwaway container
instead (below).

### Runtime change mid-review: the live stack became the static target

At roughly 14:34 a sibling (non-review) session migrated the live database
`20260808_0004` → `20260809_0008` and rebuilt the API and worker from the integration
branch. Verified by me afterwards:

```bash
docker compose exec -T postgres psql -U knowledgeway -d knowledgeway -At \
  -c "SELECT version_num FROM alembic_version;"        # 20260809_0008
curl -s http://localhost:8000/openapi.json | python3 -c "import json,sys;print([p for p in json.load(sys.stdin)['paths'] if 'graph' in p or 'structural' in p])"
# /api/repositories/{repo_id}/graph
# /api/repositories/{repo_id}/structural-cards
# /api/repositories/{repo_id}/structural-cards/{kind}
# /api/repositories/{repo_id}/symbols/{symbol_id}/subgraph
```

Data preserved: 21 324 symbols, 136 566 `symbol_edges`, 2 284 files, 1 repository,
`files` still at a single `indexed_commit_sha`. New tables `code_cards` and
`structural_cards` are **empty** (0 rows) — no card run was triggered by this workstream.

**Consequence, handled rather than glossed:** every live capture in this report is split and
labelled by era.

- Captured **before** the swap (`main` API, schema `0004`): the T1–T17 subgraph /
  callers / callees / SQL evidence.
- Captured **after** the swap (integration API, schema `0008`): T22–T27 below, including the
  first real-data run of `/api/repositories/{id}/graph` and `/structural-cards`.

For `subgraph` the two eras are provably interchangeable — I re-ran the identical requests
against the integration build and diffed against the `main`-era captures:

```bash
md5sum i_agent_{1,2,3}.json agent_1.json    # all four 29bc3fe5339303569a8a4b83bb09cd43
md5sum i_ctx_{1,2,3}.json   ctx_1.json      # all four 7e22e4afcfa8428ed33cb004c561ebc8
```

Six responses, two different code builds, two different schema versions, byte-identical.
That is a stronger basis for `Applies to: both` than the textual diff alone.

One correction to the hand-over note: the symbol ids I resolved earlier this session are
**not** stale — the migration did not re-index, so all three still resolve
(`SELECT count(*) FROM symbols WHERE id IN (…)` → `3`). The *brief's* ids were stale, which is
itself evidence for REV-404 and is cited there. Fresh ids used below:
`Agent` `0a40f5da-…`, `RunContext` `e9f15643-…`, `Toolset` `7a5089f9-…`.

### Target-drift caveat, recorded after the fact

Part-way through this workstream the main working directory at
`/home/artur/Desktop/Projekte/knowledge-way` was switched to
`integration/consolidated-verified` and picked up in-flight edits from other agent sessions.
It is therefore **not** a stable review target. Every source citation in this report was
(re-)verified against the pinned worktree at `c122529`, which is clean
(`git -C <worktree> status --porcelain` → empty, `git log --oneline -1` → `c122529`), or
against an immutable git ref (`git show main:…`). Line numbers below refer to the pinned
worktree.

Separately, the **running web container serves a production `standalone` build that is not
the pinned code**. Grepping the built bundle shows the `filteredGraph` endpoint read has
already been wrapped in a normalisation helper:

```bash
docker compose exec -T web sh -c 'grep -rho "flatMap(a=>\[.\{0,40\}\])" .next/standalone/.next/server/chunks/ssr/_0epg0oz._.js'
# flatMap(a=>[l(a.source),l(a.target)])        ← pinned source has [link.source, link.target]
```

So a browser observation made *today* would not reproduce REV-403, even though the defect is
present on the pinned target. This is stated in that finding rather than glossed over.

## Determinism, budget and integrity test results

Repository `21ffa409-9e13-493a-b919-7bb6a5b80bb9` (`pydanticAI`), commit
`640d5171fe5795e58553b5af414cbcac3e0c7673`. Symbol ids resolved this session:
`Agent` (class) = `0a40f5da-…`, `RunContext` (class) = `e9f15643-…`,
`RequestUsage.extract` = `b9e3b60f-…`.

| # | Test | Command | Observed | Verdict |
|---|---|---|---|---|
| T1 | Repeat-call byte stability | `for n in 1 2 3; do curl -s ".../symbols/0a40f5da-…/subgraph?depth=2" -o agent_$n.json; done; md5sum agent_*.json` | 3 × `29bc3fe5339303569a8a4b83bb09cd43`, 337 730 B each; `RunContext` 3 × `7e22e4afcfa8428ed33cb004c561ebc8`, 637 675 B | **stable within an index generation** |
| T2 | Node sort order | `[(n['qualified_name'],n['id']) for n in nodes] == sorted(...)` | `True` for both symbols | sorted, tie-break = `id` |
| T3 | Node cap | same responses | `nodes=100`, `max_nodes=100`, `truncated=True` for both | cap enforced exactly |
| T4 | Edge budget | same responses | `Agent` 103 edges, `RunContext` 211 edges, no `max_edges` field, no edge cap in source | **no edge budget** (REV-405) |
| T5 | Truncation honesty | response keys | `['depth','edges','max_nodes','nodes','root_symbol_id','truncated']` — no omitted count, no cause | **dishonest by omission** (REV-402) |
| T6 | True neighbourhood vs returned | recursive SQL over `symbol_edges` (below) | `Agent` depth-1 = **3 220**, depth-1+2 = **3 939**; `RunContext` = 51 / 121 | 100 of 3 220 returned, silently |
| T7 | Edges incident to the returned nodes | `SELECT count(*) … WHERE source_symbol_id IN (<the 100 ids>) OR target_symbol_id IN (…)` | **3 549** in DB vs **103** in the response | connectivity misrepresented (REV-402) |
| T8 | Edge endpoint integrity | `[e for e in edges if e['source_symbol_id'] not in ids or e['target_symbol_id'] not in ids]` | `0` dangling for `Agent`, `RunContext`, and the integration `/graph` probe | **invariant holds** |
| T9 | Repository scope of returned rows | all nodes `repository_id == 21ffa409-…`; `test_graph_api.py` foreign-symbol case → 404 | no leak | **invariant holds** |
| T10 | Cap-boundary stability | `curl ".../symbols/b9e3b60f-…/subgraph?depth=1&max_nodes=4,5,6"` | includes `_map_usage` from `groq.py`, `bedrock.py`, `anthropic.py`, `mistral.py` in `uuid4()` order; 8 distinct `_map_usage` neighbours in 8 files | **unstable across re-index** (REV-404) |
| T11 | Prior-session symbol ids | `SELECT count(*) FROM symbols WHERE id::text LIKE 'd2fcee02%' OR 'd497130%' OR '553d754a%'` | `0` | ids regenerated by re-index; deep links rot |
| T12 | Edge confidence in graph-visible edges | `SELECT relationship_type,confidence,count(*) FROM symbol_edges WHERE source_symbol_id IS NOT NULL AND target_symbol_id IS NOT NULL GROUP BY 1,2` | one row: `call | 100 | 66061` | confidence filter is a no-op (REV-415) |
| T13 | Confidence column exists? | `\d symbol_edges` | `confidence integer NOT NULL` | stored — but two-valued (100/20) |
| T14 | Payload weight | `len(json.dumps(d))`, `len(nodes[0]['source_text'])` | 342 259 B / 644 244 B; root `source_text` alone **153 293 B** | (REV-405) |
| T15 | Cost is independent of result size | `curl -w %{time_total} ".../subgraph?depth=1&max_nodes=5"` vs `GET /api/repositories` | **3.216 s** for a 5-node graph vs **0.003 s** baseline; `callers` 2.672 s, `callees` 2.516 s, `depth=2` 3.3–3.6 s | full-table edge load (REV-406) |
| T16 | Commit provenance on nodes | `[k for k in nodes[0] if 'commit' in k]` | `NONE`; no `path` either, only `file_id` | (REV-407) |
| T17 | Empty neighbourhood | subgraph of a symbol absent from `symbol_edges` | `nodes 1 edges 0 truncated False` | **honest** |
| T18 | Integration `/graph` edge schema | throwaway container probe (below) | two key sets in one array: `('confidence','relationship','source','target')` and `('confidence','id','line','source_file_id','source_symbol_id','target_name','target_symbol_id','type')`; confidence values `[1, 100]` | **two contracts, two scales** (REV-408) |
| T19 | Integration `/graph` order stability | same probe with `PYTHONHASHSEED=0,1,2,3,7` | `NODE_ORDER` md5 identical for all seeds; `EDGE_ORDER` md5 **different for every seed** | edges non-deterministic (REV-409) |
| T20 | Integration graph unit tests | `docker run --rm --network none -v <worktree>/apps/api:/src:ro -w /src knowledge-way-api python -m pytest tests/test_graph_api.py -q` | `3 passed` | pass, but against a fake DB (REV-418) |
| T21 | `/graph` on the live stack | `curl -o /dev/null -w %{http_code} ".../repositories/21ffa409-…/graph?max_nodes=100"` | `404`; absent from `/openapi.json` | working-tree UI button is broken (REV-416) |

### T22–T27 — integration API on real data, captured after the 14:34 swap

These are the first runs of the integration-only routes against the 21 324-symbol
repository. All commands from `/home/artur/Desktop/Projekte/knowledge-way`.

| # | Test | Command | Observed | Verdict |
|---|---|---|---|---|
| T22 | `/graph` size and edge count | `curl ".../repositories/21ffa409-…/graph?max_nodes=100"` | **100 nodes, 7 952 edges, 3 609 966 B (3.6 MB), 3.0–3.3 s**, `truncated: true` | node cap honoured, **79 edges per node, no edge cap** (REV-405) |
| T23 | `/graph` node budget split | same response | `repository 1, directory 18, file 27, class 34, function 20` | structural nodes correctly counted, but consume **46 of 100** |
| T24 | `/graph` edge schema and scales, live | same response | exactly the two key sets from the container probe; `confidence` = `1` (×99 structural) and `100` (×7 853 symbol) | REV-408 confirmed on real data |
| T25 | `/graph` edge endpoint integrity, live | `src/tgt not in node ids` | **0 dangling** at 7 952 edges | **invariant holds at scale** |
| T26 | `/graph` edge order | `[t for r,t in edges if r=='contains'] == sorted(...)` | `False`; byte-identical across 3 repeats in one process | set-iteration order, stable per process only (REV-409) |
| T27 | `/graph` edge redundancy | `Counter((src,tgt,type))` over the 7 853 symbol edges | **152 distinct triples, max multiplicity 2 485, 51.7× duplication** | REV-423 |
| T28 | `structural-cards`, live | `curl ".../structural-cards"` | `{"cards":[],"truncated":false}`, 200, 4 ms, `structural_cards` table = 0 rows | schema fact only — **not** evidence the pipeline works |
| T29 | `Toolset` subgraph | `curl ".../symbols/7a5089f9-…/subgraph?depth=2"` | 38 nodes, 94 edges, `truncated: false`, 399 988 B of which **344 530 B (86 %) is `source_text`** | REV-405 |
| T30 | Subgraph latency on integration | 3 repeats each of `Agent` / `RunContext` depth 2 | 2.52 / 2.59 / 2.53 s and 2.56 / **4.85** / **5.72** s | no better than `main`, and more variable (REV-406) |

Reproduction commands used for T6/T7 (run from `/home/artur/Desktop/Projekte/knowledge-way`):

```bash
docker compose exec -T postgres psql -U knowledgeway -d knowledgeway -c "
WITH d1 AS (SELECT DISTINCT CASE WHEN source_symbol_id='<SYM>' THEN target_symbol_id ELSE source_symbol_id END AS n
            FROM symbol_edges WHERE repository_id='21ffa409-9e13-493a-b919-7bb6a5b80bb9'
              AND source_symbol_id IS NOT NULL AND target_symbol_id IS NOT NULL
              AND '<SYM>' IN (source_symbol_id,target_symbol_id))
SELECT count(*) FROM d1;"
```

The integration-only `/graph` probe (T18/T19) ran a fake-`Session` FastAPI `TestClient`
against the read-only worktree in a disposable, network-less container. No file inside the
worktree or the main repo was created or modified; the probe script lives in the session
scratchpad outside the worktree.

```bash
docker run --rm --network none -e PYTHONHASHSEED=$seed -e PYTHONPATH=/src \
  -v <worktree>/apps/api:/src:ro -v <scratchpad>/probe:/probe:ro \
  -w /src knowledge-way-api python /probe/probe_graph.py
```

## Findings

| ID | Category | Sev | One-line |
|---|---|---|---|
| REV-401 | BUG_CONFIRMED | critical | Calls to Python builtins are stored and rendered as 100 %-confidence `call` edges to unrelated methods (4 360 instances) |
| REV-402 | CORRECTNESS_RISK | critical | `truncated: true` carries no cause and no count while 97 % of the neighbourhood and 97 % of the returned nodes' connectivity are dropped |
| REV-403 | BUG_CONFIRMED | high | Using the relationship or confidence filter empties the canvas, because `d3-force-3d` mutates the link objects the filter re-reads |
| REV-404 | BUG_CONFIRMED | high | Cap-boundary node selection is tie-broken by `uuid4()` primary keys that are regenerated on every re-index |
| REV-405 | DESIGN_GAP | high | No edge budget anywhere, and every graph node ships its full `source_text` (644 KB for 100 nodes) |
| REV-406 | PERFORMANCE_RISK | high | Every graph route loads and Python-sorts all 136 566 edges: 3.2 s for a 5-node result vs 3 ms baseline |
| REV-407 | CORRECTNESS_RISK | high | No commit vector and no file path in any graph response; a failed index can publish mixed-commit rows |
| REV-419 | DESIGN_GAP | high | Neighbour selection under the cap is codepoint-alphabetical, not relevance-ranked: 97 of `Agent`'s 100 nodes are test methods |
| REV-423 | CORRECTNESS_RISK | high | Degree ranking counts duplicate edges, so the overview selects the most-duplicated symbols: 7 853 edges carrying only 152 distinct relationships (51.7×, one pair repeated 2 485×) |
| REV-408 | BUG_CONFIRMED | medium | `/api/repositories/{id}/graph` returns two incompatible edge schemas and two confidence scales in one array |
| REV-409 | BUG_CONFIRMED | medium | `/api/repositories/{id}/graph` edge order depends on `PYTHONHASHSEED`, so it is not reproducible across API processes |
| REV-410 | DESIGN_GAP | medium | A node click cannot open a focused graph; the graph page still requires a raw symbol UUID typed into a text input |
| REV-411 | CORRECTNESS_RISK | medium | Changing the repository selector does not discard the displayed graph, including a fixture graph |
| REV-412 | CORRECTNESS_RISK | medium | The fixture invents relationship types and fractional confidences no ingestion path can produce, drawn with the verified-call style |
| REV-413 | BUG_CONFIRMED | medium | A client-side change of `?symbol=` reloads the graph but leaves the form inputs on the previous symbol |
| REV-414 | DESIGN_GAP | medium | At 100 nodes the canvas is unlabelled, node radius is inflated by duplicate parallel edges, and identically-named nodes are indistinguishable |
| REV-415 | CORRECTNESS_RISK | medium | `confidence` is a two-valued resolution flag shown as a percentage; every graph-visible edge is exactly 100, so the filter only ever affects the fixture |
| REV-416 | BUG_CONFIRMED | medium | The served web bundle's "Repository map" button calls `/graph`, which does not exist on `main` → 404 |
| REV-418 | TEST_GAP | medium | Graph tests run against a fake session that ignores every `WHERE` clause; no truncation-honesty, cap-stability, PostgreSQL or `mapApiGraph` test exists |
| REV-422 | OPTIMIZATION_OPPORTUNITY | low | Auto-fit fires once on `onEngineStop` and the force parameters are untuned for 100 nodes, so a large graph settles overlapped and off-frame |
| REV-417 | DESIGN_GAP | low | The canvas has no branch for `declared_dependency` or `import`; any unknown relationship renders as a verified call arrow |
| REV-420 | DESIGN_GAP | low | `GET /api/files/{file_id}/symbols` has no repository scope and no 404 — it is the only id-resolution path the graph offers |
| REV-421 | DOCUMENTATION_GAP | info | `structural-cards` sorts and filters correctly but its `truncated` also lacks a count, and the singular route hides a missing repository |

---

- ID: REV-401
- Category: BUG_CONFIRMED
- Severity: critical
- Evidence level: PostgreSQL integration-tested
- Applies to: both
- Impact: The graph presents fabricated relationships as verified, 100 %-confidence code
  evidence. A human or coding agent that trusts the graph will conclude that a test file
  calls `SpanTree.any` in `pydantic_evals` when the line is `assert any(...)` — a call to a
  Python builtin. These edges also drive the `/graph` overview's degree ranking, the
  `callers`/`callees` lists, the symbol page's "100 % confidence" text and the embedding
  document's "Static calls:" header, so the error propagates into retrieval.
- Evidence:
  `apps/api/app/ingestion.py:19-20` and `:120-146` (worktree). Resolution is a bare-name
  uniqueness lookup with no import, scope or receiver information:

  ```python
  RESOLVED_CONFIDENCE=100
  ...
  candidates.setdefault(symbol.name, []).append(symbol)      # keyed on `name`, repo-wide
  def edge(source_file, source_symbol, target_name, relationship_type, line):
    matches = candidates.get(target_name, [])
    target = matches[0] if len(matches) == 1 else None
    db.add(SymbolEdge(..., confidence=RESOLVED_CONFIDENCE if target else UNRESOLVED_CONFIDENCE))
  ```

  Live confirmation:

  ```sql
  SELECT sf.path, e.line_number, ss.qualified_name AS caller,
         ts.qualified_name AS resolved_target, tf.path AS target_file, e.confidence
  FROM symbol_edges e
  JOIN symbols ts ON ts.id=e.target_symbol_id JOIN files tf ON tf.id=ts.file_id
  JOIN files sf ON sf.id=e.source_file_id LEFT JOIN symbols ss ON ss.id=e.source_symbol_id
  WHERE e.repository_id='21ffa409-9e13-493a-b919-7bb6a5b80bb9' AND e.confidence=100
    AND e.relationship_type='call' AND ts.qualified_name LIKE '%.%' AND sf.id<>tf.id
    AND position(split_part(ts.qualified_name,'.',1) in sf.content)=0;
  ```

  → **4 360 rows**. Three of them, with the caller line pulled from `files.content`:

  | caller line | stored edge |
  |---|---|
  | `tests/test_vercel_ai.py:6793` `assert any(isinstance(item, UploadedFile) for item in loaded_part.content)` | `call → SpanTree.any` (`pydantic_evals/.../otel/span_tree.py`), confidence 100 |
  | `tests/test_vercel_ai.py:10563` `received.append(messages)` | `call → EnqueueGuard.append` (`pydantic_ai_slim/.../durable_exec/_toolset.py`), confidence 100 |
  | `tests/test_vercel_ai.py:6199` `assert len(ids) == len(set(ids))` | `call → TestEnv.set` (`tests/conftest.py`), confidence 100 |

  Rendering: `apps/web/app/graph/graph-canvas.tsx:12` gives every non-`contains`/`defines`
  relationship a solid arrow, and width `2.2` precisely because `confidence >= 0.9`;
  `:66` labels the link `call (100%)`. `apps/web/app/repositories/[repositoryId]/symbols/[symbolId]/page.tsx:20`
  prints `· 100% confidence` in the callers/callees lists.
- Probable cause + diagnostic confidence: deliberate simplification ("Resolve only a unique
  declaration name inside this repository", `ingestion.py:121`) combined with a confidence
  constant that overstates it. The name index is keyed on `Symbol.name`, so every
  single-definition method name in the repository shadows the identically named builtin or
  attribute call anywhere else. **Certain** — root cause read directly and three instances
  quoted from stored file content.
- Smallest safe next step: stop claiming 100. Reclassify these edges as
  `relationship_type='call'` with a low, honestly named field (e.g. `resolution='name-unique'`)
  and exclude names that shadow `builtins` (`set`, `any`, `append`, `get`, `items`, …) from
  the candidate index. No migration is needed to *stop displaying* 100 %: the UI change is
  one line in `graph-canvas.tsx:66` and one in the symbol page.
- Affected data/migrations/providers/cost: all 74 415 confidence-100 rows in
  `symbol_edges`; `_embedding_document` (`ingestion.py:149-158`) already baked these
  "Static calls" into 22 900 embedded chunks, so correcting resolution implies a re-embed
  (billable) — that decision belongs to workstream E, not to this fix.
- Recommended tests + acceptance criteria: a parser/ingestion unit test asserting that
  `any(...)`, `set(...)` and `x.append(...)` in a file that does not import the owning class
  produce **no** resolved edge; an API test asserting no graph edge reports a confidence it
  cannot justify. Acceptance: the query above returns 0 rows on a freshly indexed fixture
  repository.
- Fix status: report-only

---

- ID: REV-402
- Category: CORRECTNESS_RISK
- Severity: critical
- Evidence level: PostgreSQL integration-tested
- Applies to: both
- Impact: `truncated: true` is the only signal that a graph is incomplete. It states neither
  the cause (node cap) nor the magnitude. For `Agent` the response looks like a tidy
  100-node / 103-edge neighbourhood; the database holds 3 220 direct neighbours and 3 549
  edges incident to the very 100 nodes returned. A user or agent reading "Agent has 103
  relationships" is wrong by a factor of 34, and the graph's *shape* (a sparse tree) is a
  fabrication of the truncation, not a property of the code. §3 requires an honest
  `truncated` with cause and count; this does not satisfy it.
- Evidence:
  `apps/api/app/main.py:241-261` (integration) == `main.py:193-213` (main). `truncated` is a
  bare boolean set at `:256` and returned at `:261`; there is no omitted-node count, no
  omitted-edge count and no cause code. The response key set is exactly
  `['depth','edges','max_nodes','nodes','root_symbol_id','truncated']` (T5).
  T6/T7 give `3 220` true depth-1 neighbours and `3 549` incident edges against `100` /
  `103` returned. `RunContext`: 121 true depth-1+2 nodes → 100 returned, 211 edges.
  The same omission on `/graph`, now measured live (T22): `truncated: true` alongside
  `100` nodes out of **21 324** symbols and `7 952` edges out of **66 061** graph-eligible
  edges, with no count and no cause. Its `truncated` is also computed only from symbols
  (`main.py:295`: `len(selected)<len(symbols)`), so it says nothing about the 27 files and 18
  directories that were also cut, nor about dropped edges.
  Frontend: `apps/web/app/graph/graph-explorer.tsx:110` renders only
  `… · {filteredGraph.nodes.length} nodes · {filteredGraph.links.length} relationships` —
  on the pinned target the UI never surfaces `truncated` at all. `graph-model.ts` has no field
  for it and `mapApiGraph` (`graph-explorer.tsx:32-54`) drops it. Combined with REV-423, the
  count it *does* show ("7 952 relationships") overstates the distinct relationships by 51.7×.
  Status update: a sibling session has since added a `truncated` indicator to the graph
  summary bar on the working branch. The finding stands as written against `c122529` and
  against what was deployed when observed; the API half — no cause, no counts — is unchanged
  and is the larger part of the fix.
- Probable cause + diagnostic confidence: the flag was designed as a boolean and the UI
  contract was never extended. **Certain** for the API omission (source + response keys);
  **certain** for the UI omission (`truncated` appears nowhere in
  `apps/web/app/graph/*`).
- Smallest safe next step: extend the subgraph response with
  `truncation: {reason: 'max_nodes', node_cap: N, nodes_omitted: K, edges_omitted: M}`
  computed from the already-materialised candidate set (no extra query), and render it as a
  visible banner. Purely additive to the response schema.
- Affected data/migrations/providers/cost: none — response shape and UI only.
- Recommended tests + acceptance criteria: API test on a fixture with 5 neighbours and
  `max_nodes=3` asserting `nodes_omitted == 2` and a non-zero `edges_omitted`; a UI
  assertion that a truncated graph shows a truncation banner. Acceptance: no response can
  report `truncated: true` without a machine-readable cause and both counts.
- Fix status: report-only

---

- ID: REV-403
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: source-reviewed
- Applies to: both (identical text on the pinned worktree and on `main`)
- Impact: The first use of the "Relationship" or "Minimum confidence" filter replaces the
  rendered graph with `No graph data to display. The selected filters returned no connected
  nodes.` The user is told their filter matched nothing; in reality the node filter compared
  strings against objects. Both filter controls are therefore effectively unusable, and the
  error message actively misleads.
- Evidence:
  `apps/web/app/graph/graph-explorer.tsx:69-73` (pinned worktree) — identical text at
  `main:apps/web/app/graph/graph-explorer.tsx:57-62`:

  ```ts
  const links = graph.links.filter((link) => (relationship === 'all' || link.relationship === relationship) && (link.confidence == null || link.confidence >= minimum));
  const connected = new Set(links.flatMap((link) => [link.source, link.target]));
  return { links, nodes: graph.nodes.filter((node) => connected.has(node.id) || graph.links.length === 0) };
  ```

  `filteredGraph.links` are the *same object references* that were handed to
  `ForceGraph2D` (`graph-explorer.tsx:112` → `graph-canvas.tsx:34`), and the force layout
  rewrites their endpoints in place. From the running web container's `node_modules`,
  `node_modules/d3-force-3d/src/link.js:66-67`:

  ```js
  if (typeof link.source !== "object") link.source = find(nodeById, link.source);
  if (typeof link.target !== "object") link.target = find(nodeById, link.target);
  ```

  (`react-force-graph-2d@1.29.1`, `force-graph` + `d3-force-3d`, verified via
  `docker compose exec -T web sh -c 'grep -nE "link\.source|link\.target" node_modules/d3-force-3d/src/link.js'`.)
  After the first layout tick `link.source` is a node object, so `connected` is a set of
  node objects and `connected.has(node.id)` — a string — is always `false`; with
  `graph.links.length > 0` the fallback does not apply, so `nodes` becomes `[]`.
  Two independent corroborations that the authors know these objects are mutated:
  `graph-explorer.tsx:114` excludes `x, y, vx, vy, index, __indexColor` from the node-detail
  panel, and `mapApiGraph`'s `endpointId` (`:29`) already special-cases an object endpoint
  (`typeof value === 'object' ? stringValue(asRecord(value).id) : …`) — the same defect,
  patched in the mapper but not in the filter.
- Probable cause + diagnostic confidence: derived state recomputed from a mutated
  third-party-owned array. **High confidence** from source + the installed dependency;
  **not** observed in a browser by this workstream, so the evidence level stays
  `source-reviewed`.
  Important caveat for anyone trying to reproduce this in the browser: the running web
  container serves a `standalone` build whose `filteredGraph` **already normalises the
  endpoints** — the bundle reads `flatMap(a=>[l(a.source),l(a.target)])` where the pinned
  source reads `[link.source, link.target]` (see the target-drift caveat above). A live
  browser check today would therefore pass and would say nothing about the pinned target.
  A fix of exactly this shape was independently written into the main working tree by another
  agent session during this review; under the report-only mandate (§4) it is recorded here as
  a finding rather than adopted, and this workstream neither authored nor validated it.
- Smallest safe next step: one line — compare against a normalised endpoint id:
  `const endpoint = (v: unknown) => typeof v === 'object' && v !== null ? String((v as {id: string}).id) : String(v);`
  and use it in both `flatMap` and the link `source`/`target` reads. `endpointId` already
  exists in the same file and can be reused rather than reinvented.
- Affected data/migrations/providers/cost: none — client only.
- Recommended tests + acceptance criteria: a component test that renders the canvas, waits
  for `onEngineStop`, then changes the relationship filter and asserts the node count is
  `> 0`; plus a pure unit test of the filter given links whose `source`/`target` are node
  objects. Acceptance: filtering after render never yields an empty graph when matching
  links exist.
- Fix status: report-only

---

- ID: REV-404
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: PostgreSQL integration-tested
- Applies to: both
- Impact: Under the node cap, *which* nodes come back is decided by comparing random UUIDs.
  `symbols.id` defaults to `uuid.uuid4()` and every index run recreates symbol rows, so the
  same request against the same commit returns a **different set of files** after a
  re-index. This breaks reproducible evidence (§3.6), invalidates any cached or
  screenshotted graph, and rots `?symbol=` deep links entirely.
- Evidence:
  Tie-breaker: `apps/api/app/main.py:254` and `:261` sort on
  `(available[i].qualified_name, i)` where `i` is the symbol id;
  `apps/api/app/models.py:7` `def uid(): return str(uuid.uuid4())`, applied as
  `default=uid` on `Symbol.id` (`models.py:26`).
  Identity is not stable across runs — the three symbol ids resolved earlier in this session
  no longer exist after the 11:49 re-index:
  `SELECT count(*) FROM symbols WHERE id::text LIKE 'd2fcee02%' OR id::text LIKE '4d497130%' OR id::text LIKE '553d754a%';` → `0`.
  Live instance: `RequestUsage.extract` (`pydantic_ai_slim/pydantic_ai/usage.py`) has **8
  distinct neighbours all named `_map_usage`**, in `groq.py`, `bedrock.py`, `anthropic.py`,
  `mistral.py`, `openai.py`, `embeddings/cohere.py`, `embeddings/openai.py`, `cohere.py`.
  Their only ordering key is the random id:

  ```bash
  curl -s ".../repositories/21ffa409-…/symbols/b9e3b60f-7227-43f7-af7e-cd48c46eaff8/subgraph?depth=1&max_nodes=5"
  #  nodes=5 truncated=True
  #    RequestUsage.extract  b9e3b60f
  #    _extract_usage        6636efe3   models/xai.py
  #    _map_usage            08d22187   models/groq.py
  #    _map_usage            188701cf   models/bedrock.py
  #    _map_usage            49516d50   models/anthropic.py      ← in
  #                          4d741241   models/mistral.py        ← out, by uuid comparison only
  ```

  `max_nodes=4,5,6` each admit exactly one more `_map_usage`, always in `uuid4()` order.
  Repository-wide there are **599** duplicate `qualified_name` groups (max multiplicity 23,
  `SimpleState`); **93** of them sit inside `Agent`'s depth-1 candidate set alone (236
  symbols).
  Honest scope limit: at `max_nodes=100` the `Agent` boundary happens *not* to split a
  collision group (checked for every cap 2…100 by replaying the exact selection algorithm
  against the candidate set pulled from SQL — the replay reproduces the API's last included
  node, `TestGetWrapperToolsetHook.test_wrapper_prefixes_tools_streaming`, exactly). So the
  defect is proven at achievable caps, not at the default cap for this particular symbol.
- Probable cause + diagnostic confidence: `qualified_name` is not unique (by design — it is
  file-local), and the secondary key is a random surrogate instead of a stable logical
  identity such as `(path, qualified_name, start_line)`. **Certain**.
- Smallest safe next step: change the tie-breaker to a stable evidence tuple —
  `(qualified_name, file.path, start_line, id)` — which requires the file map the route
  already has to load for other purposes in `/graph` and one extra `scoped_files` call in
  `subgraph`. This makes ordering reproducible without touching identity or schema.
- Affected data/migrations/providers/cost: no migration for the sort fix. A truly stable
  symbol identity (so deep links survive a re-index) is a data-model change and belongs to
  workstream C.
- Recommended tests + acceptance criteria: an API test with two symbols sharing a
  `qualified_name` and `max_nodes` set to admit exactly one, asserting the admitted node is
  the one with the lexicographically smaller `(path, start_line)` regardless of insertion
  order. Acceptance: shuffling primary keys in the fixture does not change the response.
- Fix status: report-only

---

- ID: REV-405
- Category: DESIGN_GAP
- Severity: high — raised from the initial assessment after the live `/graph` measurement
- Evidence level: PostgreSQL integration-tested
- Applies to: both (`/graph` verified live on integration)
- Impact: §3.3 asks for "one global hard budget". Only nodes are budgeted, and the
  consequence is no longer hypothetical. The **bounded repository overview returns 3.6 MB for
  100 nodes**: 7 952 edges (79 per node, uncapped) plus 1 244 277 bytes of `source_text`
  across 54 symbol nodes. A single test function node carries 240 KB on its own. The
  38-node `Toolset` subgraph is 400 KB, 86 % of it `source_text`. Clicking any of those nodes
  dumps its full source into the detail panel, because the panel renders every remaining key.
  This is the response a browser is expected to parse and force-layout on every "Repository
  map" click.
- Evidence:
  Live, integration API, real repository (T22, T29):

  ```bash
  curl -s ".../repositories/21ffa409-…/graph?max_nodes=100" -o g.json -w "%{size_download} %{time_total}\n"
  # 3609966  3.114921
  python3 -c "import json;d=json.load(open('g.json'));print(len(d['nodes']),len(d['edges']),d['truncated'])"
  # 100 7952 True
  python3 -c "import json;d=json.load(open('g.json'));print(sum(len(n.get('source_text') or '') for n in d['nodes']))"
  # 1244277
  ```

  Heaviest nodes: `test_groq_model_thinking_part_iter` 240 225 B, `Agent` 157 090 B,
  `AnthropicModel` 121 095 B. `Toolset` subgraph: 38 nodes / 94 edges / 399 988 B, of which
  344 530 B is `source_text`.
  Static source:
  `apps/api/app/main.py:260-261` (subgraph) and `:294-295` (`/graph`) build `graph_edges` by
  unbounded comprehension, and neither response carries a `max_edges` or `edges_truncated`
  field (T4, T5, T22).
  `symbol_out` (`main.py:53`) includes `'source_text':s.source_text`; measured
  `len(nodes[0]['source_text']) == 153293`, total payloads 337 730 B (`Agent`) and
  637 675 B (`RunContext`) for 100 nodes each (T1, T14).
  The node-detail panel (`graph-explorer.tsx:114`) excludes only
  `['id','label','kind','x','y','vx','vy','index','__indexColor']` — `source_text`,
  `signature`, `start_byte` and `end_byte` are all rendered into `<dd>` elements.
  `structural_cards` shows the intended pattern is known: it caps its list *and* returns
  `truncated` (`main.py:201`).
  Structural nodes *are* correctly counted against the node cap
  (`main.py:273-280`: `budget=max_nodes-1`, `added=1+…+sum(directory not in directories …)`)
  — that part of §3.3 is satisfied; structural *edges* are not counted.
- Probable cause + diagnostic confidence: `symbol_out` is reused verbatim from the
  symbol-detail route, where full source is the point. **Certain** — measured.
- Smallest safe next step: give the graph routes a projection without `source_text` (the
  canvas uses `id`, `qualified_name`, `type`, `degree` only), and add
  `max_edges` + `edges_omitted` alongside the node cap. Two small changes, no schema impact.
  Dropping `source_text` alone takes the live overview from 3.6 MB to roughly 2.4 MB;
  de-duplicating edges (REV-423) takes it to well under 100 KB. Do both, in that order of
  effort.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: assert no graph node contains `source_text`;
  assert `len(edges) <= max_edges` and that dropping edges sets `edges_omitted > 0`.
  Acceptance: a 100-node graph response stays under a stated size budget (e.g. 200 KB).
- Fix status: report-only

---

- ID: REV-406
- Category: PERFORMANCE_RISK
- Severity: high
- Evidence level: PostgreSQL integration-tested
- Applies to: both
- Impact: Every graph and neighbour request costs ~2.5–3.6 s on a single 21 k-symbol
  repository, independent of how much data is asked for. The cause is isolated, not
  inferred: a 5-node subgraph and a 100-node subgraph cost the same, because the work is
  loading and sorting the entire `symbol_edges` table in Python before any filtering. This
  scales linearly with repository size and multiplies by concurrent users; the "Repository
  map" and symbol pages issue several of these per view.
- Evidence:
  `apps/api/app/main.py:60`:

  ```python
  def scoped_edges(db,repo_id): return sorted((e for e in db.scalars(select(SymbolEdge).where(SymbolEdge.repository_id==repo_id)).all() if e.repository_id==repo_id),key=edge_key)
  ```

  called unconditionally by `subgraph` (`:245`), `neighbors` (`:230`), `repository_graph`
  (`:267`) and `documentation` (`:320`). 136 566 rows for this repository.
  `main.py:246` then issues `Symbol.id.in_(ids)` with the union of every edge endpoint —
  up to ~21 k bind parameters in one statement.
  `main.py:294` and `:292` test membership with `edge.source_symbol_id in selected` where
  `selected` is a **list**, i.e. an O(len(edges) × 100) scan.
  Measured, same session, same process (T15):

  | request | time |
  |---|---|
  | `GET /api/repositories` | 0.003 s |
  | `.../subgraph?depth=1&max_nodes=5` | **3.216 s** |
  | `.../subgraph?depth=2` (100 nodes) | 3.32–3.63 s |
  | `.../callers` | 2.672 s |
  | `.../callees` | 2.516 s |

  Re-measured on the integration build after the migration (T30, T22) — no improvement, and
  the tail got worse: `Agent` depth 2 = 2.52 / 2.59 / 2.53 s, `RunContext` depth 2 = 2.56 /
  **4.85** / **5.72** s for byte-identical responses, and `/graph?max_nodes=100` = 3.0–3.3 s.
  A 2.2× spread across three identical requests points at the Python sort of 136 566 objects
  competing for CPU, not at the database.
  There is no index on `symbol_edges(source_symbol_id)` or `(target_symbol_id)` — `\d
  symbol_edges` shows only `ix_symbol_edges_repository_id` and `ix_symbol_edges_target_name`
  (still true at `0008`; that migration only widened `target_name` to `text`).
- Probable cause + diagnostic confidence: deliberate "filter in Python for SQLite/PostgreSQL
  parity" style, applied to a table that is three orders of magnitude larger than the result.
  **Certain** — the 5-node vs 100-node comparison isolates the cause to the fixed-cost load,
  and the absent endpoint indexes explain why pushing the filter down needs a migration.
- Smallest safe next step: in `neighbors` and `subgraph`, push the endpoint predicate into
  SQL (`WHERE repository_id=:r AND (source_symbol_id IN :frontier OR target_symbol_id IN :frontier)`)
  and keep the Python re-filter as the belt-and-braces scope check. Change `selected` to a
  `set`. Both are local edits; the supporting index on
  `(repository_id, source_symbol_id)` / `(repository_id, target_symbol_id)` is a separate,
  additive migration and must not be run as part of this review.
- Affected data/migrations/providers/cost: needs one additive index migration to realise the
  full gain; no data change, no provider cost.
- Recommended tests + acceptance criteria: assert `subgraph` issues a bounded number of rows
  (e.g. via a query counter) and that the response for `max_nodes=5` is unchanged; a
  documented latency budget measured on this same repository. Acceptance: `max_nodes=5`
  responds in < 200 ms and the response body is byte-identical to today's.
- Fix status: report-only

---

- ID: REV-407
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: PostgreSQL integration-tested (absence of provenance); source-reviewed (mixing mechanism)
- Applies to: both
- Impact: §3.6 requires every graph context to retain repository, file/path, line range and
  indexed commit. A graph node carries `repository_id`, `file_id`, `start_line`, `end_line`
  — but **no `path` and no `indexed_commit_sha`**, and the response has no commit vector.
  A node therefore cannot be cited without a second lookup, and if `files` ever hold rows
  from different commits the graph will mix them with nothing visible to say so.
- Evidence:
  `symbol_out` (`apps/api/app/main.py:53`) has no commit and no path field; measured on the
  live response: `[k for k in nodes[0] if 'commit' in k]` → `NONE`, and the node key list is
  `end_byte, end_line, file_id, id, language, name, parent_symbol_id, qualified_name,
  repository_id, signature, start_byte, start_line, type` (T16). The `/graph` overview's
  file nodes (`main.py:283`) carry `path` but no commit; the repository node (`:281`) carries
  neither. Compare `citation()` (`main.py:63-65`), which *does* assemble
  `indexed_commit_sha` — the graph routes simply never call it.
  Mixing mechanism: `files.indexed_commit_sha` is per row, and `index_repository`'s failure
  path commits whatever the session holds:

  ```python
  except Exception as e:
   repo.indexing_status='failed';repo.error_message=str(e);job.status='failed';…;db.commit();raise
  ```

  (`apps/api/app/ingestion.py:239-240`). At that point `File.indexed_commit_sha=sha` has
  already been assigned for every file processed so far (`:222-224`) and
  `delete(SymbolEdge)` has already run (`:212`), so a mid-loop exception **publishes** a
  partial generation: some files at the new commit, the rest at the old one, and possibly no
  edges at all.
  Current state is clean — `SELECT count(DISTINCT indexed_commit_sha) FROM files` → `1` — so
  no mixing is present today. I did not trigger a failing index (out of scope, §4), so the
  mechanism is `source-reviewed`; the missing provenance fields are measured.
- Probable cause + diagnostic confidence: no atomic index generation, and `symbol_out` was
  written for the symbol-detail route where the caller already knows the commit.
  **Certain** for the missing fields; **high** for the partial-publish path (the `except`
  block's `db.commit()` is unambiguous, but the exact interleaving was not reproduced).
- Smallest safe next step: add `path` and `indexed_commit_sha` to graph nodes (both are
  already loaded — `/graph` has the `files` map, `subgraph` needs one `scoped_files` call)
  and return a `scope: {repository_id, indexed_commit_sha}` block like `/api/explanations`
  already does (`main.py:313`). Render the commit next to the node count.
- Affected data/migrations/providers/cost: none for the provenance fields. Atomic index
  generations are a data-model change owned by workstreams C and E.
- Recommended tests + acceptance criteria: assert every graph node carries a non-empty
  `path` and `indexed_commit_sha`; assert a graph whose nodes span two distinct
  `indexed_commit_sha` values is either rejected or reports a commit vector. Acceptance: no
  graph response can be rendered without a visible commit.
- Fix status: report-only

---

- ID: REV-419
- Category: DESIGN_GAP
- Severity: high
- Evidence level: PostgreSQL integration-tested
- Applies to: both
- Impact: When the cap bites, the surviving neighbours are chosen by Python codepoint order
  on `qualified_name` — uppercase before lowercase, no relevance signal at all. For
  `Agent`, 97 of the 100 returned nodes are pytest test methods from `tests/`; the useful
  neighbours (the agent's own collaborators) never make the cut. The feature is present but
  does not deliver the capability §2 describes ("open a focused symbol graph / relevant
  neighbourhood").
- Evidence:
  `apps/api/app/main.py:254` — `sorted(set(candidates), key=lambda i:(available[i].qualified_name, i))`
  and `:256` — the cap is applied to that order, with no degree, distance or path weighting.
  Live response for `Agent` (T1): `qualified_name` range `'Agent' … 'TestGetWrapperToolsetHook.test_wrapper_prefixes_tools_streaming'`;
  first six are `Agent`, `Agent.from_spec`, `ImageGenerationSubagentTool.__call__`,
  `TestAfterOutputProcess.test_transform_plain_text_result`, `…_structured_result`,
  `…_text_function_result`.

  ```sql
  SELECT count(*) FROM symbols WHERE id IN (<the 100 returned ids>)
    AND file_id IN (SELECT id FROM files WHERE path LIKE 'tests/%');   --> 97
  ```

  By contrast `/api/repositories/{id}/graph` *does* rank by degree
  (`main.py:274`: `key=lambda s:(-degree[s.id],s.qualified_name,s.id)`), so the codebase
  already contains the better pattern — it is simply not used by `subgraph`.
- Probable cause + diagnostic confidence: the alphabetical key was chosen to make the result
  deterministic, and determinism was conflated with relevance. **Certain** — measured.
- Smallest safe next step: reuse the degree ranking already written for `/graph` as the
  primary sort key in `subgraph`'s candidate loop (`-degree, qualified_name, path,
  start_line`), keeping the alphabetical key as the tie-breaker. Optionally deprioritise
  test files. Ordering of the *returned* `nodes` array can stay alphabetical for stable
  output.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: on a fixture where a hub has one high-degree and
  many low-degree alphabetically-earlier neighbours, assert the high-degree neighbour is
  inside a cap of 2. Acceptance: `Agent`'s 100-node graph contains its production
  collaborators, not 97 test methods.
- Fix status: report-only

---

- ID: REV-423
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: PostgreSQL integration-tested
- Applies to: integration (the `/graph` route); the underlying duplication applies to both
- Impact: Two defects compound into a third. `symbol_edges` stores one row per *call site*
  with no aggregation, and the overview ranks symbols by raw edge count — so the ranking
  actively selects the symbols whose edges are most duplicated. The live 100-node overview
  returns **7 853 symbol edges that carry only 152 distinct (source, target, type)
  relationships**, a 51.7× redundancy, with a single pair repeated **2 485 times**. The
  canvas therefore draws 2 485 perfectly overlapping identical lines, the client's `degree`
  count (and hence every node radius) is inflated by up to three orders of magnitude, and the
  summary bar reports "7 952 relationships" when the graph expresses 152. Every number the
  user reads off this view is wrong, and the "most connected symbols" it selects are really
  "the symbols called most often from inside one big test function".
- Evidence:
  Live (T27), integration API, `max_nodes=100`:

  ```python
  sym = [e for e in graph['edges'] if 'source_symbol_id' in e]
  par = Counter((e['source_symbol_id'], e['target_symbol_id'], e['type']) for e in sym)
  # symbol edges: 7853   distinct triples: 152   max multiplicity: 2485   ratio: 51.7x
  ```

  The 2 485× pair resolves to:

  ```sql
  SELECT s.qualified_name, s.symbol_type, f.path, s.end_line-s.start_line AS lines
  FROM symbols s JOIN files f ON f.id=s.file_id WHERE s.id IN ('ac72c484-…','7e5a3110-…');
  --  test_groq_model_thinking_part_iter | function | tests/models/test_groq.py            | 3305
  --  PartDeltaEvent                     | class    | pydantic_ai_slim/…/messages.py       |   12
  ```

  A 3 305-line test function that constructs `PartDeltaEvent(...)` ~2 485 times, and
  `_persist_edges` (`apps/api/app/ingestion.py:137-140`) writes one `SymbolEdge` per
  `facts.references` entry with no grouping.
  Repository-wide the redundancy is only 1.63× (66 061 edges → 40 563 distinct triples), so
  the 51.7× figure inside the overview is **produced by the selection**: `main.py:269-274`
  computes `degree` over raw edge rows and sorts by `-degree`, which is maximised precisely by
  duplication.
  The client compounds it: `mapApiGraph` counts degree over the raw link list
  (`graph-explorer.tsx:51-53`) and `graph-canvas.tsx:43` caps radius at
  `Math.min(7, 4+sqrt(degree))`, so a degree of 2 485 and a degree of 9 render identically.
- Probable cause + diagnostic confidence: call-site granularity is the right *storage*
  decision (each row keeps its `line_number`, which is real evidence) but the wrong
  *presentation* and ranking unit. **Certain** — measured live and traced to the ingestion
  loop and the ranking key.
- Smallest safe next step: aggregate at the read boundary, not in the database. In `/graph`,
  group the symbol edges by `(source, target, relationship)` and emit one edge with a
  `call_sites: N` count and the line numbers; rank by distinct-neighbour count rather than raw
  row count. Both changes are local to `repository_graph`, and the second is a one-line change
  to the `degree` accumulation at `main.py:270-272`.
- Affected data/migrations/providers/cost: no migration — the per-call-site rows should stay,
  they are the evidence. Response shape changes (see REV-408, fix them together).
- Recommended tests + acceptance criteria: fixture with one symbol calling another 50 times;
  assert the overview returns one edge with `call_sites == 50`, and that a symbol with 50
  duplicate edges does not outrank a symbol with 10 distinct neighbours. Acceptance: the
  reported relationship count equals the number of distinct relationships drawn.
- Fix status: report-only

---

- ID: REV-408
- Category: BUG_CONFIRMED
- Severity: medium
- Evidence level: PostgreSQL integration-tested (upgraded from `unit/API-tested` after the route went live)
- Applies to: integration
- Impact: `/api/repositories/{id}/graph` returns a single `edges` array containing two
  mutually incompatible object shapes and two different confidence scales. Any consumer
  other than the one hand-tuned client must branch on key presence; a typed client or an
  OpenAPI-generated SDK cannot describe it. §5.B's "explicit, versionable schemas instead of
  loose dictionaries" is not met.
- Evidence:
  `apps/api/app/main.py:285-294` emits structural edges as
  `{'source','target','relationship','confidence':1}` and symbol edges via `edge_out`
  (`main.py:54`) as
  `{'id','source_symbol_id','target_symbol_id','target_name','type','confidence','line','source_file_id'}`.
  Confirmed **live on real data** after the route became reachable (T24): the same two key
  sets, and both confidence scales present in one array — `1` on 99 structural edges,
  `100` on 7 853 symbol edges:

  ```text
  EDGE SHAPES: 2
      ('confidence', 'relationship', 'source', 'target')
      ('confidence', 'id', 'line', 'source_file_id', 'source_symbol_id', 'target_name', 'target_symbol_id', 'type')
  confidence values: {1: 99, 100: 7853}
  relationship/type values: {'contains': 45, 'defines': 54, 'call': 7853}
  ```

  The earlier disposable-container probe (T18) produced the identical two key sets and
  `CONFIDENCE_VALUES [1, 100]`, so the synthetic and real runs agree.

  The project's own test documents the split — `apps/api/tests/test_graph_api.py:82-84`
  reads `edge["relationship"]` for one kind and `edge.get("type")` for the other in the same
  assertion block. The client absorbs it by trying both
  (`graph-explorer.tsx:45,49`: `item.source ?? item.source_id ?? item.source_symbol_id`,
  `stringValue(item.relationship, item.relationship_type, item.type, 'related')`).
  The scale clash is currently harmless only by luck: `mapApiGraph:48` normalises with
  `confidence! > 1 ? confidence!/100 : confidence!`, so `1` → 1.0 and `100` → 1.0. A genuine
  1-out-of-100 confidence would be displayed as **100 %**. `SymbolEdge.confidence` even
  defaults to `50` (`models.py:37`), which that heuristic reads as 50 %.
- Probable cause + diagnostic confidence: structural edges were added later, next to the
  existing `edge_out` rather than through it. **Certain**.
- Smallest safe next step: emit one shape from one helper — `{source, target, relationship,
  confidence, evidence?}` — with `confidence` on a single documented scale, and keep
  `edge_out` for the symbol-detail routes that already ship it. The client's `??` chains can
  then be deleted.
- Affected data/migrations/providers/cost: none — response shape only. Breaking for any
  existing consumer, so it needs a version note.
- Recommended tests + acceptance criteria: assert every element of `edges` has the identical
  key set and that `0 <= confidence <= 1` (or `<= 100`, pick one). Acceptance: an
  OpenAPI-generated client can type the array.
- Fix status: report-only

---

- ID: REV-409
- Category: BUG_CONFIRMED
- Severity: medium
- Evidence level: PostgreSQL integration-tested (live) + unit/API-tested (cross-process proof)
- Applies to: integration
- Impact: The `/graph` overview's `edges` array order changes between API processes, so two
  identical requests can return byte-different bodies. That defeats ETag/caching, makes
  response diffing in tests or CI flaky, and — once an edge budget exists (REV-405) — would
  mean a *different subset* of edges per process. §5.D's "stable sorting of nodes and edges
  with reproducible tie-breakers" is met for nodes and violated for edges.
- Evidence:
  `apps/api/app/main.py:286` `for directory in directories:` and `:289`
  `for file_id in selected_files:` iterate **sets**; `graph_edges` is never sorted before
  return (`:295`). Python randomises `str` hashing per process unless `PYTHONHASHSEED` is
  fixed. Probe (T19), same input, five seeds:

  ```text
  seed=0  md5(NODE_ORDER+EDGE_ORDER) 66875413670a65801d148d3d62b1ba6f
  seed=1  345370a95d6c5ed3b9dc6a20bc64ac09
  seed=2  870de7d70741891910239cbec15c0b27
  seed=3  ffde96f4c863cb8f154270dcd0c6f169
  seed=7  619e0d6f888ab7e0e8c198c13b5f68e4
  NODE_ORDER md5 2af49297ac8a39089a059d8314fb6976  ← identical for every seed
  first contains-edge targets, seed 0: [directory:d, directory:a/b, directory:a/b/c, directory:a, directory:d/e, file:f2]
                              seed 1: [directory:d, directory:d/e, directory:a/b/c, directory:a, directory:a/b, file:f1]
                              seed 2: [directory:d/e, directory:a/b/c, directory:a/b, directory:d, directory:a, file:f4]
  ```

  Nodes are stable because they are explicitly sorted (`main.py:282-284`).
  Confirmed live on the real route (T26): the `contains` edge targets come back unsorted —
  `directory:tests`, `directory:examples/pydantic_ai_examples`,
  `directory:pydantic_ai_slim/pydantic_ai/agent`, … — while three consecutive requests inside
  the same API process are byte-identical (`66220db694f1d959be454cee0c0f4e35` ×3). That is
  exactly the predicted signature: stable within a process, seed-dependent across processes.
  The `subgraph` route is unaffected: its edge list inherits `scoped_edges`' `edge_key`
  sort, and T1/T30 confirm byte-identical repeats across two different builds.
- Probable cause + diagnostic confidence: sets used for membership *and* iteration.
  **Certain** — reproduced across five seeds.
- Smallest safe next step: iterate `sorted(directories)` and
  `sorted(selected_files, key=lambda i: files[i].path)`, and `sorted(graph_edges, key=…)`
  before returning. Note `edge_key`'s last tie-breaker is the random edge `id`, so a fully
  reproducible order also needs REV-404's stable key.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: run the route twice under different
  `PYTHONHASHSEED` values and assert identical JSON. Acceptance: byte-identical bodies
  across processes.
- Fix status: report-only

---

- ID: REV-410
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both
- Impact: §3.2 forbids human UUID entry as the normal entry point. The graph page's own
  entry point *is* a UUID text field, and a node click cannot open a focused graph — it only
  fills a detail panel. There is no path from "I can see this node" to "show me its
  neighbourhood".
- Evidence:
  `apps/web/app/graph/graph-explorer.tsx:104`:
  `<input value={symbolId} … placeholder="symbol UUID for local graph" />`; the validation
  message at `:78` reads `Enter both a repository ID and a symbol ID …`.
  Node clicks: `graph-explorer.tsx:112` passes `onNodeClick={setSelected}`; the detail
  `<aside>` (`:114`) renders the id and metadata and offers **no action**. There is no
  `requestGraph` / router call anywhere in a click handler.
  Structural nodes make a naive fix wrong: their ids are `repository:<uuid>`,
  `directory:<path>`, `file:<uuid>` (`main.py:281-283`), so a click handler must branch on
  `kind` rather than feeding `node.id` to the subgraph route.
  Reachability of the *same* symbol identity via other routes, integration only:
  `search-client.tsx:56-57` builds both `/repositories/{repo}/symbols/{symbol_id}` and
  `/graph?repository=…&symbol=…`, and the symbol page
  (`repositories/[repositoryId]/symbols/[symbolId]/page.tsx:19-20`) offers
  `Open graph →` with the same identity — so **search → symbol → graph does reach the same
  symbol id on integration**. It does **not** on `main`: `main`'s `search.py` has no
  `symbol_id` in its result rows (`git show main:apps/api/app/search.py | grep symbol_id`
  → no match) whereas integration's does (`apps/api/app/search.py:35`), and the live
  `GET /api/search/symbols?q=RunContext` response contains no `symbol_id` key at all. The
  tree route offers no symbol link on either target.
- Probable cause + diagnostic confidence: the graph page predates the symbol page and was
  never rewired. **Certain** for the missing click action and the UUID input (read
  directly); **certain** for the main/integration search difference (grep + live response).
- Smallest safe next step: in the node-detail panel, add one button that calls the existing
  `requestGraph(repositoryId, node.id)` when `node.kind` is a symbol kind. That reuses the
  function already in the file and needs no API change. Replacing the UUID input with the
  symbol-search picker is the follow-up (`01-runtime-and-provenance.md` records that a
  working-tree prototype of it existed on `main` at review start).
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: clicking a symbol node re-roots the graph on it
  and updates the URL; clicking a `file:`/`directory:` node does not attempt a subgraph
  request. Acceptance: a user can reach any symbol's focused graph without typing or pasting
  a UUID.
- Fix status: report-only

---

- ID: REV-411
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both
- Impact: §3.7 requires that a repository switch discards or isolates stale answers. Changing
  the "Repository" dropdown updates only the form state; the canvas keeps rendering the
  previous repository's graph, and the summary line keeps saying `API result`. The screen then
  asserts that repository B looks like repository A. The same applies after `loadFixture()`:
  the dropdown shows a real indexed repository while the canvas shows invented nodes.
- Evidence:
  `apps/web/app/graph/graph-explorer.tsx:103` — the `<select>`'s only handler is
  `onChange={(event) => setRepositoryId(event.target.value)}`. There is no `useEffect` on
  `repositoryId` that clears `graph`, `source` or `selected`; the only resets happen inside
  `requestGraph` (`:77`), `requestOverview` (`:91`) and `loadFixture` (`:98`), i.e. only when
  the user explicitly loads something.
  `source` is set to `'api'` at `:83` and `:94` and to `'fixture'` at `:98`, and never back
  to `'empty'` after the initial state (`:64`).
- Probable cause + diagnostic confidence: form state and result state are independent with no
  invalidation link. **Certain** — read directly; not observed in a browser.
- Smallest safe next step: one `useEffect` keyed on `repositoryId` that resets
  `{graph: {nodes:[],links:[]}, source:'empty', selected:null, error:''}`. Two lines.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: after loading a graph, change the repository
  selector and assert the canvas shows the empty state rather than the previous graph.
  Acceptance: the rendered graph always belongs to the repository named in the selector.
- Fix status: report-only

---

- ID: REV-412
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both
- Impact: The fixture demo is visually indistinguishable from real data and teaches wrong
  semantics. It claims a repository named `knowledge-way` — the product's own repository,
  which is not indexed in this deployment — and invents relationship types `renders` and
  `handles` with confidences `0.94` and `0.87`. No ingestion path can produce either the
  types or fractional confidences (only `call` and `import`, only 100 or 20). Because
  `relationshipStyle` has no branch for them they are drawn with the *verified call* style,
  and the legend directly beneath labels that style `Calls / references`. A screenshot of the
  fixture is a screenshot of fabricated verified evidence, marked only by the muted words
  `Fixture demo` in a 13 px summary line.
- Evidence:
  `apps/web/app/graph/graph-explorer.tsx:12-25` — the fixture, including
  `{ source: 'search-page', target: 'search-client', relationship: 'renders', confidence: 0.94 }`
  and `{ …, relationship: 'handles', confidence: 0.87 }`.
  `graph-canvas.tsx:9-13` — only `contains` and `defines` get their own style; everything
  else, including `renders`/`handles`, falls through to `{color:'#6386bd', arrow:5}`, the
  style the legend calls "Calls / references" (`graph-explorer.tsx:111`,
  `globals.css` `.edge-sample.calls`).
  Producible types, live: `SELECT DISTINCT relationship_type FROM symbol_edges` → `call`,
  `import` only. Producible confidences: `ingestion.py:19-20` → `100`, `20`.
  `source` state is tracked correctly (`:64`, `:98`) and surfaced at `:110`
  (`source === 'fixture' ? 'Fixture demo' : …`) — but only as muted text, and the repository
  selector is not reset (REV-411), so the header still names a real repository.
- Probable cause + diagnostic confidence: the fixture predates the API and was kept as a
  demo without being marked as non-evidence. **Certain**.
- Smallest safe next step: keep the fixture but make it unmistakable — an
  `aria-live` banner with a distinct background, prefix every fixture label
  (`DEMO · knowledge-way`), and change its relationship types to the ones the system can
  actually produce. Cheapest correct alternative: delete the fixture; the empty state already
  explains what to do.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: assert a fixture graph renders a
  visible non-muted "demo data" banner, and that no fixture relationship type is absent from
  the set the ingestion pipeline can emit. Acceptance: a screenshot cannot be mistaken for
  workspace data.
- Fix status: report-only

---

- ID: REV-413
- Category: BUG_CONFIRMED
- Severity: medium
- Evidence level: source-reviewed
- Applies to: both
- Impact: Following a second `Open graph →` link (or any client-side navigation that changes
  `?symbol=`) reloads the canvas for the new symbol but leaves the form inputs showing the
  previous symbol. Pressing "Focus symbol" then silently re-requests the *old* symbol. The
  visible controls and the visible graph disagree.
- Evidence:
  `apps/web/app/graph/graph-explorer.tsx:60-62` reads the query string once into
  `useState` initial values:
  `const [symbolId, setSymbolId] = useState(initialSymbolId)`.
  `:89` re-fires on change: `useEffect(() => { if (initialRepositoryId && initialSymbolId) void requestGraph(initialRepositoryId, initialSymbolId); … }, [initialRepositoryId, initialSymbolId])`
  — it passes the new values as arguments but never calls `setSymbolId` / `setRepositoryId`,
  so the state (and therefore the inputs, and therefore the next manual submit) keeps the
  first values.
  `requestGraph`'s default parameters (`:76`) come from state, which is why the subsequent
  manual submit uses the stale symbol.
- Probable cause + diagnostic confidence: `useState(searchParams…)` initialiser treated as if
  it tracked the prop. **Certain** — standard React semantics, read directly. Not
  browser-observed.
- Smallest safe next step: inside that effect, also
  `setRepositoryId(initialRepositoryId); setSymbolId(initialSymbolId);`. Two statements.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: navigate `/graph?…&symbol=A` → `…&symbol=B` and
  assert the symbol input reads `B`. Acceptance: form state always matches the rendered
  graph's root.
- Fix status: report-only

---

- ID: REV-414
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: source-reviewed (rendering); PostgreSQL integration-tested (the data properties that drive it)
- Applies to: both
- Impact: §5.D asks whether the canvas is comprehensible at many nodes. Three concrete
  reasons it is not, at the default 100-node cap:
  (a) labels are gated behind a zoom threshold that auto-fit will not reach, so the user sees
  ~100 unlabelled dots plus one labelled root; (b) node radius is driven by a `degree` that
  counts duplicate parallel edges, so it does not mean what it appears to mean and saturates
  anyway; (c) `qualified_name` is not unique, so several nodes carry the identical label with
  no path shown to tell them apart.
- Evidence:
  (a) `apps/web/app/graph/graph-canvas.tsx:52`:
  `const showLabel = node.isRoot || node.id === selectedNodeId || node.id === hoveredNodeId || (globalScale >= 1.65 && (node.degree ?? 0) >= 4);`
  Auto-fit is `onEngineStop={() => graphRef.current?.zoomToFit(350, 70)}` (`:75`) into a
  viewport of `width = container.clientWidth`, `height = max(460, min(680, innerHeight-260))`
  (`:24`). A 100-node force layout fitted with 70 px padding into ~760 × 520 px yields a
  `globalScale` below 1.65, so the condition is false for every non-root, non-hovered node.
  I did **not** measure `globalScale` in a browser — this is the reason the evidence level is
  `source-reviewed`, and it is the one item here that a browser pass should confirm.
  (b) `graph-canvas.tsx:43`: `radius = node.isRoot ? 10 : Math.min(7, 4 + Math.sqrt(node.degree ?? 0))`,
  where `degree` is counted by `mapApiGraph` (`graph-explorer.tsx:51-53`) over the raw link
  list, duplicates included. Live: `RunContext`'s 211 edges include 12 duplicate
  `(source,target,type)` groups with multiplicity up to 4, and 6 self-loops;
  repository-wide there are **7 423** duplicate groups and **110** self-loops
  (`SELECT count(*) FROM (SELECT source_symbol_id,target_symbol_id,relationship_type FROM symbol_edges WHERE source_symbol_id IS NOT NULL AND target_symbol_id IS NOT NULL GROUP BY 1,2,3 HAVING count(*)>1) t`).
  In the repository overview it is far worse — 7 853 edges over 152 distinct relationships,
  one pair drawn 2 485 times (REV-423) — so the radius, which saturates at `degree >= 9`,
  conveys nothing at all: every selected node is at maximum size. The canvas is also asked to
  lay out **7 952 links over 100 nodes**, which is the dominant legibility problem and was not
  observable before the route went live.
  (c) `mapApiGraph:41` sets `label = qualified_name` first; nodes carry `file_id` but no
  `path` (REV-407). The live `max_nodes=6` response for `RequestUsage.extract` contains
  **four nodes labelled `_map_usage`** from four different provider modules, with nothing on
  screen to distinguish them.
  Positives worth recording: `relationshipStyle` (`graph-canvas.tsx:9-13`) *does* visually
  separate `contains` (purple dashed, no arrow), `defines` (green dashed, no arrow) and
  everything else (blue solid, arrow), and `globals.css` `.edge-sample.{contains,defines,calls}`
  matches those colours and dash styles, so the three-way legend is semantically correct for
  the three types it names. The legend of node kinds is derived from the data
  (`presentKinds`, `graph-explorer.tsx:68`) rather than hardcoded, and root/selection
  highlighting is real (white stroke + larger radius + forced label, `:43,51,52`).
  Accessibility: the canvas has no text alternative, no keyboard focus and no reduced-motion
  handling — flagged here for workstream A rather than analysed.
- Probable cause + diagnostic confidence: label gating tuned on a small fixture (8 nodes)
  where auto-fit does exceed the threshold. **High** for (a) — arithmetic, not measured;
  **certain** for (b) and (c) — measured.
- Smallest safe next step: (b) and (c) first, since they are cheap and certain: de-duplicate
  links in `mapApiGraph` (one `Map` keyed on `source|target|relationship`, keeping a `count`)
  and append the file basename to the label when `qualified_name` is not unique in the
  response. For (a), drop the `globalScale` gate and label the top-N nodes by degree instead.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: browser check at `max_nodes=100` — count visible
  labels after auto-fit (> 10 expected) and assert no two visible labels are identical; unit
  test that `mapApiGraph` collapses parallel links and reports a multiplicity.
- Fix status: report-only

---

- ID: REV-415
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: PostgreSQL integration-tested
- Applies to: both
- Impact: `confidence` exists in the schema, so this is not "confidence displayed when it is
  not stored" — it is worse in a subtler way. The stored value is a **two-valued resolution
  flag** (100 = "the target name was unique in the repository", 20 = "unresolved"), rendered
  as a continuous percentage with a four-step filter (`Any / 50 / 75 / 90`). Because both
  graph routes require *both* endpoints and unresolved edges have no target, **every edge the
  graph can show has confidence exactly 100**. The "Minimum confidence" control is therefore
  a guaranteed no-op on API data and only ever changes anything for the fixture's invented
  0.94 / 0.87 values. A user who sets "90 % or higher" and sees the graph unchanged will
  reasonably conclude the edges were independently vetted.
- Evidence:
  Schema: `\d symbol_edges` → `confidence integer NOT NULL`; model default `50`
  (`apps/api/app/models.py:37`). Only two values are ever written:
  `apps/api/app/ingestion.py:19-20,134`.
  Distribution of graph-visible edges (T12):

  ```sql
  SELECT relationship_type, confidence, count(*) FROM symbol_edges
  WHERE source_symbol_id IS NOT NULL AND target_symbol_id IS NOT NULL GROUP BY 1,2;
  --  call | 100 | 66061        (single row)
  ```

  Repository-wide: `call/100` 67 792, `call/20` 54 439, `import/20` 7 712, `import/100`
  6 623 — but `import` edges always have `source_symbol_id IS NULL`
  (`ingestion.py:146` passes `None` as the source symbol) and confidence-20 edges always
  have `target_symbol_id IS NULL`, so neither can enter a graph.
  Filter: `graph-explorer.tsx:71` `(link.confidence == null || link.confidence >= minimum)`
  with options `0 / 0.5 / 0.75 / 0.9` (`:111`). Live edges normalise to `1.0`
  (`mapApiGraph:48`), which passes every threshold. Side effect: the "Relationship" dropdown
  is likewise derived from present types (`:67`) and will only ever offer `call` for a
  subgraph, plus `contains` / `defines` for the integration overview — `import` can never
  appear.
- Probable cause + diagnostic confidence: a resolution flag was named "confidence" and the UI
  built a percentage filter on top of it. **Certain** — measured end to end.
- Smallest safe next step: rename the concept at the edges of the system rather than in the
  schema — expose `resolution: 'name-unique' | 'unresolved'` in `edge_out`, drop the
  confidence percentage from the link tooltip and the symbol page, and replace the
  four-step filter with a "hide unresolved" toggle (which is meaningful once `import` edges
  become renderable).
- Affected data/migrations/providers/cost: no migration required for the presentation fix;
  see REV-401 for the underlying data question.
- Recommended tests + acceptance criteria: assert no UI element shows a confidence percentage
  for an edge whose stored value comes from a binary flag; assert every filter control
  changes the rendered graph for at least one reachable input. Acceptance: no control in the
  graph UI is a permanent no-op.
- Fix status: report-only

---

- ID: REV-416
- Category: BUG_CONFIRMED
- Severity: medium — **no longer reproducible; resolved by the 14:34 deployment, retained as a merge-hazard record**
- Evidence level: manual live acceptance
- Applies to: `main` (running deployment, before 14:34) — not integration
- Impact: The "Repository map" button on the running deployment cannot work. The served web
  bundle calls `/api/repositories/{id}/graph`, a route that exists only on the integration
  branch, while the running API is `main`. The user gets the generic
  `Unable to load repository graph data.` error with no hint that the endpoint is missing.
- Evidence:
  The call is present in the **built bundle the running container actually serves**, so this
  is not a working-tree-only observation:

  ```bash
  docker compose exec -T web sh -c 'grep -rho ".\{60\}max_nodes=100.\{10\}" \
    .next/standalone/.next/server/chunks/ssr/_0epg0oz._.js'
  # f.api)(`/repositories/${encodeURIComponent(k.trim())}/graph?max_nodes=100`);v(m(a))
  ```

  The same call exists in the pinned worktree at
  `apps/web/app/graph/graph-explorer.tsx:94`, which is why it only misfires on the `main`
  lineage. The route is absent from `main`:
  `git show main:apps/api/app/main.py | grep -c "repositories/{repo_id}/graph"` → `0`.
  Live confirmation:

  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" \
    "http://localhost:8000/api/repositories/21ffa409-9e13-493a-b919-7bb6a5b80bb9/graph?max_nodes=100"   # 404
  curl -s http://localhost:8000/openapi.json | python3 -c "import json,sys;print([p for p in json.load(sys.stdin)['paths'] if 'graph' in p])"
  # ['/api/repositories/{repo_id}/symbols/{symbol_id}/subgraph']
  ```

  **Now resolved by deployment, not by a fix.** After the 14:34 rebuild the route exists and
  the same request returns 200 (T22). The defect was a branch/deployment mismatch, and it
  disappeared when the API caught up with the UI:

  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" ".../repositories/21ffa409-…/graph?max_nodes=100"   # 200
  ```

- Probable cause + diagnostic confidence: the UI was written against the integration API
  surface while the running API was `main`. **Certain** — confirmed in the served bundle and
  by the live 404 before the rebuild, and by the 200 after it.
- Smallest safe next step: nothing to fix in the code under review. Retained because it
  documents a real class of hazard — the web app can ship calls to routes the deployed API does
  not have, and the only symptom is a generic error toast. A route-existence smoke test is the
  durable fix; see below.
- Affected data/migrations/providers/cost: none. Note the wider merge hazard already recorded
  in `01-runtime-and-provenance.md`: five of the six modified files collide with integration's
  newer versions, `graph-explorer.tsx` among them (46+/24-).
- Recommended tests + acceptance criteria: a smoke test that every endpoint the web app calls
  exists in the API's OpenAPI document. Acceptance: no UI action can reach a 404 route.
- Fix status: report-only

---

- ID: REV-418
- Category: TEST_GAP
- Severity: medium
- Evidence level: unit/API-tested
- Applies to: integration (the tests do not exist on `main`)
- Impact: The three graph tests pass and cover the happy path, but they run against a fake
  session whose `scalars()` ignores every `WHERE` clause, so no test exercises the SQL scope
  predicates, any realistic corpus, or any of the defects above. Every finding in this report
  is invisible to the suite.
- Evidence:
  `apps/api/tests/test_graph_api.py:15-37` — `GraphDb.scalars` dispatches
  purely on `statement.column_descriptions[0]["entity"]` and returns the full list:

  ```python
  def scalars(self, statement):
      entity = statement.column_descriptions[0]["entity"]
      return Result(self.symbols if entity is Symbol else self.edges if entity is SymbolEdge else self.files if entity is File else [])
  ```

  So `Symbol.repository_id == repo_id`, `Symbol.id.in_(ids)` and
  `SymbolEdge.repository_id == repo_id` are never evaluated; what the tests actually verify
  is the Python-side re-filter in `scoped_*`. That is a real (and valuable) belt-and-braces
  check, but it is not a scope test.
  Coverage of the three tests (`:49`, `:62`, `:75`): symbol detail + callers/callees +
  foreign-symbol 404; a 3-symbol subgraph with `max_nodes=2` asserting
  `truncated is True` and `depth` validation 422s; and a 6-node `/graph` asserting the kinds
  and the presence of `contains`, `defines` and `type == "calls"` edges.
  Absent: no assertion that a truncated response reports counts; no assertion that every edge
  endpoint is inside `nodes` (the invariant this workstream verified by hand, T8); no
  cap-boundary stability test (REV-404); no `PYTHONHASHSEED` reproducibility test (REV-409);
  no edge-schema uniformity test (REV-408 — the test in fact *encodes* the inconsistency);
  no PostgreSQL integration test for any graph route; and **no web test infrastructure at
  all** — `find apps -name "*.test.ts*" -not -path "*/node_modules/*"` → empty,
  `apps/web/package.json` has no test script and no test dependency, so `mapApiGraph`,
  `filteredGraph` (REV-403) and `graphNodeKind` are entirely untested.
  Verification that the suite runs: `docker run --rm --network none -v <worktree>/apps/api:/src:ro -w /src knowledge-way-api python -m pytest tests/test_graph_api.py -q`
  → `3 passed, 4 warnings in 0.69s`.
- Probable cause + diagnostic confidence: fake session chosen to keep tests dependency-free.
  **Certain**.
- Smallest safe next step: add one PostgreSQL-backed graph test using the existing container
  (a handful of files/symbols/edges, two repositories) asserting scope isolation and edge
  endpoint containment under `max_nodes=2`. Then a `mapApiGraph` unit test — that needs a web
  test runner, which is the larger decision (workstream G).
- Affected data/migrations/providers/cost: test-only; a PostgreSQL test needs a disposable
  database, not the live one.
- Recommended tests + acceptance criteria: as listed above. Acceptance: each of REV-402,
  REV-404, REV-408 and REV-409 has a test that fails before its fix and passes after.
- Fix status: report-only

---

- ID: REV-422
- Category: OPTIMIZATION_OPPORTUNITY
- Severity: low
- Evidence level: source-reviewed
- Applies to: both
- Impact: The companion to REV-414(a). Auto-fit exists but is wired to fire exactly once, and
  the force simulation has no collision or charge tuning, so a 100-node graph settles as an
  overlapping cluster and any later change to the data or the viewport leaves it framed for
  the previous layout. This is an improvement opportunity, not a confirmed defect: no
  before/after measurement was taken, and §7 forbids claiming a benefit without one.
- Evidence:
  `apps/web/app/graph/graph-canvas.tsx:72-75` (pinned worktree):

  ```tsx
  d3AlphaDecay={0.035}
  d3VelocityDecay={0.3}
  cooldownTicks={180}
  onEngineStop={() => graphRef.current?.zoomToFit(350, 70)}
  ```

  Three observations follow from that block and `:24`:
  (a) `zoomToFit` runs only on `onEngineStop`. The resize handler (`:21-29`) updates
  `dimensions` but never re-fits, so resizing the window after the engine has stopped leaves
  the graph framed for the old viewport.
  (b) `cooldownTicks={180}` with `d3AlphaDecay={0.035}` is a fixed tick budget regardless of
  node count. The default `ForceGraph2D` charge/link distances are used unchanged and there is
  no `d3Force('collide', …)`, so nothing prevents node overlap — which is what makes the
  labelling problem in REV-414(a) visible rather than merely theoretical.
  (c) `zoomToFit(350, 70)` reserves 70 px padding on a viewport whose height is
  `Math.max(460, Math.min(680, window.innerHeight - 260))` (`:24`), i.e. at most 680 px, so
  padding consumes ~20 % of the vertical space at the small end.
  Edits of exactly this shape (auto-fit re-invocation, colour and force tuning) were written
  into the main working tree by another agent session during this review. Under the
  report-only mandate they are recorded here as an opportunity; this workstream did not
  author them, did not run them, and makes no claim about their effect.
- Probable cause + diagnostic confidence: parameters tuned against the 8-node fixture.
  **Medium** — the code is unambiguous, the *consequence* at 100 nodes is reasoned, not
  measured.
- Smallest safe next step: call `zoomToFit` from the existing resize handler as well as
  `onEngineStop` (the `graphRef` is already held at `:17`), and add a collision force sized
  from the node radius function already at `:43`. Both are local to `graph-canvas.tsx`.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: browser measurement at `max_nodes=100` before and
  after — record `globalScale` after auto-fit and the count of overlapping node pairs.
  Acceptance: all nodes inside the viewport after both engine stop and window resize, and a
  stated overlap figure that improved. Without those two numbers this stays an opportunity,
  not a fix.
- Fix status: report-only

---

- ID: REV-417
- Category: DESIGN_GAP
- Severity: low
- Evidence level: source-reviewed
- Applies to: both
- Impact: §3.4 forbids rendering declared dependencies as verified `calls` / `references` /
  `imports`. Today the invariant is **not violated in fact** — no endpoint emits
  `declared_dependency` (there is no workspace graph route, `workspaces` is empty, and
  `symbol_edges` only holds `call` and `import`). But the renderer has no branch for it: the
  moment a workspace overview emits `declared_dependency`, or `import` edges become
  renderable, they will be drawn with the exact style the legend calls "Calls / references".
  The gap is latent, and it is one endpoint away from being an active misleading-evidence bug.
- Evidence:
  `apps/web/app/graph/graph-canvas.tsx:9-13` — `contains` and `defines` are special-cased and
  everything else returns the solid blue arrowed style; `graph-explorer.tsx:111` labels that
  style `Calls / references`; `globals.css` `.edge-sample.calls { border-top-color: #6386bd; }`
  matches. `graph-model.ts` has no relationship vocabulary at all (`relationship: string`),
  so nothing constrains what can arrive.
  No `declared_dependency` string exists anywhere under `apps/` on the integration branch;
  `WorkspaceDependency` is exposed only through the CRUD routes (`main.py:95-119`), never as
  graph edges.
- Probable cause + diagnostic confidence: the style function was written for the two
  structural types that exist and defaults everything else to "call". **Certain**.
- Smallest safe next step: make the default explicit — an `unknown`/`declared` style (grey,
  dashed, no arrow) plus a legend entry, so any new relationship type degrades to "not a
  verified code edge" rather than to "call". Add the type to `graph-model.ts` as a union.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: assert an edge with `relationship:
  'declared_dependency'` renders with the non-verified style and a distinct legend entry.
  Acceptance: no unrecognised relationship type can inherit the verified-call style.
- Fix status: report-only

---

- ID: REV-420
- Category: DESIGN_GAP
- Severity: low
- Evidence level: manual live acceptance
- Applies to: both
- Impact: `GET /api/files/{file_id}/symbols` — the route the graph workflow depends on to turn
  a file into symbol ids — performs no repository scope check and no existence check. It
  returns `200 []` for a nonexistent file id, and for a real file id it returns that file's
  symbols regardless of any repository or workspace context the caller believes it is in.
- Evidence:
  `apps/api/app/main.py:221-222`:

  ```python
  @app.get('/api/files/{file_id}/symbols')
  def symbols(file_id:str,db:Session=Depends(get_db)): return [ … for s in db.scalars(select(Symbol).where(Symbol.file_id==file_id)).all()]
  ```

  No `Repository`/`File` lookup, no `repository_id` filter — the only graph-adjacent route
  without the `scoped_*` treatment applied everywhere else (`main.py:56-62`).
  Live: `curl -o /dev/null -w "%{http_code}" http://localhost:8000/api/files/00000000-0000-0000-0000-000000000000/symbols`
  → `200`.
  Likely overlaps workstream B (§5.B scope checks); recorded here because it is the id
  resolution path §5.D navigation depends on.
- Probable cause + diagnostic confidence: written as a convenience lookup before the scoped
  helpers existed. **Certain**.
- Smallest safe next step: 404 on a missing file and accept an optional `repository_id` to
  validate against, mirroring `scoped_symbol`.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: unknown file id → 404; file from another
  repository → 404 when a repository scope is supplied. Acceptance: consistent with the other
  symbol routes.
- Fix status: report-only

---

- ID: REV-421
- Category: DOCUMENTATION_GAP
- Severity: info
- Evidence level: source-reviewed
- Applies to: integration
- Impact: The `structural-cards` routes are the best-behaved part of this workstream and are
  worth recording as the pattern to copy, with two small blemishes.
- Evidence:
  `apps/api/app/main.py:192-201` — sorting is fully deterministic and derived from data, not
  the database: `sorted(…, key=lambda c:(c.path.count('/'), c.path, c.kind))`; the path
  filter is applied **before** the `limit` (`:200` then `:201`), which is exactly what §5.B
  asks for and the opposite of a filter-after-LIMIT bug; `kind` is validated against a closed
  set with 422 (`:195`); the repository is checked (`:194`).
  `apps/api/app/structural_cards.py:12-13,47` — `canonical()` uses
  `json.dumps(sort_keys=True, separators=…, ensure_ascii=True)` and both fingerprints are
  content-derived, so cards are reproducible.
  Blemish 1: `truncated: len(cards) > limit` (`:201`) again reports no count — same shape as
  REV-402, one line to fix while REV-402 is being fixed.
  Blemish 2: the singular route (`:202-206`) never checks the repository, so a request against
  a nonexistent repository returns `404 Structural card not found` instead of
  `404 Repository not found` — a confusing but harmless diagnostic.
  Now reachable live, and empty (T28):

  ```bash
  curl -s ".../repositories/21ffa409-…/structural-cards"
  # {"repository_id":"21ffa409-…","path":"","cards":[],"truncated":false}   200, 4 ms
  ```

  `structural_cards` holds **0 rows** after the `0008` migration. That is a schema fact, not
  evidence that `refresh_structural_cards` works — cards are only written during an index run
  (`ingestion.py:235`), and no index has run since the migration. No card run was triggered.
  `refresh_structural_cards` itself therefore remains `source-reviewed`, and worth flagging to
  workstream E: it iterates all 136 566 edges once **per directory-or-package path**
  (`structural_cards.py:30-39`), which is a quadratic term inside every index run.
- Probable cause + diagnostic confidence: n/a. **Certain** — read directly.
- Smallest safe next step: add the omitted count; add the repository existence check.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: assert `truncated` is accompanied by a count and
  that a nonexistent repository yields `Repository not found`.
- Fix status: report-only

---

## Not assessed

- **Browser behaviour of the canvas.** No browser session was driven by this workstream, to
  avoid colliding with the dedicated live browser pass. REV-403, REV-411, REV-413, REV-422
  and part (a) of REV-414 are therefore `source-reviewed` and each names the exact observation
  that would upgrade it to `browser E2E verified`. The `globalScale` value reached by
  `zoomToFit` at 100 nodes is the single most valuable measurement still outstanding.
  Note that a browser check is currently **not** a valid test of the pinned target for the
  frontend findings: the served `standalone` bundle differs from `c122529` (it already
  normalises link endpoints — see the target-drift caveat). Reproducing REV-403, REV-411,
  REV-413 or REV-422 requires building the pinned worktree, which was not done.
- ~~**Integration-branch runtime for `/graph` and `/structural-cards`.**~~ **Now assessed.**
  This was `not assessed` for most of the review because neither route existed on the live
  `main` stack and migrating `0004` → `0008` was outside my mandate. A sibling session
  performed that migration at 14:34, so both routes were re-tested against the real
  21 324-symbol repository (T22–T28), which upgraded REV-408 and REV-409 from
  `unit/API-tested` to `PostgreSQL integration-tested` and produced REV-423 and the sharpened
  REV-405. I did not request, perform or authorise the migration.
- **`refresh_structural_cards` behaviour.** The `structural_cards` table now exists but holds
  0 rows, because cards are only written during an index run and none has run since the
  migration. An empty response is a schema fact, not a working pipeline. Triggering a card
  run was explicitly out of scope, so the function stays `source-reviewed` (REV-421).
- **Cap-boundary instability at the default `max_nodes=100`.** Proven at `max_nodes=4..9`
  (REV-404). Whether the *default* cap splits a name-collision group depends on the symbol;
  it does not for `Agent` (checked for every cap 2…100). Establishing how often it does
  across all 21 324 symbols would need a full replay per symbol, which was not run.
- **Behaviour after a re-index.** Re-indexing would have been long-running work outside the
  §4 gate, so the "different data after a re-index" half of REV-404 rests on the proven facts
  that ids are `uuid4()` and that the previous session's ids are gone — not on an observed
  before/after pair.
- **Mixed-commit graphs.** `files` currently holds exactly one distinct
  `indexed_commit_sha`, so no mixing could be observed. The publish-on-failure mechanism in
  REV-407 was read, not reproduced (reproducing it means running a failing index).
- **`declared_dependency` rendering.** No endpoint emits such edges and `workspaces` is
  empty, so §3.4 could not be exercised; REV-417 is a latent-gap finding, not an observed
  violation.
- **Cross-repository graph behaviour.** One repository is indexed. Repository scope was
  verified as a *predicate* (SQL + Python double filter, plus the foreign-symbol unit test),
  not by observing a second repository's data being excluded.
- ~~**Edge-budget worst case.**~~ **Now measured.** Initially recorded as unmeasured, with the
  largest observed case being 211 edges over 100 nodes. The live `/graph` run supersedes that:
  **7 952 edges over 100 nodes, 3.6 MB**, multiplicity up to 2 485. REV-405 no longer rests on
  the absence of a cap in the source. No deliberately pathological input was constructed —
  this is the default request the UI issues.
- **Behaviour of the `0008` migration itself.** I verified only its outcome (version row,
  preserved row counts, `symbol_edges.target_name` now `text`, two new empty tables). Upgrade
  and downgrade correctness belong to workstream C; I did not run either.
- **`repository_graph`'s greedy fill semantics.** `main.py:279` uses `continue`, not `break`,
  so a low-cost symbol in an already-selected file can displace a higher-degree symbol in a
  deep new directory. Deterministic and bounded, so no finding was raised; the resulting
  selection is simply not "top-N by degree" as it first reads. The live run (T23) shows the
  budget splitting as 46 structural nodes to 54 symbols, which is consistent with that greedy
  behaviour but was not isolated as its cause. Whether it materially changes which symbols a
  user sees is still not assessed; REV-423 shows the ranking has a larger problem anyway.
