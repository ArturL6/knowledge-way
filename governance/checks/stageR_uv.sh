#!/usr/bin/env bash
# Verify the repository can be installed exactly from the committed uv lockfile.
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root"

test -f pyproject.toml
test -f uv.lock
test ! -e apps/api/requirements.txt
test ! -e apps/mcp/requirements.txt
grep -Fq 'uv sync --frozen' apps/api/Dockerfile
uv sync --frozen --extra mcp --extra dev
uv run pytest -q apps/api/tests apps/mcp/tests