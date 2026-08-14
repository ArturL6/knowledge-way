# ADR-005 — Ratify HUMAN-DIRECTIVE-003

- **Status:** Accepted
- **Date:** 2026-08-14
- **Decision owner:** Project owner
- **Authority:** HUMAN-DIRECTIVE-003, committed at `governance/directives/HUMAN-DIRECTIVE-003.md`

## Context

The owner replaces the prior four-job autonomous layout with state-based navigation:
Sol decides the next PLAN-backed packet, Hermes implements only an issued instruction,
and benchmark execution follows changes to integration. This preserves ADR-003 change
control and the existing packet/reviewer gate while removing self-selection by the
implementer.

## Decisions

1. **Exactly three jobs.** `sol-navigator-run`, `implementer-run`, and `benchmark-run`
   run every 20 minutes. The prior reviewer, drift-audit, and promotion jobs are retired;
   review and merge authorization are responsibilities of Sol within the navigator contract.
2. **Navigator instruction contract.** Sol reads PLAN, directives, STATUS, PRs, and reviews
   and records one `next_instruction` in STATUS for an unblocked PLAN packet. The
   implementer never self-selects a packet. Sol reviews `pr_open` work with ADR-003
   re-execution, writes the verdict, and is the required merge approver.
3. **Autonomy and gates.** The loop continues through the planned stages without owner
   interaction except for the stated stopping conditions: two consecutive same-topic drift
   verdicts, product-LLM spend reaching USD 40 of the USD 50 cap, unavailable Vertex
   credentials for embedding work, failed gold-task validation, or the owner Stage-4
   go/no-go decision. Only numbered committed directives bind owner decisions.
4. **Small subset first.** Any LLM or embedding change first runs on one repository or the
   tighter cap of 200 files, 500 chunks, or 50 cards. Evidence records output samples,
   failure rate, measured cost, and linear full-corpus extrapolation. Full-corpus work waits
   for committed subset evidence and Sol visibility; deterministic indexing is exempt.
5. **Automated comparative benchmarking.** Packet 0.3 supplies the retrieval harness;
   benchmark-run executes it after integration changes. Packet 0.4 supplies a scripted,
   headless GitNexus comparison runner over the same gold tasks without copying PolyForm
   Noncommercial code. Regressions become STATUS drift flags.
6. **Heartbeat and budget records.** No-op ticks append local RUNLOG heartbeats but push no
   more than one consolidated heartbeat commit per hour; action ticks push immediately.
   Product LLM calls record estimated cumulative USD spend in RUNLOG. Agent-loop cost is
   reported by Sol's daily drift audit but does not consume that product budget.

## Consequences

- PLAN and scheduler operations documentation use the three-job, 20-minute topology.
- STATUS has a nullable `next_instruction` field and no stale drift flags at ratification.
- The first navigator instruction is expected to be packet 0.1, followed by eligible
  parallel-capable packets under the existing dependency graph.
