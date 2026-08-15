"""Pure rank-fusion domain logic (packet 1.5).

Weighted reciprocal-rank fusion (RRF): each ranked result list is tagged with a retrieval
mode ("semantic", "lexical", "symbol", ...) and each mode's contribution is scaled by a
per-mode trust weight before being reciprocal-rank-summed. Plain equal-weight RRF
(score += 1/(k+rank) summed across every list, unweighted) lets N weak modes outvote one
strong mode: measured on the fastapi-stack gold set, a junk row landing at rank 1 in both
lexical AND symbol search (score ~= 1/61 + 1/61 = 0.0328) outscored a gold row that only
semantic search found, at rank 1 (score ~= 1/61 = 0.0164) -- hybrid hit@5 (0.56) came in
*below* semantic-alone hit@5 (0.60), which should never happen. Scaling each mode's
contribution by a trust weight (semantic > lexical/symbol by default -- see
DEFAULT_MODE_WEIGHTS below) fixes that without discarding any mode's recall.

No SQLAlchemy/FastAPI/pgvector imports here: import-linter forbids app.domain depending on
adapters or frameworks (pyproject.toml [[tool.importlinter.contracts]]). This module only
ever sees plain result dicts (as produced by app.search.result()) tagged with a plain mode
string -- it has no idea a database exists.
"""

DEFAULT_RRF_K = 60

# Defaults chosen so semantic's own rank-1 contribution cannot be diluted below a junk row
# that lands at rank 1 in *both* weaker modes at once (the exact failure mode measured above):
# weight_lexical + weight_symbol (0.5 + 0.4 = 0.9) < weight_semantic (1.0). Lexical and symbol
# keep meaningful weight below that ceiling so they still carry a query semantic embeddings
# miss entirely (e.g. an exact identifier hit semantic ranks low). Config-tunable via
# settings.fusion_weight_* / settings.fusion_rrf_k (app/config.py) so a future sweep doesn't
# need a code change.
DEFAULT_MODE_WEIGHTS = {
    "semantic": 1.0,
    "lexical": 0.5,
    "symbol": 0.4,
}


def _key(item):
    return (item["type"], item["file_id"], item["start_line"], item["end_line"])


def _identity(item):
    return (item["type"], item["result_id"])


def fuse_rankings(mode_result_sets, weights=None, k=DEFAULT_RRF_K, limit=None):
    """Deterministic weighted RRF over `mode_result_sets`, an iterable of (mode, results)
    pairs.

    Each result list is ranked internally by its own score (highest first, `_key` as a
    deterministic tie-break), then every row contributes `weight[mode] / (k + rank)` to its
    fused score. Rows are deduped/merged across lists on identity `(type, result_id)` --  not
    location -- so distinct rows that happen to share a span stay separate, but the same row
    found via multiple retrieval paths accumulates one merged score. A mode missing from
    `weights` defaults to 1.0, which reproduces plain unweighted RRF for callers that don't
    tag modes (e.g. a bare single-list call) or don't care about per-mode trust.

    With a single (mode, results) pair the fused ORDER is identical to unweighted RRF
    regardless of that mode's weight, since multiplying every score by the same positive
    constant never changes relative order -- so single-mode retrieval is unaffected by these
    weights, only hybrid (multi-list) fusion is.
    """
    weights = weights or {}
    combined = {}
    for mode, results in mode_result_sets:
        weight = weights.get(mode, 1.0)
        for rank, item in enumerate(sorted(results, key=lambda x: (-x["score"], _key(x))), 1):
            identity = _identity(item)
            if identity not in combined:
                combined[identity] = dict(item, score=0.0)
            combined[identity]["score"] += weight / (k + rank)
    fused = sorted(combined.values(), key=lambda x: (-x["score"], _key(x)))
    return fused[:limit] if limit is not None else fused
