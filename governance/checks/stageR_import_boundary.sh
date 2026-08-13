#!/usr/bin/env bash
# Verify R.6's executable hexagonal import boundary, including a known-bad
# temporary module so the check cannot pass merely because it is unwired.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
export PYTHONPATH="$repo_root/apps/api${PYTHONPATH:+:$PYTHONPATH}"

cleanup() {
  rm -f apps/api/app/domain/_boundary_violation.py
}
trap cleanup EXIT

uv run lint-imports

printf '%s\n' 'from app.adapters.inbound.http import routes' > apps/api/app/domain/_boundary_violation.py
if uv run lint-imports --no-cache; then
  printf '%s\n' 'ERROR: import-linter accepted the deliberate domain-to-adapter violation.' >&2
  exit 1
fi

cleanup
trap - EXIT
uv run lint-imports --no-cache
printf '%s\n' 'PASS: R.6 import boundaries reject a deliberate violation and pass on HEAD.'