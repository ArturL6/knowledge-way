# Packet 0.4 — GitNexus local test drive

**Observed:** 2026-08-14 UTC; **GitNexus:** 1.6.9; **product-LLM spend:** USD 0.00.

This is a license-clean behavior study. It records CLI/eval-server requests and
responses; it neither copies nor mechanically rewrites GitNexus's PolyForm
Noncommercial source. Chat/LLM mode was not used.

## Reproduction and corpus identity

```bash
GITNEXUS_SKIP_OPTIONAL_GRAMMARS=1 ONNXRUNTIME_NODE_INSTALL=skip npm install -g gitnexus
# clone and detach each member at the corpus SHA, then index it
cd /path/to/starlette && gitnexus analyze . --name kw-starlette-0-4-remediation
gitnexus eval-server --port 4849 --idle-timeout 120
python benchmarks/scripts/run_gitnexus_evaluation.py \
  --base-url http://127.0.0.1:4849 --repo kw-starlette-0-4-remediation \
  --output benchmarks/results/2026-08-14-gitnexus-fastapi-stack.json
```

The pinned `fastapi-stack` revisions are FastAPI `40e33e492dbf4af6172997f4e3238a32e56cbe26`, Starlette `8d0cff820f89b5d5b19677246293513a9d1c952c`, and Pydantic `7cedbfb03df82ac55c844c97e6f975359cb51bb9`. The evaluated Starlette index reports 2,333 symbols and 4,048 edges. Its owner-recorded analysis time was 9.85 s, comparable to the ~9.5 s keyless bar (not a claim of improvement).

Initial FTS availability was limited because LadybugDB's extension needed egress. `gitnexus analyze --repair-fts` subsequently succeeded; keyword/BM25 observations must be called **environment-limited** if that repair cannot be replayed. The raw, single-run fixture is [`results/2026-08-14-gitnexus-fastapi-stack.json`](results/2026-08-14-gitnexus-fastapi-stack.json).

## UID and trace protocol

The runner first calls eval-server `cypher` to resolve both exact IDs:

* `Class:starlette/routing.py:Route`
* `Class:starlette/routing.py:BaseRoute`

It passes the resolved Route UID to context and impact. It also submits the
resolved source/destination pair to eval-server `trace`; v1.6.9 responds HTTP
400, `unsupported tool 'trace'` (supported endpoints exclude trace). This is a
real attempted trace result, classified **not-representable** for this HTTP
interface—not a substituted context result. The raw request and error are in
observation 05.

Context and UID-targeted upstream impact both report `epistemic: lower-bound`.
Impact reports 27 symbols, depth counts 3/11/13, and the boundary that
`BaseRoute` has four implementations whose interface/dynamic-dispatch callers
are not traced. These fields are recorded verbatim in the fixture; they are not
claimed as complete impact.

## Appendix A.7 results

| # | class | tool | classification | latency (ms) | evidence / gap |
|---:|---|---|---|---:|---|
| 1 | Where is feature implemented? | query | correct | 215.963 | `starlette/routing.py` returned |
| 2 | What does a symbol do? | context UID | correct | 65.051 | Route class/range identified |
| 3 | Who calls it? | context UID | partial | 51.075 | import callers, lower-bound graph |
| 4 | What does it call? | context UID | partial | 50.879 | members/inheritance, not complete calls |
| 5 | Trace X to Y | trace UIDs | not-representable | 0.601 | eval-server endpoint unsupported |
| 6 | What changes if X changes? | impact UID | partial | 0.525 | 27, lower-bound impact |
| 7 | Which repo consumes endpoint X? | query | not-representable | 223.622 | repository groups deferred to Stage 3 |
| 8 | Which tests should run? | context UID | correct | 63.241 | test-file imports listed |
| 9 | Where does a value originate? | context UID | partial | 67.402 | no complete value provenance |
| 10 | Does equivalent functionality exist? | query | partial | 289.693 | discovery, not equivalence proof |
| 11 | How does action flow across repos? | query | not-representable | 318.334 | group evaluation excluded until Stage 3 |
| 12 | What architecture knowledge is missing? | cypher | partial | 2.680 | inventory, not runtime/contract oracle |

## Oracle-backed gold-task subset

The runner executes two applicable committed Starlette task queries and compares
raw query text to each task's mechanically derived changed-file oracle:

| task ID | oracle changed file | result | rationale |
|---|---|---|---|
| `encode-starlette-issue-2950` | `starlette/testclient.py` | correct | path occurs in raw response |
| `encode-starlette-issue-3388` | `starlette/responses.py` | incorrect | path does not occur in raw response |

This subset is deliberately small and deterministic (no BYOK needed). It makes
no claim that a ranked answer is correct unless the committed oracle path is
present. Cross-repository task evaluation remains out of scope until Stage 3.
