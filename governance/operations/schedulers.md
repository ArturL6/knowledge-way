# Hermes scheduler contracts

These are the active Knowledge-Way scheduler contracts ratified by ADR-005. The
append-only per-job heartbeat files (`RUNLOG-implementer.md`,
`RUNLOG-sol-navigator.md`, and `RUNLOG-benchmark.md`) are the durable record.
All times use the Hermes scheduler timezone (`Europe/Berlin`).

## Conflict-resistant governance writes

`governance/operations/RUNLOG*.md` uses Git's `union` merge driver through
`.gitattributes`. Packet branches must not modify `governance/STATUS.md` or any
RUNLOG file. The acting scheduler commits packet-state transitions and its own
heartbeats directly on `integration/roadmap-v2`; packet PRs contain only their
packet implementation/evidence. This preserves both concurrent job histories
without making a packet rebase depend on mutable governance state.

| Job | Scheduler job ID | Exact schedule | Contract |
|---|---|---|---|
| `sol-navigator-run` | runtime configured | `every 20m` | Sol reads STATUS, PLAN, open PRs, and reviews. It reviews a `pr_open` packet with re-execution and a verdict, nudges stale in-progress work, or writes one PLAN-traceable `next_instruction`. It runs the drift audit every 24 hours and never writes application code. |
| `implementer-run` | runtime configured | `every 20m` | Works only in `/home/hermes/projects/knowledge-way-roadmap-v2`. It executes one addressed, unblocked instruction, resolves its review-blocked PR, merges only after an approving verdict, or no-ops. It never self-selects packets. |
| `benchmark-run` | runtime configured | `every 20m` | Runs only hermetic scorecards when integration changes: self-provisions an ephemeral keyless stack at the exact integration SHA, seeds pinned corpus snapshots, verifies served==pinned, commits results, then tears down. It never scores a pre-existing API. After packet 0.4b is done, each cycle runs both Knowledge-Way and GitNexus on the same 25-task/oracle binding and records capability flags (Vertex semantic readiness; LadybugDB FTS availability). See [hermetic benchmark runs](hermetic-benchmark-runs.md) and [HD-006](../directives/HUMAN-DIRECTIVE-006.md). |

## Binding heartbeat behavior

Each job appends a concise line for a tick that takes action:

```text
<ISO-8601 timestamp> | <job-name> | tick | <action taken>
```

Action ticks push immediately. No-op ticks are recorded locally but are pushed in
at most one consolidated heartbeat commit per hour. Product LLM calls additionally
record cumulative estimated USD spend; at USD 40, LLM-consuming packets pause.

## Superseded-PR closure rule

When the navigator's review verdict on a PR is **"close without merge"** because
the work is superseded or obsolete, the implementer closes that PR unmerged on
its next tick, records the closure in RUNLOG, and deletes its branch. This is an
authorized housekeeping action under case (c) of the implementer contract and
does not require another review. The navigator skips a PR it has already
verdict-marked for closure as non-actionable.
