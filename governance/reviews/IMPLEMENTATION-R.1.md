# R.1 implementation evidence

## REVIEW-001 remediation

- Scheduler contracts and configured job IDs/schedules: `d16fe19`
- CI-advisory ratification and reviewer re-execution control: `b9569a7`
- PLAN change-control rule: `42f9560`
- ADR-002 R.2/local-gauntlet correction: `2e05fed`
- Real R.0 PR #58 dry run, reviewed then closed unmerged: `f22cec8`
- Full R.1 evidence verifier and R.1 resubmission state: `8c50e97`

## Local gauntlet — 2026-08-13

```text
./governance/checks/stageR_governance.sh
PASS: R.1 committed governance artifacts, scheduler evidence, and dry-run evidence are complete.

PYTHONPATH=apps/api pytest -q apps/api/tests
58 passed, 22 warnings in 1.60s

PYTHONPATH=apps/mcp pytest -q apps/mcp/tests
10 passed in 0.02s

git diff --check
PASS (no output)
```

The repository has separate application roots; `PYTHONPATH` is required for the existing un-packaged test layout. No application behavior changed in R.1.
