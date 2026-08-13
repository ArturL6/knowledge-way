# Implementation evidence — R.4 Hexagon: extract ports and move adapters

## Scope and SHA binding

- **Tested implementation SHA:** `2fcf9d7b1473f5169076ff7b78684c29b131f029` (`test(R.4): add in-memory port fakes`).
- This implementation includes the original R.4 adapter extraction at `869eabdd133479081e1b6033e0e9e6d56970fd27` plus the reviewer-required, Docker-free in-memory fakes for every application port and their contract exercise.
- The immediate successor is this evidence/STATUS-only handoff commit; it changes no executable application code. Its verification is explicitly bound to the tested implementation SHA above.
- PostgreSQL (`models.py`, `db.py`), tree-sitter, LLM provider, Git CLI, and RQ worker implementations remain in their required outbound-adapter paths; legacy import shims preserve compatibility while the staged migration is incomplete.

## Reviewer-required fake contracts

`apps/api/app/application/fakes.py` supplies in-memory implementations for all eight ports: `RepoStore`, `SourceControl`, `LexicalSearch`, `VectorSearch`, `CodeParser`, `LLM`, `Embeddings`, and `JobQueue`.

`apps/api/tests/test_ports.py` verifies structural compatibility with every runtime-checkable Protocol and executes each operation without Docker or an outbound adapter.

## Local gauntlet (executed at tested implementation SHA)

```text
./.venv/bin/python -m pytest -q apps/api/tests/test_ports.py
1 passed in 0.02s

./.venv/bin/python -m pytest -q
70 passed, 209 warnings in 1.86s

./.venv/bin/python -m pytest -q apps/api/tests/test_readonly_api.py apps/api/tests/test_graph_api.py apps/api/tests/test_workspaces_api.py apps/api/tests/test_repository_cards.py
7 passed, 39 warnings in 1.07s

./.venv/bin/python -m compileall -q apps/api/app
(exit 0)

git diff --check
(exit 0)

UV_BIN=/home/hermes/.hermes/hermes-agent/venv/bin/uv governance/checks/stageR_uv.sh
uv 0.12.3; lockfile sync completed
70 passed, 209 warnings in 1.83s
```

Ruff, import-linter, and type checking are not configured yet; R.6 owns boundary enforcement. `apps/web` and UI-facing API contracts are untouched, so Playwright is not applicable. R.4 is behavior-preserving and makes no retrieval change, so a retrieval scorecard is not applicable.

## Packet verification

The STATUS verify command, `pytest -q`, is covered by the 70-passing full suite above.
