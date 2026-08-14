# Packet 0.4 — GitNexus local test drive

**Observation date:** 2026-08-14 UTC

**Tool/version:** GitNexus 1.6.9 (`gitnexus --version`)

**License posture:** This packet records CLI-observed behavior and raw outputs only. No GitNexus (PolyForm Noncommercial) source was copied, read into this repository, or mechanically rewritten. No chat/LLM mode was invoked; product-LLM spend is **USD 0.00**.

## Reproduction

```bash
GITNEXUS_SKIP_OPTIONAL_GRAMMARS=1 ONNXRUNTIME_NODE_INSTALL=skip npm install -g gitnexus
# Clone each corpus member and detach at the SHA in benchmarks/corpora.json.
gitnexus analyze /path/to/starlette --index-only --name kw-starlette-0-4
# Repeat for fastapi and pydantic, then from the selected indexed checkout:
gitnexus eval-server --port 4850 --idle-timeout 300
python benchmarks/scripts/run_gitnexus_evaluation.py \
  --base-url http://127.0.0.1:4850 --repo kw-starlette-0-4 \
  --output benchmarks/results/2026-08-14-gitnexus-fastapi-stack.json
```

The runner uses the documented `eval-server` HTTP surface (`POST /tool/{query,context,impact,cypher}`), not a chat mode. It preserves each tool response and wall latency. Context/impact calls resolve the `Route` UID first (`Class:starlette/routing.py:Route`); a direct UID impact call was also observed. Trace is deliberately **not** issued with an ambiguous bare symbol: its source/destination UIDs need an explicitly selected target pair, which this class does not supply.

## Pinned workspace and index evidence

| member | pinned SHA | GitNexus alias | observed index | analyze wall time |
|---|---|---|---:|---:|
| Starlette 0.38.6 | `8d0cff820f89b5d5b19677246293513a9d1c952c` | `kw-starlette-0-4` | 2,333 nodes, 4,048 deduplicated `CodeRelation` edges, 97 clusters, 57 flows | 9.85 s |
| FastAPI 0.115.0 | `40e33e492dbf4af6172997f4e3238a32e56cbe26` | `kw-fastapi-0-4` | 21,344 nodes, 27,362 edges, 278 clusters, 136 flows | 19.16 s |
| Pydantic 2.9.2 | `7cedbfb03df82ac55c844c97e6f975359cb51bb9` | `kw-pydantic-0-4` | 18,212 nodes, 30,544 edges, 595 clusters, 268 flows | 22.29 s |

Starlette's 9.85 s wall time is comparable to the owner-observed ~9.5 s keyless bar (not faster); this includes a 1.15 s process/measurement envelope around GitNexus's reported 8.7 s index duration. The 4,048 graph count comes from `MATCH ()-[r:CodeRelation]->() RETURN count(DISTINCT r)`—never an undeduplicated relation-row count.

Initial Starlette analysis reported: `FTS extension unavailable; continuing without FTS features. load-only policy: extension not pre-installed`. This is an **environment limitation**, not a product-quality result. A subsequent `gitnexus analyze --repair-fts` completed successfully in this environment; replay users must run that repair and record its own result before treating keyword/BM25 comparisons as fair. This packet makes no retrieval-quality claim from the temporarily degraded first pass.

Raw replay evidence: [`results/2026-08-14-gitnexus-fastapi-stack.json`](results/2026-08-14-gitnexus-fastapi-stack.json). The selected Starlette index status reported the same pinned `8d0cff8` current/indexed commit.

## Appendix A.7 question-class results

Classifications distinguish **accuracy gaps** (a representable single-repository request with incomplete/noisy output) from **representation gaps** (the requested relation has no modelled cross-repository/group or architecture input). “Not representable” is a result, not a failure hidden as an incorrect answer.

| # | question class / exercised prompt | tool | result | latency ms | gap/evidence |
|---:|---|---|---|---:|---|
| 1 | Where is route registration implemented? | query | correct | 269.802 | returns `starlette/routing.py` route-related definitions (accuracy limited by ranking noise) |
| 2 | What does `Route` do? | context | correct | 65.376 | UID resolves `Class:starlette/routing.py:Route`, lines 207–301 |
| 3 | Who calls `Route`? | context | partial | 56.585 | imports/call relations returned, but dynamic/interface dispatch is incomplete |
| 4 | What does `Route` call? | context | partial | 53.740 | inheritance/override and members returned; not a complete execution-call proof |
| 5 | Trace X to Y | context after UID resolution | not-representable | 46.436 | no target symbol pair/oracle was supplied; runner never passes bare names to trace |
| 6 | What changes if `Route` changes? | impact | partial | 62.213 | 27 upstream impacted symbols; `epistemic: lower-bound` |
| 7 | Which repository consumes endpoint X? | query | not-representable | 484.825 | individual indexes exist, but `gitnexus group` cross-repository evaluation is explicitly Stage 3 scope |
| 8 | Which tests should run after changing `Route`? | context | correct | 95.520 | context returns test-file import evidence, including routing/test-client suites |
| 9 | Where does this value originate? | context | partial | 84.471 | source-level context is present but provenance/value-flow is not complete |
| 10 | Does equivalent functionality already exist? | query | partial | 254.707 | related definitions/flows are searchable; equivalence is not a declared semantic relation |
| 11 | How does this user action flow across repositories? | query | not-representable | 305.391 | cross-repository group/contract evidence intentionally out of scope until Stage 3 |
| 12 | What architecture knowledge is missing from the index? | cypher | partial | 3.981 | node inventory is queryable, but missing runtime/contracts/dynamic-dispatch knowledge requires external evidence |

**Epistemic evidence.** `context Route` returned `epistemic: lower-bound` and the boundary: `BaseRoute is an interface with 4 implementations; callers that bind via the interface (e.g. a DI container or dynamic dispatch) are not traced to the concrete symbol — actual impact may be higher.` UID-targeted `impact Route` likewise returned `epistemic: lower-bound`, the same boundary, `impactedCount: 27`, and depth counts 3/11/13. Thus neither context nor impact output is represented as complete.

## Gold-task applicability

The 25 Stage-0 gold tasks are historical file/symbol change tasks across all three corpus members. Their search/navigation components are applicable to classes 1–4, 6, 8–10; this run deliberately uses the shared framework anchor (`starlette.routing.Route`) so observed raw evidence is independently replayable. Classes 7 and 11 require the excluded group feature; class 5 requires a concrete pair; class 12 needs an architecture oracle. A later Stage-3 group evaluation may add cross-repository task-oracle scoring without reclassifying these scope-limited outcomes.

## Conclusion

GitNexus gives fast, keyless, pinned single-repository graph observation, including explicit lower-bound completeness warnings. The main gaps in this controlled run are representation (cross-repository/group, concrete trace pair, runtime/value provenance) rather than a claim that its keyword quality is poor. No semantic/chat result is manufactured, and no LLM budget was consumed.
