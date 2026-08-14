#!/usr/bin/env python3
"""Run a snapshot-bound retrieval scorecard against a live Knowledge-Way API."""
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


class HarnessError(RuntimeError):
    """A baseline cannot be trusted or reproduced."""


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower), 3)


def request(base: str, path: str, timeout: float) -> tuple[Any, float]:
    started = time.perf_counter()
    try:
        with urlopen(base.rstrip("/") + path, timeout=timeout) as response:
            return json.load(response), round((time.perf_counter() - started) * 1000, 3)
    except HTTPError as exc:
        raise HarnessError(f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:300]}") from exc
    except (URLError, OSError) as exc:
        raise HarnessError(f"connection error: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise HarnessError(f"invalid JSON response: {exc}") from exc


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
        payload["_content_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        tasks.append(payload)
    if not tasks:
        raise HarnessError(f"no historical gold tasks found in {tasks_dir}")
    return tasks


def task_digest(tasks: list[dict[str, Any]]) -> str:
    """Hash task identities and content, not merely their paths."""
    material = "\n".join(
        f"{task['id']}\0{task['_source']}\0{task['_content_sha256']}" for task in tasks
    )
    return hashlib.sha256(material.encode()).hexdigest()


def expected_manifest(corpus: dict[str, Any]) -> list[dict[str, str]]:
    active = next(
        (item for item in corpus["corpora"] if item["id"] == corpus["active_workspace"]),
        None,
    )
    if not active:
        raise HarnessError("active workspace absent from corpora.json")
    return [
        {key: member[key] for key in ("id", "source_url", "resolved_sha")}
        for member in active["members"]
    ]


def capture_manifest(base: str, corpus: dict[str, Any], timeout: float) -> list[dict[str, str]]:
    served, _ = request(base, "/api/repositories", timeout)
    if not isinstance(served, list):
        raise HarnessError("repository manifest response is not a list")
    manifest = []
    for expected in expected_manifest(corpus):
        matches = [repo for repo in served if repo.get("name") == expected["id"]]
        if len(matches) != 1:
            raise HarnessError(f"expected exactly one served repository named {expected['id']}")
        repo = matches[0]
        got_url = str(repo.get("clone_url", "")).removesuffix(".git")
        want_url = expected["source_url"].removesuffix(".git")
        got_sha = repo.get("indexed_commit_sha")
        if got_url != want_url or got_sha != expected["resolved_sha"]:
            raise HarnessError(
                f"snapshot mismatch for {expected['id']}: expected "
                f"{want_url}@{expected['resolved_sha']}, got {got_url}@{got_sha}"
            )
        manifest.append(
            {
                "id": expected["id"],
                "repository_id": str(repo["id"]),
                "source_url": expected["source_url"],
                "indexed_commit_sha": expected["resolved_sha"],
            }
        )
    return manifest


def normalize_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def rank_metrics(
    results: list[dict[str, Any]], gold_files: set[str], gold_symbols: set[str]
) -> dict[str, Any]:
    def values(ranks: list[int]) -> dict[str, float]:
        first = ranks[0] if ranks else None
        return {
            "hit_at_1": float(first == 1),
            "hit_at_5": float(bool(first and first <= 5)),
            "mrr": round(1 / first, 6) if first else 0.0,
        }

    files = [
        index
        for index, hit in enumerate(results, 1)
        if normalize_path(str(hit.get("path", ""))) in gold_files
    ]
    symbols = [
        index
        for index, hit in enumerate(results, 1)
        if str(hit.get("symbol") or hit.get("qualified_name") or "") in gold_symbols
    ]
    return {"files": values(files), "symbols": values(symbols)}


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for mode in MODES:
        mode_rows = [row for row in rows if row["mode"] == mode]
        available = [row for row in mode_rows if row["status"] == "ok"]
        if not available:
            output[mode] = {
                "status": "unavailable",
                "reason": mode_rows[0].get("reason", "not run") if mode_rows else "not run",
                "task_count": len(mode_rows),
            }
            continue
        if len(available) != len(mode_rows):
            raise HarnessError(f"incomplete {mode} coverage")

        def mean(group: str, metric: str) -> float:
            return round(statistics.fmean(row["metrics"][group][metric] for row in available), 6)

        latencies = [row["latency_ms"] for row in available]
        output[mode] = {
            "status": "ok",
            "task_count": len(mode_rows),
            "scored_task_count": len(available),
            "files": {metric: mean("files", metric) for metric in ("hit_at_1", "hit_at_5", "mrr")},
            "symbols": {metric: mean("symbols", metric) for metric in ("hit_at_1", "hit_at_5", "mrr")},
            "latency_ms": {"p50": percentile(latencies, 0.5), "p95": percentile(latencies, 0.95)},
        }
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure snapshot-bound live /api/search retrieval quality.")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--tasks-dir", type=Path, default=ROOT / "benchmarks/tasks")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmarks/results/current-search-baseline.json")
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 101))
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    corpus = json.loads((ROOT / "benchmarks/corpora.json").read_text())
    tasks = load_tasks(args.tasks_dir)
    manifest = capture_manifest(args.api_base_url, corpus, args.timeout)
    rows = []
    semantic = "unconfigured"
    for task in tasks:
        gold = task["gold"]
        files = {normalize_path(item["path"]) for item in gold.get("files", [])}
        symbols = {
            symbol if isinstance(symbol, str) else str(symbol.get("qualified_name") or symbol.get("name") or "")
            for symbol in gold.get("symbols", [])
        } - {""}
        for mode in MODES:
            payload, latency = request(
                args.api_base_url,
                "/api/search?" + urlencode({"q": task["description"], "mode": mode, "limit": args.limit}),
                args.timeout,
            )
            if mode == "semantic" and payload.get("semantic") is not True:
                rows.append({"task_id": task["id"], "task_source": task["_source"], "mode": mode, "status": "unavailable", "reason": "semantic: unconfigured", "latency_ms": latency})
                continue
            if not isinstance(payload.get("results"), list):
                raise HarnessError(f"{mode}/{task['id']}: response lacks results list")
            if mode == "semantic":
                semantic = "ready"
            rows.append({"task_id": task["id"], "task_source": task["_source"], "mode": mode, "status": "ok", "latency_ms": latency, "result_count": len(payload["results"]), "metrics": rank_metrics(payload["results"], files, symbols)})

    scorecard = {
        "schema_version": "1.1",
        "kind": "knowledge-way-retrieval-scorecard",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness_git_sha": git_sha(),
        "api_base_url": args.api_base_url,
        "command": f"python benchmarks/run_retrieval.py --api-base-url {args.api_base_url} --limit {args.limit} --output {args.output}",
        "configuration": {"modes": list(MODES), "limit": args.limit, "timeout_seconds": args.timeout, "active_workspace": corpus["active_workspace"], "task_content_sha256": task_digest(tasks), "task_set": [{"id": task["id"], "source": task["_source"], "sha256": task["_content_sha256"]} for task in tasks]},
        "served_snapshot_manifest": manifest,
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(), "embedding_provider": os.environ.get("EMBEDDING_PROVIDER", "unset")},
        "semantic": semantic,
        "task_count": len(tasks),
        "summary": aggregate(rows),
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scorecard, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "task_count": len(tasks), "semantic": semantic, "summary": scorecard["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HarnessError as error:
        print(f"run_retrieval: {error}", file=sys.stderr)
        raise SystemExit(1)
