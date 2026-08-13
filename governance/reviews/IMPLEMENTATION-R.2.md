# R.2 implementation evidence

## Scope delivered

- Rebuilt `packet/R.2-branch-consolidation` from `integration/roadmap-v2`, whose merge-base with `origin/main` is `90b3ba5812194536930b4a5b633204937a3371b1` (the fetched current main).
- Cherry-picked the four-file, 249-line deterministic repository-card POC from `feat/hierarchical-retrieval-poc` (including indexed-snapshot pinning and its FastAPI endpoint tests).
- Added the R.2 branch verifier at `governance/checks/stageR_branch.sh`.
- Added the PLAN-required Playwright smoke harness for the existing repository-to-index entry point. This packet does not change a web contract.

## Local gauntlet — 2026-08-13

**Verified implementation head:** `d3341091ad8237d981aecf46ff3a52578b5f8b0a` (`fix(R.2): make branch verifier executable`). This is the packet implementation head executed by the complete gauntlet below. The only subsequent packet commit records this evidence and changes the STATUS handoff from `review_blocked` to `pr_open`; it does not alter application, test, web, or verifier content.

```text
/tmp/knowledge-way-r2-venv/bin/python -m pytest -q apps/api/tests
59 passed, 22 warnings in 1.63s

PYTHONPATH=apps/mcp /tmp/knowledge-way-r2-venv/bin/python -m pytest -q apps/mcp/tests
10 passed in 0.02s

cd apps/web && npm test
PASS (no legacy Vitest files are present on the R.2 base; command exited 0)

cd apps/web && npm run build
PASS: Next.js production build completed; 6 routes generated.

cd apps/web && npm run test:e2e
1 passed (repository dashboard add-to-index smoke flow)

./governance/checks/stageR_branch.sh origin/main origin/integration/roadmap-v2
PASS: R.2 branch is based on origin/main and contains the hierarchical retrieval POC artifacts.

git diff --check
PASS (no output)
```

The FastAPI test suite includes the endpoint coverage for the added `GET /api/repositories/{repo_id}/repository-card` endpoint in `apps/api/tests/test_repository_cards.py`.

## Review-004 remediation

- Promoted the recorded R.1 integration merge (`45f6af96af239e05112c42eb709c5cc935d409b5`) to `origin/integration/roadmap-v2`; the remote integration branch now contains R.1 and is an ancestor of the packet branch.
- Rebuilt PR #59's comparison base through that remote integration ref. Its R.2 delta now excludes the R.1 governance packet.
- Committed `governance/checks/stageR_branch.sh` with executable mode `100755` and ran the exact declared verifier successfully as recorded above.
