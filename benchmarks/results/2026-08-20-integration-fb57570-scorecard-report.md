# K.1→K.3 scorecard — integration fb57570 — 2026-08-20

Verified integration head: `fb5757061df8b84002acd4d774f740833d4504c7`.
Pinned manifest was checked before scoring with `python3 benchmarks/scripts/validate.py` and `python3 benchmarks/scripts/validate_fork_realism.py` (`VALID`, `VALID`). The isolated disposable stack indexed only the pinned fastapi-stack repositories at their manifest commits.

## Scorecard 1 — keyless K-packet exit co-binding

Artifact: `benchmarks/results/2026-08-20-integration-fb57570-keyless-scorecard.json`

- Stack: isolated Docker Compose project `knowledge-way-quickstart-1494829069`, `.env.example` keyless profile (`EMBEDDING_PROVIDER=none`, `CODE_CARDS_ENABLED=false`, `RERANK_PROVIDER=none`).
- Served pins verified by the runner manifest capture:
  - FastAPI `40e33e492dbf4af6172997f4e3238a32e56cbe26`
  - Starlette `8d0cff820f89b5d5b19677246293513a9d1c952c`
  - Pydantic `7cedbfb03df82ac55c844c97e6f975359cb51bb9`
- Result summary:
  - `text`: files MRR 0.114667, hit@5 0.24
  - `hybrid`: files MRR 0.114667, hit@5 0.24
  - `symbols`: files MRR 0.16, hit@5 0.16
  - `exact`: files MRR 0.0, hit@5 0.0
  - `semantic`: unavailable as expected in keyless run (`semantic: unconfigured`).

### Drift / regression record

Compared with the prior keyless baseline `2026-08-14-fastapi-stack-current-search-benchmark-run-08e23b8.json`, hybrid file MRR moved from 0.16 to 0.114667 and hybrid file hit@5 moved from 0.16 to 0.24. This is recorded as keyless retrieval drift for follow-up triage.

## Scorecard 2 — semantic-enabled Vertex guard

Status: **blocked**. No `VERTEX_*`, `GOOGLE_*`, `GCP_*`, `GEMINI_*`, or `EMBEDDING_PROVIDER` semantic configuration was present in the cron environment, so the Vertex semantic guard was not run and was not substituted with keyless results. The independent keyless scorecard above did run.

Guard not evaluated: semantic-enabled hybrid must not drop below `0.68`.
