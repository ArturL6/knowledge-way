# Packet 1.3 — pgvector ANN cost extrapolation (HD-003 §4)

Per HD-003 §4 / STATUS.md packet 1.3 constraints: a bounded (<=500 chunk) subset was
embedded with the real production provider (Vertex `text-embedding-005` @768) to validate
the ANN pipeline end-to-end, and a full-corpus cost extrapolation is committed here BEFORE
any full-corpus embed. **No full-corpus embed has been run.**

## Subset actually embedded (real Vertex spend)

- **Repository:** `encode/starlette` (member of the `fastapi-stack` workspace, `benchmarks/corpora.json`)
- **Chunks embedded:** 500 (first 500 `code_chunks` rows by id, non-blank `source_text`)
- **Embedding input:** the production `_embedding_document` text (repo/path/language/kind/
  symbol/signature/calls/imports header + source code), matching what `ingestion.py` would
  send in a real index run
- **Total embedding input characters:** 541,698
- **Provider/model:** `vertex:text-embedding-005`, `outputDimensionality=768` — verified 500/500
  vectors returned, all 768-dimensional
- **Estimated spend for this subset:** 541,698 / 1,000 x $0.000025/1k chars ≈ **$0.0135** (~1.4 cents)
- **Validation performed with this subset:** real ANN query via `search_with_capability(...,
  mode="semantic")` against Postgres, returning correctly ranked, on-topic results (see PR body
  for the transcript, e.g. query "how are static files served" -> `StaticFiles.get_path` /
  `StaticFiles.get_response` in `starlette/staticfiles.py`); `EXPLAIN` confirms the query plan
  uses the new HNSW index (see PR body).

## Full fastapi-stack corpus size (measured, not embedded)

The full `fastapi-stack` workspace (fastapi + starlette + pydantic, pinned SHAs per
`benchmarks/corpora.json`) was **chunked and parsed only** (`EMBEDDING_PROVIDER=none`, zero
provider calls, zero spend) to get a real chunk count for this extrapolation:

| repo | chunks | avg source chars/chunk | total source chars |
|---|---:|---:|---:|
| fastapi | 6,160 | 1,978 | 12,183,372 |
| starlette | 1,617 | 613 | 992,016 |
| pydantic | 11,375 | 474 | 5,394,058 |
| **TOTAL** | **19,152** | **970** | **18,569,446** |

## Extrapolation

The real embedding input is the `_embedding_document` wrapper, not raw `source_text` alone.
Measured on the 500-chunk subset above: 541,698 embedding-input chars / 318,947 raw
`source_text` chars for those same 500 rows = **1.699x** header overhead.

- Raw-`source_text`-only estimate (lower bound, ignores header overhead):
  18,569,446 / 1,000 x $0.000025/1k ≈ **$0.464**
- Overhead-adjusted estimate (measured 1.699x ratio applied to the full corpus):
  18,569,446 x 1.699 = 31,553,489 embedding-input chars
  31,553,489 / 1,000 x $0.000025/1k ≈ **$0.789**

**Full-corpus embed of the entire `fastapi-stack` workspace (19,152 chunks) is estimated at
roughly $0.46-$0.79**, using Vertex's published per-character online-prediction price for
text embedding models ($0.000025 / 1,000 characters; batch prediction is cheaper at
$0.00002/1,000 chars). This is comfortably inside the packet's USD 40 pause / USD 50 hard cap,
but per HD-003 §4 and the packet's `next_instruction`, **the full-corpus embed is not run in
this packet** — it is held for explicit owner approval, independent of how small the estimate is.

**Pricing source caveat:** the per-character price above was obtained via web search against
third-party pricing aggregators (getmaxim.ai, cloudprice.net), not a direct fetch of Google
Cloud's own pricing page (the fetch attempt did not return usable page content in this
session). It matches this repository's own recollection/prior estimates (`vertex-readiness.md`
notes text-embedding-005 pricing "per ~1k input tokens"), but should be re-confirmed against
the live Cloud Billing / Vertex AI pricing console before treating the dollar figures above as
authoritative for an actual purchase decision.

## Actual spend this packet

- Subset embedding (500 real chunks, starlette): ~$0.0135
- Two probe calls during ANN validation (`embed_texts` on 1-2 short strings, twice): negligible,
  well under $0.0001 each
- **Total real Vertex spend this packet: ~1-2 cents.** No full-corpus embed was run. No other
  paid provider was called (OpenRouter was not used; a local repo-root `.env` configuring it
  was explicitly overridden with `EMBEDDING_PROVIDER=vertex` for all commands in this packet).
