#!/usr/bin/env bash
# R.2 branch-consolidation verifier.
set -euo pipefail

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

main_ref="${1:-origin/main}"
integration_ref="${2:-integration/roadmap-v2}"

[[ "$(git merge-base "$main_ref" "$integration_ref")" == "$(git rev-parse "$main_ref")" ]] \
  || fail "$integration_ref does not descend from $main_ref"
git merge-base --is-ancestor "$main_ref" HEAD \
  || fail "packet branch does not descend from $main_ref"
for file in \
  apps/api/app/repository_cards.py \
  apps/api/tests/test_repository_cards.py \
  docs/evaluation/starlette-repository-card-poc.md; do
  [[ -f "$file" ]] || fail "missing hierarchical retrieval POC artifact: $file"
done
git diff --check

echo "PASS: R.2 branch is based on $main_ref and contains the hierarchical retrieval POC artifacts."
