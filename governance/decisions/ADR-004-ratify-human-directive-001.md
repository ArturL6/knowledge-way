# ADR-004 — Ratify HUMAN-DIRECTIVE-001

- **Status:** Accepted
- **Date:** 2026-08-13
- **Decision owner:** Project owner
- **Authority:** HUMAN-DIRECTIVE-001, committed at `governance/directives/HUMAN-DIRECTIVE-001.md`

## Context

The owner has set final inputs for the roadmap's execution order, benchmark fixtures,
provider policy, local testability, budget boundary, and deferred hardening. The governing
product goal remains unchanged: evidence-backed multi-repository project intelligence that
measurably reduces coding-agent exploratory work, evaluated through Stage 0 and Stage 4.

This ADR converts the owner directive into governed execution decisions. It does not alter
PLAN.md directly and leaves ADR-003 PLAN change control in force.

## Decisions

1. **Benchmark workspaces.** Stages 0–2 use public `fastapi-stack`: `fastapi/fastapi`
   (consumer), `encode/starlette` (framework provider), and `pydantic/pydantic` (models
   provider). Stage 3.2 adds `PostHog/posthog` and `PostHog/posthog-js` only when the
   HTTP-contract extractor is ready. The PostHog pair must not be indexed earlier.
   Gold tasks are mechanically derived from 25–40 closed issue / merged-fix-PR pairs in
   the primary repositories; Sol validates a random sample of ten.
2. **Providers and budget.** The production defaults are Vertex AI
   `text-embedding-005` (768 dimensions) for embeddings and Vertex AI
   `gemini-2.5-flash-lite` for optional code cards. OpenRouter remains an available
   adapter/fallback, not the default. Reranking remains `none` until packet 1.8 demonstrates
   a measured benefit. The existing OpenRouter/Vertex adapters remain sufficient.
   The monthly LLM budget cap is USD 50. Each LLM-using run records cumulative estimated
   spend in RUNLOG. At USD 40, LLM-consuming packets pause and STATUS records a drift flag;
   deterministic packets may continue. Provider/model changes require an ADR that states
   the complete re-embedding cost.
3. **Local quickstart invariant.** Packet 0.6 supplies a keyless quickstart with
   `EMBEDDING_PROVIDER=none`, Docker Compose startup, a `fastapi-stack` seed/index command,
   API-doc and UI URLs, and a clean-machine scripted verification that includes search and
   Playwright smoke. Every future stage exit requires the quickstart verification on the
   promoted integration head.
4. **Main and Stage R.** `main` is frozen for feature work; it receives only stage
   promotions and labeled `hotfix/*` branches, which must merge back to integration within
   one tick. R.7a synchronizes `origin/main` into integration before Stage R exits, runs the
   full gauntlet, and enforces a test-count ratchet: deleted tests that are not migrated are
   drift. R.7a is conflict-sensitive and is planned before being executed on a full two-hour
   implementer tick.
5. **Scope priority.** Running, measured software takes priority over hardening. Until the
   Stage 4 verdict, defer 5.4 operations/auth/logging hardening, Zoekt (5.2), SCIP (5.3),
   and Stage 6 UI work beyond the quickstart. Keep the existing UI working through its smoke
   test. Stages 0–4 and basic incremental indexing (5.1) remain in scope.
6. **GitNexus.** Packet 0.4 evaluates GitNexus locally against `fastapi-stack`; use no-key
   core indexing/graph/search capability and do not copy PolyForm Noncommercial code. BYOK
   OpenRouter is allowed only for its chat-agent answers. Stage 4 records a GitNexus parity
   table.
7. **Cadence.** Autonomous implementer/reviewer cadence is two-hourly. Idle reviewer and
   promotion jobs remain silent; they do not produce user-facing no-work notifications.

## Consequences

- STATUS adds R.7a as the Stage-R-exit blocker and Stage 0 packets 0.1–0.6.
- `.env.example` retains `EMBEDDING_PROVIDER=none` as the zero-key quickstart default while
  documenting the production OpenRouter decision.
- Reviewer checks this ADR against HUMAN-DIRECTIVE-001 substantively, enforces the quickstart
  and test-count ratchet, and rejects descoped hardening as scope drift.
