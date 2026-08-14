# Hermes scheduler contracts

These are the active Knowledge-Way scheduler contracts ratified by ADR-005 and
HUMAN-DIRECTIVE-003. The append-only [`RUNLOG.md`](RUNLOG.md) is the durable
heartbeat and product-LLM-spend record. All times use the Hermes scheduler timezone
(`Europe/Berlin`). Runtime scheduler configuration is owned by the project owner.

| Job | Schedule | Contract |
|---|---|---|
| `sol-navigator-run` | every 20 minutes | Reads STATUS, PLAN, directives, PRs, and reviews. It does exactly one: review a `pr_open` packet with ADR-003 re-execution and record an approving or blocking verdict; nudge an `in_progress` packet stale for over six hours; issue one PLAN-backed `next_instruction` if no PR is open; or no-op. Once per 24 hours it also performs the drift audit. It never writes application code. |
| `implementer-run` | every 20 minutes | Works only in `/home/hermes/projects/knowledge-way-roadmap-v2`. It executes only an unblocked `next_instruction` addressed to it, resolves its `review_blocked` PR, or merges only after Sol's recorded approving verdict. It runs the full local gauntlet, opens/updates a PR into integration, and never self-selects work. LLM/embedding work follows the subset-first rule and product spend pauses at USD 40 of the USD 50 cap. |
| `benchmark-run` | every 20 minutes | Does nothing until the Stage 0 retrieval harness exists. Thereafter it runs and commits the scorecard when integration changed since the prior scorecard; once packet 0.4 exists it runs our system and scripted GitNexus on the same gold tasks. A regression is written as a STATUS drift flag. It never modifies application code. |

## Instruction and merge contract

`STATUS.md` contains a nullable `next_instruction` object issued by `sol-navigator`.
An instruction identifies an unblocked PLAN packet, objective, constraints, and a
done condition. The implementer follows that instruction rather than choosing an
eligible packet. A merge requires a committed Sol reviewer verdict approving the
exact packet head and re-execution evidence required by ADR-003.

## Binding heartbeat behavior

Every tick appends a local line in this format:

```text
<ISO-8601 timestamp> | <job-name> | tick | <action taken>
```

Action ticks commit and push immediately. A no-op tick is a minimal state check; its
local heartbeat is consolidated into at most one pushed heartbeat commit per hour.
RUNLOG records estimated cumulative spend for product LLM calls only (embeddings,
cards, planner fallback, rerank, and GitNexus chat evaluation). Agent scheduler costs
do not count against the USD 50 product cap.
