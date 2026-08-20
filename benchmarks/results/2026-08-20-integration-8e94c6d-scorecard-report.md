# K.1→K.3 scorecard — integration 8e94c6d — 2026-08-20

Verified integration head: `8e94c6da6d6f525602f1225528944dc50f0ba9e2` (origin/main `d72137f`).

Preflight per HUMAN-DIRECTIVE-011/ADR-012: `/` had 19,570,812 KiB free (>5 GiB), so no Docker builder prune was required before disposable provisioning. ADC guard checked `/home/hermes/.gcloud-kw/application_default_credentials.json`: absent (`adc_exit=1`). K.0 semantic-capable quickstart is not on `origin/integration/roadmap-v2` (it remains on branch `packet/K.0-semantic-quickstart-provisioning`), so no semantic-enabled Vertex run was attempted and no fallback provider was used.

## Scorecard — keyless hermetic retrieval

Artifact: `benchmarks/results/2026-08-20-integration-8e94c6d-keyless-scorecard.json`

- Stack: isolated Docker Compose project `knowledge-way-quickstart-2104332058`, exact-head disposable worktree, `.env.example` keyless profile (`EMBEDDING_PROVIDER=none`, `CODE_CARDS_ENABLED=false`, `RERANK_PROVIDER=none`).
- Validation before scoring: `python3 benchmarks/validate_tasks.py` (`VALID: 25 provenance-backed gold tasks`), `python3 benchmarks/scripts/validate.py` (`VALID`), `python3 benchmarks/scripts/validate_fork_realism.py` (`VALID`).
- Quickstart smoke passed API docs, web UI, and browser selected-workspace add/index/search/evidence flow.
- Served pins verified from the scorecard manifest:
  - FastAPI `40e33e492dbf4af6172997f4e3238a32e56cbe26`
  - Starlette `8d0cff820f89b5d5b19677246293513a9d1c952c`
  - Pydantic `7cedbfb03df82ac55c844c97e6f975359cb51bb9`

Result summary:

| mode | status | file MRR | file hit@5 | p50 ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: |
| text | ok | 0.131333 | 0.24 | 805.114 | 1096.077 |
| hybrid | ok | 0.131111 | 0.24 | 2026.043 | 2964.270 |
| symbols | ok | 0.004853 | 0.00 | 1298.933 | 2051.310 |
| exact | ok | 0.000000 | 0.00 | 497.620 | 802.874 |
| semantic | unavailable | n/a | n/a | n/a | n/a |

Semantic status: unavailable as expected in the keyless run (`semantic: unconfigured`). This is not a semantic scorecard.

## Teardown

Removed only the disposable stack resources for `knowledge-way-quickstart-2104332058` (containers, network, postgres volume, project images) and ran `docker image prune -af --filter until=24h` (reclaimed `0B`). Root-owned indexed-repository files left by the container in the disposable worktree required a root-in-container cleanup; the worktree was then removed. No pre-existing service was scored.
