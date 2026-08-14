# REVIEW-047 — Packet 0.3 retrieval scorecard harness

```yaml
verdict: drift
packet: "0.3"
pr: 74
reviewed_head: "71328846c04cb7f1e17ec43c6eb2259e99ca9b0c"
reviewed_integration_head: "85752be30f8f45ff025ba6d9d21cc57e4383631c"
criteria_checked:
  - "Exact PR head independently fetched and checked out: PASS"
  - "Packet branch excludes STATUS and RUNLOG governance writes: PASS"
  - "python benchmarks/run_retrieval.py --help: PASS"
  - "python benchmarks/validate_tasks.py: PASS (25 tasks)"
  - "uv sync --extra dev && uv run pytest -q: PASS (95 tests)"
  - "PYTHONPATH=apps/api:apps/mcp uv run lint-imports: PASS (2 contracts)"
  - "git diff --check and current-integration merge-tree: PASS"
  - "All supported single modes plus hybrid attempted over 25 tasks: PASS"
  - "Semantic absence recorded as unconfigured under HUMAN-DIRECTIVE-005 section 3: PASS"
  - "Reproducible snapshot-bound baseline required by PLAN 0.3 and standing rule 5: FAIL"
  - "Harness failure semantics and metric logic independently testable: FAIL"
drift_findings:
  - "The committed scorecard contains no served repository IDs or indexed_commit_sha values, and the harness never captures them. The replay note merely assumes the endpoint serves the revisions in corpora.json. This cannot prove which snapshots produced the measurements and violates the instruction to commit exact snapshot evidence plus PLAN standing rule 5."
  - "configuration.task_source_sha256 hashes repeated task-source path strings rather than task contents. Gold labels or descriptions can change without changing this digest, so it is not a reproducibility identity."
  - "Every request failure is converted to status unavailable and the process still exits 0. A dead or partially failing API can therefore produce an apparently successful baseline artifact. Only explicitly expected capability absence (semantic unconfigured here) may be non-fatal; unexpected mode/task failures must fail the run."
  - "No focused harness tests cover rank metrics, aggregation, task-content identity, snapshot capture, or failure behavior. The generic suite does not execute these new paths."
required_actions:
  - "Update the harness and scorecard to capture and validate the exact served workspace/repository snapshot manifest, including repository identity and indexed_commit_sha for every repository in the selected corpus; abort on mismatch with benchmarks/corpora.json."
  - "Hash canonical task contents (or the committed task tree/blob identities), not filenames, and record the selected task set deterministically."
  - "Exit nonzero on unexpected HTTP/response failures or incomplete supported-mode coverage; preserve semantic: unconfigured as the explicit HD-005 exception."
  - "Add focused offline tests for file/symbol hit@1, hit@5 and MRR, aggregation, task digest, snapshot mismatch, and expected versus unexpected unavailability."
  - "Re-run the actual 25-task baseline after remediation, commit the replacement artifact, update the PR head, and request exact-head re-review."
scope_creep_risk: medium
merge_authorized: false
```

## Independent evidence

The review used freshly fetched refs (`integration/roadmap-v2` at
`85752be30f8f45ff025ba6d9d21cc57e4383631c`, `main` at
`d72137f4cfbf3beaf1ae392710b7da489ed1972f`) and a detached worktree at the
exact PR head. The packet diff is limited to `benchmarks/run_retrieval.py` and
one JSON scorecard. Current-integration merge simulation is clean.

The committed artifact has 125 rows (25 tasks × 5 modes). Text, exact,
symbols, and hybrid rows are `ok`; semantic rows are honestly unavailable.
Inspection found zero snapshot/workspace/repository SHA fields in result rows.
The green existing suite is insufficient to authorize merge because the
binding reproducibility and failure-semantics criteria above fail.
