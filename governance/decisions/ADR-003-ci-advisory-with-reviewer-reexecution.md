# ADR-003 — CI is advisory; reviewer re-execution and PLAN change control are binding

- **Status:** Accepted
- **Date:** 2026-08-13
- **Decision owner:** Knowledge-Way roadmap v2

## Context

Commit f747d25 edited PLAN.md to make CI optional/advisory without an ADR, inside packet
R.1. Editing PLAN.md directly violates the plan's own change rule ("changed only via ADR +
reviewer verdict") and, substantively, self-run local gauntlet output committed by the
implementer is self-attested evidence — the exact weakness the governance was built to
close.

## Decision

1. CI remains **optional advisory automation** (no hosted runner is assumed). The PLAN.md
   wording introduced by f747d25 is hereby ratified retroactively by this ADR.
2. **Compensating control (binding):** for every packet review, the reviewer MUST
   re-execute on the packet branch itself: (a) the packet's `verify` command,
   (b) the unit test suite, (c) import-linter once it exists (R.6). A verdict that
   relies only on implementer-committed output is invalid. Each REVIEW-NNN.md records
   the re-executed commands and their results, marked "(reviewer rerun)".
3. **PLAN change control (binding):** any diff touching `governance/PLAN.md` without an
   accompanying new ADR in the same PR is an automatic `drift` finding for `reviewer-run`
   and `drift-audit`. This rule itself may only change via ADR.

## Consequences

- Merge gate = recorded local gauntlet + reviewer re-execution + reviewer verdict.
- If a hosted CI runner becomes available later, promoting checks back to required status
  needs a new ADR superseding point 1 only.
