# ADR-005 — Ratify HUMAN-DIRECTIVE-003

- **Status:** Accepted
- **Date:** 2026-08-14
- **Decision owner:** Project owner
- **Authority:** `governance/directives/HUMAN-DIRECTIVE-003.md`

## Context

HUMAN-DIRECTIVE-003 replaces the former four-job, packet-selecting automation
with a state-based loop. It preserves ADR-003 PLAN change control and the
evidence-backed, multi-repository product goal. It also clarifies that the
product-LLM budget does not include scheduler-agent execution costs.

## Decisions

1. The only roadmap schedulers are `sol-navigator-run`, `implementer-run`, and
   `benchmark-run`; each runs every 20 minutes. Retire the former
   `reviewer-run`, `drift-audit`, and separate promotion contracts. The
   navigator reviews and authorizes merges; the implementer performs a merge
   only after its recorded approving verdict.
2. Sol is the navigator. It writes a PLAN-traceable `next_instruction` in
   STATUS for the implementer, reviews a `pr_open` packet by re-executing its
   evidence, writes a verdict, nudges stale work, and performs the drift audit
   at least every 24 hours. It never writes application code.
3. The implementer performs exactly one state-selected action: execute an
   unblocked addressed instruction, resolve its blocked PR, merge after an
   approving verdict, or no-op. It never self-selects work or merges without
   that verdict.
4. The benchmark scheduler runs the Stage 0 scorecard after integration
   changes, commits results, compares the scripted external comparator result once that
   runner exists, and records regressions for Sol.
5. Any LLM- or embedding-changing packet must first use one repository or the
   smallest binding limit of 200 files, 500 chunks, or 50 cards. Its committed
   evidence includes samples, failure rate, measured cost, and linear full-run
   cost extrapolation. Full-corpus processing waits for that evidence and Sol's
   review. Deterministic indexing is exempt.
6. The USD 50 cap and USD 40 pause govern product LLM calls only. Such calls
   record cumulative estimated spend in RUNLOG; scheduler-agent costs are not
   charged to this cap.
7. Automation continues through the roadmap without owner intervention except
   for the directive channel, drift brake, budget pause, credential stop,
   failing gold-task validation, and the Stage 4 owner go/no-go. The first
   owner-testable milestone is keyless quickstart plus an indexed fastapi-stack
   and working search/graph surfaces.

## Consequences

- PLAN and scheduler contracts use the three-job, 20-minute topology.
- STATUS contains a nullable `next_instruction` contract and has no stale
  drift flags at ratification.
- RUNLOG remains append-only, but no-op heartbeats are consolidated into at
  most one push per hour; action ticks push immediately.
- HUMAN-DIRECTIVE-003 supersedes incompatible earlier scheduler cadence and
  self-selection language.
