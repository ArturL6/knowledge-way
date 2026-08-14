#!/usr/bin/env bash
# Start the documented keyless local stack, prove its HTTP entry points work, then stop it.
# Use --keep-running to leave the stack available after the checks succeed.
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

keep_running=false
if [[ "${1:-}" == "--keep-running" ]]; then
  keep_running=true
elif [[ $# -ne 0 ]]; then
  printf 'usage: %s [--keep-running]\n' "$0" >&2
  exit 64
fi

created_env=false
override_file="$(mktemp)"
project_name="knowledge-way-quickstart-${RANDOM}${RANDOM}"
compose=(docker compose --project-name "$project_name" -f docker-compose.yml -f "$override_file")
cleanup() {
  status=$?
  if ! "$keep_running"; then
    "${compose[@]}" down --remove-orphans >/dev/null 2>&1 || true
  fi
  rm -f "$override_file"
  if "$created_env"; then
    rm -f .env
  fi
  exit "$status"
}
trap cleanup EXIT

if [[ ! -f .env ]]; then
  cp .env.example .env
  created_env=true
fi

# This is intentionally strict: quickstart must never accidentally spend money or require cloud
# credentials because a developer happened to have a production-shaped .env in the checkout.
require_setting() {
  local name=$1 expected=$2
  if ! grep -qx "${name}=${expected}" .env; then
    printf 'quickstart requires %s=%s in .env (refusing a billable configuration)\n' "$name" "$expected" >&2
    exit 2
  fi
}
require_setting EMBEDDING_PROVIDER none
require_setting CODE_CARDS_ENABLED false
require_setting RERANK_PROVIDER none

# A separate compose project and ephemeral API/web ports keep this smoke test independent of a
# developer's already-running Knowledge-Way stack. Redis and Postgres stay internal: only the two
# browser-facing services need host ports.
printf '%s\n' 'services:' > "$override_file"
printf '%s\n' '  postgres:' '    ports: !reset []' '  redis:' '    ports: !reset []' >> "$override_file"
printf '%s\n' '  api:' '    ports: !override' '      - "127.0.0.1::8000"' '  web:' '    ports: !override' '      - "127.0.0.1::3000"' >> "$override_file"

printf '%s\n' 'Starting keyless Knowledge-Way stack (EMBEDDING_PROVIDER=none)...'
"${compose[@]}" up --build --wait
api_port=$("${compose[@]}" port api 8000 | sed -E 's/.*:([0-9]+)$/\1/')
web_port=$("${compose[@]}" port web 3000 | sed -E 's/.*:([0-9]+)$/\1/')

# Probe inside each container: this remains reliable on hosts where a firewall or a competing
# developer stack prevents loopback access to Docker's ephemeral published port. Compose considers
# a container started before its HTTP server has necessarily bound its socket, so allow the two
# application servers a bounded time to become ready.
wait_for_api() {
  for _ in {1..30}; do
    if "${compose[@]}" exec -T api python -c 'from urllib.request import urlopen; assert urlopen("http://127.0.0.1:8000/docs").status == 200' >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  printf '%s\n' 'timed out waiting for API docs' >&2
  return 1
}
wait_for_web() {
  for _ in {1..30}; do
    if "${compose[@]}" exec -T web node -e 'fetch("http://127.0.0.1:3000").then(response => { if (!response.ok) process.exit(1) })' >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  printf '%s\n' 'timed out waiting for web UI' >&2
  return 1
}
wait_for_api
printf 'PASS API docs: http://127.0.0.1:%s/docs\n' "$api_port"
wait_for_web
printf 'PASS web UI: http://127.0.0.1:%s\n' "$web_port"

printf '%s\n' 'PASS keyless local quickstart smoke test'
if "$keep_running"; then
  printf '%s\n' "Stack remains running (--keep-running). Stop it with: ${compose[*]} down"
fi
