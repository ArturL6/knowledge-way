# Implementation evidence — R.5 Hexagon: split main.py

## Scope

- **Packet:** R.5 — Hexagon: split main.py
- **Branch:** `packet/R.5-split-main`
- **Tested implementation SHA:** `7fce9f7ca8a41490c8015f8890f99d43640ae811` (`refactor(R.5): split FastAPI routes from main`).
- **Evidence basis:** the implementation commit changes only the extracted inbound HTTP router/dependencies, `main.py`, the affected readonly API test, this artifact, and the initial `in_progress` STATUS signal. The succeeding commits before this replacement are explicitly non-implementation commits: `22301f2e98e765990e581ca10a43c13fa29189c9` changes only STATUS to the former `pr_open` signal; `f47c213c98919bf2fb34a0686213220f6ded0a00` changes only STATUS and the append-only reviewer verdict. This replacement evidence commit and its STATUS re-signal likewise make no application or test-code changes.
- **Scope implemented:** the FastAPI application composition root is now 32 lines.  All 38 HTTP routes, request models, HTTP-specific data mapping, and endpoint helper functions were extracted to `apps/api/app/adapters/inbound/http/`.
- **Composition root:** `apps/api/app/main.py` now only constructs/configures FastAPI, wires CORS, owns the startup lifecycle, and includes the inbound HTTP router.
- **Compatibility:** endpoint paths, methods, dependency injection (`get_db`), request/response behavior, and startup behavior remain unchanged.  The affected readonly endpoint monkeypatch now targets its actual inbound-adapter dependency.

## Local gauntlet

```text
uv run pytest -q
70 passed, 209 warnings in 1.90s

uv run pytest -q apps/api/tests/test_readonly_api.py apps/api/tests/test_graph_api.py apps/api/tests/test_workspaces_api.py apps/api/tests/test_repository_cards.py
7 passed, 39 warnings in 1.25s

python3 -m compileall -q apps/api/app
(exit 0)

git diff --check
(exit 0)

PYTHONPATH=apps/api uv run python -c "from app.main import app; ..."
47 FastAPI route objects; 51 method/path registrations; representative endpoints present
```

## Applicability notes

- No static formatter/linter/type checker is configured at this stage; boundary enforcement belongs to R.6.
- No `apps/web` files or UI-facing API contract changed, so Playwright is not applicable.
- This is a behavior-preserving hexagonal restructure and does not touch retrieval, so no retrieval scorecard is required.
- The exact STATUS packet verifier is `pytest -q`; its successful full-suite result is recorded above.
