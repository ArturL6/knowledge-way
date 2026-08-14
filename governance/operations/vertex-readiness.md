# Vertex credential readiness protocol

**Status:** awaiting owner-provisioned `VERTEX_PROJECT_ID` and application-default
credentials (ADC). Vertex is **not configured** until the verification below is
recorded as passing.

## One-time verification

When the environment variables and ADC appear, the implementer runs a minimal
HD-003 subset probe before any corpus embedding:

1. Embed **no more than 10 chunks** with `text-embedding-005`.
2. Verify every returned vector is 768 dimensional.
3. Record the command/context, chunk count, result, any failure, and approximate
   cost (expected to be cents) in this file and RUNLOG.
4. Do not perform full-corpus embedding unless this verification passes.

## Packet rules

- Packet 0.3 always runs its scorecard. Without verified Vertex it reports
  `semantic: unconfigured`; after verification it reruns semantic scoring and
  commits that result as the binding pre-Stage-1 baseline.
- Stage 1's relative-improvement exit criterion compares with the semantic
  baseline, never the degraded unconfigured baseline.
- Packet 1.4 and every embedding-generating packet hard-pause and flag the
  owner when credentials are absent or unverified. They never silently use a
  fallback provider.
- The default local quickstart remains keyless with
  `EMBEDDING_PROVIDER=none` and is unaffected by this protocol.

## Verification record

_No probe has been run: credentials were not present at ratification._
