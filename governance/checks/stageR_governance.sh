#!/usr/bin/env bash
# R.1 governance bootstrap verifier.
# It is intentionally offline: scheduled-job presence is checked by the Hermes
# scheduler, while this repository check guarantees the committed governance
# contract is complete and internally consistent.
set -euo pipefail

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

for file in \
  governance/PLAN.md \
  governance/STATUS.md \
  governance/decisions/ADR-001-retain-redis-rq.md \
  governance/decisions/ADR-002-retain-nextjs-react19.md; do
  [[ -f "$file" ]] || fail "missing $file"
done

[[ -d governance/reviews ]] || fail "missing governance/reviews"
[[ -d governance/checks ]] || fail "missing governance/checks"

grep -Fq 'stage: R' governance/STATUS.md || fail 'STATUS does not declare Stage R'
grep -Fq 'id: "R.1"' governance/STATUS.md || fail 'STATUS does not contain R.1'
grep -Fq 'state: in_progress' governance/STATUS.md || fail 'R.1 is not in progress'
grep -Fq 'Retain Redis + RQ' governance/decisions/ADR-001-retain-redis-rq.md || fail 'ADR-001 decision missing'
grep -Fq 'Next.js + React 19' governance/decisions/ADR-002-retain-nextjs-react19.md || fail 'ADR-002 decision missing'

echo 'PASS: R.1 committed governance artifacts are present and internally consistent.'
