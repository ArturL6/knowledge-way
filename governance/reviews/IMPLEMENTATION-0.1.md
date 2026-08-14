# Implementation evidence — 0.1 workspace selection

- **Packet:** 0.1 — Workspace selection: fastapi-stack
- **Branch:** `packet/0.1-fastapi-stack-corpus`
- **Scope:** commits the owner-selected permanent Stage 0–2 `fastapi-stack` workspace in `benchmarks/corpora.json`.

## Selected, pinned workspace

| Repository | Role | Tag | Verified commit |
|---|---|---:|---|
| `fastapi/fastapi` | consumer | `0.115.0` | `40e33e492dbf4af6172997f4e3238a32e56cbe26` |
| `encode/starlette` | framework provider | `0.38.6` | `8d0cff820f89b5d5b19677246293513a9d1c952c` |
| `pydantic/pydantic` | model/schema provider | `v2.9.2` | `7cedbfb03df82ac55c844c97e6f975359cb51bb9` |

The manifest records FastAPI → Starlette and FastAPI → Pydantic `DEPENDS_ON`
relationships, including their package-metadata evidence. The selected tags were cloned from
the public upstream repositories and each checked-out `HEAD` exactly matched the recorded
commit above. The pre-Stage-0 Click/Flask fixtures remain explicitly labelled as legacy harness
fixtures so their existing neutral-harness tasks remain reproducible; they are not the active
workspace.

## Verification (2026-08-14)

```text
python3 benchmarks/scripts/validate.py
VALID

python3 -m unittest discover -s benchmarks/tests -v
Ran 4 tests in 0.288s
OK

test -f benchmarks/corpora.json
PASS

active workspace contract: PASS
```

No LLM, embedding, or card provider was called; the monthly estimated spend remains unchanged.
