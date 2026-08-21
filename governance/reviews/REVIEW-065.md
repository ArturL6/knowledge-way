# REVIEW-065 — K.0 stale volume-teardown update

```yaml
review_id: "REVIEW-065"
packet: "K.0-remediation"
pr: null
base: "a1ef51ae442bee29647ea52ee4dfc430ade5e69c"
head: "f4cd812f882c9c7225686faed036fe78e461d9ac"
verdict: "needs_changes"
reviewed_at: "2026-08-21T02:41:19Z"
checks:
  - "Authoritative refs independently refreshed: PASS (integration a1ef51a, main d72137f, packet head f4cd812)"
  - "Provisioning-only scope: PASS (only scripts/quickstart_smoke.sh changes; no retrieval, STATUS/RUNLOG, comparator, or future-packet code)"
  - "Exact-head shell syntax and whitespace: PASS (bash -n and git diff --check)"
  - "Current-integration ancestry: FAIL (packet head is based on 6747379 and does not contain current integration)"
  - "Current-integration mergeability: FAIL (merge simulation conflicts in scripts/quickstart_smoke.sh cleanup)"
  - "Remediation currency: FAIL (current integration already tears down the isolated project with --volumes --rmi local and preserves generated teardown configuration for --keep-running; this head carries only the older --volumes subset)"
semantic_guard: "awaiting_owner"
follow_up: "The first post-ADC semantic-enabled scorecard must run on the same exact integration head as its keyless scorecard and confirm hybrid hit@5 >=0.68; otherwise reopen drift."
next_instruction: "Close or supersede this stale K.0 branch without merging it. Strict queue remains K.1; PR #84 remains blocked under REVIEW-062 until updated evidence satisfies its findings. Do not begin K.2 or K.3."
```

## Findings

The exact head is provisioning-only and its isolated-project `--volumes` teardown is
safe in isolation, but it cannot merge into the refreshed integration head. Integration
already contains the complete K.0 teardown contract: project-scoped named-volume removal,
local project-image removal, and retention of the generated override/configuration when
`--keep-running` is requested. Merging this older one-subset patch creates a content
conflict in `cleanup()` and provides no missing behavior.

Do not rebase or force-push. Close or supersede this stale branch; there is no reason to
resolve it by replaying redundant K.0 code. K.1 remains the next queue item, with PR #84
still unchanged at its previously blocked exact head.

The owner-designated ADC file remains absent, so the semantic guard is
`awaiting_owner`; no fallback provider is permitted. Keyless evidence continues. The
first post-ADC scorecard must pair semantic and keyless evidence on the same exact
integration head and confirm hybrid hit@5 >=0.68, or drift reopens.

Root disk audit: `/dev/sda1` 75G total, 67G used, 5.6G available, 93%. This is another
consecutive audit below 10G, so the existing HD-011 owner disk drift flag remains open.
No prune ran: only the benchmark job may run builder-cache prune below 5G, and broad
system/volume pruning or pruning a running stack's volumes remains forbidden.
