#!/usr/bin/env python3
"""Offline validator for packet 0.2 provenance-backed gold task records."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS = ROOT / "tasks"
SHA = re.compile(r"^[0-9a-f]{40}$")
ISSUE_URL = re.compile(r"^https://github\.com/[^/]+/(starlette|pydantic)/issues/\d+$")
PR_URL = re.compile(r"^https://github\.com/[^/]+/(starlette|pydantic)/pull/\d+$")

def fail(message: str) -> None:
    raise ValueError(message)

def main() -> int:
    try:
        paths = sorted(TASKS.glob("*.json"))
        if not 25 <= len(paths) <= 40:
            fail(f"expected 25–40 task records, found {len(paths)}")
        ids: set[str] = set()
        for path in paths:
            record = json.loads(path.read_text())
            task_id = record.get("id")
            if not isinstance(task_id, str) or task_id in ids:
                fail(f"{path.name}: missing or duplicate id")
            ids.add(task_id)
            if not isinstance(record.get("description"), str) or not record["description"].strip():
                fail(f"{path.name}: issue-text description is required")
            issue = record.get("source_issue", {})
            pr = record.get("fix_pr", {})
            if not isinstance(issue.get("number"), int) or not ISSUE_URL.match(issue.get("url", "")):
                fail(f"{path.name}: invalid source issue provenance")
            if not isinstance(pr.get("number"), int) or not PR_URL.match(pr.get("url", "")):
                fail(f"{path.name}: invalid fix PR provenance")
            if not SHA.match(pr.get("merge_commit_sha", "")) or not SHA.match(pr.get("head_sha", "")):
                fail(f"{path.name}: fix PR must retain 40-character commit traceability")
            gold = record.get("gold", {})
            files = gold.get("files")
            if not isinstance(files, list) or not files or not all(isinstance(item.get("path"), str) and item["path"] for item in files):
                fail(f"{path.name}: mechanically derived changed files are required")
            file_paths = {item["path"] for item in files}
            if not isinstance(gold.get("tests"), list) or not set(gold["tests"]).issubset(file_paths):
                fail(f"{path.name}: gold tests must be a subset of changed PR files")
            if not isinstance(gold.get("symbols"), list) or any(symbol.get("path") not in file_paths or not symbol.get("symbol") for symbol in gold["symbols"]):
                fail(f"{path.name}: invalid mechanically derived symbols")
            if "GitHub merged-PR file-list" not in gold.get("derivation", ""):
                fail(f"{path.name}: missing mechanical-derivation statement")
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1
    print(f"VALID: {len(paths)} provenance-backed gold tasks")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
