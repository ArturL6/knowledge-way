#!/usr/bin/env bash
# Verify the repository can be installed exactly from the committed uv lockfile.
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root"

# UV_BIN supports hermetic CI/bootstrap paths while production developers use uv on PATH.
uv_bin=${UV_BIN:-uv}

test -f pyproject.toml
test -f uv.lock
test ! -e apps/api/requirements.txt
test ! -e apps/mcp/requirements.txt
grep -Fq 'uv sync --frozen' apps/api/Dockerfile
"$uv_bin" sync --frozen --extra mcp --extra dev
"$uv_bin" run pytest -q apps/api/tests apps/mcp/tests