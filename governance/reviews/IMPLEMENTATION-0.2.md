# Packet 0.2 implementation evidence

**Verified implementation head:** `6a14371557577dbbc3b8521651d607045e81965a` (`feat(0.2): add provenance-backed gold tasks`). The succeeding handoff commit changes only packet state, this evidence, and the append-only RUNLOG; it does not alter task records, the validator, application behavior, dependencies, or infrastructure.

## Delivered scope

- 25 records under `benchmarks/tasks/`: 12 Starlette and 13 Pydantic closed issues, each with the unaltered issue-body description, source issue URL/number, merged fix-PR URL/number, PR head and merge-commit SHAs, and GitHub file-list provenance.
- Gold files are the merged PR's changed-file entries; gold tests are the mechanically selected changed test paths; gold symbols are added Python `def`/`class` definitions found in the PR patch. The record states this derivation, including intentionally empty symbol/test lists when applicable.
- `benchmarks/validate_tasks.py` is an offline authoritative validator for record count, unique IDs, issue/PR provenance, 40-character commit traceability, changed-file derivation, and tests/symbols being derived from the changed-file set.
- No product LLM, embedding, card, rerank, retrieval, application, infrastructure, or PostHog work was performed. Estimated cumulative product LLM spend remains USD 0.00.

## Exact implementation-head verification

Executed from the repository root:

```text
$ python benchmarks/validate_tasks.py
VALID: 25 provenance-backed gold tasks
$ python benchmarks/scripts/validate.py
VALID
$ python -m unittest discover -s benchmarks/tests -v
Ran 4 tests in 0.233s
OK
$ uv sync --frozen --extra dev
success
$ uv run pytest -q
95 passed, 284 warnings in 2.28s
$ PYTHONPATH=apps/api uv run lint-imports
Contracts: 2 kept, 0 broken.
$ git diff --check
success
```

The task packet has no web, API-contract, retrieval, or LLM/embedding change; therefore Playwright, endpoint-specific smoke, scorecard, and HD-003 subset execution are not applicable.