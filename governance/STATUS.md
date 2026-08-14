# Knowledge-Way packet board

```yaml
stage: R
packets:
  - id: "R.0"
    title: "Governance dry run"
    state: done (dry run, closed unmerged)
    branch: "packet/R.0-dryrun"
    verify: "true"
    blocked_by: []
  - id: "R.1"
    title: "Governance bootstrap"
    state: done
    branch: "packet/R.1-governance-bootstrap"
    verify: "governance/checks/stageR_governance.sh"
    blocked_by: []
    integration_merge: "76ca480dc0c6e776ddb3f0103518ca4b0eddc619"
  - id: "R.2"
    title: "Branch consolidation, main as base"
    state: done
    branch: "packet/R.2-branch-consolidation"
    verify: "governance/checks/stageR_branch.sh"
    blocked_by: ["R.1"]
    integration_merge: "debf40c1eff58cdbbc459c8fdb0dcd2f52c9409e"
  - id: "R.3"
    title: "uv migration"
    state: done
    branch: "packet/R.3-uv-migration"
    verify: "governance/checks/stageR_uv.sh"
    blocked_by: ["R.2"]
    integration_merge: "08f025b2445904dbba29ce2c41242e1f0eff4756"
  - id: "R.4"
    title: "Hexagon: extract ports and move adapters"
    state: done
    branch: "packet/R.4-hexagon-adapters"
    verify: "pytest -q"
    blocked_by: ["R.3"]
    integration_merge: "e27e411d794383356865eba6a21623d9f85e5207"
  - id: "R.5"
    title: "Hexagon: split main.py"
    state: done
    branch: "packet/R.5-split-main"
    verify: "pytest -q"
    blocked_by: ["R.4"]
    integration_merge: "5ba2409b764f82b3e14b8f2e035351e41ee88174"
  - id: "R.6"
    title: "Boundary enforcement"
    state: done
    branch: "packet/R.6-boundary-enforcement"
    verify: "governance/checks/stageR_import_boundary.sh"
    blocked_by: ["R.5"]
    integration_merge: "3b34bc165f2e37869790788a023ba740d8a178eb"
  - id: "R.7"
    title: "Evidence table"
    state: done
    branch: "packet/R.7-evidence-table"
    verify: "governance/checks/stageR_evidence.sh"
    blocked_by: ["R.6"]
    integration_merge: "68d0f136dc1a015c7c0d183ec494a59f64d9da1d"
  - id: "R.7a"
    title: "Synchronize origin/main into integration"
    state: done
    branch: "packet/R.7a-sync-main"
    verify: "governance/checks/stageR_sync_main.sh"
    blocked_by: ["R.7"]
    integration_merge: "ec1e86e0057f617cfb260a178c7ffecd9095bd7a"
    notes: "origin/main merged at 2823ded; 84-test ratchet and full local gauntlet are recorded in IMPLEMENTATION-R.7a. Quickstart remains owned by blocked packet 0.6 and must pass before Stage-R promotion."
  - id: "0.1"
    title: "Workspace selection: fastapi-stack"
    state: pr_open
    branch: "packet/0.1-fastapi-stack-corpus"
    verify: "test -f benchmarks/corpora.json"
    blocked_by: ["R.7a"]
    notes: "Prefilled owner selection: fastapi/fastapi, encode/starlette, pydantic/pydantic."
  - id: "0.2"
    title: "Gold tasks from historical issue/fix-PR pairs"
    state: todo
    branch: "packet/0.2-gold-tasks"
    verify: "python benchmarks/validate_tasks.py"
    blocked_by: ["0.1"]
    notes: "25–40 closed issues; labels mechanically derived from merged fix PRs; Sol samples 10."
  - id: "0.3"
    title: "Retrieval scorecard baseline harness"
    state: todo
    branch: "packet/0.3-scorecard-harness"
    verify: "python benchmarks/run_retrieval.py --help"
    blocked_by: ["0.1", "0.2"]
  - id: "0.4"
    title: "GitNexus local test drive"
    state: todo
    branch: "packet/0.4-gitnexus-test-drive"
    verify: "test -f benchmarks/gitnexus-findings.md"
    blocked_by: ["0.1"]
    notes: "Study behavior only; never copy PolyForm Noncommercial code."
  - id: "0.5"
    title: "Benchmark scheduler wiring"
    state: todo
    branch: "packet/0.5-benchmark-scheduler"
    verify: "true"
    blocked_by: ["0.3"]
  - id: "0.6"
    title: "Local quickstart v1"
    state: done
    branch: "packet/0.6-local-quickstart"
    verify: "scripts/quickstart_smoke.sh"
    blocked_by: ["R.7a"]
    notes: "PR #67 merged from exact reviewed head d1ae95757a5dd78353cddc33c22b7226be811d46 under committed REVIEW-032; independent packet verify, full applicable gauntlet, and selected-workspace browser flow passed. GitHub review approval was not a gate."
last_review: REVIEW-032
drift_flags: []
next_instruction: null
```

The YAML block is the machine-readable source used by scheduled jobs. Packet state changes require a corresponding committed review artifact or PR evidence.
