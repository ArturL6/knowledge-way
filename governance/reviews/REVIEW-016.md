# REVIEW-016 — Packet R.7a main synchronization

```yaml
verdict: blocked
packet: "R.7a"
pr: 65
head: 1cbfb2de6480898209f73d31c34fb3b3b86cba0c
criteria_checked:
  - "Exact integration...HEAD diff inspected: PASS (47 files, +2056/-176; diff-check clean)"
  - "Deliberate origin/main integration: PASS (origin/main and origin/integration/roadmap-v2 are ancestors; merge 2823ded has integration and main parents)"
  - "Deleted-but-unmigrated test audit: PASS (no deleted test files; candidate has 21 tracked API/web test files versus integration 14 and main 19)"
  - "Test-count ratchet: PASS (reviewer collected and ran 85 API tests; 10 MCP tests and 70 web unit tests also passed)"
  - "Full relevant local gauntlet: PASS (uv lock/sync, compileall, API/MCP/web tests, web production build, Playwright smoke, import-linter, Stage-R evidence, deliberate boundary rejection, and diff-check)"
  - "fastapi-stack fixtures, keyless quickstart Stage-R promotion invariant, main policy, and descopes: PASS"
  - "Current binding owner provider decision: FAIL (ADR-004 and production runtime defaults select OpenRouter; current owner decision requires Vertex AI text-embedding-005 at 768 dimensions and optional Vertex AI gemini-3.5-flash-lite cards)"
  - "Hosted CI policy: PASS (GitHub Actions removal is intentional and is not a gate; exact local evidence is green)"
drift_findings:
  - "ADR-004 lines 26-30 and consequences still encode the superseded OpenRouter-first policy. The current binding owner decision supersedes HUMAN-DIRECTIVE-001 section 2: production embeddings must default to Vertex AI text-embedding-005 with 768 dimensions; optional Code Cards must default to Vertex AI gemini-3.5-flash-lite. OpenRouter remains an adapter/fallback, reranking remains none, and USD 50 cap/USD 40 pause controls remain binding."
  - "apps/api/app/config.py and .env.example likewise set production embedding/card defaults to OpenRouter. This is a runtime configuration mismatch, not paperwork-only drift. The keyless quickstart must still explicitly override EMBEDDING_PROVIDER=none."
required_actions:
  - "Update ADR-004 to state the current owner decision: Vertex AI text-embedding-005 (768 dimensions) production embedding default; Vertex AI gemini-3.5-flash-lite optional Code Card default; OpenRouter adapter/fallback; reranking none; USD 50 cap and USD 40 pause. Explicitly note that this supersedes HUMAN-DIRECTIVE-001's older OpenRouter-only wording."
  - "Align apps/api/app/config.py and .env.example production defaults with that decision while preserving the explicit keyless quickstart override EMBEDDING_PROVIDER=none."
  - "Re-run and record the same full relevant local R.7a gauntlet on the corrected exact head. Do not add hosted CI; its intentional absence is not a block. Quickstart execution remains the Stage-R promotion invariant owned by packet 0.6, not an independent R.7a packet block."
scope_creep_risk: low
```
