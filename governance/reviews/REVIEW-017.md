# REVIEW-017 — Packet R.7a main synchronization

```yaml
verdict: review_blocked
packet: "R.7a"
pr: 65
head: 1cbfb2de6480898209f73d31c34fb3b3b86cba0c
criteria_checked:
  - "Exact integration...HEAD diff inspected: PASS (47 files, +2056/-176)"
  - "Deliberate origin/main integration: PASS (origin/main is an ancestor; synchronization merge 2823ded is present)"
  - "Deleted-but-unmigrated test audit and ratchet: PASS (no deleted test files; recorded reviewer run is 85 API, 10 MCP, and 70 web unit tests)"
  - "Full relevant local gauntlet on the exact corrected implementation: PASS (lock/sync, compileall, API/MCP/web, production build, Playwright, import-linter, Stage-R checks, boundary rejection, diff-check)"
  - "fastapi-stack fixture, keyless quickstart promotion invariant, main policy, and descopes: PASS"
  - "Current binding owner provider decision: FAIL"
  - "Hosted CI absence: PASS (intentional owner decision; local evidence is the gate)"
drift_findings:
  - "ADR-004 lines 26-30 and 59-63 still select OpenRouter as the production default, contrary to the superseding owner decision."
  - "apps/api/app/config.py defaults embedding_provider and code_card_provider to openrouter. The production defaults must be Vertex AI text-embedding-005 at 768 dimensions and Vertex AI gemini-3.5-flash-lite for optional Code Cards."
  - ".env.example and IMPLEMENTATION-R.7a describe OpenRouter as the production default. The example must preserve the explicit keyless EMBEDDING_PROVIDER=none override while documenting Vertex production defaults."
required_actions:
  - "Update ADR-004 to record that the current owner decision supersedes HUMAN-DIRECTIVE-001's older OpenRouter-only wording: Vertex AI text-embedding-005 (768 dimensions) is the production embedding default; Vertex AI gemini-3.5-flash-lite is the optional Code Card default; OpenRouter remains adapter/fallback; reranking remains none; USD 50 cap/USD 40 pause remains binding."
  - "Align runtime defaults and .env.example with that decision without weakening the keyless quickstart invariant."
  - "Correct IMPLEMENTATION-R.7a and rerun/record the full relevant local gauntlet on the resulting exact head. Do not restore GitHub Actions."
scope_creep_risk: low
```

PR #65 is **review_blocked** at `1cbfb2de6480898209f73d31c34fb3b3b86cba0c`. The block is a concrete production configuration and binding-decision mismatch, not a paperwork-only objection. Quickstart execution remains a Stage-R promotion invariant owned by packet 0.6 and is not an independent R.7a block.