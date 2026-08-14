# Implementation evidence — 0.6 local quickstart v1

## Scope

- **Packet:** 0.6 — Local quickstart v1
- **Branch:** `packet/0.6-local-quickstart`
- **Base:** `integration/roadmap-v2` at `8ce8364`
- **LLM/embedding/card spend:** USD 0.00 (the quickstart enforces no provider calls)

`scripts/quickstart_smoke.sh` starts an isolated Compose project on ephemeral loopback API/web ports. It copies `.env.example` only when needed, requires `EMBEDDING_PROVIDER=none`, `CODE_CARDS_ENABLED=false`, and `RERANK_PROVIDER=none`, probes API docs and the web UI, then removes the generated `.env` and Compose project unless `--keep-running` is selected. `.dockerignore` keeps local environments, caches, data, and frontend artifacts out of image build contexts. The quickstart exercised and exposed a pre-existing container startup path defect: migration readiness calculated `alembic.ini` relative to the PostgreSQL adapter rather than the API root. The adapter now resolves the API-level configuration deterministically, so the migrated keyless API can start.

## Local gauntlet and packet verification

```text
uv run pytest -q                                                    PASS — 95 passed
PYTHONPATH=apps/api uv run lint-imports                             PASS — 2 kept, 0 broken
governance/checks/stageR_import_boundary.sh                        PASS — deliberate violation rejected; HEAD passes
governance/checks/stageR_uv.sh                                     PASS — lock check and 95 tests
governance/checks/stageR_evidence.sh                               PASS — 12 tests; edge/evidence invariant
governance/checks/stageR_sync_main.sh                              PASS — main contained; R.7a done
(cd apps/web && npm test -- --run)                                 PASS — 70 passed
(cd apps/web && npm run build)                                     PASS
(cd apps/web && npm run test:e2e)                                  PASS — 1 Playwright test
bash -n scripts/quickstart_smoke.sh && git diff --check             PASS
scripts/quickstart_smoke.sh                                        PASS — API docs and web UI returned HTTP 200
                                                                  API http://127.0.0.1:32780/docs
                                                                  web http://127.0.0.1:32781
```

The direct quickstart run built the API, worker, migration, and web images; created an isolated Postgres volume/network; ran migrations; passed both HTTP probes; and cleaned up the generated `.env` afterward. It made no LLM, embedding, card, or rerank request.
