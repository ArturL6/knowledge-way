#!/usr/bin/env bash
# R.7: evidence is persisted for parser-derived edges and non-null at the schema boundary.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
export PYTHONPATH="$repo_root/apps/api${PYTHONPATH:+:$PYTHONPATH}"
uv run pytest -q apps/api/tests/test_ingestion_graph.py apps/api/tests/test_migrations.py
uv run python - <<'PY'
from app.models import Evidence, SymbolEdge
assert Evidence.__tablename__ == "evidence"
assert SymbolEdge.__table__.c.evidence_id.nullable is False
print("PASS: every SymbolEdge requires evidence and parser ingestion persists it.")
PY
