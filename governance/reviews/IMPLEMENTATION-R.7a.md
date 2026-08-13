# Implementation evidence — R.7a main synchronization

## Scope

- **Packet:** R.7a — Synchronize `origin/main` into integration
- **Branch:** `packet/R.7a-sync-main`
- **Synchronization commit:** `2823ded86403e8391727a44dd1c2ed53afbb786d`
- **Main parent:** `0954b41`; **integration parent:** `3ef3937`

`origin/main` was deliberately merged into the integration-based packet branch. Conflicts in the FastAPI composition/model/migration paths and web package manifests were resolved by retaining the roadmap hexagonal route adapter and the main-line endpoint/graph behavior. The evidence migration now descends from main's `20260810_0010` revision, all test fixtures create the mandatory evidence rows, and the repository-card endpoint remains available.

## Test-count ratchet

| Ref | Tracked API/web test files | API pytest collection |
|---|---:|---:|
| integration merge parent (`HEAD^1`) | 14 | not collected separately |
| main merge parent (`HEAD^2`) | 19 | not collected separately |
| synchronized candidate | 21 | 84 tests |

The candidate exceeds both parents' tracked test-file count and restores the requested approximately-80 test collection ratchet (84 collected).

## Corrected implementation and local gauntlet

**Corrected implementation SHA:** `42e8a10c8df44ab1ecbe2fca5e8081aa9d7a8163`

This correction makes ADR-004, runtime defaults, and `.env.example` conform to
HUMAN-DIRECTIVE-001: production embeddings are OpenRouter
`openai/text-embedding-3-small` (1536 dimensions), production code cards use the existing
OpenRouter card model, and reranking remains `none`. The keyless example still explicitly sets
`EMBEDDING_PROVIDER=none`. It also replaces deleted `requirements.txt` CI installs with the
locked root `uv` project and runs the web production build in CI.

```text
uv lock --check                                                       PASS — 75 packages resolved
uv sync --extra mcp --extra dev --frozen                              PASS
python3 -m compileall -q apps/api/app apps/api/tests apps/mcp        PASS
uv run pytest apps/api/tests -q                                       PASS — 85 passed
uv run pytest apps/mcp/tests -q                                       PASS — 10 passed
(cd apps/web && npm test -- --run)                                    PASS — 70 passed
(cd apps/web && npm run build)                                        PASS
(cd apps/web && npm run test:e2e)                                     PASS — 1 Playwright test
PYTHONPATH=apps/api uv run lint-imports                               PASS — 2 kept, 0 broken
governance/checks/stageR_evidence.sh                                 PASS — 12 passed
governance/checks/stageR_import_boundary.sh                          PASS — deliberate violation rejected; HEAD passes
git diff --check                                                      PASS
```

The test-count ratchet is preserved and increased: API collection is now 85 tests (from the
recorded 84); MCP remains 10 and web unit tests remain 70. `ruff` and a type checker are not
configured in the locked project environment; the configured import-boundary static check passes.
No LLM, embedding, or card-provider call was made, so no spend was incurred.

## Quickstart

Packet 0.6 owns `scripts/quickstart_smoke.sh`; it does not yet exist and is explicitly blocked by R.7a. Therefore a keyless quickstart cannot honestly be executed in this packet. R.7a retains the Stage-R exit gate: packet 0.6 must supply and pass it before any Stage-R promotion.
