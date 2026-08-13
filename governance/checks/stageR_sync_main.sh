#!/usr/bin/env bash
set -euo pipefail

main_ref="${1:-origin/main}"
integration_ref="${2:-HEAD}"

git merge-base --is-ancestor "$main_ref" "$integration_ref" || {
  echo "FAIL: $integration_ref does not contain $main_ref"
  exit 1
}

git diff --check "$main_ref...$integration_ref"

python - "$integration_ref" <<'PY'
import re
import subprocess
import sys

text = subprocess.check_output(
    ["git", "show", f"{sys.argv[1]}:governance/STATUS.md"], text=True
)
match = re.search(r'- id: "R\.7a"\n(?:    .*\n)*?    state: ([^\n]+)', text)
if not match:
    raise SystemExit("FAIL: STATUS has no R.7a packet")
if not match.group(1).startswith("done"):
    raise SystemExit(f"FAIL: R.7a is not done: {match.group(1)!r}")
print("PASS: main is contained and R.7a is done")
PY
