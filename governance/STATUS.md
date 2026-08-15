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
    state: merge_authorized
    branch: "packet/1.1-postgres-fts"
    pr: 78
    verify: "pytest -q && lint-imports"
    blocked_by: ["0.3"]
    notes: "REVIEW-055 on_track at head 17644ae authorizes merge (HD-004). FTS + ADR-008 rare-term/DF digestion (N=50): hybrid file hit@5 0.16->0.32 (+100%), text 0.16->0.24, p95 improved vs baseline (text 1.0s, hybrid 2.2s). 102 tests, boundaries green. Merger to merge and set done. Stage-1 target hybrid hit@5 >= 0.44 (ADR-007) via later semantic/graph packets; hybrid p95<=1s deferred (symbol-pass/1.2). Pre-existing app/worker.py __main__ guard bug to be filed separately."
next_instruction:
  issued_by: "navigator (Sol)"
  issued_at: "2026-08-15T11:05:00+00:00"
  packet: "1.1"
  objective: >-
    Replace the ILIKE lexical passes in apps/api/app/search.py with Postgres
    full-text search: a code-aware tsvector (identifier splitting for
    camelCase/snake_case/dotted paths at index time) + GIN index, ts_rank_cd
    scoring, and a pg_trgm exact-substring path for quoted/config/error queries.
    Keep the SQLite ILIKE path behind a dialect branch so the portable
    test_search.py suite still runs. Land a hermetic scorecard delta showing
    lexical file hit@5 >= baseline and p95 latency down.
  constraints:
    - "Branch packet/1.1-postgres-fts from integration/roadmap-v2; NEVER rebase or force-push."
    - "New Alembic migration 20260815_0011_chunk_fts.py, down_revision 20260813_0010; FTS objects guarded to the postgresql dialect (mirror the CREATE EXTENSION vector precedent)."
    - "FTS SQL stays in app/search.py or app/adapters/outbound/postgres/*; NEVER in app.application or app.domain (import-linter contracts must stay green)."
    - "Dialect-branch search_with_capability: Postgres -> FTS/ts_rank_cd + pg_trgm exact; SQLite -> existing ILIKE fallback. Preserve the /api/search result row shape (path/symbol fields the scorecard reads)."
    - "No new billable config; keyless. No GitNexus/comparator reference in any product path (HD-007)."
    - "Full local gauntlet: uv sync, pytest, lint-imports, packet verify, and a hermetic run_retrieval scorecard delta committed to benchmarks/results/."
  done_when:
    - "pytest and lint-imports green; migration chain intact (test_migrations)."
    - "EXPLAIN shows index (GIN) scans for the FTS lexical path on Postgres."
    - "Committed scorecard shows lexical file hit@5 >= 0.16 baseline (improvement expected) with p95 latency not regressed; evidence bound to the exact PR head SHA."
    - "PR opened into integration/roadmap-v2 with evidence; pr_open set via a direct integration commit."
last_review: REVIEW-055
drift_flags: []
```

The YAML block is the machine-readable source used by scheduled jobs. Packet state changes require a corresponding committed review artifact or PR evidence.
