#!/usr/bin/env bash
# R.1 governance bootstrap verifier.
# It validates committed artifacts. Scheduler configuration itself is evidenced in
# governance/operations/schedulers.md and append-only real-tick heartbeat lines.
set -euo pipefail

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

for file in \
  governance/PLAN.md \
  governance/STATUS.md \
  governance/decisions/ADR-001-retain-redis-rq.md \
  governance/decisions/ADR-002-retain-nextjs-react19.md \
  governance/decisions/ADR-005-ratify-human-directive-003.md \
  governance/directives/HUMAN-DIRECTIVE-003.md \
  governance/operations/schedulers.md \
  governance/operations/RUNLOG.md \
  governance/operations/dryrun-report.md; do
  [[ -f "$file" ]] || fail "missing $file"
done

[[ -d governance/reviews ]] || fail "missing governance/reviews"
[[ -d governance/checks ]] || fail "missing governance/checks"
compgen -G 'governance/decisions/ADR-003-*.md' >/dev/null || fail 'missing ADR-003'
compgen -G 'governance/reviews/REVIEW-*-dryrun.md' >/dev/null || fail 'missing dry-run review'

grep -Fq 'stage: R' governance/STATUS.md || fail 'STATUS does not declare Stage R'
grep -Fq 'id: "R.1"' governance/STATUS.md || fail 'STATUS does not contain R.1'
grep -Fq 'next_instruction:' governance/STATUS.md || fail 'STATUS lacks next_instruction contract'
grep -Fq 'drift_flags: []' governance/STATUS.md || fail 'STATUS has stale drift flags'
grep -Fq 'Retain Redis + RQ' governance/decisions/ADR-001-retain-redis-rq.md || fail 'ADR-001 decision missing'
grep -Fq 'Next.js + React 19' governance/decisions/ADR-002-retain-nextjs-react19.md || fail 'ADR-002 decision missing'
grep -Fq 'PLAN change control' governance/PLAN.md || fail 'PLAN change-control clause missing'

for job in sol-navigator-run implementer-run benchmark-run; do
  grep -Fq "\`$job\`" governance/operations/schedulers.md || fail "scheduler contract missing $job"
done
grep -Fq 'every 20m' governance/operations/schedulers.md || fail 'scheduler cadence is not 20 minutes'
grep -Fq 'Ratify HUMAN-DIRECTIVE-003' governance/decisions/ADR-005-ratify-human-directive-003.md || fail 'ADR-005 decision missing'

grep -Eq 'REVIEW-[^ ]*-dryrun\.md' governance/operations/dryrun-report.md || fail 'dry-run report does not reference dry-run review'

echo 'PASS: R.1 committed governance artifacts, scheduler evidence, and dry-run evidence are complete.'
