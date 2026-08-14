# Knowledge-Way packet board

```yaml
stage: R (promoted to main)
stage_promotion:
  authorized_review: "REVIEW-046"
  reviewed_integration_head: "c437a4e3342d5d2cc7ecb61ec20dc26029d7f094"
  promotion_sha: "d72137f4cfbf3beaf1ae392710b7da489ed1972f"
  promoted_at: "2026-08-14T16:01:45+00:00"
owner_testable: true
owner_quickstart:
  - "git clone --branch integration/roadmap-v2 https://github.com/ArturL6/knowledge-way.git"
  - "cd knowledge-way"
  - "./scripts/quickstart_smoke.sh --keep-running"
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
    state: done
    branch: "packet/0.1-fastapi-stack-corpus"
    verify: "test -f benchmarks/corpora.json"
    blocked_by: ["R.7a"]
    integration_merge: "dfc4c6bef000994fc4fbe83cc11128da7dcada9f"
    notes: "Prefilled owner selection: fastapi/fastapi, encode/starlette, pydantic/pydantic. PR #66 merged at dfc4c6bef000994fc4fbe83cc11128da7dcada9f after committed REVIEW-033 on_track authorization for exact head 42e74e6d8086ef8e9888c4125023801e497a48d9; GitHub approval was not a gate."
  - id: "0.2"
    title: "Gold tasks from historical issue/fix-PR pairs"
    state: done
    branch: "packet/0.2-gold-tasks"
    verify: "python benchmarks/validate_tasks.py"
    blocked_by: ["0.1"]
    integration_merge: "259d28fbe6c5b441ed72b90e9466a6fe771e89ae"
    notes: "PR #72 merged at 259d28fbe6c5b441ed72b90e9466a6fe771e89ae from exact reviewed head bdc788a625117aac8bb54ffeb666e09d32aec3d0 after committed REVIEW-043 on_track authorization; packet verify, benchmark checks, 95 tests, and boundary contracts passed. GitHub approval was not a gate."
  - id: "0.3"
    title: "Retrieval scorecard baseline harness"
    state: done
    branch: "packet/0.3-scorecard-harness"
    verify: "python benchmarks/run_retrieval.py --help"
    blocked_by: ["0.1", "0.2"]
    integration_merge: "2eb873874cdcdae1013575c01c080d3906db6667"
    notes: "PR #74 merged at 2eb873874cdcdae1013575c01c080d3906db6667 from exact reviewed head 67819c93fc53bf8cc8e1aac69ed2e827e7c04fb6 after REVIEW-048 on_track authorization. Independent review passed packet verify, 25-task validation, 95 tests (including 5 focused harness tests), both import contracts, snapshot/task-content binding, fatal failure semantics, packet governance hygiene, diff check, and current-integration merge simulation. The replacement baseline has complete supported-mode coverage; semantic remains honestly unconfigured under HUMAN-DIRECTIVE-005. GitHub approval was not a gate."
  - id: "0.4"
    title: "GitNexus local test drive"
    state: review_blocked
    branch: "packet/0.4-gitnexus-test-drive-v3"
    verify: "test -f benchmarks/gitnexus-findings.md"
    blocked_by: ["0.1"]
    pr: 77
    head_sha: "c8b962db68a953121bad1586b4c2ae4964fd306b"
    notes: "PR #75 was closed unmerged under HD-005 §1. PR #77 exact head c8b962d passes the applicable checks but REVIEW-050 blocks it as stale: current integration cca8530 is not an ancestor. HD-006 §1 requires merging current integration into the packet branch, resolving without STATUS/RUNLOG packet writes, then adding a remediation commit and requesting exact-head re-review; rebases and all force pushes are forbidden. PR #76 was closed unmerged. Study behavior only; never copy PolyForm Noncommercial code."
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
next_instruction:
  issued_by: sol-navigator
  issued_at: "2026-08-14T18:08:22+00:00"
  packet: "0.4"
  objective: "Execute the PLAN 0.4 GitNexus local test drive against the committed fastapi-stack workspace and gold-task question classes, producing a reproducible, license-clean comparative findings artifact."
  constraints:
    - "Branch packet/0.4-gitnexus-test-drive from refreshed integration/roadmap-v2; packet branches must not modify governance/STATUS.md or any governance/operations/RUNLOG*."
    - "Follow HUMAN-DIRECTIVE-005 section 4 exactly: install GitNexus with GITNEXUS_SKIP_OPTIONAL_GRAMMARS=1 and ONNXRUNTIME_NODE_INSTALL=skip, use eval-server for scripted calls, and resolve symbol UIDs before trace calls."
    - "Study behavior and record results only; never copy or mechanically rewrite PolyForm Noncommercial GitNexus source code."
    - "Evaluate the PLAN Appendix A.7 question classes on the committed fastapi-stack corpus and applicable gold tasks; record correct/partial/incorrect/not-representable plus latency, commands, versions, corpus snapshots, and enough raw evidence for independent replay."
    - "Capture context/impact epistemic exact-or-lower-bound fields and boundary explanations. Dedupe CodeRelation rows before graph counts. Keep cross-repository group evaluation out of scope until Stage 3."
    - "Verify LadybugDB FTS extension availability; if egress or repair-fts fails, label keyword results environment-limited rather than treating degradation as a product result. Record analyze timing and compare it honestly with the owner-observed ~9.5s Starlette bar."
    - "Use subset-first, BYOK, product-budget-accounted execution for any chat/LLM mode; do not require chat to complete deterministic graph/search evaluation, and never manufacture unavailable results."
    - "Create benchmarks/gitnexus-findings.md and any reproducible runner/result fixtures needed for the packet; run the full applicable local gauntlet and packet verify. Playwright is required only if a web or UI-facing contract is touched."
    - "Open exactly one PR into integration/roadmap-v2 with evidence bound to its exact head; do not merge without a committed exact-head on_track reviewer verdict."
  done_when: "benchmarks/gitnexus-findings.md exists with reproducible GitNexus results over the fastapi-stack workspace, all 12 PLAN Appendix A.7 classes are classified (including honest not-representable/environment-limited outcomes), required epistemic/latency/version/snapshot evidence is captured, the applicable gauntlet passes, and the exact-head packet 0.4 PR is open into integration/roadmap-v2."
last_review: REVIEW-050
drift_flags: []
```

The YAML block is the machine-readable source used by scheduled jobs. Packet state changes require a corresponding committed review artifact or PR evidence.
