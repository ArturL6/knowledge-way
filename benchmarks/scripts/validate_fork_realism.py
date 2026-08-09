#!/usr/bin/env python3
"""Validate the checked-in, commit-pinned fork-realism oracle without network access."""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[0-9a-f]{40}$")


def fail(message: str) -> None:
    raise ValueError(message)


def main() -> int:
    try:
        data = json.loads((ROOT / "fork_realism.json").read_text())
        if data.get("schema_version") != "1.0" or data.get("track") != "fork_realism":
            fail("unsupported realism manifest")
        repositories = data.get("repositories", [])
        ids = [repository.get("id") for repository in repositories]
        if len(ids) != 3 or len(set(ids)) != len(ids) or set(ids) != {"pydantic", "fastapi", "starlette"}:
            fail("expected exactly pydantic, fastapi, and starlette")
        for repository in repositories:
            if not all(repository.get(field) for field in ("url", "upstream", "baseline", "head")):
                fail(f"incomplete repository: {repository.get('id')}")
            if not SHA.match(repository["baseline"]) or not SHA.match(repository["head"]):
                fail(f"un-pinned commit in {repository['id']}")
        scenarios = {scenario.get("id"): scenario for scenario in data.get("scenarios", [])}
        if set(scenarios) != {"initial-baseline", "remove-v1-contract-entrypoint"}:
            fail("unexpected scenario set")
        incremental = scenarios["remove-v1-contract-entrypoint"]
        if incremental.get("changed_repositories") != ["pydantic"]:
            fail("incremental scenario must change only pydantic")
        if set(incremental.get("expected_invalidated_repositories", [])) != {"pydantic", "fastapi", "starlette"}:
            fail("incremental invalidation oracle is incomplete")
        query_ids = [query.get("id") for scenario in scenarios.values() for query in scenario.get("queries", [])]
        if len(query_ids) != len(set(query_ids)) or not all(query_ids):
            fail("query ids must be present and unique")
        removed = next(query for query in incremental["queries"] if query["id"] == "removed-symbol-is-stale-free")
        if removed.get("expected_symbols") != [] or not removed.get("forbidden_symbols"):
            fail("removal scenario must require stale-fact absence")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
