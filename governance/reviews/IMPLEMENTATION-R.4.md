# Implementation evidence — R.4 Hexagon: extract ports and move adapters

## Scope

- Added the Stage R target package layout for `domain`, `application/ports`, and inbound/outbound adapters.
- Defined the eight runtime-checkable application port Protocols: `RepoStore`, `SourceControl`, `LexicalSearch`, `VectorSearch`, `CodeParser`, `LLM`, `Embeddings`, and `JobQueue`.
- Moved the PostgreSQL (`models.py`, `db.py`), tree-sitter, LLM-provider, Git CLI, and RQ-worker implementations to their specified outbound adapters.
- Rewired application entry points and container askpass permissions to adapter paths.
- Kept small legacy import shims so external callers and untouched tests remain behavior-compatible during the staged migration.

## Local gauntlet

Executed from the packet branch using the repository's Python 3.12 virtual environment:

```text
./.venv/bin/python --version
Python 3.12.3

./.venv/bin/python -m pytest -q
70 passed, 209 warnings in 1.81s

./.venv/bin/python -m pytest -q apps/api/tests/test_readonly_api.py apps/api/tests/test_graph_api.py apps/api/tests/test_workspaces_api.py apps/api/tests/test_repository_cards.py
7 passed, 39 warnings in 1.14s

./.venv/bin/python -m compileall -q apps/api/app
(exit 0)

git diff --check
(exit 0)
```

`uv` is not installed on the cron host (`uv: command not found`), so the required test suite was exercised with the committed project `.venv` (Python 3.12.3). No web/UI-facing contract changed; Playwright is not applicable. This behavior-preserving restructure does not touch retrieval behavior, so a retrieval scorecard is not applicable.

## Packet verification

`STATUS.md` verify command (`pytest -q`) passed as the 70-test suite above.
