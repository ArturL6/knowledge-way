# Hermes scheduler contracts

These are the active Knowledge-Way scheduler contracts ratified by ADR-005. The
append-only [`RUNLOG.md`](RUNLOG.md) is the durable heartbeat record. All times
use the Hermes scheduler timezone (`Europe/Berlin`).

| Job | Scheduler job ID | Exact schedule | Contract |
|---|---|---|---|
| `sol-navigator-run` | runtime configured | `every 20m` | Sol reads STATUS, PLAN, open PRs, and reviews. It reviews a `pr_open` packet with re-execution and a verdict, nudges stale in-progress work, or writes one PLAN-traceable `next_instruction`. It runs the drift audit every 24 hours and never writes application code. |
| `implementer-run` | runtime configured | `every 20m` | Works only in `/home/hermes/projects/knowledge-way-roadmap-v2`. It executes one addressed, unblocked instruction, resolves its review-blocked PR, merges only after an approving verdict, or no-ops. It never self-selects packets. |
| `benchmark-run` | runtime configured | `every 20m` | After the Stage 0 harness exists, runs it when integration changes and commits results. Once scripted, it compares GitNexus on identical tasks and flags regressions for Sol. |

## Binding heartbeat behavior

Each job appends a concise line for a tick that takes action:

```text
<ISO-8601 timestamp> | <job-name> | tick | <action taken>
```

Action ticks push immediately. No-op ticks are recorded locally but are pushed in
at most one consolidated heartbeat commit per hour. Product LLM calls additionally
record cumulative estimated USD spend; at USD 40, LLM-consuming packets pause.
