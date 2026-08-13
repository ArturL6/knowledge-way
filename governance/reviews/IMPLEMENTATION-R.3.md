# Implementation evidence — R.3: uv migration

**Packet:** R.3 — uv migration
**Branch:** `packet/R.3-uv-migration`
**Verified implementation head:** `d2d5d5e0b64a7625121c9eb4d2bc133d1a814af5` (`fix(R.3): require Python 3.12 toolchain`). The subsequent commit records this evidence and changes the STATUS handoff from `review_blocked` to `pr_open`; it contains no application, dependency, Docker, test, or verifier changes.

## Scope delivered

- Replaced API and MCP `requirements.txt` manifests with root `pyproject.toml` and committed `uv.lock`.
- Added uv extras for development tests and the optional MCP bridge.
- Converted the API Docker build and Compose build contexts to install the frozen lockfile through uv.
- Updated migration, MCP, and demo setup instructions to use `uv sync --frozen`.
- Added `governance/checks/stageR_uv.sh`, which asserts legacy manifests are absent, uses the frozen lockfile, and runs the API plus MCP suites.

## Local gauntlet results

| Check | Result |
|---|---|
| Frozen clean-checkout install | PASS — `UV_BIN=/tmp/knowledge-way-uv-bootstrap/bin/uv bash governance/checks/stageR_uv.sh` in fresh `/tmp/knowledge-way-r3-python312-clean` clone under Python 3.12.3 |
| Unit/API endpoint test suite | PASS — `69 passed` (`apps/api/tests` and `apps/mcp/tests`) under Python 3.12.3 |
| Touched FastAPI endpoint coverage | PASS — existing FastAPI TestClient endpoint suite included in the 69 tests; no endpoint contracts changed by this dependency-only packet |
| Playwright | Not applicable — `apps/web` and UI-facing contracts were untouched |
| Retrieval scorecard | Not applicable — no retrieval behavior changed |
| Packet verify | PASS — `UV_BIN=/tmp/knowledge-way-uv-bootstrap/bin/uv bash governance/checks/stageR_uv.sh`; `69 passed` |
| Python 3.12+ policy | PASS — `pyproject.toml` declares `requires-python = ">=3.12"`; API image uses `python:3.12-slim` |
| Compose configuration | PASS — `docker compose config --quiet` using `.env.example` in the clean checkout |
| API image build | PASS — `docker build -f apps/api/Dockerfile .` in the clean checkout using `python:3.12-slim` |
| Diff whitespace | PASS — `git diff --check` |

The test run emits existing FastAPI `on_event`, `datetime.utcnow`, and tree-sitter deprecation warnings only (209 warnings); no test failures occurred. Static ruff, import-linter, and type-check commands are not configured in this stage's migrated dev dependencies; import-boundary enforcement is assigned to R.6. Playwright and the retrieval scorecard are not applicable because this packet changes neither `apps/web`/a UI contract nor retrieval behavior.
