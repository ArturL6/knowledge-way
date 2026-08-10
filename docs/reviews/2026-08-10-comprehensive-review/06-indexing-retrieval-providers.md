# 06 — Indexing, Retrieval, Provider and Cost Analysis

> Workstream **§5.E** of `docs/CODING_AGENT_COMPREHENSIVE_REVIEW_PROGRAM.md`.
> Builds on the shared brief `01-runtime-and-provenance.md`; targets, live DB state and
> exclusions are not restated here.

## Cost and safety statement

**No provider call was made in this workstream — zero OpenAI / OpenRouter / Vertex / Gemini /
Cohere requests, directly or indirectly. No indexing run, reindex, sync or code-card run was
started. No migration was executed. No project file was modified except this report.**

Everything below rests on four evidence sources, all free:

1. Source review of the static target
   (`origin/integration/consolidated-verified` @ `c122529`) and of live `main` + working tree.
2. `EXPLAIN` / `EXPLAIN ANALYZE` on **SELECT only** against the live PostgreSQL 16 + pgvector
   database, plus `\d`, `\di+`, `pg_stat_activity`, `pg_locks`, `pg_stat_user_tables`.
3. `GET`-only calls to `http://localhost:8000` (lexical and symbol search are computed
   locally; `semantic.enabled` is `false` in this deployment, so no `GET` could have reached a
   provider).
4. The integration branch's own pytest suite plus three purpose-built review tests, all run
   **inside the `api` container against SQLite in-memory with fake/counting providers**. The
   worktree was copied to a container-local `/tmp/kwrev` with `docker cp`; nothing was written
   to the repository or to PostgreSQL.

```
docker exec -w /tmp/kwrev -e PYTHONPATH=/tmp/kwrev <api> python -m pytest tests -q
→ 50 passed, 20 warnings in 1.24s          (integration branch suite, no network)
```

The three review tests live in the session scratchpad only:
`test_rev_partial_overwrite.py`, `test_rev_search_scope.py`, `test_rev_embedding_reuse.py`.

## Runtime change mid-review — evidence is split across two schemas

**The live target changed underneath this workstream while it was running.** A sibling
(non-review) session added a `migrate` service to `docker-compose.yml` running
`alembic upgrade head` and restarted the stack; because the working directory had been switched
to the integration branch, all four pending revisions applied. Every measurement below is
therefore labelled with the schema it was taken against, and the load-bearing ones were
**re-taken after the change**.

| | Before (first measurement pass) | After (re-measured) |
|---|---|---|
| `alembic_version` | `20260808_0004` | `20260809_0008` |
| Tables | 12 | **14** (`code_cards`, `structural_cards` added) |
| `symbol_edges.target_name` | `character varying(512)` | `text` (table rewritten) |
| Deployed `api` / `worker` image | `main` lineage | **rebuilt from the integration branch** |
| Row counts | 1 / 2 284 / 21 324 / 22 900 / 136 566 | **identical** — data fully preserved |
| `code_cards`, `structural_cards` rows | n/a | **0 — no code-card run has ever executed here, and none was triggered** |

What this changes, precisely:

- **The re-index timings remain `main`-lineage evidence.** The 55 s and 697 s runs happened at
  schema `0004` on `main` code and cannot be re-taken (that would require an indexing run).
  Their attribution is unaffected, because the mechanism behind them — see REV-503 — was
  re-measured on `0008` and is unchanged.
- **All four RI-check measurements and the lexical scan were re-taken on `0008`** and confirm
  the findings; both readings are shown side by side in the sections below.
- **The four missing FK indexes were not added by migrations `0005`–`0008`.** Verified directly:
  the only new index on a symbol-referencing column is `uq_code_cards_symbol_id`. REV-503 stands
  in full.
- **The live target is now the integration branch**, so several findings previously argued from
  source are now live-verified, and REV-516's search half is resolved on the live target while
  its graph half is confirmed still open. Evidence levels were upgraded accordingly in
  REV-515, REV-516 and REV-517.
- **`code_cards.py` and `structural_cards.py` are deployed code for the first time**, and
  `POST /api/repositories/{repo_id}/code-cards` now resolves against a real table. That raises
  the practical severity of REV-509 (discarded billed responses), REV-518 (adapter boundary) and
  REV-511 (no cost audit) from latent to reachable: a single call to that route would now start
  a real, billable Gemini run against 21 324 symbols. **It was not called.** The route being
  backed by a real table makes it more dangerous to touch, not less.
- **REV-501's leaked transaction is gone**, cleared incidentally by the stack restart. That is
  itself confirmation of the finding's proposed operational fix, and the diagnosis is preserved
  below with its original evidence.

Source evidence throughout continues to cite the pinned read-only worktree at `c122529`, never
the working tree, which now carries in-flight edits from two other sessions.

## Summary

The indexer is **not** an incremental, atomically published index. It is an in-place,
whole-repository rewrite inside one long transaction, and the integration branch removed the
last remaining delta shortcut that `main` still has. Three defects in this area are
data-affecting rather than merely slow:

- A failed index job **commits its own destructive rewrite** (REV-500). This is proven, not
  suspected. The session's SIGKILL observation was misleading: SIGKILL skips the `except`
  block, so it was the one failure mode that *is* safe.
- The live deployment currently holds an **abandoned PostgreSQL transaction (xid 775) that has
  been `idle in transaction` for 20 minutes** with `RowExclusiveLock` on `symbols`,
  `code_chunks` and `symbol_edges` (REV-501). The repository cannot be re-indexed while it
  exists and `VACUUM` cannot advance. Root cause: SQLAlchemy's connection pool is inherited
  across RQ's `fork()`.
- Repository scope is applied **in Python, after the SQL `LIMIT`** (REV-502), so a scoped
  search can silently return zero results for a repository that does contain matches.

On performance, the stated 12.7× re-index hypothesis is **confirmed in its location and
refuted in its mechanism** — see the dedicated section. The single highest-value change in
this whole workstream is a four-line migration adding four btree indexes; measured, that
converts an 11–22 ms operation into 0.095 ms and it is what the 642 s regression is made of.

Retrieval has no index behind it in either modality that matters: lexical search is
`ILIKE '%…%'` over a 165 MB table (measured worst case **646 ms** SQL / **1.13 s** end to end),
and semantic search fetches every embedded chunk of every repository into Python and computes
cosine in the interpreter — with **no pgvector index possible**, because the `embedding`
column is declared `Vector()` with no dimension.

What is genuinely right, and worth protecting: the opt-in defaults are correct
(`embedding_provider="none"`, `code_cards_enabled=False`, `rerank_provider="none"`,
`rerank_candidate_limit=40`), every provider is unreachable unless both the switch and the
credential are set, `providers.py` contains no domain logic, Vertex honours `Retry-After` with
bounded backoff, and the whole suite runs with providers mocked. §3.10's "opt-in" and
"testable without provider access" halves hold. Its "cost-observable" half does not (REV-511).

## Retrieval modalities

Routes as they exist on each branch. "Scope vs LIMIT" is the §5.B question: does the
repository predicate reach SQL, or does Python discard rows the database already truncated?

| Modality | Route / entry point | Scope enforced | Provenance returned | Index used | Scope vs LIMIT |
|---|---|---|---|---|---|
| **Lexical (exact substring)** | `GET /api/search?mode=text\|exact` → `search.py:67-70` | `repository_id` (integration only) + `repo:` / `lang:` / `path:` filters, **all applied in Python**; `lang`/`path` do reach SQL | repository, repository_id, file_id, path, start/end line, snippet; `symbol_id` + `indexed_commit_sha` **integration only** (REV-516) | none — `Seq Scan` + `ILIKE '%…%'` | **LIMIT first** (`limit*2` in SQL), scope filter after → REV-502 |
| **Lexical (OR-term fallback)** | `search.py:71-75` | same | same | none — `Seq Scan`, N `ILIKE` clauses | **LIMIT first** (`limit*8`), scope after |
| **Symbol** | `GET /api/search/symbols` (no scope param, both branches) · `mode=symbols` | route accepts **no** `repository_id`; only in-Python `repo:` filter | repository, path, line range, symbol name; no `indexed_commit_sha` on `main` | none — `Seq Scan` + `ILIKE` on `name`/`qualified_name` | **LIMIT first** (`limit*3`), scope after |
| **Semantic** | `POST /api/search/semantic` (no scope param) · `mode=semantic` → `search.py:83-97` | **none in SQL**; `repository_id` applied in Python per row | as lexical | **none possible** — `Vector()` has no dimension, so no HNSW/IVFFlat exists or can be built | **no LIMIT at all**: every embedded chunk of every repository is fetched and cosine-scored in Python, then scoped → REV-505 |
| **Rerank (optional)** | `?rerank=true` (integration only) → `search.py:104-116` | inherits the fused candidate set (≤100) | as lexical | n/a | applied after fusion, before final `[:limit]` — correct ordering here |
| **Graph — symbol subgraph** | `GET …/symbols/{id}/subgraph` (both) | repository-scoped in SQL (`scoped_symbol`, `scoped_edges`, `scoped_symbols`) | repository_id, file_id, line range, byte range — **no `path`, no `indexed_commit_sha`** | `ix_symbol_edges_repository_id` | scope in SQL, but **all** 136 566 edges are loaded into Python and re-scanned per hop → 3.2–3.4 s measured (REV-517) |
| **Graph — repository overview** | `GET …/{id}/graph` — **integration only**, returns 404 on `main` | repository-scoped in SQL | node kinds + as above; no commit | as above | scope in SQL; whole-edge-set Python load |
| **Citations (explanations / documentation)** | `citation()` `main.py:63-65` | repository-scoped | **full** — repository, repository_id, `indexed_commit_sha`, file_id, path, clamped line range, symbol_id | n/a | correct |

Two structural observations from the table:

- The only place the full §3.6 provenance contract is honoured is `citation()`. Search honours
  it on integration and not on `main`; the graph honours it on neither.
- Scope is a Python post-filter in every retrieval modality. That is what makes REV-502 a
  correctness bug rather than a style preference, and it is what ADR 0001 §5 ("Repository,
  workspace, commit, file, symbol, and authorization filters are applied before a result is
  returned") is trying to prevent.

## Re-index performance analysis — verdict on the stated hypothesis

### Which code produced the measurements

Both measurements (55 s initial, 11 m 37 s = 697 s re-index) ran on **live `main` + working
tree**. `ingestion.py` differs between the branches by 129 lines, so the attribution must be
stated per branch:

| | `main` (measured) | `integration` (static target) |
|---|---|---|
| Unchanged-file skip | `ingestion.py:151` — `if f and f.content_hash==digest and not full: continue` | **removed**: `ingestion.py:222` — `if f and f.content_hash==digest: f.indexed_commit_sha=sha` (no `continue`) |
| Per-file `DELETE Symbol` / `DELETE CodeChunk` | `:152`, only for files not skipped | `:223`, for **every** file, every run |
| Bulk `DELETE SymbolEdge` | `:141`, `if full` only | `:212`, always |
| Bulk `DELETE CodeCard` | n/a (no table) | `:211`, always |
| Edge rebuild | `:162`, `if full` only | `:232`, always |
| `refresh_structural_cards` | absent | `:235`, always |

The 697 s run was a `full` re-index, so on `main` the skip at `:151` was bypassed and all 2 284
files took the delete-and-reparse path. **The measurement therefore describes the code path
that integration now takes unconditionally, for `sync` as well as `full`.** Integration is
strictly worse: it applies the measured path to every sync and adds
`refresh_structural_cards` and `_restore_code_cards` on top.

### Verdict: the hypothesis is right about *where* and wrong about *why*

> Hypothesis under test: "`ingestion.py` issues two `DELETE` statements per file (≈4 568
> statements) plus re-inserts all 136 566 edges, instead of one bulk delete per repository."

**Location — confirmed.** The two per-file `DELETE`s are real and the count is right:
`ingestion.py:223` (integration) / `:152` (`main`) issue `delete(Symbol).where(file_id=…)` and
`delete(CodeChunk).where(file_id=…)` once per file, 2 × 2 284 = 4 568 statements.

**Mechanism — refuted, twice over.**

*First:* the statement count is not the cost. Each statement's own predicate is indexed
(`ix_symbols_file_id`, `ix_code_chunks_file_id`) and resolves in **0.095 ms**:

```
EXPLAIN (ANALYZE,BUFFERS) SELECT 1 FROM code_chunks WHERE file_id=(SELECT id FROM files LIMIT 1);
→ Index Only Scan using ix_code_chunks_file_id … Execution Time: 0.095 ms
```

4 568 index lookups cost well under a second. The cost is per **row deleted**, not per
statement: `symbols` has four incoming foreign keys and **not one of the referencing columns is
indexed**. Verified from the live schema (`\d symbols`, `\di+`):

```
Referenced by:
  code_chunks.symbol_id     → symbols(id) ON DELETE SET NULL   -- no index
  symbol_edges.source_symbol_id → symbols(id)                  -- no index
  symbol_edges.target_symbol_id → symbols(id)                  -- no index
  symbols.parent_symbol_id  → symbols(id)                      -- no index
```

PostgreSQL fires a referential-integrity trigger **per deleted row** for each of those, and
each one degrades to a sequential scan. Measured on the live data at its real size, on **both**
schemas — the second pass after the mid-review migration rewrote `symbol_edges`:

| RI check fired per deleted `symbols` row | Plan | On `0004` | On `0008` |
|---|---|---|---|
| `symbol_edges.source_symbol_id` | `Seq Scan`, 136 566 rows removed | 22.4 ms | **19.75 ms** |
| `symbol_edges.target_symbol_id` | `Seq Scan`, 136 566 rows removed | 18.8 ms | **18.27 ms** |
| `code_chunks.symbol_id` (`SET NULL`) | `Seq Scan`, 22 899 rows removed | 13.6 ms | **12.66 ms** |
| `symbols.parent_symbol_id` | `Seq Scan`, 21 324 rows removed | 11.4 ms | **10.00 ms** |
| **total per deleted symbol** | | ≈ 66 ms | **≈ 61 ms** |
| `code_cards.symbol_id` — *the one referencing column that has an index* | `Index Only Scan using uq_code_cards_symbol_id` | n/a (table did not exist) | **0.014 ms** |

The last row is the decisive control, and it only became available *because* of the mid-review
migration. `code_cards.symbol_id` is a fifth incoming foreign key to `symbols(id)`, added by
revision `0005`, and it happens to be indexed as a side effect of its `UNIQUE` constraint.
Measured in the same session, on the same hardware, against the same table, an indexed
referencing column costs **0.014 ms** and an unindexed one costs **10–20 ms**: a factor of
roughly **1 400×**. The four slow columns are not slow because of anything about their data;
they are slow because nobody created the index.

21 324 symbols × 61–66 ms = **1 300–1 412 s** as an upper bound on a partly cold cache. The measured
delta is 697 − 55 = **642 s**, i.e. ≈ 30 ms per symbol — exactly what these four scans cost
once the pages are in `shared_buffers` (the measurements above still show `read=2 069…7 268`
disk buffers). The mechanism predicts the measurement to within cache warmth, and nothing else
in the code path predicts anything of this magnitude.

*Second:* the "re-inserts all 136 566 edges" half of the hypothesis is refuted by a clean
control that is already in hand. **The 55 s initial index inserted the same 21 324 symbols,
22 900 chunks and 136 566 edges from scratch, and issued zero `DELETE`s** (`existing` is empty,
so every file takes the `db.add(f)` branch at `:224`). Clone, `rglob` over 2 284 files,
tree-sitter parse, `_persist_edges` and all 180 790 inserts together cost **≤ 55 s**. The
entire 642 s delta is therefore on the deletion path. Insert batching would recover nothing
measurable.

### Consequence: the hypothesis's implied fix does not work

Replacing 4 568 per-file `DELETE`s with **one** bulk `DELETE FROM symbols WHERE
repository_id=$1` would **not** recover the 12.7×. PostgreSQL fires the same per-row RI
triggers regardless of how many statements delete the rows. A bulk delete is a good
simplification, but on its own it is a no-op for this regression. Prioritised strictly by
measured cause:

1. **Add four btree indexes** — `code_chunks(symbol_id)`, `symbol_edges(source_symbol_id)`,
   `symbol_edges(target_symbol_id)`, `symbols(parent_symbol_id)`. Pure migration, no code
   change, measured 100–230× per check. This is REV-503 and it is the whole regression.
2. Then, and only then, collapse the per-file deletes into per-repository bulk deletes
   (fewer round trips, clearer transaction shape).
3. Restore a real unchanged-file skip (REV-507) so the deletes are not issued at all for
   unchanged files.

The measurement that would settle it definitively: apply the four indexes to a **throwaway
copy** of this database, re-run the same full re-index of `pydanticAI` at the same commit, and
compare against 697 s. Prediction: under 90 s. Do not run that against the live database
during an analysis mandate — and not at all until REV-501's abandoned transaction is cleared,
because it would block.

## Whole-corpus vectors in Python

`search.py:88-91` is the semantic path:

```python
for chunk, file in db.execute(chunk_stmt().where(CodeChunk.embedding_model == provider.model)
                                          .where(CodeChunk.embedding.is_not(None))):
    repo = repos.get(chunk.repository_id)
    score = _cosine(query_vector, list(chunk.embedding))
    if allowed(repo) and score is not None: semantic.append(result('chunk', score, repo, file, chunk))
```

No repository predicate, no `LIMIT`, no `ORDER BY`, no pgvector operator. `_cosine`
(`search.py:40-43`) is three pure-Python passes over the vector. Proven by counting `_cosine`
invocations with a fake provider (no network): with 42 embedded chunks across two repositories
and `repository_id` set to a repository holding 2 of them,

```
rows fetched + cosine-scored in Python=42  in-scope candidates=2  returned=2
```

At the real corpus size the numbers are:

| | current (22 900 chunks) | 10× (229 000) | 100× (2.29 M) |
|---|---|---|---|
| rows fetched per query (no LIMIT) | 22 900 | 229 000 | 2 290 000 |
| `source_text` transferred per query | **82.8 MB** (measured `sum(length(source_text))`) | 828 MB | 8.3 GB |
| SQL-side floor, measured | **646 ms** (full `code_chunks` seq scan) | ~6.5 s | ~65 s |
| Python float ops (768-dim) | ~53 M | ~530 M | ~5.3 B |

The 646 ms and 82.8 MB are measured. The 10×/100× rows are linear projection from one measured
point — `source-reviewed` arithmetic, not a benchmark. Every one of those queries also
constructs a 22 900-entry list of dicts each slicing 1 200 characters of snippet, in one
process, synchronously inside a FastAPI request.

**A pgvector index cannot be added without a migration.** `models.py:29` declares
`embedding: Mapped[…] = mapped_column(Vector(), nullable=True)` and
`db_migrations/versions/20260808_0002_optional_embeddings.py:21` emits `Vector()` — no
dimension. Live schema confirms the column type is bare `vector` with no typmod, and `\di+`
shows **38 indexes, all btree, none on `embedding`**. pgvector requires a fixed dimension to
build `hnsw` or `ivfflat`. So the SQL alternative (`ORDER BY embedding <=> $1 LIMIT 30`, with
`repository_id` in the `WHERE`) is currently unavailable by construction, not merely unused.

## Lexical index paths

There is no text index of any kind. `\di+` lists 38 indexes across 12 tables, all `btree`; no
`GIN`, no `gin_trgm_ops`, no `tsvector` column, no `pg_trgm`. `rg` over all eight migrations
finds no `gin`, `gist`, `trgm` or `tsvector`. A leading-wildcard `ILIKE '%…%'` cannot use a
btree index in any case.

Measured against the live database and the live API:

```
EXPLAIN (ANALYZE,BUFFERS) … WHERE code_chunks.source_text ILIKE '%zzz_no_such_token_qq%' LIMIT 60;
→ Seq Scan on code_chunks, Rows Removed by Filter: 22900, Buffers: hit=5460 read=12729
→ Execution Time: 646.258 ms

EXPLAIN (ANALYZE,BUFFERS) … WHERE code_chunks.source_text ILIKE '%ModelRetry%' LIMIT 60;
→ Seq Scan, Rows Removed by Filter: 677 (early exit at the LIMIT)
→ Execution Time: 6.535 ms
```

```
GET /api/search?q=zzz_no_such_token_qq&mode=text&limit=30  → 1.129 s, 1.137 s
GET /api/search?q=ModelRetry+validation+error&mode=hybrid&limit=30 → 0.799 s, 1.428 s
```

The 100× spread between those two plans is the important finding: latency is governed by
**how early the `LIMIT` is satisfied**, so a common term is fast and a rare or absent term
costs a full 165 MB scan. That is precisely backwards from user expectation, and the
zero-result case — the one where a user retypes and retries — is the slowest. The `text`
branch also runs the OR-term fallback (`search.py:71-75`, `limit*8`) whenever the exact branch
found nothing, so a miss pays for two full scans; the end-to-end 1.13 s versus the 646 ms SQL
floor is consistent with that.

## Provider adapter boundaries

`providers.py` is clean and should be left alone structurally. `EmbeddingProvider`,
`RerankProvider` and `ChatProvider` are `Protocol`s; `OpenRouterEmbeddingProvider`,
`VertexEmbeddingProvider` and `CohereRerankProvider` do HTTP, response-shape validation
(`_validate_embeddings`, `:145-151`) and nothing else — no repository, symbol, chunk or scope
concept appears in the file. Selection is a pure function of settings
(`embedding_provider()` `:154-170`, `rerank_provider()` `:173-177`), and both return `None`
unless the switch **and** the credential are present, so a misconfigured deployment cannot
accidentally emit a request. Swapping OpenRouter for Vertex is a one-line env change. ADR
0001's "adapters hold no domain logic" is satisfied **for provider adapters**.

Two boundary defects, both small:

- `code_cards.py:18,66-67` imports `VertexEmbeddingProvider` and calls its private
  `_refresh_credentials()` to get an ADC token. The code-card module depends on the *embedding*
  adapter's internals for an unrelated concern (REV-518).
- ADR 0001's `CodeGraphStore` / `VectorSearchIndex` / `ProvenanceStore` contracts **do not
  exist**: `rg -n "CodeGraphStore|VectorSearchIndex|ProvenanceStore" --glob '!docs/**'` returns
  nothing. Retrieval strategy is hard-wired in `search.py`, which is exactly the coupling the
  ADR exists to prevent (REV-513).

Prompt and document construction correctly live outside the adapters (`code_cards._prompt`,
`ingestion._embedding_document`), which is the right side of that line.

## Retry / 429 / resume

| Path | 429 handling | `Retry-After` | Backoff | Resume | Persist-as-you-go |
|---|---|---|---|---|---|
| Vertex embeddings (`providers.py:107-136`) | 8 attempts | yes, numeric only | `min(60, 2^(n+1))` | n/a | no — one transaction |
| Vertex Gemini code cards (`code_cards.py:93-122`) | 8 attempts | yes, numeric **and** RFC-2822 date (`:100-103`) | `min(60, 2^(n+1))` | yes, via `source_hash` reselect (`:150`) | yes, `db.commit()` per card (`:197`) |
| Cohere rerank (`providers.py:33-45`) | **none** — bare `raise_for_status()` | no | no | n/a | n/a |
| OpenRouter embeddings (`providers.py:56-64`) | none written; inherits the `openai` SDK default | not handled explicitly | SDK default | n/a | no |

The code-card path is genuinely well built: `MAX_RATE_LIMIT_RETRIES = 8`, `_retry_delay`
handles both `Retry-After` forms, targets are reselected by `source_hash` so a resumed run
re-requests only what is missing, and each valid card is committed before the next request.
Two gaps remain:

- **Already-billed responses are discarded** (REV-509). `_post_batch` (`:125-135`) issues
  `concurrency` (default 8) requests concurrently; the parse loop (`:171-188`) raises on the
  first malformed or empty response. Up to 7 responses that were paid for, received and are
  perfectly valid are never parsed or persisted, and the job aborts. With `concurrency: 8` a
  single bad response wastes up to 7 requests and stops the run.
- **Vertex embeddings have no resume and no partial persistence.** `_embed_full_index_chunks`
  runs inside the single index transaction, so a failure on batch 700 of 716 depends entirely
  on REV-500's `except`-block commit to keep the earlier 699 batches — and that commit also
  publishes a half-built index.

## Telemetry, token and cost audit

| Signal the mandate asks for | Present? | Where |
|---|---|---|
| `context_s`, `provider_s`, `parse_s`, `persist_s`, `total_s` | **yes, code cards only** | `code_cards.py:198`, a single `logger.warning` line |
| valid / invalid / empty counts | partially | per-symbol log lines `outcome=persisted\|invalid\|empty_summary` (`:184,187,198`); **never aggregated** — the run aborts on the first non-persisted outcome, and the return value is `{total, completed, model}` only |
| token audit | per card only | `CodeCard.input_tokens` / `output_tokens` from `usageMetadata` (`:189-190`), exposed on `GET …/code-card` (`main.py:191`) |
| cost audit | **no** | no price table, no per-run total, no aggregate endpoint anywhere |
| ingestion phase timings | **no** | `indexing_jobs.progress` carries `{phase, files}` / `{phase, total, completed}` — no durations, no counts of rows written |
| embedding telemetry | **no** | `_embed_full_index_chunks` logs nothing and records nothing |

Nothing in `docs/` claims those metric names, so this is a capability gap rather than a
documentation contradiction — `docs/HOSTED_PRODUCT_AND_UI_VISION.md:21` lists "cost/usage
metadata" as vision and `docs/NEXT_STEPS.md:85` lists "explicit cost controls" as future work,
both correctly forward-looking. The operational consequence is concrete and this review
demonstrates it: **the 12.7 × regression could not be attributed from the product's own
telemetry.** `indexing_jobs` records start, end and a phase string; every number in the section
above had to come from outside the product.

`code_cards.py` also logs normal successes at `WARNING` (`:114,120,198`), which will make any
real code-card run indistinguishable from an incident in the log stream.

## Findings

| ID | Category | Severity | One-line |
|---|---|---|---|
| REV-500 | CORRECTNESS_RISK | blocker | A failed index job commits its own destructive rewrite; the repository is marked `failed` but the old index is already gone |
| REV-501 | BUG_CONFIRMED | critical | RQ's `fork()` leaks the SQLAlchemy pool: an abandoned transaction has held locks on `symbols`/`code_chunks`/`symbol_edges` for 20 min and blocks re-indexing and `VACUUM` |
| REV-502 | BUG_CONFIRMED | high | Repository scope is applied in Python after the SQL `LIMIT`, so a scoped search silently returns zero results for a repository that has matches |
| REV-503 | PERFORMANCE_RISK | high | Four unindexed FK referencing columns turn every symbol deletion into four sequential scans — the measured 12.7× re-index regression, fixable by one migration |
| REV-504 | BUG_CONFIRMED | high | The embedding-reuse cache is keyed on `content_hash` but looked up by the document hash, so every full re-index re-pays for every embedding |
| REV-505 | PERFORMANCE_RISK | high | Semantic search fetches every embedded chunk of every repository into Python with no `LIMIT` and no repository predicate; no pgvector index exists or can be built |
| REV-506 | PERFORMANCE_RISK | high | No lexical index of any kind; `ILIKE '%…%'` seq-scans 165 MB — 646 ms measured, worst on zero-result queries |
| REV-507 | DESIGN_GAP | high | Integration removed the only unchanged-file skip, so every `sync` is now a full destructive rewrite |
| REV-508 | CORRECTNESS_RISK | high | Chunk `source_text` is sent to the embedding provider untruncated; 879 live chunks exceed the model's input limit and one reaches 868 248 characters |
| REV-509 | CORRECTNESS_RISK | medium | A code-card batch discards up to `concurrency-1` already-billed valid responses when one response is malformed |
| REV-510 | DESIGN_GAP | medium | The Cohere reranker has no 429, `Retry-After` or backoff handling at all, unlike the Vertex adapters |
| REV-511 | DESIGN_GAP | medium | No ingestion telemetry, no aggregate token or cost audit; code-card timings are log-only and unqueryable |
| REV-512 | DOCUMENTATION_GAP | medium | `README.md` advertises "Incremental Git synchronization" and "full-text search"; neither exists as described |
| REV-513 | DESIGN_GAP | medium | ADR 0001's storage contracts do not exist in code; retrieval strategy is hard-wired in `search.py` |
| REV-514 | TEST_GAP | medium | No scope or limit-ordering test exists, and ingestion tests run on SQLite where FK cascades are not enforced — deletion semantics are untested |
| REV-515 | DESIGN_GAP | medium | `/api/search/symbols` and `/api/search/semantic` accept no repository scope, and the web client never sends one |
| REV-516 | CORRECTNESS_RISK | medium | On the live target search results carry no `indexed_commit_sha`, and graph nodes carry none on either branch |
| REV-517 | PERFORMANCE_RISK | medium | Graph routes load all 136 566 edges into Python per request — 3.2–3.4 s measured for an 11-node subgraph |
| REV-518 | DESIGN_GAP | low | `code_cards.py` reaches into `VertexEmbeddingProvider._refresh_credentials` for an ADC token |
| REV-519 | DESIGN_GAP | low | `ChatProvider` has no implementation; `openai_api_key` / `openai_chat_model` are dead config |
| REV-520 | DESIGN_GAP | info | The whole index is one transaction: atomic by accident, but no published index generation and locks held for its full duration |

---

### REV-500

- **ID:** REV-500
- **Category:** CORRECTNESS_RISK
- **Severity:** blocker
- **Evidence level:** `unit/API-tested`
- **Applies to:** both
- **Impact:** A failed indexing job **commits** the destructive rewrite it was in the middle
  of. The repository is flagged `failed` and its `indexed_commit_sha` is left at the old value,
  while the underlying rows have already been replaced with a partial index. Files deleted from
  the checkout are gone permanently, new symbols are live, and embeddings/edges may be half
  built. Every read path — search, graph, citations, MCP — then serves data that no commit ever
  produced, under a status that says the index is stale rather than corrupt. The only recovery
  is a full successful re-index, which currently takes 11 m 37 s.
- **Evidence:** `apps/api/app/ingestion.py:239-240` (integration) and `:166-167` (`main`):

  ```python
  except Exception as e:
   repo.indexing_status='failed';repo.error_message=str(e);job.status='failed';job.error_message=str(e);job.finished_at=datetime.utcnow();db.commit();raise
  ```

  There is no `db.rollback()`. The session still holds every pending change from `:211`
  onward — `delete(CodeCard)`, `delete(SymbolEdge)`, 4 568 per-file `delete(Symbol)` /
  `delete(CodeChunk)`, all inserts, `db.delete(f)` for removed files, and any embeddings
  written so far — and `db.commit()` flushes and commits all of it.

  Proven with `test_rev_partial_overwrite.py` (SQLite in-memory, no provider, no git network).
  Two files are indexed, then `b.py` is removed, `a.py` gains a symbol, and
  `refresh_structural_cards` is monkeypatched to raise:

  ```
  PROVEN: failed job committed the rewrite; status=failed files=['a.py'] symbols=['alpha', 'beta', 'gamma']
  1 passed
  ```

  `status=failed`, yet `b.py`'s file row is gone and the new symbol `gamma` is committed.
  Reachable non-DB exception sources after `:211`: `analyze_source` (tree-sitter),
  `refresh_structural_cards`, `_embed_full_index_chunks`'s explicit
  `RuntimeError('embedding provider returned an incomplete embedding batch')` (`:174`), any
  provider HTTP error, and `run('git','branch','--show-current')` at `:238`.
- **Probable cause + confidence:** **Certain.** A missing `db.rollback()` before the failure
  bookkeeping. The author's intent is visible — the bookkeeping needs a live session — but it
  reuses the session that carries the destructive work instead of rolling back first and then
  writing the two status rows.
- **Note on the session's SIGKILL observation:** the brief records that a SIGKILL'd job left
  uncommitted `DELETE`s rolled back. That safety was **incidental to the kill signal**, not
  general. `SIGKILL` terminates the process without running Python cleanup, so the `except`
  block never executes and the server-side transaction is abandoned rather than committed.
  Every failure mode that *does* raise a Python exception — the common ones — takes the unsafe
  path. Do not generalise from the SIGKILL result.
- **Smallest safe next step:** `except Exception as e: db.rollback()` **first**, then re-load
  `repo` and `job` and write only the status fields, then commit, then re-raise. Roughly three
  lines, no schema change. Add the regression test from this finding.
- **Affected data/migrations/providers/cost:** all of `files`, `symbols`, `code_chunks`,
  `symbol_edges`, `code_cards`, `structural_cards` for the repository. No migration. Interacts
  with cost: it is currently the only reason a mid-run embedding failure does not throw away
  every embedding paid for so far, so the rollback fix must land together with real
  incremental persistence of embeddings, or the two changes will trade one loss for another.
- **Recommended tests + acceptance criteria:** (1) the test above, asserting that after an
  injected failure the pre-existing rows are **byte-identical** to their pre-run state;
  (2) the same test against real PostgreSQL, where `ON DELETE CASCADE` is enforced;
  (3) assert `repositories.indexing_status='failed'` **and** `indexed_commit_sha` unchanged
  **and** row counts unchanged.
- **Fix status:** report-only

---

### REV-501

- **ID:** REV-501
- **Category:** BUG_CONFIRMED
- **Severity:** critical
- **Evidence level:** `PostgreSQL integration-tested`
- **Applies to:** `main` (working tree) as observed; the missing fork guard applies to both
- **Status update (mid-review):** the leaked transaction is **gone**, cleared incidentally when
  a sibling session restarted the stack to run migrations. Re-verified afterwards:
  `SELECT … FROM pg_stat_activity WHERE state<>'idle'` returns only the observing query, and no
  `idle in transaction` backend remains. This is not a fix — nothing in the code changed — but it
  does confirm the proposed operational remedy below (closing the parent's descriptors aborts the
  transaction). Two consequences for severity: the newly deployed integration `worker.py` opens
  no DB session before forking, so the specific trigger is not present in the currently running
  image; but integration also has **no reaper** (`reconcile.py` is `main`-only), so an orphaned
  job now leaves the repository `indexing` forever instead. The underlying missing
  `engine.dispose()` guard is unfixed on both branches. Evidence below is as originally observed
  at schema `0004`.
- **Impact:** As observed live, a PostgreSQL backend was stuck `idle in
  transaction` for over 20 minutes with an open xid. It held `RowExclusiveLock` on
  `symbols`, `code_chunks`, `symbol_edges` and their indexes and toast relations, plus row
  locks taken by an uncommitted `DELETE FROM symbols`. Consequences, all live: (1) a new index
  or reindex job for this repository will **block indefinitely** on those row locks and then be
  killed by the RQ timeout, reported as a generic failure with no diagnosable cause;
  (2) `VACUUM` cannot remove any tuple newer than xid 775, so bloat accumulates indefinitely
  — `code_chunks` is already 176 MB total for 22 900 rows; (3) any query taking a key-share
  lock blocks, which happened to this review's own `EXPLAIN` and had to be cancelled.
- **Evidence:**

  ```
  docker compose exec -T postgres psql … -x -c "SELECT … FROM pg_stat_activity WHERE pid=2417;"

  pid              | 2417
  client_addr      | 172.21.0.6                     -- = knowledge-way-worker-1
  backend_start    | 2026-08-10 11:50:02.310429+00  -- worker container booted 11:50:01
  xact_start       | 2026-08-10 11:50:28.513436+00
  query_start      | 2026-08-10 11:51:08.319202+00
  state_change     | 2026-08-10 11:51:15.144146+00
  state            | idle in transaction
  backend_xid      | 775
  wait_event       | ClientRead
  query            | DELETE FROM symbols WHERE symbols.file_id = $1::VARCHAR
  now              | 2026-08-10 12:11:02.998998+00  -- 20m34s later, still open
  ```

  `pg_locks` for pid 2417: `RowExclusiveLock` on `symbols`, `code_chunks`, `symbol_edges`,
  every one of their indexes, and `pg_toast_16828` / `pg_toast_16855`; `RowShareLock` on
  `repositories` and `files`; `transactionid ExclusiveLock`. 50 lock rows.

  This is the SIGKILL'd job from the brief (`c3807649 failed 11:50:26 → 11:51:28`). Root
  cause, from source: `apps/api/app/db.py:10-11` creates a module-level `engine` with the
  default `QueuePool`. The live working-tree `apps/api/app/worker.py:9-11` opens a session in
  the **parent** worker process at boot (`db=SessionLocal(); reconcile_indexing_jobs(db); db.close()`);
  `db.close()` returns the connection to the pool without closing the socket. `Worker(...).work()`
  then `fork()`s a work-horse per job, and the child inherits and reuses that pooled socket.
  When the child was SIGKILLed, the **parent still held a duplicate of the file descriptor**,
  so PostgreSQL never saw EOF and the transaction was never aborted. `pool_pre_ping=True`
  cannot help — the socket is alive, just shared. There is no `engine.dispose()` on either side
  of the fork.

  `apps/api/app/reconcile.py:36-64` fixes only the *row* status; it never touches the leaked
  connection, which is why the brief's reaper verification looked clean while the transaction
  survived.

  On the integration branch `worker.py` is 4 lines and opens no DB connection before forking,
  so the parent has nothing to leak — integration does not exhibit this today, but it also has
  no reaper, and the missing `engine.dispose()` guard means any future parent-side DB access
  reintroduces it.
- **Probable cause + confidence:** **High.** Classic fork-unsafe connection pool; the timing
  (backend_start = worker boot, xact_start = job start, the exact statement from
  `ingestion.py:152`) matches on every field.
- **Smallest safe next step:** two independent changes. (1) Operationally, clear the leaked
  backend before any further indexing — restarting the `worker` container closes the parent's
  descriptors and PostgreSQL aborts xid 775. (2) In code, call `engine.dispose(close=False)`
  in the work-horse after `fork()` — RQ exposes this via a `Worker` subclass or the work-horse
  entry point — so the child never reuses an inherited socket. Both are small; the second is
  the real fix and belongs on a branch with a test.
- **Affected data/migrations/providers/cost:** no data corruption observed (row counts still
  2 284 / 21 324 / 22 900 / 136 566, `n_dead_tup = 0` on all four tables). Availability and
  storage only. No provider cost.
- **Recommended tests + acceptance criteria:** integration test that enqueues an index job,
  `SIGKILL`s the work-horse, and asserts within 5 s that no `idle in transaction` backend
  remains for the database and that a subsequent index job for the same repository completes.
  Acceptance: `SELECT count(*) FROM pg_stat_activity WHERE state='idle in transaction'` = 0.
- **Fix status:** report-only

---

### REV-502

- **ID:** REV-502
- **Category:** BUG_CONFIRMED
- **Severity:** high
- **Evidence level:** `unit/API-tested`
- **Applies to:** both
- **Impact:** Scoping a search to a repository can return **zero results for a repository that
  demonstrably contains matches**. The SQL `LIMIT` is applied without any repository predicate,
  so rows from other repositories consume the entire candidate budget and the Python scope
  filter then discards all of them. The user sees an empty result set that is
  indistinguishable from "this repository has no match" — a silently wrong answer on a
  platform whose whole premise is evidence. Severity rises with corpus size and with the
  number of repositories; the live deployment has one repository, which hides it completely.
  Directly violates §5.B ("filters take effect before SQL `LIMIT`") and ADR 0001 §5.
- **Evidence:** `apps/api/app/search.py:62-80`. `chunk_stmt()` (`:62-66`) applies `lang` and
  `path` to SQL but **never** `repository_id`. Scope lives only in the Python closure
  `allowed()` (`:61`), which runs after the row is fetched:

  ```python
  for chunk, file in db.execute(chunk_stmt().where(CodeChunk.source_text.ilike(f'%{q.text}%')).limit(limit * 2)):
      repo = repos.get(chunk.repository_id)
      if allowed(repo): lexical.append(...)
  ```

  Same shape at `:73` (`limit * 8`) and `:78` (`limit * 3`, symbols). Proven with
  `test_rev_search_scope.py`: 50 matching chunks in repository `noisy`, 3 in `wanted`,
  `limit=5` (so SQL `LIMIT 10`):

  ```
  unscoped hits=5  scoped-to-wanted hits=0  (wanted really has 3 matching chunks)
  1 passed
  ```
- **Probable cause + confidence:** **Certain.** Scope was implemented as a presentation filter
  (it also has to serve the free-text `repo:` prefix, which needs a name match) and the SQL
  predicate was never added alongside it.
- **Smallest safe next step:** add `.where(CodeChunk.repository_id == repository_id)` to
  `chunk_stmt()` and the symbol statement when `repository_id` is set, and resolve `q.repo`
  to a repository id set server-side before the query rather than after. Keep `allowed()` as a
  defence-in-depth assertion.
- **Affected data/migrations/providers/cost:** none — read path only. Adding the predicate also
  reduces scanned rows, so it is a small performance win.
- **Recommended tests + acceptance criteria:** the two-repository fixture above, for every
  mode (`text`, `exact`, `symbols`, `hybrid`, `semantic`). Acceptance: for any `limit` and any
  distribution of matches across repositories, a scoped query returns exactly the in-scope
  matches, up to `limit`.
- **Fix status:** report-only

---

### REV-503

- **ID:** REV-503
- **Category:** PERFORMANCE_RISK
- **Severity:** high
- **Evidence level:** `PostgreSQL integration-tested`
- **Applies to:** both (schema-level; measured on `main`, and integration triggers it on every
  sync as well as every full index)
- **Impact:** This is the measured 12.7× re-index regression. `symbols` has four incoming
  foreign keys and none of the referencing columns is indexed, so PostgreSQL fires four
  per-row referential-integrity checks for every deleted symbol, each degrading to a
  sequential scan of `symbol_edges` (59 MB), `code_chunks` (165 MB) or `symbols` (50 MB).
  At 21 324 symbols that is the difference between a 55 s and a 697 s index. Secondary
  consequences: the transaction stays open ~12× longer, so REV-520's lock window and REV-500's
  blast radius both scale with it, and RQ's job timeout has to be raised to compensate (which
  both branches did, independently and differently).
- **Evidence:** live `\d symbols` shows the referencing constraints; live `\di+` shows 38
  indexes, all btree, none on `code_chunks.symbol_id`, `symbol_edges.source_symbol_id`,
  `symbol_edges.target_symbol_id` or `symbols.parent_symbol_id`. Measured RI-check cost
  (`EXPLAIN (ANALYZE,BUFFERS)` on the exact predicates PostgreSQL's RI triggers use):
  22.4 / 18.8 / 13.6 / 11.4 ms = **≈66 ms per deleted symbol** on schema `0004`, re-measured as
  19.75 / 18.27 / 12.66 / 10.00 ms = **≈61 ms** on `0008` after the mid-review migration rewrote
  `symbol_edges`. **The migration did not add the missing indexes** — verified with
  `SELECT indexname FROM pg_indexes WHERE indexdef LIKE '%symbol_id%' OR indexdef LIKE '%parent_symbol%'`,
  whose only hit is `uq_code_cards_symbol_id`. That new constraint is the in-schema control: the
  same RI predicate against an **indexed** referencing column measures **0.014 ms**
  (`Index Only Scan using uq_code_cards_symbol_id`) versus 10–20 ms unindexed — ≈1 400×, same
  session, same hardware. Full numbers,
  the 1 412 s upper bound, and the 55 s control that rules out insert cost are in the
  *Re-index performance analysis* section above. Statements: `ingestion.py:223` (integration) /
  `:152` (`main`).
- **Probable cause + confidence:** **High.** `models.py` marks `repository_id` and `file_id`
  with `index=True` but not the symbol-referencing columns (`:29,26,37`), so no migration ever
  created them. The measured per-check cost and the measured 642 s delta agree to within cache
  warmth, and the 55 s from-scratch index rules out every alternative in the same code path.
- **Smallest safe next step:** one migration, four `CREATE INDEX CONCURRENTLY` statements, plus
  `index=True` on the four `mapped_column`s so a fresh database matches. No code change, no
  data change, fully reversible. Note that the hypothesis's alternative fix — collapsing to one
  bulk `DELETE` per repository — does **not** substitute for this, because RI triggers fire per
  row regardless of statement count.
- **Affected data/migrations/providers/cost:** one additive migration; roughly +8 MB of index
  on current data. No provider cost. Expect a small write-amplification cost on insert, far
  below the delete saving.
- **Recommended tests + acceptance criteria:** apply the indexes to a throwaway copy of the
  database and re-run the identical full re-index of `pydanticAI` at commit `640d5171…`.
  Acceptance: wall clock under 90 s (from 697 s) with byte-identical resulting row counts
  (2 284 / 21 324 / 22 900 / 136 566). Also assert in a migration test that the four indexes
  exist. Do not run this against the live database, and not at all until REV-501 is cleared.
- **Fix status:** report-only

---

### REV-504

- **ID:** REV-504
- **Category:** BUG_CONFIRMED
- **Severity:** high
- **Evidence level:** `unit/API-tested`
- **Applies to:** integration only (`main`'s two sides agree, so `main` is unaffected)
- **Impact:** The embedding-reuse cache can never hit. Every full re-index re-embeds every
  chunk from scratch, including chunks whose source has not changed by one byte. On the live
  corpus that is 22 900 chunks totalling 82.8 MB of text (≈20 M tokens) re-sent to a paid
  provider on every re-index — the exact hidden-cost failure §3.10 exists to prevent. The
  reuse code reads as a working optimisation, so the spend is invisible.
- **Evidence:** the cache is **populated** by `content_hash` at
  `apps/api/app/ingestion.py:215-217`:

  ```python
  reusable_embeddings[(chunk.content_hash, chunk.embedding_model)] = list(chunk.embedding)
  ```

  and **looked up** by the hash of the assembled embedding document at `:168-169`:

  ```python
  text=_embedding_document(repo,chunk,files[...],...); key=hashlib.sha256(text.encode()).hexdigest()
  cached=reusable_embeddings.get((key,provider.model))
  ```

  `chunk.content_hash` is `sha256(source_text)` (`:106`); `key` is `sha256` of a document that
  begins `Repository: …\nPath: …` and only then contains the source. The two digests cannot
  coincide for any input. `main`'s version uses `chunk.content_hash` on both sides
  (`main` `:112` vs `:146`) and is correct.

  Proven with `test_rev_embedding_reuse.py` (counting fake provider, no network): full index,
  then an identical full index of an unchanged checkout at the same commit:

  ```
  embedded chunks=5  first run embedded=5  identical second run embedded=5
  1 passed
  ```
- **Probable cause + confidence:** **Certain.** The `_embedding_document` refactor changed what
  is embedded (source text → contextual document) and updated the lookup key accordingly, but
  the population site 50 lines away still stores the old key.
- **Smallest safe next step:** store the document hash. Persist it — a new
  `code_chunks.embedding_input_hash` column is the honest fix, since the document depends on
  the repository name, file path, symbol signature, the code card and the static call/import
  lists, none of which `content_hash` covers. Until then, populating the cache with a
  recomputed `_embedding_document` hash over the *old* rows would work but requires the old
  cards and edges, which have already been deleted at `:211-212` — so the column is the right
  answer.
- **Affected data/migrations/providers/cost:** one additive migration
  (`embedding_input_hash`); direct provider cost — currently 100 % of embedding spend on every
  re-index is avoidable.
- **Recommended tests + acceptance criteria:** the test above, inverted. Acceptance: a second
  full index of an unchanged checkout makes **zero** `embed_texts` calls; changing one file's
  source re-embeds only that file's chunks; changing a code card re-embeds only the chunks
  whose document changed.
- **Fix status:** report-only

---

### REV-505

- **ID:** REV-505
- **Category:** PERFORMANCE_RISK
- **Severity:** high
- **Evidence level:** `unit/API-tested` for the in-Python behaviour and row counts;
  `PostgreSQL integration-tested` for the absent index and the 646 ms SQL floor;
  `source-reviewed` for the 10× / 100× projections
- **Applies to:** both
- **Impact:** Semantic search is O(entire corpus) per query, in one Python process, inside the
  request. No `LIMIT`, no repository predicate, no pgvector operator, and no index that could
  serve one — the `embedding` column has no declared dimension, so `hnsw`/`ivfflat` cannot be
  built at all. At today's 22 900 chunks a semantic query would fetch 82.8 MB of chunk text
  plus 22 900 vectors and perform ~53 M interpreter-level float operations. This is also the
  most severe instance of REV-502: because there is no `LIMIT`, the whole corpus is *scored*
  before scope is applied, so cross-repository work is done for a single-repository query.
- **Evidence:** `apps/api/app/search.py:83-97` (quoted in full in the *Whole-corpus vectors*
  section) and `_cosine` at `:40-43`. Proven with `test_rev_search_scope.py`, counting
  `_cosine` invocations: 42 embedded chunks across two repositories, `repository_id` scoping to
  a repository with 2 →

  ```
  rows fetched + cosine-scored in Python=42  in-scope candidates=2  returned=2
  ```

  No index: live `\d code_chunks` shows `embedding | vector` with no typmod and five btree
  indexes, none on `embedding`; `\di+` lists 38 indexes, all btree. Source of the missing
  dimension: `models.py:29` `mapped_column(Vector(), nullable=True)` and
  `db_migrations/versions/20260808_0002_optional_embeddings.py:21`
  `op.add_column("code_chunks", sa.Column("embedding", Vector(), nullable=True))`.
  `rg -n "ivfflat|hnsw"` over all eight migrations: no match. SQL-side floor, measured: a full
  `code_chunks` sequential scan is **646 ms** (18 189 buffers).
- **Probable cause + confidence:** **Certain** for the mechanism. The comment at `:86-87`
  states the intent explicitly — "Python cosine is portable to SQLite tests and pgvector
  production" — so test portability was traded for production scalability. `Vector()` without
  a dimension follows from the same choice, since a dimension would pin one embedding model.
- **Smallest safe next step:** two steps, in order. (1) Add the SQL predicates that are correct
  regardless of index: `repository_id`, and `ORDER BY` + `LIMIT` on a bounded candidate set.
  Even without an index that bounds the Python work to the candidate limit. (2) Separately,
  decide the dimension question — a migration pinning `Vector(768)` (or one column per model
  family) plus an HNSW index, keeping the Python path as the SQLite test fallback behind the
  existing `embedding_model` guard.
- **Affected data/migrations/providers/cost:** step 2 is a non-trivial migration on
  `code_chunks` (22 900 rows, 176 MB) and forces an explicit decision about supporting two
  embedding dimensions at once. No provider cost. Correctness is unaffected — this is latency
  and memory only, since the current path is exhaustive and therefore exact.
- **Recommended tests + acceptance criteria:** (1) the `_cosine`-counter test above, inverted:
  a scoped semantic query must score at most `candidate_limit` rows, not the corpus;
  (2) a PostgreSQL test asserting an HNSW index exists and is used
  (`EXPLAIN` shows `Index Scan using …`); (3) a recall comparison between the exact Python path
  and the indexed path on a frozen fixture, per ADR 0001's validation gate. Acceptance for a
  performance claim: p95 semantic latency measured at 22 900 and at 229 000 chunks.
- **Fix status:** report-only

---

### REV-506

- **ID:** REV-506
- **Category:** PERFORMANCE_RISK
- **Severity:** high
- **Evidence level:** `PostgreSQL integration-tested` (SQL) and `manual live acceptance` (API)
- **Applies to:** both (the lexical SQL is identical on the two branches)
- **Impact:** Lexical search has no index behind it. Every query is a sequential scan of
  `code_chunks` (165 MB, 22 900 rows) with `ILIKE '%…%'`, which no btree can serve. Measured
  worst case **646 ms** in SQL and **1.13 s** end to end. The pathology is that latency is
  governed by how quickly the `LIMIT` fills, so **zero-result queries are the slowest** — the
  case where a user immediately retypes and retries. `mode=text` additionally runs the OR-term
  fallback whenever the exact branch found nothing, so a miss pays for two full scans.
  At 10× the corpus a miss is ~6.5 s of pure CPU per request, with no request-level bound.
- **Evidence:** no text index exists: live `\di+` = 38 indexes, all btree; no `pg_trgm`, no
  `tsvector` column, and `rg -n "gin|gist|trgm|tsvector"` over all eight migrations finds
  nothing. Measured:

  ```
  -- schema 0004
  ILIKE '%zzz_no_such_token_qq%' LIMIT 60 → Seq Scan, Rows Removed by Filter: 22900,
                                            Buffers: hit=5460 read=12729, 646.258 ms
  ILIKE '%ModelRetry%'          LIMIT 60 → Seq Scan, Rows Removed by Filter:   677,   6.535 ms
  GET /api/search?q=zzz_no_such_token_qq&mode=text&limit=30 → 1.129 s, 1.137 s
  GET /api/search?q=ModelRetry+validation+error&mode=hybrid&limit=30 → 0.799 s, 1.428 s

  -- re-measured on schema 0008, integration code deployed
  ILIKE '%zzz_no_such_token_qq%' LIMIT 60 → Seq Scan, Rows Removed by Filter: 22900,
                                            Buffers: hit=4132 read=14057, 693.430 ms
  ```

  Code: `search.py:68` and `:73`. The finding is schema-independent: `code_chunks` was untouched
  by the migration (still 165 MB / 22 900 rows) and no text index was added by any of the four
  new revisions.
- **Probable cause + confidence:** **High.** `ILIKE` was the portable choice (it works on
  SQLite for the tests, same trade-off as REV-505) and no full-text or trigram index was ever
  added, despite `README.md:9` advertising "full-text search" (REV-512).
- **Smallest safe next step:** a `GIN … gin_trgm_ops` index on `code_chunks.source_text` after
  `CREATE EXTENSION pg_trgm` makes `ILIKE '%…%'` indexable with no query rewrite — the smallest
  change that removes the worst case. A `tsvector` + `GIN` index is the better long-term answer
  for term queries but requires rewriting the query builder and changes ranking semantics, so
  it is a separate decision.
- **Affected data/migrations/providers/cost:** one additive migration plus an extension; a
  trigram index over 165 MB of text is large (expect tens of MB) and slows inserts, so measure
  the index build and the re-index impact before adopting. No provider cost.
- **Recommended tests + acceptance criteria:** measure p95 for a hit query, a miss query and a
  common-term query at the current corpus size, before and after. Acceptance: the miss case is
  no longer the slowest, and no query mode exceeds 100 ms in SQL at 22 900 chunks.
- **Fix status:** report-only

---

### REV-507

- **ID:** REV-507
- **Category:** DESIGN_GAP
- **Severity:** high
- **Evidence level:** `source-reviewed`
- **Applies to:** integration (regression relative to `main`)
- **Impact:** The integration branch removed the only code that avoided work for unchanged
  files, so **every** index — `sync` as well as `full` — is now a complete destructive rewrite
  of every file, symbol, chunk, edge and card in the repository. A `sync` after a one-line
  commit does the same 4 568 deletes, 180 790 inserts and (with REV-503) ~642 s of RI scanning
  as a full rebuild. Combined with REV-500, every routine sync now carries the full
  partial-overwrite blast radius. There is no `git diff`-based delta indexing anywhere in
  either branch and no stable logical symbol identity: symbol UUIDs are regenerated on every
  run (`models.py:26`, `default=uid`), so every previously issued symbol deep link, MCP
  reference and cached citation breaks after any index. Per §7, no delta-indexing claim can be
  made.
- **Evidence:** `main` `ingestion.py:151`:

  ```python
  if f and f.content_hash==digest and not full: continue
  ```

  integration `ingestion.py:222` — the `continue` is gone:

  ```python
  if f and f.content_hash==digest: f.indexed_commit_sha=sha
  ```

  Execution falls straight through to `:223`, which deletes and re-parses unconditionally.
  Integration also removed the three `if full:` guards, so `delete(SymbolEdge)` (`:212`),
  `_persist_edges` (`:232`) and `refresh_structural_cards` (`:235`) now run on every sync too
  (`git diff main origin/integration/consolidated-verified -- apps/api/app/ingestion.py`).

  The likely motive is visible in the test suite:
  `apps/api/tests/test_incremental_structural_cards.py:45` asserts
  `all(c.indexed_commit_sha==sha2 for c in cards.values())` after a `full=False` run. With the
  skip in place, unchanged files keep the old SHA and that assertion fails. So real delta
  indexing appears to have been traded for derived-card commit freshness — a legitimate
  requirement, solved the expensive way.

  The backlog is honest about the state: `backlog/KW-004-incremental-git-indexing.md:7` ("Sync
  currently scans the entire checkout") and `docs/ENGINEERING_BACKLOG.md:9` ("use
  `git diff --name-status <indexed SHA>..<HEAD>`; do not scan all files"). `README.md:8`
  is not (REV-512).
- **Probable cause + confidence:** **High** for the mechanism (the diff is unambiguous);
  **medium** for the motive, inferred from the test assertion.
- **Smallest safe next step:** restore the skip and update `indexed_commit_sha` on the
  unchanged file's symbols, chunks and structural cards with a cheap bulk `UPDATE` instead of a
  delete-and-reparse. That satisfies the structural-card assertion at O(rows updated) rather
  than O(rows rewritten). Real `git diff --name-status`-driven indexing is KW-004 and should
  stay a separate, tested slice.
- **Affected data/migrations/providers/cost:** with embeddings enabled this multiplies provider
  cost by the ratio of unchanged to changed files — on a typical commit, 2 283 files' worth of
  avoidable embedding spend per sync (compounded by REV-504). No migration.
- **Recommended tests + acceptance criteria:** index a two-commit fixture where one of three
  files changed; assert (1) only the changed file's symbol rows have new ids, (2) the unchanged
  files' symbol ids are **stable across the sync**, (3) all `indexed_commit_sha` values equal
  the new SHA, (4) `_parser_symbols_and_chunks` is called exactly once. Add an equivalence
  guard — sync-to-head must produce the same facts as a fresh full index at head — which is
  already specified in `benchmarks/README.md:54` and not yet enforced in a test.
- **Fix status:** report-only

---

### REV-508

- **ID:** REV-508
- **Category:** CORRECTNESS_RISK
- **Severity:** high
- **Evidence level:** `PostgreSQL integration-tested` for the sizes; `source-reviewed` for the
  provider consequence
- **Applies to:** both
- **Impact:** Chunk text is sent to the embedding provider with no truncation and no token
  budget. On the live corpus **879 chunks (3.8 %) exceed the ~8 000-character / 2 048-token
  input limit of the configured `text-embedding-005`**, 364 exceed 32 000 characters, and the
  largest is **868 248 characters**. A batch is `embedding_batch_size = 32` chunks, so a single
  request can carry tens of megabytes. Vertex will reject an oversized *single* instance with
  400, and the bisect logic explicitly cannot split further — it raises
  (`providers.py:120-126`). The practical consequence: **enabling embeddings on this repository
  cannot complete.** It will fail near the end of an 11 m 37 s index, after paying for every
  earlier batch, and then REV-500 will commit the half-embedded index under a `failed` status.
  Note the code-card path *is* bounded (`code_card_max_source_characters: 12000`,
  `code_cards.py:77`) — only the embedding path is not.
- **Evidence:** live measurement:

  ```sql
  SELECT count(*), max(length(source_text)), round(avg(length(source_text))),
         sum(length(source_text)),
         count(*) FILTER (WHERE length(source_text)>32000),
         count(*) FILTER (WHERE length(source_text)>8000)
  FROM code_chunks;
  → 22900 | 868248 | 3616 | 82807822 | 364 | 879
  ```

  The largest chunks are whole files:
  `tests/models/cassettes/test_multimodal_tool_returns/…google_vertex].yaml` at 868 248
  characters, lines 1–311. Cause: `.yaml` is in `EXT` (`ingestion.py:15`) but not in
  `PARSER_LANGUAGES` (`:18`), so it takes `_legacy_symbols_and_chunks` (`:112-117`); the
  regex finds no declarations, so `chunks()` returns `[(None,1,len(lines),content)]` (`:36`)
  — one chunk containing the entire base64-video cassette. `_embed_full_index_chunks` then
  iterates every chunk of the repository with no language filter and no length filter
  (`:166-175`) and passes `text` straight to `provider.embed_texts`.
- **Probable cause + confidence:** **High.** The bisect in `VertexEmbeddingProvider` shows the
  aggregate-payload problem was anticipated; the single-oversized-input case was not, and no
  size guard exists on the ingestion side.
- **Smallest safe next step:** two independent guards, both cheap. (1) Skip or truncate chunks
  above a configurable character budget in `_embed_full_index_chunks`, mirroring
  `code_card_max_source_characters`. (2) Exclude generated/data files from chunking — a
  868 KB base64 cassette is not retrievable code and should not be a chunk at all, which also
  reduces REV-506's scan and the 82.8 MB corpus.
- **Affected data/migrations/providers/cost:** avoids a guaranteed failed embedding run and the
  spend leading up to it. Reduces embedding volume materially (879 chunks carry a
  disproportionate share of the 82.8 MB). No migration.
- **Recommended tests + acceptance criteria:** a unit test with a fake provider asserting that
  no `embed_texts` input exceeds the configured budget and that no request's aggregate payload
  exceeds a configured byte ceiling. Acceptance: a full index of `pydanticAI` with embeddings
  enabled completes; no provider 400 occurs. That acceptance run needs explicit cost approval
  and was **not** performed here.
- **Fix status:** report-only

---

### REV-509

- **ID:** REV-509
- **Category:** CORRECTNESS_RISK
- **Severity:** medium
- **Evidence level:** `source-reviewed`
- **Applies to:** integration (`code_cards.py` is absent on `main`)
- **Impact:** Provider work that was requested, billed and successfully returned is thrown
  away. `_post_batch` issues `code_card_request_concurrency` (default **8**) requests
  concurrently and waits for all of them; the parse loop then raises on the first malformed or
  empty response. Up to 7 valid, paid-for cards that arrived in the same batch are never parsed
  and never persisted, and the job aborts. On resume they are re-requested and paid for again.
  The mandate's requirement is "Persistierung jeder *gültigen* Code Card" — every valid card
  persisted — and a valid card in the same batch as an invalid one is currently discarded.
- **Evidence:** `apps/api/app/code_cards.py:125-135` gathers the batch; `:170` awaits it;
  `:171-188` iterates and raises:

  ```python
  responses = asyncio.run(_post_batch(token, [item[3] for item in prepared], concurrency))
  for (symbol, card_started, context_elapsed, _), (response, provider_elapsed) in zip(prepared, responses):
      response.raise_for_status()
      ...
      except (KeyError, IndexError, TypeError, ValueError) as error:
          # Valid cards from earlier batches are durable; this symbol is retried on resume.
          raise RuntimeError(f"invalid code-card JSON for {symbol.qualified_name}; resumable retry required") from error
  ```

  The comment is precise and correct about *earlier batches* — `db.commit()` at `:197` makes
  those durable — and silent about the remainder of the *current* batch, which is the loss.
  `raise_for_status()` at `:172` has the same shape.
- **Probable cause + confidence:** **High.** Fail-fast was chosen deliberately (the resume path
  exists and works); the interaction with batch concurrency was not considered.
- **Smallest safe next step:** collect per-item outcomes across the whole batch, persist every
  valid card, then decide whether to continue or abort based on the accumulated
  valid/invalid/empty counts. This also produces the aggregate counts REV-511 is missing.
- **Affected data/migrations/providers/cost:** direct provider cost, bounded by
  `concurrency - 1` requests per failure. No migration.
- **Recommended tests + acceptance criteria:** extend `test_code_cards.py` with a batch of 8
  where item 3 returns malformed JSON. Acceptance: 7 cards persisted, 1 recorded as invalid,
  and a resumed run re-requests exactly 1 symbol.
- **Fix status:** report-only

---

### REV-510

- **ID:** REV-510
- **Category:** DESIGN_GAP
- **Severity:** medium
- **Evidence level:** `source-reviewed`
- **Applies to:** integration (the Cohere adapter is integration-only)
- **Impact:** The reranker has no rate-limit handling of any kind. Cohere's 429 becomes an
  immediate exception; `search.py:114-116` swallows it and degrades the response to
  `reranking.state = 'degraded'`. So a rate-limited reranker silently changes result **ordering**
  for every affected query with no retry and no operator-visible signal beyond one response
  field. The failure is invisible in aggregate: users get worse rankings and nothing is logged.
- **Evidence:** `apps/api/app/providers.py:33-45` — one `client.post`, then
  `response.raise_for_status()`. No `Retry-After`, no attempt loop, no backoff. Compare
  `VertexEmbeddingProvider.embed_texts` `:107-136` (8 attempts, `Retry-After`, capped
  exponential backoff) and `code_cards._retry_delay` `:93-105` (both `Retry-After` forms).
  `OpenRouterEmbeddingProvider.embed_texts` (`:56-64`) also writes no retry logic and depends
  on the `openai` SDK's undeclared default. Swallow site: `search.py:114-116`, `except
  Exception:` with no logging.
- **Probable cause + confidence:** **High.** The Cohere adapter is the newest of the three and
  the retry pattern established in the other two was not applied.
- **Smallest safe next step:** extract the existing `_retry_delay` / attempt-loop into one
  shared helper in `providers.py` and use it in all three adapters. Log the degradation in
  `search.py` instead of swallowing it silently.
- **Affected data/migrations/providers/cost:** no data. Retrying a 429 costs one extra request;
  the current behaviour costs result quality instead.
- **Recommended tests + acceptance criteria:** a fake-client test for the reranker mirroring
  `test_vertex_retries_a_rate_limited_batch`. Acceptance: a 429 with `Retry-After: 1` is
  retried once and succeeds; exhausted retries surface `reranking.state='degraded'` **and**
  emit a log line.
- **Fix status:** report-only

---

### REV-511

- **ID:** REV-511
- **Category:** DESIGN_GAP
- **Severity:** medium
- **Evidence level:** `source-reviewed`
- **Applies to:** integration for the code-card telemetry; both for the absent ingestion
  telemetry and cost audit
- **Impact:** §3.10 requires provider work to be "kostenbeobachtbar" — cost-observable. It is
  not. Token counts are stored per card and readable only one symbol at a time; there is no
  per-run total, no aggregate, no price model and no endpoint that answers "what did this run
  cost". Timing telemetry exists for code cards only, as a single log line — not persisted, not
  queryable, and emitted at `WARNING` for successful operations. Ingestion has **no** timing
  telemetry at all. This review is the demonstration: attributing the 12.7 × regression
  required `pg_stat_activity`, `EXPLAIN ANALYZE` and manual arithmetic, because
  `indexing_jobs` records only start, end and a phase string.
- **Evidence:** present — `code_cards.py:198`
  `logger.warning("code_card_result outcome=persisted symbol=%s context_s=%.3f provider_s=%.3f parse_s=%.3f persist_s=%.3f total_s=%.3f", …)`;
  `input_tokens` / `output_tokens` at `:189-190`, surfaced by `main.py:191`. Absent —
  `rg -n "cost|input_tokens|output_tokens"` over `apps/api/app` finds no aggregation and no
  price table; `generate_code_cards` returns `{"total", "completed", "model"}` (`:204`) with no
  invalid/empty counts (and cannot have them, since it aborts on the first — REV-509);
  `indexing_jobs.progress` is only `{'phase': …, 'files': …}` (`ingestion.py:238`);
  `_embed_full_index_chunks` emits nothing. Accuracy caveat: `total_s` is measured from
  `card_started`, set during batch *preparation* (`:164,169`), so for
  `concurrency > 1` it includes waiting for the whole batch and is not a per-card figure.
  Docs are correctly forward-looking, not contradictory:
  `docs/HOSTED_PRODUCT_AND_UI_VISION.md:21`, `docs/NEXT_STEPS.md:85`.
- **Probable cause + confidence:** **High.** Telemetry was added where a specific debugging
  need arose (code cards) and nowhere else.
- **Smallest safe next step:** persist the counters that already exist. Extend
  `indexing_jobs.progress` (already `JSON`, no migration needed) with phase durations, rows
  written per table, and provider request/token totals for the run, and write it on completion
  *and* on failure. Demote successful code-card lines to `INFO`.
- **Affected data/migrations/providers/cost:** none — `progress` is already `JSON`. Enables
  every future performance or cost claim, which §7 currently forbids from being made.
- **Recommended tests + acceptance criteria:** assert that a completed index job's `progress`
  contains non-zero durations for each phase and row counts matching the tables, and that a
  failed job records the phase it failed in. Acceptance: the 12.7 × regression would be
  diagnosable from `indexing_jobs` alone.
- **Fix status:** report-only

---

### REV-512

- **ID:** REV-512
- **Category:** DOCUMENTATION_GAP
- **Severity:** medium
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** `README.md`'s MVP capability list makes two claims the code does not support, and
  both are in the areas §7 explicitly guards. A reader — or an agent — planning around
  "incremental synchronization" or "full-text search" will size cost and latency wrongly by
  more than an order of magnitude.
- **Evidence:** `README.md:8` — "Incremental Git synchronization with content-hash
  deduplication". The content hash is computed and stored, but on integration it no longer
  avoids any work (REV-507): `ingestion.py:222` drops the `continue`, so every file is deleted
  and re-parsed on every sync. There is no `git diff` anywhere in `ingestion.py`
  (`rg -n "git.*diff" apps/api/app` → no match).
  `README.md:9` — "PostgreSQL metadata, **full-text search**, pgvector-ready embeddings".
  There is no full-text search: no `tsvector`, no `GIN`, no `pg_trgm` in any of the eight
  migrations, and `search.py:68` uses `ILIKE '%…%'` (REV-506). "pgvector-ready" is also
  generous given that `Vector()` has no dimension and therefore admits no vector index
  (REV-505).
  The backlog contradicts the README and is correct:
  `backlog/KW-004-incremental-git-indexing.md:7`, `docs/ENGINEERING_BACKLOG.md:9`.
- **Probable cause + confidence:** **Certain.** The README describes the intended MVP; the
  incremental skip was later removed and full-text search was never built.
- **Smallest safe next step:** two line edits — "content-hash deduplication (full checkout
  scan; commit-diff indexing tracked as KW-004)" and "substring and symbol search (no
  full-text index yet)". Cheaper than any code change and removes a false claim.
- **Affected data/migrations/providers/cost:** none.
- **Recommended tests + acceptance criteria:** a docs check in CI that the README capability
  list only names capabilities with a passing test behind them. Acceptance: no README claim
  lacks a test reference.
- **Fix status:** report-only

---

### REV-513

- **ID:** REV-513
- **Category:** DESIGN_GAP
- **Severity:** medium
- **Evidence level:** `documented only / pending`
- **Applies to:** both
- **Impact:** ADR 0001 is "Accepted" and specifies three storage contracts as the mechanism by
  which alternative backends stay adapters. None exists. Retrieval strategy is written directly
  into `search.py` — the in-Python cosine loop *is* the vector index, with no seam to replace
  it. That is what makes REV-505 a rewrite rather than an adapter swap, and it means the ADR's
  own validation gate ("validate an adapter against the same frozen, commit-pinned fixture")
  cannot be executed because there is nothing to validate against.
- **Evidence:** `docs/adr/0001-storage-backend-adapters.md` §"Initial Contracts" specifies
  `CodeGraphStore` (`get_snapshot`, `get_symbol`, `get_bounded_subgraph`, `find_impact`),
  `VectorSearchIndex` (`upsert`, `search`, `remove_snapshot`, `status`) and `ProvenanceStore`
  (`record`, `trace`).

  ```
  rg -n "CodeGraphStore|VectorSearchIndex|ProvenanceStore" --glob '!docs/**' .
  → no matches (exit 1)
  ```

  What *does* satisfy the ADR: `providers.py` holds no domain logic — three `Protocol`s, three
  HTTP adapters, response validation, and settings-driven selection, with no repository,
  symbol, chunk or scope concept in the file. ADR 0001 §5's ordering requirement ("filters are
  applied before a result is returned") is violated by `search.py` in the narrower sense that
  matters: filters are applied before *returning* but after the database has already truncated
  the candidate set (REV-502).
- **Probable cause + confidence:** **Certain.** The ADR documents an intended design; only the
  provider half was built.
- **Smallest safe next step:** nothing structural. Mark the "Initial Contracts" section as
  *proposed, not implemented* so the ADR stops reading as a description of the code, and
  extract the first contract only when a second backend is actually needed — the ADR's own §6
  says exactly that ("A new adapter is introduced only after a measured workload demonstrates a
  concrete need"). Introducing three interfaces with one implementation each now would add
  indirection without removing risk.
- **Affected data/migrations/providers/cost:** none.
- **Recommended tests + acceptance criteria:** if and when a contract is extracted, the ADR's
  five-point validation gate against a frozen fixture is the acceptance criterion. Until then,
  the acceptance criterion is documentation accuracy.
- **Fix status:** report-only

---

### REV-514

- **ID:** REV-514
- **Category:** TEST_GAP
- **Severity:** medium
- **Evidence level:** `unit/API-tested`
- **Applies to:** both
- **Impact:** The 50-test suite passes in 1.24 s and covers parser facts, provider selection,
  retry behaviour and graph shape well. Two gaps let this workstream's most serious defects
  through. (1) **No scope or limit-ordering test exists**, which is why REV-502 and REV-505
  were shippable. (2) **Every ingestion test runs on SQLite in-memory**, where `ON DELETE
  CASCADE` is not enforced and no ORM `relationship(cascade=…)` is declared — so ingestion's
  deletion semantics, the exact area where REV-500 and REV-503 live, are never exercised
  against the semantics production uses. `ingestion.py:210` asserts the opposite in a comment:
  "Make deletion explicit so SQLite tests and PostgreSQL have identical semantics." They are
  not identical.
- **Evidence:** `apps/api/tests/test_search.py` is 23 lines and tests only `parse_query`,
  `query_terms` and the `result` dict shape — no `repository_id`, no `limit`, no multi-repository
  fixture (`rg -n "scope|repository_id|limit" apps/api/tests/test_search.py` → no match).
  `test_ingestion_graph.py` and `test_incremental_structural_cards.py` both use
  `create_engine('sqlite://')`. The divergence is proven: in
  `test_rev_partial_overwrite.py` the removed file's `File` row disappears while its `Symbol`
  row survives as an orphan —

  ```
  status=failed files=['a.py'] symbols=['alpha', 'beta', 'gamma']
  ```

  `beta` belongs to the deleted `b.py`. On PostgreSQL the FK cascade would remove it. `models.py`
  declares `ondelete='CASCADE'` on the columns but no `relationship()` anywhere, and SQLite
  does not enforce FKs without `PRAGMA foreign_keys=ON`.
  `test_incremental_structural_cards.py` is also mis-named relative to what it verifies: it
  asserts derived-card *freshness* after a sync, not that unchanged files were skipped — so it
  passes on integration precisely *because* delta indexing was removed (REV-507).
- **Probable cause + confidence:** **Certain.** SQLite was chosen for a fast suite (a good
  trade for parser and provider tests) and no PostgreSQL-backed ingestion test was added
  alongside.
- **Smallest safe next step:** add two tests, not a framework. (1) The two-repository
  scope-versus-limit test from REV-502. (2) One PostgreSQL-backed ingestion test against a
  throwaway database asserting post-delete row counts and orphan absence. The existing
  `test_migrations.py` shows the project is willing to keep DB-shaped tests.
- **Affected data/migrations/providers/cost:** none — test-only, and both must use a throwaway
  database, never the live one.
- **Recommended tests + acceptance criteria:** as above. Acceptance: reverting the fixes for
  REV-500, REV-502, REV-504 and REV-507 each makes at least one test fail.
- **Fix status:** report-only

---

### REV-515

- **ID:** REV-515
- **Category:** DESIGN_GAP
- **Severity:** medium
- **Evidence level:** `manual live acceptance` — now confirmed against **integration** code
  running live, not only `main`
- **Applies to:** both
- **Impact:** Two of the four retrieval modalities cannot be scoped at all. `GET
  /api/search/symbols` and `POST /api/search/semantic` accept no `repository_id` on either
  branch and pass none through, so they always search every indexed repository. The web search
  client never sends `repository_id` even to the route that supports it. With one repository
  this is invisible; with a workspace it means symbol and semantic discovery ignore the
  workspace boundary entirely, which is §3.1's "Scope kommt vom Server" inverted — the server
  offers no way to express scope.
- **Evidence:** integration `main.py:301-302`:

  ```python
  @app.get('/api/search/symbols')
  def symbol_search(q:str,db:Session=Depends(get_db)): return {'results':search(db,q,'symbols')}
  ```

  `main.py:303-306` (`/api/search/semantic`) reads only `body.get('query','')` and passes no
  `repository_id`. Identical on `main` at `:227-232`. Only `GET /api/search` gained the
  parameter, on integration only (`:296-300`, with a 404 validation). Live confirmation
  against `main`:

  ```
  GET /api/search/symbols?q=ModelRetry → 30 results, no scope parameter accepted
  openapi.json paths: /api/search, /api/search/semantic, /api/search/symbols
  ```

  Re-confirmed against the **integration** image now deployed, from the live OpenAPI document —
  the asymmetry is unchanged by the newer code:

  ```
  /api/search                GET params=['q','mode','limit','repository_id','rerank']
  /api/search/symbols        GET params=['q']            ← no scope
  /api/search/semantic       ['post']                    ← no scope
  GET /api/search?q=x&repository_id=<unknown-uuid> → HTTP 404   (the one route that validates)
  ```

  Web client: `apps/web/app/search/search-client.tsx:34` requests
  `/search?q=…&mode=…&rerank=…` — no `repository_id`.
- **Probable cause + confidence:** **Certain.** Scope was retrofitted onto one route and not
  propagated.
- **Smallest safe next step:** add `repository_id` to both routes with the same 404 validation
  `GET /api/search` already has, and pass it through. Once REV-502 puts the predicate in SQL
  this is a two-line change per route.
- **Affected data/migrations/providers/cost:** none. For semantic search, scoping in SQL also
  bounds REV-505's Python work.
- **Recommended tests + acceptance criteria:** API tests asserting all three search routes
  accept `repository_id`, reject an unknown id with 404, and return only in-scope results.
  Acceptance: no retrieval route can return a result outside the requested scope.
- **Fix status:** report-only

---

### REV-516

- **ID:** REV-516
- **Category:** CORRECTNESS_RISK
- **Severity:** medium
- **Evidence level:** `manual live acceptance` for both halves — the search half was observed
  broken on `main` and observed **fixed** after the integration image was deployed; the graph
  half was observed broken on both
- **Applies to:** `main` for search (**resolved on the live target**); **both** for graph (open)
- **Impact:** §3.6 requires every hit and every piece of graph context to carry repository,
  file/path, line range **and indexed commit**. On the live target, search results carry no
  `indexed_commit_sha` and no `symbol_id`, so a consumer cannot tell which commit the snippet
  came from or deep-link to the symbol. On **both** branches, graph nodes carry no `path` and
  no `indexed_commit_sha`. Because symbol UUIDs are regenerated on every index (REV-507), a
  graph response that omits the commit cannot be validated against anything later.
- **Evidence:** live `GET /api/search?q=ModelRetry&mode=text&limit=2` returns result keys
  `type, score, repository, repository_id, file_id, path, language, start_line, end_line,
  snippet, symbol` — no `indexed_commit_sha`, no `symbol_id`. Integration fixed this in
  `search.py:34-36`, which adds both. Graph, both branches — `main.py:53`:

  ```python
  def symbol_out(s): return {'id':…,'repository_id':…,'file_id':…,'name':…,'qualified_name':…,
    'type':…,'language':…,'start_line':…,'end_line':…,'start_byte':…,'end_byte':…,
    'parent_symbol_id':…,'signature':…,'source_text':…}
  ```

  No `path`, no `indexed_commit_sha`. Confirmed live:

  ```
  GET …/symbols/9e17df59…/subgraph?depth=1
  node keys: end_byte end_line file_id id language name parent_symbol_id qualified_name
             repository_id signature source_text start_byte start_line type
  ```

  After the integration image was deployed the search half is **confirmed fixed on the live
  target** and the graph half **confirmed still broken**, both by direct observation:

  ```
  GET /api/search?…&repository_id=… →
    result keys: end_line file_id indexed_commit_sha language path repository repository_id
                 score snippet start_line symbol symbol_id type
    indexed_commit_sha = 640d5171fe5795e58553b5af414cbcac3e0c7673
    symbol_id          = 02ed2984-9f7d-4089-a9c9-cfadda91e1d0

  GET …/symbols/69f63028…/subgraph?depth=1 →
    has path: False | has indexed_commit_sha: False
  ```

  The pattern to follow already exists: `citation()` (`main.py:63-65`) emits the complete
  contract including `indexed_commit_sha` with a documented fallback chain, and clamps the line
  range to the file length.
- **Probable cause + confidence:** **Certain.** `citation()` was built to the contract;
  `symbol_out` and (on `main`) `result` predate it and were not aligned.
- **Smallest safe next step:** add `path` and `indexed_commit_sha` to `symbol_out`, reusing
  `citation()`'s fallback chain. The graph handlers already load the `files` map
  (`scoped_files`), so no extra query is needed. Search is already fixed on integration; no
  separate work is needed there beyond merging.
- **Affected data/migrations/providers/cost:** none — additive response fields. Web consumers
  should be checked for strict response parsing.
- **Recommended tests + acceptance criteria:** a contract test asserting every retrieval and
  graph response item carries repository_id, path, start/end line and a non-null
  `indexed_commit_sha`. Acceptance: no evidence-bearing response object omits any of the four.
- **Fix status:** report-only

---

### REV-517

- **ID:** REV-517
- **Category:** PERFORMANCE_RISK
- **Severity:** medium
- **Evidence level:** `manual live acceptance`
- **Applies to:** both (graph semantics are Workstream D's; the loading pattern is noted here
  because it is the same whole-table-into-Python shape as REV-505)
- **Impact:** Every graph request loads **all 136 566 edges** of the repository into Python,
  sorts them, and re-scans the list once per traversal hop. Measured **3.2–3.4 s** for a
  subgraph that returns 11 nodes and 18 edges. The node budget bounds the *response*, not the
  work, so latency is a function of repository size rather than result size and does not
  improve when the caller asks for less.
- **Evidence:** `main.py:60` `scoped_edges` materialises and sorts every edge for the
  repository; `subgraph` (`:242-261`) then filters that list inside the `for _ in range(depth)`
  loop, and `repository_graph` (`:263+`) does the same. Measured against live `main`:

  ```
  -- main image, schema 0004
  GET …/symbols/9e17df59…/subgraph?depth=2 → 3.393 s, 3.436 s, 3.227 s   (11 nodes, 18 edges)

  -- integration image, schema 0008 (re-measured after the mid-review redeploy)
  GET …/symbols/69f63028…/subgraph?depth=2 → 5.009 s, 4.743 s, 2.786 s
  GET …/{repo_id}/graph?max_nodes=60       → HTTP 200 in 3.143 s
  ```

  The integration-only repository-overview route is now live and exhibits the same cost, so the
  finding covers both graph routes with live measurements on both images. For scale: the same
  repository's whole `symbol_edges` table is 59 MB / 84 MB with indexes.
- **Probable cause + confidence:** **High.** Determinism was the design driver — the sorted
  Python list gives stable tie-breaking — and it was achieved by materialising everything.
- **Smallest safe next step:** push the frontier expansion into SQL, one bounded query per hop
  (`WHERE repository_id = … AND (source_symbol_id IN :frontier OR target_symbol_id IN :frontier)`),
  keeping the existing Python sort for tie-breaking on the small result set. Requires indexes
  on `symbol_edges(source_symbol_id)` and `(target_symbol_id)` — the same two that REV-503
  needs, so one migration serves both.
- **Affected data/migrations/providers/cost:** shares REV-503's migration. No provider cost.
- **Recommended tests + acceptance criteria:** determinism tests must keep passing byte-for-byte
  (Workstream D owns those). Acceptance: p95 for `depth=2` under 300 ms at 136 566 edges, with
  identical node and edge ordering to the current implementation.
- **Fix status:** report-only

---

### REV-518

- **ID:** REV-518
- **Category:** DESIGN_GAP
- **Severity:** low
- **Evidence level:** `source-reviewed`
- **Applies to:** integration
- **Impact:** The code-card module obtains its Google ADC token by calling a **private static
  method on the embeddings adapter**. Disabling, replacing or moving the Vertex *embedding*
  adapter silently breaks *code cards*, and code cards cannot be authenticated independently.
  It is the one place ADR 0001's adapter boundary is crossed.
- **Evidence:** `apps/api/app/code_cards.py:18` `from app.providers import VertexEmbeddingProvider`
  and `:66-67`:

  ```python
  def _access_token():
      return VertexEmbeddingProvider._refresh_credentials()
  ```

  `_refresh_credentials` (`providers.py:84-95`) is a `@staticmethod` with a leading underscore
  — private by convention. Code cards also build their own endpoint (`code_cards.py:70-73`)
  and their own retry loop (`:108-122`), so the token is the only thing borrowed.
- **Probable cause + confidence:** **Certain.** Convenience reuse of working ADC code.
- **Smallest safe next step:** move the ADC refresh to a module-level function in
  `providers.py` (e.g. `google_access_token()`) and have both call sites use it. Pure move, no
  behaviour change.
- **Affected data/migrations/providers/cost:** none.
- **Recommended tests + acceptance criteria:** the existing
  `test_code_cards.py` monkeypatch points keep working. Acceptance: no module imports a
  private member of another module.
- **Fix status:** report-only

---

### REV-519

- **ID:** REV-519
- **Category:** DESIGN_GAP
- **Severity:** low
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** `ChatProvider` is declared but never implemented, and `openai_api_key` /
  `openai_chat_model` are never read by any code path. `/api/chat` returns a canned string
  telling the user to "Configure OPENAI_API_KEY to enable synthesized answers", which no code
  would act on if they did. Two consequences: operators believe a chat provider cost exists
  when it does not, and a reviewer must assume `/api/chat` is billable when it is not — this
  review treated it as billable and did not call it.
- **Evidence:** `providers.py:18-19` declares the `Protocol`;
  `rg -n "ChatProvider"` finds only the declaration. `config.py:9-10` defines
  `openai_api_key` and `openai_chat_model`; `rg -n "openai_api_key|openai_chat_model"` over
  `apps/api/app` finds only `config.py`. `main.py:332` produces the canned answer, and
  `main.py:313` labels `/api/explanations` honestly as `'answer_mode':'retrieval_only'`.
  `providers.py:3` also imports `json` without using it.
- **Probable cause + confidence:** **Certain.** Scaffolding for a synthesis feature that was
  deliberately deferred in favour of retrieval-only, grounded answers — which is the right
  product call.
- **Smallest safe next step:** delete the unused `Protocol`, the two dead settings and the
  unused import, and change the chat copy to state that answers are retrieval-only by design
  rather than blocked on a missing key. Pure deletion.
- **Affected data/migrations/providers/cost:** removes a phantom provider dependency from the
  cost surface.
- **Recommended tests + acceptance criteria:** assert `/api/chat` and `/api/explanations` make
  no outbound HTTP request with all provider settings unset. Acceptance: the documented
  provider surface matches the code's actual provider surface.
- **Fix status:** report-only

---

### REV-520

- **ID:** REV-520
- **Category:** DESIGN_GAP
- **Severity:** info
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** The design answer to §5.E's "atomic, published index generations" question:
  there are none. The index is a single transaction that mutates live rows in place. It is
  *atomic* almost by accident — MVCC means readers see the previous snapshot until commit —
  but atomicity is the only snapshot property it has. There is no generation identity, no way
  to keep the previous index queryable while the next one builds, no way to roll forward or
  back between generations, and REV-500 breaks even the atomicity on the common failure path.
  Practical costs: locks are held for the whole run (11 m 37 s measured, longer with
  embeddings), which is what makes REV-501's abandoned transaction so damaging; `VACUUM`
  cannot reclaim during a run; and two concurrent index jobs for one repository will block on
  each other rather than being rejected. Per §7, no atomic-published-snapshot claim may be
  made.
- **Evidence:** transaction boundaries in `ingestion.index_repository` (integration
  `:189-241`), traced precisely — exactly three commits on the success path:

  | Line | Boundary | What is committed |
  |---|---|---|
  | `:190` | `db.commit()` | the `IndexingJob` row, `status='running'` |
  | `:201` | `db.commit()` | `local_path`, `latest_detected_commit_sha`, `indexing_status='indexing'` |
  | `:211-237` | *(no commit)* | `delete(CodeCard)`, `delete(SymbolEdge)`, 4 568 per-file `delete(Symbol)`/`delete(CodeChunk)`, all inserts, `db.delete(f)` for removed files, `_persist_edges`, `_restore_code_cards`, `refresh_structural_cards`, and **all provider embedding calls** — three `db.flush()` calls (`:231,234`) push SQL without committing |
  | `:238` | `db.commit()` | the entire rewrite plus `indexed_commit_sha` and `status='ready'` |
  | `:240` | `db.commit()` | on failure — **also commits everything pending** (REV-500) |

  So the destructive work and every provider call share one transaction, and `indexing_status`
  is committed *outside* it. Confirmed live in REV-501's `pg_locks` output: 50 locks including
  `RowExclusiveLock` on all three large tables, held indefinitely.
- **Probable cause + confidence:** **Certain**, and it is a deliberate simplicity trade — one
  transaction is much simpler than generation management, and at this scale it is defensible.
- **Smallest safe next step:** do not restructure. Fix REV-500 first (rollback on failure),
  which restores the atomicity this design already claims, then REV-503, which shrinks the lock
  window ~12×. Generation identity is only worth building when zero-downtime reindexing or
  multi-generation queries become a stated requirement; ADR 0001 §4 already sketches the
  identity (scope + commit + model + schema version) for that day.
- **Affected data/migrations/providers/cost:** real index generations would be a substantial
  schema change (generation column or partitioning on every large table). Not recommended now.
- **Recommended tests + acceptance criteria:** for the current design, a concurrency test:
  two index jobs for the same repository must not interleave destructively — one should be
  rejected with 409, not blocked. Acceptance: `POST …/reindex` while a job runs returns 409.
- **Fix status:** report-only

---

## Not assessed

- **Any provider-backed path end to end.** No OpenRouter, Vertex, Gemini or Cohere request was
  made. Every provider finding is `source-reviewed` or proven with a fake/counting provider.
  REV-504, REV-508, REV-509 and REV-510 would each be settled definitively by one small
  metered run, which needs explicit cost approval that was not given. `provider E2E verified`
  appears nowhere in this report.
- **Re-index timing after the REV-503 fix.** The prediction (697 s → under 90 s) is arithmetic
  from measured per-check costs, not a measurement. Settling it requires an indexing run,
  which is forbidden here, and must use a throwaway copy of the database.
- **`refresh_structural_cards` cost on the real corpus.** `structural_cards.py:19-52` is
  O(paths × files) plus O(paths × edges); with ~400 ancestor directories and 136 566 edges the
  boundary loop at `:36-39` is on the order of 5·10⁷ Python iterations per index, and there are
  two more nested comprehensions per path at `:31-34`. It runs unconditionally on integration
  (`ingestion.py:235`). This was **not measured**, because it does not exist on `main` and the
  697 s figure therefore cannot contain it. It is a plausible second-largest cost after
  REV-503, and it would be dwarfed by REV-503 if both are present. Settling it requires one
  integration-branch index run with per-phase timing (REV-511).
- **Integration-branch runtime — partially superseded.** The brief recorded the database as
  pinned at `0004`; a sibling session migrated it to `0008` and redeployed integration images
  mid-review. Read-only routes of the integration build were therefore exercised and are cited
  as `manual live acceptance` (REV-515, REV-516, REV-517). Everything **write- or
  provider-shaped** in the integration build remains unexercised: `code_cards.generate_code_cards`,
  `refresh_structural_cards`, `reembed_repository`, `_embed_full_index_chunks`, the `rerank`
  query path, and `POST /api/repositories/{repo_id}/code-cards`. `code_cards` and
  `structural_cards` are **empty (0 rows)** — their existence is a schema fact and is not
  evidence that either pipeline has ever run.
- **`refresh_structural_cards` on the real corpus — still not assessed, and now reachable.** It
  is deployed code as of the redeploy, but exercising it requires an indexing run. `structural_cards`
  having 0 rows confirms it has never executed against this 2 284-file / 136 566-edge corpus.
- **The mid-review migration itself.** Not performed, not reviewed, and not verified for
  correctness by this workstream — it was executed by another session. `symbol_edges.target_name`
  changing from `character varying(512)` to `text` implies a full table rewrite; row counts were
  confirmed preserved (2 284 / 21 324 / 22 900 / 136 566) but no deeper integrity check was made.
  Migration correctness belongs to Workstream C.
- **`pg_stat_user_tables` counters after the restart.** `n_live_tup` / `n_dead_tup` now read `0`
  for every table because the statistics collector was reset; the pre-migration bloat figures
  quoted in REV-501 are from before the restart. Actual row counts were re-confirmed with
  `count(*)`, not from the statistics view.
- **Semantic search latency at real scale.** No chunk in the live database has an embedding
  (`count(*) FILTER (WHERE embedding IS NOT NULL) = 0`), so the semantic path could not be
  exercised against real data even in principle, and doing so would require a provider call.
  The 646 ms SQL floor and the 82.8 MB transfer volume are measured; the per-query totals and
  the 10× / 100× projections are arithmetic.
- **`pg_trgm` / GIN index build cost and size** for REV-506. Creating an index is a write; not
  attempted. Needs measurement on a throwaway copy before adoption.
- **`benchmarks/scripts/*`.** Inventoried, not executed.
  `benchmarks/scripts/run_fork_e2e_nightly.py` is the only one that references providers or
  code cards; `fetch_corpora.py`, `run_benchmark.py`, `validate.py`,
  `validate_fork_realism.py` and `verify_live_queries.py` do not, but running any of them
  would trigger indexing. `benchmarks/README.md:53-54` specifies an incremental-evaluation and
  equivalence-guard protocol that would settle REV-507 properly; whether it has ever been run
  is `documented only / pending`.
- **Alembic upgrade/downgrade behaviour** for the index-adding migrations proposed in REV-503,
  REV-504 and REV-505. No migration was executed. `docs/migrations.md` and Workstream C own
  this.
- **Whether REV-501's leaked transaction has already blocked a real job.** The two failed rows
  in `indexing_jobs` are both explained by the brief (job timeout, deliberate SIGKILL), and no
  third failure exists. The blocking behaviour is inferred from the lock set, not observed on a
  real job — deliberately, since observing it would require starting an indexing run.
- **`data/` as source code.** Excluded per the brief. Inspected only as indexed input: 2 284
  files, 82.8 MB of chunk text, largest single chunk 868 248 characters (REV-508).
