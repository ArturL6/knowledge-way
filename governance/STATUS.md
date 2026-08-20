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
    state: deferred
    branch: "packet/0.5-benchmark-scheduler"
    verify: "formalize HD-010 dual-scorecard benchmark contract"
    blocked_by: ["K.3"]
    notes: "Deferred post-sprint resume position 4; scheduler runs but its formal contract follows sprint evidence."
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
    state: done
    branch: "packet/1.0x-worker-entrypoint-housekeeping"
    pr: 83
    verify: "docker compose up starts the worker without command overrides; scripts/quickstart_smoke.sh passes"
    blocked_by: []
    integration_merge: "3448d4d8e351365bf13f0950a735ff36e954185e"
    notes: "PR #55 closed unmerged as obsolete under HUMAN-DIRECTIVE-009/ADR-010. PR #83 merged at 3448d4d8e351365bf13f0950a735ff36e954185e from exact reviewed head 80b49d6dfc044548b3f752dd6fc036f8c19e1099 under committed REVIEW-060 on_track. The Compose worker now starts with python -m app.adapters.outbound.rq_jobs.worker without command overrides; direct worker startup and scripts/quickstart_smoke.sh including real-browser seed/index/search/evidence flow passed."
  - id: "K.0"
    title: "Semantic-capable quickstart provisioning and benchmark hygiene"
    state: done
    branch: "packet/K.0-semantic-quickstart-provisioning"
    pr: 85
    integration_merge: "ce1352e22ea53fb3745e61e5393caf06385d900d"
    verify: "same exact integration head produces hermetic keyless and semantic-enabled scorecards with pinned served-manifest verification and teardown; default keyless quickstart remains green"
    blocked_by: ["1.0x"]
    notes: "PR #85 merged at ce1352e22ea53fb3745e61e5393caf06385d900d from exact REVIEW-061-authorized head 6747379bc383a51882d1887621431d4fd4607a39. Independent keyless quickstart, 113 tests, boundaries, ADC fail-fast, scope hygiene, and mergeability passed. Provisioning-only teardown remediation PR #87 merged at cbab2743f4aeaa9cc663b8052c0dce5080365302 from exact REVIEW-063-authorized head c33381326c485f88d671cdc41c835559d522efae; its project-scoped fixture volume and Compose down --volumes leave no isolated project resources or checkout residue. Semantic guard remains awaiting_owner because the sole authorized ADC path is absent; mandatory first post-ADC scorecard must confirm hybrid >=0.68 or reopen drift."
  - id: "K.1"
    title: "Query digestion, BM25 re-scoring, and lexical latency"
    state: todo
    branch: "packet/K.1-query-digestion-bm25"
    verify: "dual hermetic scorecards: keyless text hit@5 materially improves toward >=0.40; semantic-enabled hybrid >=0.68; text p95 improves; digester and BM25 unit tests pass"
    blocked_by: ["K.0"]
    citations_required: ["Spärck Jones 1972", "Robertson & Zaragoza 2009"]
  - id: "K.2"
    title: "Name-first compact retrieval units"
    state: todo
    branch: "packet/K.2-name-first-entities"
    verify: "dual hermetic scorecards: hybrid p95 <=1s, identifier exact hit@1 >=0.9, keyless hit@5 >=0.40, semantic-enabled hybrid >=0.68"
    blocked_by: ["K.1"]
    citations_required: ["public IR sources cited in PR/ADR"]
  - id: "K.3"
    title: "Graph expansion into fusion"
    state: todo
    branch: "packet/K.3-graph-expansion-fusion"
    verify: "flagged with/without dual scorecards: keyless hit@5 >=0.44 and semantic-enabled hybrid >=0.68; revert if neutral"
    blocked_by: ["K.2"]
    citations_required: ["Cormack, Clarke & Buettcher 2009"]
  - id: "1.2"
    title: "Hybrid retrieval latency"
    state: deferred
    branch: "packet/1.2-hybrid-latency"
    verify: "absorbed by K.1/K.2"
    blocked_by: ["K.3"]
    notes: "Deferred: K.2 owns the p95 <=1s exit and replaces the ILIKE symbol pass."
  - id: "1.2b"
    title: "Exact and quoted query mode"
    state: deferred
    branch: "packet/1.2b-exact-mode"
    verify: "absorbed by K.2"
    blocked_by: ["K.3"]
    notes: "Deferred: K.2 owns indexed exact/prefix/pg_trgm routing and identifier hit@1 target."
  - id: "1.4"
    title: "Card embeddings and local-model evaluation"
    state: deferred
    branch: "packet/1.4-local-embedding-evaluation"
    verify: "subset-first Vertex comparison; local adoption only with owner sign-off and hybrid hit@5 within 0.05 absolute"
    blocked_by: ["K.3"]
    notes: "Deferred post-sprint resume position 1; K.2 entity/card lexical indexing supplies preparation only."
  - id: "1.6"
    title: "Deterministic query planner"
    state: deferred
    branch: "packet/1.6-query-planner"
    verify: "packet verification and semantic-enabled scorecard delta"
    blocked_by: ["K.3"]
    notes: "Deferred post-sprint resume position 2; K.1 digestion and K.2 routing cover partial preparation."
  - id: "1.7"
    title: "Hierarchical retrieval"
    state: deferred
    branch: "packet/1.7-hierarchical-retrieval"
    verify: "remaining hierarchy scope re-scoped after K.3"
    blocked_by: ["K.3"]
    notes: "Deferred: K.3 absorbs the keyless graph-expansion portion; remaining hierarchy is tracked for post-sprint re-scoping."
  - id: "1.8"
    title: "Rerank evaluation"
    state: deferred
    branch: "packet/1.8-rerank-evaluation"
    verify: "retain only if scorecard value justifies latency"
    blocked_by: ["K.3"]
    notes: "Deferred post-sprint resume position 3."
next_instruction:
  issued_by: "navigator"
  issued_at: "2026-08-20T16:27:30+00:00"
  packet: "K.1"
  objective: "Complete query digestion, pure BM25 re-scoring, and lexical latency work against the landed K.0 provisioning path and preserve the dual-scorecard gates."
  constraints:
    - "Strict queue: work only K.1; do not begin K.2 or K.3. Packet branches must not edit STATUS/RUNLOG, rebase, or force-push."
    - "Preserve K.0's keyless default, caller semantic configuration, ADC fail-fast/read-only mount, and disposable browser preparation. Never use a fallback semantic provider."
    - "Carry dual hermetic scorecards on the same exact head with pinned served-manifest verification and teardown. While ADC is absent, semantic is awaiting_owner and keyless evidence continues."
    - "The first post-ADC semantic scorecard must confirm hybrid >=0.68; regression reopens drift."
    - "Do not add comparator code, contact, or references. Preserve boundaries, evidence guarantees, test-count ratchet, and HD-011 disk safety."
  done_when: "K.1 exact-head review demonstrates materially improved keyless text hit@5 toward >=0.40, improved text p95, digester/BM25 tests, and the dual-scorecard guard; while ADC is absent, approval may be awaiting_owner only with the mandatory first-post-ADC hybrid >=0.68 follow-up."
last_review: REVIEW-062
drift_flags:
  - detected_at: "2026-08-20T17:23:57+00:00"
    detected_by: "sol-navigator-run"
    scope: "HD-011 root disk safety"
    status: "owner_action_required"
    detail: "Two consecutive navigator audits reported less than 10GB free on /: 9.5G at 2026-08-20T17:13:05+00:00 and 9.9G at 2026-08-20T17:23:57+00:00. No prune ran because free space remains above 5GB; only benchmark provisioning may run docker builder prune -af below 5GB, and running-stack volumes must never be pruned."
  - detected_at: "2026-08-20T09:49:42+00:00"
    detected_by: "benchmark-run"
    scope: "semantic-enabled benchmark runner"
    status: "open"
    detail: "origin/integration/roadmap-v2 advanced through c094aec, but the binding semantic-enabled scorecard could not run: ${HOME}/.gcloud-kw/application_default_credentials.json is absent in this scheduler environment. Disposable exact-head worktrees were used through c094aec; no pre-existing service was scored. Exact-head scripts/quickstart_smoke.sh still hard-requires EMBEDDING_PROVIDER=none and prints 'Starting keyless Knowledge-Way stack (EMBEDDING_PROVIDER=none)...', so it cannot satisfy HD-009/ADR-010 semantic-enabled Vertex settings. Because credentials were absent and the quickstart remains keyless-only at this head, the run paused before stack startup, pinned-corpora manifest verification, or the 25-task scorecard. The disposable worktree was torn down; no scorecard was committed."
```

The YAML block is the machine-readable source used by scheduled jobs. Packet state changes require a corresponding committed review artifact or PR evidence.
