"""Packet 1.5: weighted RRF fusion (app/domain/retrieval.py) is a pure function -- these
tests construct synthetic ranked lists directly, no DB, no embeddings."""

from app.domain.retrieval import DEFAULT_MODE_WEIGHTS, DEFAULT_RRF_K, fuse_rankings


def _row(result_id, score, file_id="f", start_line=1, end_line=2, kind="chunk"):
    return {"type": kind, "result_id": result_id, "file_id": file_id,
            "start_line": start_line, "end_line": end_line, "score": score}


# --- the core dilution fix --------------------------------------------------

def test_semantic_rank1_beats_junk_agreed_on_by_two_weak_modes():
    """The measured bug: a gold row semantic ranks #1 (and no other mode recalls at all) must
    beat a junk row that lexical AND symbol both rank #1 -- under equal-weight RRF the junk
    row's two contributions (1/61 + 1/61 = 0.0328) outscored semantic's one (1/61 = 0.0164)."""
    gold = _row("gold", score=0.9)
    junk_a = _row("junkA", score=0.9)
    junk_b = _row("junkB", score=0.5)

    fused = fuse_rankings(
        [("lexical", [junk_a, junk_b]), ("symbol", [junk_a]), ("semantic", [gold])],
        weights=DEFAULT_MODE_WEIGHTS, k=DEFAULT_RRF_K,
    )

    assert fused[0]["result_id"] == "gold"


def test_equal_weight_rrf_would_have_failed_this_case():
    """Sanity check that the scenario above is a real dilution case, not a strawman: with
    weight 1.0 for every mode (old behavior), junk actually wins."""
    gold = _row("gold", score=0.9)
    junk_a = _row("junkA", score=0.9)
    junk_b = _row("junkB", score=0.5)

    fused = fuse_rankings(
        [("lexical", [junk_a, junk_b]), ("symbol", [junk_a]), ("semantic", [gold])],
        weights={"lexical": 1.0, "symbol": 1.0, "semantic": 1.0}, k=60,
    )

    assert fused[0]["result_id"] == "junkA"


# --- hybrid >= best single mode ---------------------------------------------
#
# NOTE on scope: with semantic weighted above lexical/symbol (by design -- see
# DEFAULT_MODE_WEIGHTS), a gold row found *only* by semantic is protected from being outranked
# by a solitary junk row in either weaker mode (tested below), which is the direction the
# measured bug (hybrid hit@5 < semantic-alone hit@5) actually requires. The converse -- a gold
# row found only by lexical or symbol outranking a solitary *semantic* junk row -- is not and
# cannot be guaranteed by any per-mode-weight scheme that also fixes the measured bug: trusting
# semantic more necessarily means a real semantic hit (even an irrelevant one) can outscore a
# lone weaker-mode hit. That asymmetry is intentional, not an oversight.

def test_semantic_only_gold_survives_one_non_colluding_junk_row_per_weaker_mode():
    """The direction the measured bug requires: a gold row semantic alone ranks #1 must stay
    #1 even when lexical and symbol each (independently, not colluding on the same identity)
    rank some other row #1."""
    gold = _row("gold", score=0.9)
    junk_lexical = _row("junk-lexical", score=0.9)
    junk_symbol = _row("junk-symbol", score=0.9)

    fused = fuse_rankings(
        [("semantic", [gold]), ("lexical", [junk_lexical]), ("symbol", [junk_symbol])],
        weights=DEFAULT_MODE_WEIGHTS, k=DEFAULT_RRF_K,
    )

    assert fused[0]["result_id"] == "gold"


# --- single-mode fusion is unaffected by weights ----------------------------

def test_single_mode_order_is_identical_regardless_of_weight():
    rows = [_row("a", score=0.9), _row("b", score=0.5), _row("c", score=0.1)]
    unweighted = [r["result_id"] for r in fuse_rankings([("lexical", rows)])]
    heavily_weighted = [r["result_id"] for r in fuse_rankings([("lexical", rows)], weights={"lexical": 0.01})]
    assert unweighted == heavily_weighted == ["a", "b", "c"]


def test_exact_lexical_match_still_ranks_first_in_single_mode():
    """Exact substring matches get score=1.0 from app.search.result(); that must still put
    them at rank 1 within their own list regardless of the lexical mode weight."""
    exact = _row("exact-hit", score=1.0)
    fuzzy = _row("fuzzy-hit", score=0.6)
    fused = fuse_rankings([("lexical", [fuzzy, exact])], weights=DEFAULT_MODE_WEIGHTS)
    assert fused[0]["result_id"] == "exact-hit"


# --- dedupe / merge on identity, not location -------------------------------

def test_dedupe_merges_same_identity_across_modes_with_weighted_sum():
    lexical_hit = _row("row-a", score=1.0)
    semantic_hit = _row("row-a", score=0.6)
    fused = fuse_rankings(
        [("lexical", [lexical_hit]), ("semantic", [semantic_hit])],
        weights=DEFAULT_MODE_WEIGHTS, k=DEFAULT_RRF_K,
    )
    assert len(fused) == 1
    assert fused[0]["result_id"] == "row-a"
    expected = DEFAULT_MODE_WEIGHTS["lexical"] / 61 + DEFAULT_MODE_WEIGHTS["semantic"] / 61
    assert fused[0]["score"] == expected


def test_distinct_rows_at_the_same_location_stay_separate():
    first = _row("row-a", score=0.9)
    second = _row("row-b", score=0.5)
    third = _row("row-c", score=0.1)
    fused = fuse_rankings([("lexical", [first, second, third])])
    assert {item["result_id"] for item in fused} == {"row-a", "row-b", "row-c"}


def test_unknown_mode_defaults_to_weight_one():
    row = _row("a", score=0.9)
    fused = fuse_rankings([("some_future_mode", [row])], weights=DEFAULT_MODE_WEIGHTS, k=60)
    assert fused[0]["score"] == 1.0 / 61


# --- determinism -------------------------------------------------------------

def test_ties_break_deterministically_on_key():
    # Two different rows, same fused score (equal per-list rank contribution), different
    # locations -- the winner must be picked by _key, and it must be stable across repeats.
    early = _row("a", score=0.9, file_id="f", start_line=1, end_line=2)
    late = _row("b", score=0.9, file_id="z", start_line=1, end_line=2)
    runs = [[item["result_id"] for item in fuse_rankings([("lexical", [early, late])])] for _ in range(5)]
    assert all(run == runs[0] for run in runs)
    assert runs[0] == ["a", "b"]  # "f" < "z" lexicographically


def test_limit_truncates_after_fusion():
    rows = [_row(str(i), score=1.0 - i * 0.01) for i in range(10)]
    fused = fuse_rankings([("lexical", rows)], limit=3)
    assert len(fused) == 3
    assert [r["result_id"] for r in fused] == ["0", "1", "2"]
