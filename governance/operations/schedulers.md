# Hermes scheduler contracts

These are the active Knowledge-Way scheduler contracts. The append-only
[`RUNLOG.md`](RUNLOG.md) is the durable heartbeat record. All times use the Hermes
scheduler timezone (`Europe/Berlin`).

| Job | Scheduler job ID | Exact schedule | Contract |
|---|---|---|---|
| `implementer-run` | `dc21e8d234ae` | `every 120m` | Works only in `/home/hermes/projects/knowledge-way-roadmap-v2`; syncs `main` into integration, selects the lowest eligible packet, implements only that packet, records a local gauntlet, opens/updates a PR into integration, and never merges. It stops for `drift_flags`. |
| `reviewer-run` | `11110c170694` | `every 120m` | Codex Sol high independently reviews every `pr_open` packet against `PLAN.md`, re-executes verify and unit tests on the packet branch, commits an append-only `REVIEW-NNN.md` verdict, and never merges. |
| `drift-audit` | `e742b46675e8` | `0 9 * * 1` | Codex Sol high performs a read-only weekly audit of integration/current packet scope, branch freshness, boundary/dependency drift, scorecards, and STATUS consistency. |
| `benchmark-run` | `df479074a062` | `0 10 * * 1` | Runs the Stage 0 retrieval harness against integration when its corpus and harness exist; otherwise records that Stage 0 prerequisites are absent. |
| `approved-promotion` | `5ea7228f47d0` | `every 120m` | A separate merge-only agent re-verifies an eligible packet and merges it into integration only after a committed Sol-high `on_track` verdict and green local evidence. |

## Binding heartbeat behavior

Before any other action, each of the four roadmap jobs (`implementer-run`,
`reviewer-run`, `drift-audit`, `benchmark-run`) appends and pushes exactly one line:

```text
<ISO-8601 timestamp> | <job-name> | tick | <action taken>
```

The configured prompts require that behavior. `approved-promotion` is deliberately
not one of the four R.1 jobs and is not part of the R.1 heartbeat criterion.
