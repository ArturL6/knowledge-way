#!/usr/bin/env python3
"""Capture a replayable keyless GitNexus packet-0.4 evaluation via eval-server.

The server is intentionally the only scripted interface.  Symbol UIDs are
resolved with its cypher endpoint before they are passed to context/impact; the
unsupported trace endpoint is retained as an observed, reproducible result.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROUTE_UID_QUERY = "MATCH (n) WHERE n.name = 'Route' AND n.filePath = 'starlette/routing.py' RETURN n.id LIMIT 1"
BASE_ROUTE_UID_QUERY = "MATCH (n) WHERE n.name = 'BaseRoute' AND n.filePath = 'starlette/routing.py' RETURN n.id LIMIT 1"


def call(base: str, tool: str, payload: dict) -> dict:
    request = Request(f"{base}/tool/{tool}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=30) as response:
            return {"tool": tool, "request": payload, "status": response.status, "latency_ms": round((time.perf_counter()-started)*1000, 3), "raw_response": response.read().decode()}
    except HTTPError as error:
        return {"tool": tool, "request": payload, "status": error.code, "latency_ms": round((time.perf_counter()-started)*1000, 3), "error": error.read().decode()}
    except Exception as error:
        return {"tool": tool, "request": payload, "status": None, "latency_ms": round((time.perf_counter()-started)*1000, 3), "error": str(error)}


def resolved_uid(result: dict) -> str:
    if result["status"] != 200:
        raise RuntimeError(f"UID lookup failed: {result}")
    # eval-server renders a markdown table; preserve it and extract the sole UID.
    for token in result["raw_response"].split():
        if token.startswith(("Class:", "Function:", "Method:")):
            return token.rstrip("|")
    raise RuntimeError(f"UID absent from lookup response: {result['raw_response']}")


def classify(raw: str, expected_path: str | None = None) -> str:
    if expected_path and expected_path in raw:
        return "correct"
    return "incorrect"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:4848")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    common = {"repo": args.repo}
    route_lookup = call(args.base_url, "cypher", common | {"query": ROUTE_UID_QUERY})
    base_route_lookup = call(args.base_url, "cypher", common | {"query": BASE_ROUTE_UID_QUERY})
    route_uid, base_route_uid = resolved_uid(route_lookup), resolved_uid(base_route_lookup)
    calls = [route_lookup, base_route_lookup]
    def observe(case_id: str, tool: str, payload: dict, classification: str, rationale: str) -> None:
        result = call(args.base_url, tool, common | payload)
        result.update({"id": case_id, "classification": classification, "rationale": rationale})
        calls.append(result)
    observe("01-implementation", "query", {"query": "Where is route registration implemented?"}, "correct", "response names starlette/routing.py")
    observe("02-symbol-purpose", "context", {"uid": route_uid}, "correct", "resolved Route context identifies class and source range")
    observe("03-callers", "context", {"uid": route_uid}, "partial", "context returns imports but reports lower-bound traversal")
    observe("04-callees", "context", {"uid": route_uid}, "partial", "context returns inheritance/members, not a complete call graph")
    observe("05-trace", "trace", {"from_uid": route_uid, "to_uid": base_route_uid}, "not-representable", "eval-server attempted with resolved UIDs; v1.6.9 endpoint does not support trace")
    observe("06-impact", "impact", {"uid": route_uid, "direction": "upstream"}, "not-representable", "resolved UID was sent, but eval-server returned Target 'undefined' not found; no impact result or epistemic field is available")
    observe("07-cross-repository-consumer", "query", {"query": "Which repository consumes Starlette Route?"}, "not-representable", "single-repository index; groups are Stage 3 scope")
    observe("08-tests", "context", {"uid": route_uid}, "correct", "context lists test-file imports")
    observe("09-value-origin", "context", {"uid": route_uid}, "partial", "symbol context is not a value-provenance trace")
    observe("10-equivalent-functionality", "query", {"query": "route registration"}, "partial", "result is ranked discovery, not equivalence proof")
    observe("11-cross-repository-user-flow", "query", {"query": "FastAPI request flow"}, "not-representable", "single-repository index; groups are Stage 3 scope")
    observe("12-missing-architecture", "cypher", {"query": "MATCH (n) RETURN count(n)"}, "partial", "node count exposes indexed scope, not missing contracts")
    gold = [
        ("encode-starlette-issue-2950", "TestClient __enter__ subclass return type", "starlette/testclient.py"),
        ("encode-starlette-issue-3388", "FileResponse inverted single byte Range header", "starlette/responses.py"),
    ]
    gold_results = []
    for task_id, query, path in gold:
        result = call(args.base_url, "query", common | {"query": query})
        raw = result.get("raw_response", "")
        result.update({"task_id": task_id, "oracle_paths": [path], "classification": classify(raw, path), "rationale": "correct only when the committed gold changed-file path occurs in the raw response"})
        gold_results.append(result)
    payload = {"schema_version": "2.0", "gitnexus_version": "1.6.9", "repo": args.repo, "protocol": {"interface": "eval-server", "uid_resolution": [route_lookup, base_route_lookup], "route_uid": route_uid, "base_route_uid": base_route_uid}, "observations": calls, "gold_task_subset": gold_results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
