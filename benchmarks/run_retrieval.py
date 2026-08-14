#!/usr/bin/env python3
"""Score Knowledge-Way's live /api/search endpoint against committed gold tasks.

The harness deliberately makes no indexing or embedding calls.  It only measures the
snapshot already served by the API, so a scorecard can be replayed by restoring the
recorded repository snapshots and running the command recorded in its output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

MODES = ("text", "exact", "symbols", "semantic", "hybrid")
ROOT = Path(__file__).resolve().parents[1]


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower), 3)


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_tasks(tasks_dir: Path) -> list[dict[str, Any]]:
    tasks = []
    for path in sorted(tasks_dir.glob("*.json")):
        payload = json.loads(path.read_text())
        if "gold" not in payload or "description" not in payload:
            continue
        payload["_source"] = str(path.relative_to(ROOT))
        tasks.append(payload)
    if not tasks:
        raise ValueError(f"no historical gold tasks found in {tasks_dir}")
    return tasks


def search(base_url: str, query: str, mode: str, limit: int, timeout: float) -> tuple[dict[str, Any], float]:
    url = base_url.rstrip("/") + "/api/search?" + urlencode({"q": query, "mode": mode, "limit": limit})
    started = time.perf_counter()
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:300]}") from exc
    except URLError as exc:
        raise RuntimeError(f"connection error: {exc.reason}") from exc
    return payload, round((time.perf_counter() - started) * 1000, 3)


def normalize_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def rank_metrics(results: list[dict[str, Any]], gold_files: set[str], gold_symbols: set[str]) -> dict[str, Any]:
    file_ranks = [index for index, hit in enumerate(results, 1) if normalize_path(str(hit.get("path", ""))) in gold_files]
    symbol_ranks = [index for index, hit in enumerate(results, 1) if str(hit.get("symbol") or hit.get("qualified_name") or "") in gold_symbols]
    def values(ranks: list[int]) -> dict[str, float | None]:
        first = ranks[0] if ranks else None
        return {"hit_at_1": float(first == 1), "hit_at_5": float(bool(first and first <= 5)), "mrr": round(1 / first, 6) if first else 0.0}
    return {"files": values(file_ranks), "symbols": values(symbol_ranks)}


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for mode in MODES:
        mode_rows = [row for row in rows if row["mode"] == mode]
        available = [row for row in mode_rows if row["status"] == "ok"]
        if not available:
            reason = next((row.get("reason") for row in mode_rows if row.get("reason")), "not run")
            output[mode] = {"status": "unavailable", "reason": reason, "task_count": len(mode_rows)}
            continue
        def mean(key: str, target: str) -> float:
            return round(statistics.fmean(row["metrics"][key][target] for row in available), 6)
        latencies = [row["latency_ms"] for row in available]
        output[mode] = {
            "status": "ok",
            "task_count": len(mode_rows), "scored_task_count": len(available),
            "files": {metric: mean("files", metric) for metric in ("hit_at_1", "hit_at_5", "mrr")},
            "symbols": {metric: mean("symbols", metric) for metric in ("hit_at_1", "hit_at_5", "mrr")},
            "latency_ms": {"p50": percentile(latencies, .5), "p95": percentile(latencies, .95)},
        }
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure live /api/search retrieval quality on committed historical gold tasks.")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000", help="API origin, without /api (default: %(default)s)")
    parser.add_argument("--tasks-dir", type=Path, default=ROOT / "benchmarks/tasks")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmarks/results/current-search-baseline.json")
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 101))
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    tasks = load_tasks(args.tasks_dir)
    rows: list[dict[str, Any]] = []
    semantic_state = "unconfigured"
    for task in tasks:
        gold = task["gold"]
        gold_files = {normalize_path(item["path"]) for item in gold.get("files", [])}
        gold_symbols = {
            symbol if isinstance(symbol, str) else str(symbol.get("qualified_name") or symbol.get("name") or "")
            for symbol in gold.get("symbols", [])
        } - {""}
        for mode in MODES:
            row: dict[str, Any] = {"task_id": task["id"], "task_source": task["_source"], "mode": mode, "query": task["description"], "status": "ok"}
            try:
                payload, latency = search(args.api_base_url, task["description"], mode, args.limit, args.timeout)
                if mode == "semantic":
                    semantic_state = "ready" if payload.get("semantic") is True else "unconfigured"
                    if semantic_state == "unconfigured":
                        row.update(status="unavailable", reason="semantic: unconfigured", latency_ms=latency)
                        rows.append(row)
                        continue
                results = payload.get("results")
                if not isinstance(results, list):
                    raise RuntimeError("response lacks a results list")
                row.update(latency_ms=latency, result_count=len(results), metrics=rank_metrics(results, gold_files, gold_symbols))
            except RuntimeError as exc:
                row.update(status="unavailable", reason=str(exc))
            rows.append(row)
    corpus = json.loads((ROOT / "benchmarks/corpora.json").read_text())
    source_digest = hashlib.sha256("\n".join(sorted(row["task_source"] for row in rows)).encode()).hexdigest()
    scorecard = {
        "schema_version": "1.0", "kind": "knowledge-way-retrieval-scorecard",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness_git_sha": git_sha(), "api_base_url": args.api_base_url,
        "command": "python benchmarks/run_retrieval.py --api-base-url " + args.api_base_url + " --limit " + str(args.limit) + " --output " + str(args.output.relative_to(ROOT) if args.output.is_relative_to(ROOT) else args.output),
        "configuration": {"modes": list(MODES), "limit": args.limit, "timeout_seconds": args.timeout, "active_workspace": corpus["active_workspace"], "task_source_sha256": source_digest},
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(), "embedding_provider": os.environ.get("EMBEDDING_PROVIDER", "unset")},
        "semantic": semantic_state, "task_count": len(tasks), "summary": aggregate(rows), "results": rows,
        "replay_notes": "The endpoint must serve repositories indexed at the revisions in benchmarks/corpora.json. Unavailable modes are intentionally not scored.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scorecard, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "task_count": len(tasks), "semantic": semantic_state, "summary": scorecard["summary"]}, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
