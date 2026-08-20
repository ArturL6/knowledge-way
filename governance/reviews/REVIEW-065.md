# REVIEW-065 — K.0 kept-stack teardown configuration

```yaml
review_id: "REVIEW-065"
packet: "K.0-remediation"
pr: 98
base: "9386aca32ad9277e13970e894d968c102471e74d"
head: "8b0f109a29c5db8916f19d2da8ad272195d26fb0"
verdict: "on_track"
reviewed_at: "2026-08-20T23:06:41Z"
checks:
  - "Authoritative refs independently refreshed: PASS (integration 9386aca, main d72137f, PR #98 head 8b0f109; GitHub head OID matched fetched exact head)"
  - "HD-011/ADR-012 provisioning-only scope: PASS (generated teardown-file lifetime fix plus same-change keyless scorecard only; no retrieval implementation, STATUS/RUNLOG, or K.1/K.2/K.3 code)"
  - "Keyless default and caller semantic configuration: PASS (unchanged; generated override and generated .env survive only explicit --keep-running so the printed project-scoped teardown command remains usable)"
  - "ADC fail-fast/read-only mount: PASS (unchanged sole owner path /home/hermes/.gcloud-kw/application_default_credentials.json; ADC absent; no fallback provider)"
  - "Disposable browser preparation: PASS (unchanged lockfile install and Chromium preparation)"
  - "Project-scoped teardown safety: PASS (normal cleanup remains project-scoped down --remove-orphans --volumes --rmi local; kept-stack owner can run the printed command before deleting its disposable worktree)"
  - "Keyless exact-change evidence: PASS (scorecard harness SHA 1e9a66b, pinned served SHAs fastapi 40e33e4 / starlette 8d0cff8 / pydantic 7cedbfb, 25 tasks, semantic honestly unconfigured)"
  - "Shell syntax and regression suite: PASS (bash -n; pytest 113 passed; import-linter 2 kept, 0 broken)"
  - "Whitespace and current-integration compatibility: PASS (git diff --check clean; no-conflict --no-commit merge simulation against refreshed integration 9386aca)"
  - "HD-011 disk audit: owner drift remains open at 7.4G available; no prune run because above 5G, and no broad or running-stack volume prune performed"
semantic_guard: "awaiting_owner"
follow_up: "The first post-ADC semantic-enabled scorecard must run on the same exact integration head as its keyless scorecard and confirm hybrid hit@5 >=0.68; otherwise reopen drift."
next_instruction: "Merge only exact head 8b0f109, then continue strict queue at K.1; do not begin K.2 or K.3."
```

## Findings

No blocking finding. The exact head fixes an operational contradiction in `--keep-running`: the script previously printed a Compose teardown command and then deleted the generated override and generated `.env` required by that command. Explicit kept-stack runs now retain those disposable files; ordinary smoke runs still remove them after project-scoped teardown. The change does not alter retrieval behavior, semantic configuration, ADC handling, browser preparation, or the keyless default.

The branch is not based on the latest integration only because benchmark/audit evidence advanced integration after its implementation commit. An independent no-commit merge simulation against `9386aca` completed without conflict. The committed scorecard is correctly bound to implementation SHA `1e9a66b`, where the script change exists, and records keyless operation with semantic unconfigured.

The semantic guard remains `awaiting_owner`: `/home/hermes/.gcloud-kw/application_default_credentials.json` is absent. No fallback is permitted. The first post-ADC scorecard must confirm hybrid hit@5 >=0.68 or reopen drift.

Root disk audit: `/dev/sda1` 75G total, 65G used, 7.4G available, 90%. The existing HD-011 owner drift remains open. No prune ran; only benchmark provisioning may run `docker builder prune -af` below 5G, and broad or running-stack volume pruning remains prohibited.
