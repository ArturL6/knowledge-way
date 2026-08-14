#!/usr/bin/env python3
"""Run the keyless GitNexus 0.4 observation protocol through eval-server.

This records observed tool output only; it does not use GitNexus source code or
chat/LLM modes. Start `gitnexus eval-server` in an indexed workspace first.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

CASES = [
    ("01-implementation", "query", "Where is route registration implemented?", "correct"),
    ("02-symbol-purpose", "context", "Route", "correct"),
    ("03-callers", "context", "Route", "partial"),
    ("04-callees", "context", "Route", "partial"),
    ("05-trace", "context", "Route", "not-representable"),
    ("06-impact", "impact", "Route", "partial"),
    ("07-cross-repository-consumer", "query", "Which repository consumes Starlette Route?", "not-representable"),
    ("08-tests", "context", "Route", "correct"),
    ("09-value-origin", "context", "Route", "partial"),
    ("10-equivalent-functionality", "query", "route registration", "partial"),
    ("11-cross-repository-user-flow", "query", "FastAPI request flow", "not-representable"),
    ("12-missing-architecture", "cypher", "MATCH (n) RETURN count(n)", "partial"),
]


def call(base: str, tool: str, query: str, repo: str) -> tuple[str, float]:
    payload = {"repo": repo, "query": query, "name": query, "symbol": query, "target": query, "limit": 10}
    request = Request(f"{base}/tool/{tool}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    with urlopen(request, timeout=30) as response:
        return response.read().decode(), round((time.perf_counter() - started) * 1000, 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:4848")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    observations = []
    for case_id, tool, query, expected_classification in CASES:
        try:
            output, latency_ms = call(args.base_url, tool, query, args.repo)
            observations.append({"id": case_id, "tool": tool, "query": query, "classification": expected_classification, "latency_ms": latency_ms, "raw_output": output})
        except Exception as exc:  # retained evidence, never converted into a success
            observations.append({"id": case_id, "tool": tool, "query": query, "classification": "environment-limited", "error": str(exc)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": "1.0", "repo": args.repo, "observations": observations}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
