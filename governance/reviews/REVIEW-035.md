# REVIEW-035 — HUMAN-DIRECTIVE-004 merge authorization clarification

```yaml
verdict: on_track
packet: "HD-004-directive"
pr: 71
reviewed_head_sha: dc3227632f00e7b94eb1d8c167cc30c205a25dca
criteria_checked:
  - "Exact-head identity: PASS (explicit refresh of origin/integration/roadmap-v2, origin/main, all PR refs, and GitHub headRefOid immediately before verdict; PR #71 remains dc3227632f00e7b94eb1d8c167cc30c205a25dca)"
  - "Owner-directive fidelity: PASS (the committed directive exactly states that GitHub approval is not a gate and that merge authorization requires a committed on_track review whose reviewed_head_sha equals the current PR head)"
  - "Conflict with PLAN/standing rules: PASS (clarifies the existing reviewer-verdict gate without weakening exact-head re-execution, local-gauntlet evidence, packet scope, or branch direction)"
  - "ADR-003 independent exact-head re-execution: PASS (uv sync --frozen --extra dev; uv run pytest -q: 95 passed)"
  - "Hexagonal boundary: PASS (PYTHONPATH=apps/api uv run lint-imports: 2 contracts kept, 0 broken)"
  - "Patch hygiene: PASS (git diff --check origin/integration/roadmap-v2...HEAD)"
  - "Scope: PASS (one governance directive only; no application code, PLAN, STATUS packet definition, dependency, or infrastructure change)"
  - "Integration current with main: PASS (refreshed origin/main 0954b41f3e285fe67aa573e9e336056464649be6 is an ancestor of origin/integration/roadmap-v2 07eb296cb8477ae115d21afcb978b830dd3bcdbf)"
  - "Scorecard delta: NOT APPLICABLE (governance-only clarification; no retrieval behavior changed)"
drift_findings: []
required_actions: []
scope_creep_risk: low
```

PR #71 is **on_track** and authorized to merge only while its current head remains
`dc3227632f00e7b94eb1d8c167cc30c205a25dca`. Any head change invalidates this
authorization and requires a new exact-head review. GitHub review approval was not
requested and is not treated as a gate.
