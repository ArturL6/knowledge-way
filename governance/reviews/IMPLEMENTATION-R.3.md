# Implementation evidence — R.3: uv migration

**Packet:** R.3 — uv migration  
**Branch:** `packet/R.3-uv-migration`  
**Head:** pending final governance commit

## Scope delivered

- Replaced API and MCP `requirements.txt` manifests with root `pyproject.toml` and committed `uv.lock`.
- Added uv extras for development tests and the optional MCP bridge.
- Converted the API Docker build and Compose build contexts to install the frozen lockfile through uv.
- Updated migration, MCP, and demo setup instructions to use `uv sync --frozen`.
- Added `governance/checks/stageR_uv.sh`, which asserts legacy manifests are absent, uses the frozen lockfile, and runs the API plus MCP suites.

## Local gauntlet results

| Check | Result |
|---|---|
| Frozen clean-checkout install | PASS — `uv sync --frozen --extra mcp --extra dev` in fresh `/tmp/knowledge-way-r3-clean` clone |
| Unit/API endpoint test suite | PASS — `69 passed` (`apps/api/tests` and `apps/mcp/tests`) |
| Touched FastAPI endpoint coverage | PASS — existing FastAPI TestClient endpoint suite included in the 69 tests; no endpoint contracts changed by this dependency-only packet |
| Playwright | Not applicable — `apps/web` and UI-facing contracts were untouched |
| Retrieval scorecard | Not applicable — no retrieval behavior changed |
| Packet verify | PASS — `UV_BIN=/tmp/knowledge-way-uv-bootstrap/bin/uv bash governance/checks/stageR_uv.sh`; `69 passed` |
| Compose configuration | PASS — `docker compose config --quiet` using `.env.example` in the clean checkout |
| API image build | PASS — `docker build -f apps/api/Dockerfile .` in the clean checkout |
| Diff whitespace | PASS — `git diff --check` |

The test run emits pre-existing FastAPI `on_event` and tree-sitter deprecation warnings only.
