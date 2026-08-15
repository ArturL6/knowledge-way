# REVIEW-059 — Packet 1.9a workspace/graph UX fixes

```yaml
verdict: on_track
packet: "1.9a"
pr: 82
reviewed_head: "4977b602ce36e01f97e59a08b611830da7de4bb2"
reviewed_integration_head: "88dbbbe"
reviewed_at: "2026-08-15T16:20:00+00:00"
criteria_checked:
  - "Exact PR head 4977b60; diff frontend-only (graph-explorer, workspaces-client, real-api e2e+config, playwright.config, package.json, .gitignore); no STATUS/RUNLOG/python; no gitnexus: PASS"
  - "vitest 73/73; tsc --noEmit clean; existing mocked Playwright 3/3: PASS"
  - "REAL-API Playwright E2E re-executed BY REVIEWER against the live keyless stack (web build with same-origin /api proxy -> API 34747): 3/3 PASS (create ws + add free repo; already-owned repo excluded + note; ready-repo whole-repo graph renders)"
  - "Fixes address the owner-reported bugs: workspaces-client excludes repos owned by another workspace (loadOwnership) + note; graph-explorer falls back to all ready repos when active workspace is empty (workspaceScopeEmpty): PASS"
drift_findings: []
required_actions: []
observations:
  - "Backend keeps one-workspace-per-repo (409); this packet makes the UX honest about it rather than changing the model. Multi-membership remains an open owner option."
  - "loadOwnership refetches on expand, not live across tabs (acceptable)."
  - "Reviewer's first real-API run failed 3/3 due to a REVIEWER harness error (built browser calls cross-origin -> API CORS blocked); rebuilding with the intended same-origin next rewrite proxy passed 3/3. Not a code defect."
  - "Process fix recorded: UI packets now require real-API E2E, not mocked-only (the gap that let packet 1.9 ship these bugs)."
scope_creep_risk: low
```

## Independent execution
Detached-HEAD review at 4977b60. vitest 73/73, tsc clean, mocked Playwright 3/3. Built the branch web (same-origin `/api` -> `API_INTERNAL_URL=34747` rewrite proxy) and ran the real-API Playwright suite against the live keyless stack: 3/3 pass, covering the exact flows the owner reported broken. Per HD-004 this authorizes merge of PR #82.
