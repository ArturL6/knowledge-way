# REVIEW-064 — K.0 disposable project image teardown

```yaml
review_id: "REVIEW-064"
packet: "K.0-remediation"
pr: 91
base: "981529c2560ba9308dc338341bf114f3646dcc4d"
head: "b5745d38ca31db51c76c92b6f9fdbfe21b0c86ae"
verdict: "on_track"
reviewed_at: "2026-08-20T19:01:47Z"
checks:
  - "Authoritative refs independently refreshed: PASS (integration 981529c, main d72137f, PR #91 head b5745d3; GitHub head OID matched fetched exact head)"
  - "HD-011/ADR-012 provisioning-only scope: PASS (one-line scripts/quickstart_smoke.sh teardown change only; no retrieval, STATUS/RUNLOG, comparator, or K.1/K.2/K.3 code)"
  - "Keyless default and caller semantic configuration: PASS (unchanged EMBEDDING_PROVIDER=none default and caller-provided Vertex settings)"
  - "ADC fail-fast/read-only mount: PASS (unchanged sole ADC path /home/hermes/.gcloud-kw/application_default_credentials.json and read-only mount; no fallback provider)"
  - "Disposable browser preparation: PASS (unchanged lockfile npm install and Chromium preparation)"
  - "Project-scoped image teardown: PASS (Compose down adds --rmi local to existing isolated project down --remove-orphans --volumes; it cannot target another project or running stack's volumes)"
  - "HD-011 prune safety: PASS (no builder/system/volume prune introduced or run; root had 8.4G available, above the benchmark-only 5G builder-prune threshold)"
  - "Shell syntax: PASS (bash -n on exact-head script)"
  - "Regression suite: PASS (uv run pytest -q: 113 passed)"
  - "Whitespace and mergeability: PASS (git diff --check clean; refreshed integration is an ancestor of exact head; GitHub reports MERGEABLE)"
semantic_guard: "awaiting_owner"
follow_up: "The first post-ADC semantic-enabled scorecard must run on the same exact integration head as its keyless scorecard and confirm hybrid hit@5 >=0.68; otherwise reopen drift."
next_instruction: "After this provisioning-only remediation, continue strict queue at K.1; do not begin K.2 or K.3."
```

## Findings

No blocking finding. The exact head changes only disposable quickstart teardown from
`docker compose down --remove-orphans --volumes` to the same project-scoped command
with `--rmi local`. This closes the observed per-run image leak without broad pruning
and preserves the existing stack, fixture-volume, keyless, Vertex ADC, and browser
contracts. Because the Compose project name is unique per run, local images and named
volumes selected by teardown belong to that disposable project; no running unrelated
stack or volume is selected.

The semantic guard remains `awaiting_owner`: the owner-designated ADC file is absent.
No fallback is permitted. Keyless evidence continues, and every K review retains the
condition that the first post-ADC scorecard must confirm hybrid hit@5 >=0.68 or reopen
drift.

Root disk audit: `/dev/sda1` 75G total, 64G used, 8.4G available, 89%. The existing
owner disk drift flag remains open after consecutive audits below 10G. No prune ran;
only benchmark provisioning may run `docker builder prune -af` below 5G, and neither
`docker system prune --volumes` nor pruning a running stack's volumes is allowed.
