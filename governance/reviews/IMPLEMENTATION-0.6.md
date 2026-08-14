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

## REVIEW-024 remediation (2026-08-14)

The reviewed root-only smoke was replaced with a functional isolated-stack proof. Before building
Next.js, the script reserves independent loopback API and web ports, injects the API URL into the
web build/runtime environment, and allows that exact web origin through the isolated API CORS
configuration. It also starts the RQ adapter's real module entry point (the legacy compatibility
module does not execute its worker loop when run as `-m`).

The new `scripts/quickstart_playwright.mjs` drives the Compose browser artifact: it uses the
repository dashboard to add `fastapi/fastapi`, pins the fixture through the public reindex endpoint
to `f336ff831c4af3d4f625c2593a27b1e0cae93eb7`, waits for a ready snapshot, searches `FastAPI`, and
opens the resulting source evidence. The exact packet verification returned:

```text
PASS API docs: http://127.0.0.1:46901/docs
PASS web UI: http://127.0.0.1:56879
PASS browser add/index/search/evidence: 0dcb822b-c95d-4b27-a06f-d9c9749b3cd0 @ f336ff831c4af3d4f625c2593a27b1e0cae93eb7
PASS keyless local quickstart smoke test
```

The complete local gauntlet after remediation returned: `uv run pytest -q` — **95 passed**;
`PYTHONPATH=apps/api uv run lint-imports` — **2 kept, 0 broken**;
`stageR_import_boundary.sh`, `stageR_uv.sh`, `stageR_evidence.sh`, and `stageR_sync_main.sh` —
**PASS**; web unit tests — **70 passed**; `npm run build` — **PASS**; existing web Playwright —
**1 passed**; and `bash -n`, `node --check`, and `git diff --check` — **PASS**. No provider call
was made, so cumulative estimated monthly LLM/embedding/card/rerank spend remains USD 0.00.

## REVIEW-025 selected-fixture remediation (2026-08-14)

The Compose-browser smoke now seeds the owner-selected permanent `fastapi-stack` rather than a
single FastAPI substitute. It pins and waits for all three public repositories, using their
immutable release commits: FastAPI 0.115.0 at
`40e33e492dbf4af6172997f4e3238a32e56cbe26`, Starlette 0.38.6 at
`8d0cff820f89b5d5b19677246293513a9d1c952c`, and Pydantic v2.9.2 at
`7cedbfb03df82ac55c844c97e6f975359cb51bb9`. It creates the workspace through the public API,
adds each repository as a member, and records the two FastAPI provider dependencies before running
the browser search/open-evidence proof.

```text
scripts/quickstart_smoke.sh                                        PASS
PASS API docs: http://127.0.0.1:41555/docs
PASS web UI: http://127.0.0.1:49175
PASS browser selected-workspace add/index/search/evidence: fastapi-stack @ 40e33e492dbf4af6172997f4e3238a32e56cbe26, starlette-stack @ 8d0cff820f89b5d5b19677246293513a9d1c952c, pydantic-stack @ 7cedbfb03df82ac55c844c97e6f975359cb51bb9; dependencies=2
PASS keyless local quickstart smoke test

uv run pytest -q                                                    PASS — 95 passed
PYTHONPATH=apps/api uv run lint-imports                             PASS — 2 kept, 0 broken
governance/checks/stageR_import_boundary.sh                        PASS
governance/checks/stageR_uv.sh                                     PASS — 95 tests
governance/checks/stageR_evidence.sh                               PASS — 12 tests
governance/checks/stageR_sync_main.sh                              PASS
(cd apps/web && npm test -- --run)                                 PASS — 70 passed
(cd apps/web && npm run build)                                     PASS
(cd apps/web && npm run test:e2e)                                  PASS — 1 Playwright test
node --check scripts/quickstart_playwright.mjs; bash -n scripts/quickstart_smoke.sh; git diff --check  PASS
```

The run uses `EMBEDDING_PROVIDER=none`, `CODE_CARDS_ENABLED=false`, and `RERANK_PROVIDER=none`;
no LLM, embedding, card, or rerank request was made. Cumulative estimated monthly spend remains
USD 0.00.
