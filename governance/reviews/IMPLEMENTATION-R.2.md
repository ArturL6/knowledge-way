# R.2 implementation evidence

## Scope delivered

- Rebuilt `packet/R.2-branch-consolidation` from `integration/roadmap-v2`, whose merge-base with `origin/main` is `90b3ba5812194536930b4a5b633204937a3371b1` (the fetched current main).
- Cherry-picked the four-file, 249-line deterministic repository-card POC from `feat/hierarchical-retrieval-poc` (including indexed-snapshot pinning and its FastAPI endpoint tests).
- Added the R.2 branch verifier at `governance/checks/stageR_branch.sh`.
- Added the PLAN-required Playwright smoke harness for the existing repository-to-index entry point. This packet does not change a web contract.

## Local gauntlet — 2026-08-13

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

./governance/checks/stageR_branch.sh
PASS: R.2 branch is based on origin/main and contains the hierarchical retrieval POC artifacts.

git diff --check
PASS (no output)
```

The FastAPI test suite includes the endpoint coverage for the added `GET /api/repositories/{repo_id}/repository-card` endpoint in `apps/api/tests/test_repository_cards.py`.
