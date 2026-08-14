# HUMAN-DIRECTIVE-006 — GitNexus comparative scorecard gate

**From:** Project owner  
**To:** sol-navigator-run, implementer-run, benchmark-run  
**Authority:** Owner directive. This is binding plan sequencing and benchmark policy. Record its durable packet and scheduler changes directly on `integration/roadmap-v2`; packet branches must not change `STATUS.md` or `RUNLOG` files.

## Trigger and packet insertion

After the currently authorized **packet 0.4 GitNexus test-drive line** (the replacement/v2 line where applicable) merges into `integration/roadmap-v2`, Sol must insert **packet 0.4b — GitNexus comparative scorecard** before any Stage 1 packet may begin.

`0.4b` is blocked by `0.4` and blocks Stage 1. Stage 1's exit bar is not final until the committed 0.4b comparative numbers exist. No Stage 1 implementation may begin while 0.4b is `todo`, `in_progress`, `pr_open`, or `review_blocked`.

## Packet 0.4b objective

Create and execute a reproducible scripted GitNexus runner against **all 25 committed gold tasks**. Score GitNexus against the exact same changed-file oracles and `hit_at_5` / `MRR` definitions used by the Knowledge-Way scorecard. Commit the generated result as:

```text
benchmarks/results/<UTC-or-commit-identifying>-gitnexus-<workspace>.json
```

The result must bind the exact task content hashes, `benchmarks/corpora.json` pinned corpus SHAs, runner command/version, per-task rankings/outcomes, aggregate file `hit_at_5` and `MRR`, and explicit unavailable/degraded reasons. It must not fabricate a metric for a query GitNexus cannot represent.

## Capability flags and environment honesty

Every comparative result records capability flags for both sides:

- **Knowledge-Way semantic:** `unconfigured` until Vertex credentials have passed the existing readiness protocol. Do not silently substitute an embedding provider.
- **GitNexus FTS:** explicitly verify the LadybugDB FTS extension download from `extension.ladybugdb.com` (and repair FTS if needed). If that download is unavailable, mark GitNexus keyword capability `keyword-degraded` with the concrete environment reason; do not call it a GitNexus product-quality result.

Retain the HD-005 constraints: license-clean behavioral evaluation only, use `eval-server` for scripted calls, resolve UIDs before trace calls, and preserve epistemic/boundary evidence where an operation supplies it.

## Ongoing scheduler rule

After packet 0.4b is done, every hermetic benchmark scorecard cycle runs **both** sides on the same pinned corpus and gold task set:

1. self-provision Knowledge-Way at the exact integration head, seed the pinned snapshots, and verify served snapshot equals pinned snapshot;
2. provision/run GitNexus against that same pinned corpus and execute the scripted runner;
3. emit one comparable result artifact per side/cycle with capability flags and the shared task/oracle binding;
4. commit results directly on integration; always tear down ephemeral resources.

The benchmark scheduler never scores either side against a pre-existing API/index. A served-vs-pinned mismatch after self-provisioning is a real drift defect. A mismatch observed on somebody else's server is noise and must not create a score or drift flag.

## Gold-task quality escalation

If GitNexus's comparable aggregate score is **below 0.2**, treat that as a **gold-task-quality flag**, not a product verdict. Record the flag, pause Stage 1 start, and have Sol review the task set/oracles before Stage 1 begins. Do not weaken or rewrite gold tasks merely to clear the threshold; any task-set correction requires independent review and rebinding of results.
