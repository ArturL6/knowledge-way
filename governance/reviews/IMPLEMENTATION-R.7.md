# Implementation evidence — R.7 Evidence table

## Scope

- **Packet:** R.7 — Evidence table
- **Branch:** `packet/R.7-evidence-table`
- **Tested implementation base:** `42b6b42351e8cbd59365d7dc715324e34cb63927`
- **Scope implemented:** adds the `evidence` persistence model and Alembic revision `20260813_0010`; adds a mandatory `symbol_edges.evidence_id` foreign key with `RESTRICT` deletion; deterministically backfills one immutable legacy-evidence row per existing edge from its `source_file_id` and `line_number`; and creates parser-derived, line-bounded tree-sitter evidence before every new symbol edge.
- **Enforcement:** `SymbolEdge.evidence_id` is non-nullable at the ORM/schema boundary. The dedicated graph test confirms SQLite rejects an attempted edge without evidence. The migration creates/backfills `evidence_id`, makes it non-null, and then installs the PostgreSQL FK.
- **Snapshot/provenance:** new parser evidence carries its repository, indexed commit SHA, source path, exact start/end line, extractor (`tree-sitter`), parser version, and SHA-256 content hash. Legacy backfill preserves the old file snapshot/path and marks extraction as `legacy-backfill`/`R.7`.

## Local gauntlet results

Executed from `packet/R.7-evidence-table` after implementation:

```text
python3 -m compileall -q apps/api/app apps/api/tests apps/mcp                 PASS
uv run pytest -q                                                              PASS — 72 passed in 1.85s
FastAPI endpoint tests                                                        N/A — no endpoint or HTTP contract changed
PYTHONPATH=apps/api uv run lint-imports                                       PASS — 2 kept, 0 broken
governance/checks/stageR_import_boundary.sh                                  PASS — deliberate violation rejected; HEAD passes
governance/checks/stageR_evidence.sh                                         PASS — 11 targeted tests passed; model contract passed
git diff --check                                                              PASS
```

The full suite and targeted verifier emitted only existing deprecation warnings (FastAPI startup events, `datetime.utcnow`, and tree-sitter language bindings); neither had failures.

`ruff`, `mypy`, and `pyright` are not configured or installed in the locked project development environment, so their binaries could not be spawned. Import-linter is the configured static boundary checker and passed. No `apps/web` files or UI-facing contract changed, so Playwright is not applicable. R.7 does not alter retrieval behavior, so a retrieval scorecard is not applicable.
