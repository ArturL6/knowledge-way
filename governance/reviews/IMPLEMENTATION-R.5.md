# Implementation evidence — R.5 Hexagon: split main.py

## Scope

- **Packet:** R.5 — Hexagon: split main.py
- **Branch:** `packet/R.5-split-main`
- **Scope implemented:** the FastAPI application composition root is now 32 lines.  All 38 HTTP routes, request models, HTTP-specific data mapping, and endpoint helper functions were extracted to `apps/api/app/adapters/inbound/http/`.
- **Composition root:** `apps/api/app/main.py` now only constructs/configures FastAPI, wires CORS, owns the startup lifecycle, and includes the inbound HTTP router.
- **Compatibility:** endpoint paths, methods, dependency injection (`get_db`), request/response behavior, and startup behavior remain unchanged.  The affected readonly endpoint monkeypatch now targets its actual inbound-adapter dependency.

## Local gauntlet

```text
uv run pytest -q
70 passed, 209 warnings in 1.94s

uv run pytest -q apps/api/tests/test_readonly_api.py apps/api/tests/test_graph_api.py apps/api/tests/test_workspaces_api.py apps/api/tests/test_repository_cards.py
7 passed, 39 warnings in 1.13s

python3 -m compileall -q apps/api/app
(exit 0)

git diff --check
(exit 0)

PYTHONPATH=apps/api uv run python -c "from app.main import app; ..."
38 routes registered; representative endpoints present
```

## Applicability notes

- No static formatter/linter/type checker is configured at this stage; boundary enforcement belongs to R.6.
- No `apps/web` files or UI-facing API contract changed, so Playwright is not applicable.
- This is a behavior-preserving hexagonal restructure and does not touch retrieval, so no retrieval scorecard is required.
- The exact STATUS packet verifier is `pytest -q`; its successful full-suite result is recorded above.
