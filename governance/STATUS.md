# Knowledge-Way packet board

```yaml
stage: 1 (retrieval quality and latency)
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
    title: "external comparator local test drive"
    state: done
    branch: "packet/0.4-external-comparator-test-drive-v3"
    verify: "true"
    blocked_by: ["0.1"]
    integration_merge: "c7f91b199029a8e8ef2655d4c25927b7cb18bdd3"
    notes: "PR #77 merged at c7f91b199029a8e8ef2655d4c25927b7cb18bdd3 from exact reviewed head 7d2758bcd365f712ea72fe7eedbe3b7dc1291f4a after REVIEW-052 on_track authorization. Independent current-integration merge simulation, packet verify, 25-task validation, runner help, 95 tests, import-boundary checks, and diff hygiene passed. Observation 06 remains honestly not-representable with no unsupported metrics. GitHub approval was not a gate."
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
  - id: "1.1"
    title: "Postgres FTS for lexical search"
    state: done
    branch: "packet/1.1-postgres-fts"
    pr: 78
    verify: "pytest -q && lint-imports"
    blocked_by: ["0.3"]
    integration_merge: "0a7ae11c352328856bd768cde0a295efddeffbbf"
    notes: "PR #78 merged at 0a7ae11c352328856bd768cde0a295efddeffbbf from exact reviewed head 17644ae0d5a5bd394e6da0edb473f2bfb1d806d7 after REVIEW-055 on_track authorization (HD-004). FTS + ADR-008 rare-term/DF digestion (N=50): hybrid file hit@5 0.16->0.32 (+100%), text 0.16->0.24, p95 improved vs baseline (text 1.0s, hybrid 2.2s). 102 tests, boundaries green. Stage-1 target hybrid hit@5 >= 0.44 (ADR-007) via later semantic/graph packets; hybrid p95<=1s deferred (symbol-pass/1.2). Pre-existing app/worker.py __main__ guard bug to be filed separately. GitHub review approval was not a gate."
  - id: "1.9"
    title: "Usable workspace + code graph UI"
    state: done
    branch: "packet/1.9-workspace-graph-ui"
    pr: 79
    verify: "cd apps/web && npm run test && npx playwright test"
    blocked_by: []
    integration_merge: "81f01102f17f373acd3c72541c518d275665c46b"
    notes: "PR #79 merged at 81f01102f17f373acd3c72541c518d275665c46b from exact reviewed head 2c52d65425a84a54964416921eab7e4e2719f8cc under committed REVIEW-056 on_track (HD-004). GitHub review approval was not a gate."
  - id: "1.3"
    title: "pgvector ANN semantic queries"
    state: done
    branch: "packet/1.3-pgvector-ann"
    pr: 80
    verify: "pytest -q && lint-imports"
    blocked_by: ["1.1"]
    integration_merge: "ba5e7e802cd2a058626cfd8940b3bf638cb014ea"
    notes: "PR #80 merged at ba5e7e802cd2a058626cfd8940b3bf638cb014ea from exact reviewed head c14785c33a246b712429e8abd9a74143cebb65f3 under committed REVIEW-057 on_track (HD-004). Real pgvector HNSW ANN query behind VectorSearch port; Python cosine path retained only as SQLite test fallback. Full-corpus embed + semantic scorecard delta held for owner cost approval (~USD0.46-0.79). GitHub review approval was not a gate."
  - id: "1.5"
    title: "Rank fusion (weighted RRF)"
    state: done
    branch: "packet/1.5-weighted-rrf"
    pr: 81
    verify: "pytest -q && lint-imports"
    blocked_by: ["1.1", "1.3"]
    integration_merge: "c8860206396dcce7582da7916672caa3f6882778"
    notes: "Fixes hybrid<semantic (0.56<0.60): equal-weight RRF dilutes a strong single-mode signal. Move fusion to pure app/domain/retrieval.py, weight per-mode so hybrid hit@5 >= every single mode. Embedded scorecard confirmation run at review (one Vertex embed)."
  - id: "1.9a"
    title: "Workspace/graph UI bug fixes (real-API E2E)"
    state: done
    branch: "packet/1.9a-workspace-ux-fixes"
    pr: 82
    verify: "cd apps/web && npm run test && npm run test:e2e:real"
    blocked_by: ["1.9"]
    integration_merge: "9129e7aec39cfe56384ddc0d0e3747eecf7a269d"
    notes: "REVIEW-059 on_track. Fixes: add-repo excludes repos owned by another workspace (+note); graph falls back to all repos when active workspace empty. Real-API Playwright 3/3 re-run by reviewer against the live stack. Frontend-only."
  - id: "1.0x"
    title: "Compose worker entrypoint repair and obsolete PR housekeeping"
    state: pr_open
    branch: "packet/1.0x-worker-entrypoint-housekeeping"
    pr: 83
    verify: "docker compose up starts the worker without command overrides; scripts/quickstart_smoke.sh passes"
    blocked_by: []
    notes: "PR #55 closed unmerged as obsolete under HUMAN-DIRECTIVE-009/ADR-010. PR #83 is open at exact head 80b49d6dfc044548b3f752dd6fc036f8c19e1099; it replaces the Compose worker command with python -m app.adapters.outbound.rq_jobs.worker. Implementer verification: 113 pytest passed; import-linter contracts passed; direct Compose worker startup passed without a worker command override; scripts/quickstart_smoke.sh passed including real-browser seed/index/search/evidence flow."
  - id: "1.2"
    title: "Hybrid retrieval latency"
    state: todo
    branch: "packet/1.2-hybrid-latency"
    verify: "semantic-enabled hermetic scorecard: hybrid p95 <= 1s and file hit@5 >= 0.68"
    blocked_by: ["1.0x"]
  - id: "1.2b"
    title: "Exact and quoted query mode"
    state: todo
    branch: "packet/1.2b-exact-mode"
    verify: "identifier task subset exact-mode hit@1 >= 0.9"
    blocked_by: ["1.2"]
  - id: "1.4"
    title: "Card embeddings and local-model evaluation"
    state: todo
    branch: "packet/1.4-local-embedding-evaluation"
    verify: "subset-first Vertex comparison; local adoption only with owner sign-off and hybrid hit@5 within 0.05 absolute"
    blocked_by: ["1.2b"]
  - id: "1.6"
    title: "Deterministic query planner"
    state: todo
    branch: "packet/1.6-query-planner"
    verify: "packet verification and semantic-enabled scorecard delta"
    blocked_by: ["1.4"]
  - id: "1.7"
    title: "Hierarchical retrieval"
    state: todo
    branch: "packet/1.7-hierarchical-retrieval"
    verify: "packet verification and semantic-enabled scorecard delta"
    blocked_by: ["1.6"]
  - id: "1.8"
    title: "Rerank evaluation"
    state: todo
    branch: "packet/1.8-rerank-evaluation"
    verify: "retain only if scorecard value justifies latency"
    blocked_by: ["1.7"]
next_instruction:
  issued_by: "navigator"
  issued_at: "2026-08-20T10:45:00+02:00"
  packet: "1.0x"
  objective: "Close obsolete PR #55 unmerged and repair docker-compose worker command to python -m app.adapters.outbound.rq_jobs.worker."
  constraints:
    - "Case-(c) owner-directed housekeeping; no future-stage work."
    - "Use a packet branch; do not modify STATUS.md or RUNLOG files on that branch."
    - "Run docker compose worker startup without command overrides and scripts/quickstart_smoke.sh."
    - "Open a PR to integration/roadmap-v2 with exact-head evidence."
  done_when: "PR #55 is closed unmerged; compose worker starts via docker compose up without command override; quickstart smoke passes; packet PR is pr_open."
last_review: REVIEW-059
drift_flags:
  - detected_at: "2026-08-20T09:49:42+00:00"
    detected_by: "benchmark-run"
    scope: "semantic-enabled benchmark runner"
    status: "open"
    detail: "origin/integration/roadmap-v2 advanced to 262938b, but the binding semantic-enabled scorecard could not run: ${HOME}/.gcloud-kw/application_default_credentials.json is absent in this scheduler environment, and scripts/quickstart_smoke.sh at the exact head refuses EMBEDDING_PROVIDER=vertex by requiring EMBEDDING_PROVIDER=none in .env. No pre-existing service was scored."
```

The YAML block is the machine-readable source used by scheduled jobs. Packet state changes require a corresponding committed review artifact or PR evidence.
