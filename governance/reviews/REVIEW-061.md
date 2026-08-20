# REVIEW-061 — Packet K.0 semantic-capable quickstart provisioning

```yaml
verdict: on_track
packet: "K.0"
pr: 85
reviewed_head_sha: "6747379bc383a51882d1887621431d4fd4607a39"
reviewed_integration_head: "8e94c6da6d6f525602f1225528944dc50f0ba9e2"
semantic_guard: awaiting_owner
criteria_checked:
  - "Exact-head identity: PASS (refreshed origin packet head and GitHub PR headRefOid both 6747379bc383a51882d1887621431d4fd4607a39)"
  - "HD-011/ADR-012 provisioning-only scope: PASS (only scripts/quickstart_smoke.sh changed; no retrieval code, STATUS, RUNLOG, comparator code, or future K-packet work)"
  - "Keyless default: PASS (unset EMBEDDING_PROVIDER resolves to none; independent exact-head scripts/quickstart_smoke.sh completed API/web health and real-browser selected-workspace add/index/search/evidence flow)"
  - "Caller semantic configuration and ADC mount: PASS (embedding, Vertex project, code-card, and rerank settings are injected into the disposable API/worker project; owner ADC directory is mounted read-only only for Vertex)"
  - "ADC fail-fast and no fallback: PASS (with EMBEDDING_PROVIDER=vertex and VERTEX_PROJECT_ID=test, absent /home/hermes/.gcloud-kw/application_default_credentials.json exited 2 before Compose startup with a clear error; no provider substitution)"
  - "Disposable browser provisioning: PASS (lockfile-pinned npm ci and Chromium installation execute before the browser flow; exact-head clean-worktree smoke exercised this path)"
  - "Full Python suite and boundaries: PASS (113 passed; import-linter 2 contracts kept, 0 broken; compileall passed)"
  - "Patch hygiene and mergeability: PASS (git diff --check clean; git merge-tree --write-tree against refreshed integration produced 1ef0a620a775374b8c4737ae5f67cbe7745b0088; GitHub reports MERGEABLE)"
  - "Disk audit: PASS (/ has 14G available after review execution; no pruning threshold crossed)"
  - "Semantic scorecard: AWAITING_OWNER (the sole authorized ADC path is absent; no fallback scorecard was attempted)"
drift_findings: []
required_actions:
  - "Mandatory follow-up: the first post-ADC semantic-enabled scorecard on the landed exact integration head must confirm hybrid >=0.68; a regression reopens drift."
scope_creep_risk: low
```

## Independent execution

Review ran in detached worktree `/tmp/kw-k0-review` at the exact PR head. The
unchanged, unset-environment path built an isolated Compose stack, passed API and
web health, installed the locked web dependencies, provisioned Chromium, and
completed the real-browser selected-workspace add/index/search/evidence flow for
all three pinned repositories. Teardown completed. The Vertex path was exercised
separately and refused startup because the owner-provisioned ADC file is absent.

Per HD-011/ADR-012, the semantic guard is explicitly `awaiting_owner`; this is
not a waived score gate and no fallback provider is permitted. The first tick
after ADC appears must produce the binding semantic scorecard on the landed exact
integration head, confirm hybrid hit@5 >=0.68, or reopen drift.

PR #85 is authorized to merge **only** at exact reviewed head
`6747379bc383a51882d1887621431d4fd4607a39`. Any head change requires a new
exact-head review. GitHub review approval is not a gate.
