# Implementation evidence — R.6 Boundary enforcement

- **Packet:** R.6 — Boundary enforcement
- **Implementation commit:** `b4ad2c4f68b1f81e741048d593d9fe6e57a1a39e`
- **Branch:** `packet/R.6-boundary-enforcement`
- **Scope:** Adds import-linter 2.1.0 to the locked development environment, two executable contracts, and the packet verifier.

## Boundary contracts

`pyproject.toml` configures import-linter with `app` as its root package. It rejects dependencies from either `app.domain` or `app.application` to:

1. `app.adapters`; and
2. framework/infrastructure packages: FastAPI, SQLAlchemy/Alembic, tree-sitter, Redis/RQ, OpenAI, psycopg, and pgvector.

`governance/checks/stageR_import_boundary.sh` first checks HEAD, creates a temporary domain module importing an HTTP adapter and requires lint-imports to fail, removes the fixture, and rechecks HEAD. The fixture is removed through an EXIT trap if any command exits early.

## Local gauntlet results

Executed from this packet branch after implementation:

```text
python3 -m compileall -q apps/api/app apps/api/tests apps/mcp        PASS
uv run pytest -q                                                     PASS — 70 passed in 1.85s
FastAPI endpoint tests                                                PASS — included in 70 pytest tests (apps/api/tests)
git diff --check                                                      PASS
governance/checks/stageR_import_boundary.sh                           PASS
```

The R.6 verifier recorded both required observations:

```text
HEAD: 2 import-linter contracts kept, 0 broken.
Deliberate app.domain -> app.adapters.inbound.http.routes fixture: rejected.
HEAD after fixture cleanup: 2 contracts kept, 0 broken.
PASS: R.6 import boundaries reject a deliberate violation and pass on HEAD.
```

No `apps/web` files or UI-facing API contracts were touched, so Playwright is not applicable. This packet makes no retrieval change, so a retrieval scorecard is not applicable. The pytest run emitted 209 pre-existing deprecation warnings (FastAPI `on_event`, `datetime.utcnow`, and tree-sitter); it had no test failures.
