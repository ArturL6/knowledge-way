# REVIEW-063 — K.0 quickstart teardown remediation

```yaml
verdict: on_track
packet: "K.0-remediation"
pr: 87
reviewed_head_sha: "c33381326c485f88d671cdc41c835559d522efae"
reviewed_integration_head: "350ae1fb341b58f64f7d6e3d35f49afd5c26c407"
semantic_guard: awaiting_owner
criteria_checked:
  - "Exact-head identity: PASS (freshly fetched PR ref and GitHub headRefOid both c33381326c485f88d671cdc41c835559d522efae)"
  - "HD-011/ADR-012 provisioning-only scope: PASS (only scripts/quickstart_smoke.sh changes; no retrieval, STATUS/RUNLOG, comparator, or K.1/K.2/K.3 code)"
  - "Keyless default and browser flow: PASS (independent exact-head quickstart completed API/web health and real-browser selected-workspace add/index/search/evidence flow with EMBEDDING_PROVIDER=none)"
  - "Caller semantic configuration and ADC safety: PASS (Vertex configuration remains caller-provided, owner ADC mount remains read-only, and absent ADC independently failed before stack startup with exit 2)"
  - "Disposable fixture storage and teardown: PASS (project-scoped quickstart-data volume replaced checkout bind mounts; Compose down --volumes targets only the isolated project; exact project containers, volumes, and network were absent after teardown; checkout remained clean)"
  - "HD-011 disk safety: PASS (no broad prune command introduced or run; root had 9.5G available after execution, first consecutive daily audit below 10G, above the 5G benchmark prune threshold)"
  - "Focused/full verification: PASS (bash -n, git diff --check, 113 pytest tests, and import-linter 2 kept/0 broken)"
  - "Current integration compatibility: PASS (PR is mergeable on refreshed integration head 350ae1f)"
  - "Semantic scorecard: AWAITING_OWNER (authorized ADC path absent; no fallback provider used)"
drift_findings: []
required_actions:
  - "Merge only exact reviewed head c33381326c485f88d671cdc41c835559d522efae; any head change requires a fresh independent review."
  - "Keep semantic_guard=awaiting_owner while /home/hermes/.gcloud-kw/application_default_credentials.json is absent; never use a fallback provider. The first post-ADC semantic-enabled scorecard must confirm hybrid >=0.68 or reopen drift."
  - "Continue strict queue at K.1 after this K.0 teardown remediation; do not begin K.2 or K.3."
scope_creep_risk: low
```

## Independent execution

Review ran from a detached disposable worktree at exact PR head
`c33381326c485f88d671cdc41c835559d522efae`, fetched independently from PR #87.
The unchanged keyless default provisioned an isolated stack and completed the
real-browser selected-workspace add/index/search/evidence flow. Teardown removed
the exact project's containers, both named volumes, and network; no checkout
residue remained. The project-scoped `down --volumes` operation is permitted
resource teardown, not the prohibited broad volume-prune behavior.

The Vertex invocation independently exited 2 before startup because the sole
authorized ADC file is absent. Semantic verification therefore remains
`awaiting_owner`, without fallback or waiver. The first post-ADC scorecard must
confirm hybrid >=0.68 or reopen drift.
