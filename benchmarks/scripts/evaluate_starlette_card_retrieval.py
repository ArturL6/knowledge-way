#!/usr/bin/env python3
"""Run a provenance-rich Starlette retrieval evaluation through the live API.

The evaluator records separate ranks for the expected implementation definition
and any chunk from the expected source file.  It never calls a provider itself;
semantic and hybrid requests are delegated to the configured API.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

MODES = ("text", "symbols", "semantic", "hybrid")


def rank_of(results: list[dict], expected: dict, predicate) -> int | None:
    for rank, hit in enumerate(results, 1):
        if predicate(hit, expected):
            return rank
    return None


def first_definition_rank(results: list[dict], expected: dict) -> int | None:
    return rank_of(
        results,
        expected,
        lambda hit, exp: hit.get("path") == exp["path"] and hit.get("symbol") == exp["symbol"],
    )


def first_source_rank(results: list[dict], expected: dict) -> int | None:
    return rank_of(results, expected, lambda hit, exp: hit.get("path") == exp["path"])


def reciprocal_rank(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / rank


def run_case(api_base_url: str, repository_id: str, case: dict, mode: str, limit: int) -> dict:
    params = {"q": case["query"], "mode": mode, "limit": limit, "repository_id": repository_id}
    started = time.monotonic()
    with urlopen(api_base_url.rstrip("/") + "/api/search?" + urlencode(params), timeout=60) as response:
        payload = json.load(response)
    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
    results = payload["results"]
    definition_rank = first_definition_rank(results, case["expected"])
    source_rank = first_source_rank(results, case["expected"])
    return {
        "id": case["id"],
        "query": case["query"],
        "intent": case["intent"],
        "mode": mode,
        "expected": case["expected"],
        "definition_rank": definition_rank,
        "definition_rr": reciprocal_rank(definition_rank),
        "source_rank": source_rank,
        "source_rr": reciprocal_rank(source_rank),
        "latency_ms": elapsed_ms,
        "result_count": len(results),
        "semantic_capability": payload.get("semantic"),
        "top_results": [
            {key: item.get(key) for key in ("type", "score", "path", "symbol", "start_line", "end_line")}
            for item in results[:5]
        ],
    }


def aggregate(rows: list[dict]) -> dict:
    count = len(rows)
    definitions = [row["definition_rr"] for row in rows]
    sources = [row["source_rr"] for row in rows]
    latencies = sorted(row["latency_ms"] for row in rows)
    return {
        "cases": count,
        "definition_recall_at_10": sum(row["definition_rank"] is not None and row["definition_rank"] <= 10 for row in rows) / count if count else 0.0,
        "definition_mrr": sum(definitions) / count if count else 0.0,
        "source_recall_at_10": sum(row["source_rank"] is not None and row["source_rank"] <= 10 for row in rows) / count if count else 0.0,
        "source_mrr": sum(sources) / count if count else 0.0,
        "median_latency_ms": statistics.median(latencies) if count else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "starlette-card-retrieval-cases.json",
    )
    parser.add_argument("--phase", choices=("baseline", "card_enriched"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=10, choices=(10,))
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite output: {args.output}")

    manifest = json.loads(args.cases.read_text())
    repository = manifest["repository"]
    with urlopen(args.api_base_url.rstrip("/") + f"/api/repositories/{repository['id']}", timeout=30) as response:
        observed_repository = json.load(response)
    if observed_repository.get("indexed_commit_sha") != repository["indexed_commit_sha"]:
        raise SystemExit("live repository commit does not match the pinned benchmark manifest")
    if observed_repository.get("indexing_status") != "ready":
        raise SystemExit("live repository is not ready for a retrieval evaluation")
    rows = []
    by_mode = {}
    for mode in MODES:
        mode_rows = []
        for case in manifest["cases"]:
            row = run_case(args.api_base_url, repository["id"], case, mode, args.limit)
            print(json.dumps({key: row[key] for key in ("id", "mode", "definition_rank", "source_rank", "latency_ms")}), flush=True)
            rows.append(row)
            mode_rows.append(row)
        by_mode[mode] = aggregate(mode_rows)

    artifact = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": args.phase,
        "repository": repository,
        "observed_repository": observed_repository,
        "cases_file": str(args.cases),
        "limit": args.limit,
        "modes": list(MODES),
        "summary": by_mode,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "summary": by_mode}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
