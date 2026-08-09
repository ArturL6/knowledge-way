#!/usr/bin/env python3
"""Verify small, commit-pinned evidence checks through the live search API."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "real-indexed-query-cases.json",
    )
    args = parser.parse_args()
    payload = json.loads(args.cases.read_text())
    base = args.api_base_url.rstrip("/") + "/api/search?"
    failures = []

    for case in payload["cases"]:
        url = base + urlencode({"q": case["query"], "mode": case["mode"], "limit": 10})
        with urlopen(url, timeout=30) as response:
            result = json.load(response)
        expected = case["expected"]
        hits = result["results"]
        found = any(all(hit.get(key) == value for key, value in expected.items()) for hit in hits)
        print(json.dumps({"id": case["id"], "pass": found, "result_count": len(hits), "top_hit": hits[0] if hits else None}))
        if not found:
            failures.append(case["id"])

    if failures:
        print("FAILED: " + ", ".join(failures))
        return 1
    print(f"PASS: {len(payload['cases'])} live query cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
