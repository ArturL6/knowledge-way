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
# Pick loopback ports before Compose builds the browser bundle.  The API endpoint is baked into
# Next.js client code, so an ephemeral Docker mapping discovered after build cannot work.
pick_port() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'; }
api_port=$(pick_port)
web_port=$(pick_port)
while [[ "$web_port" == "$api_port" ]]; do web_port=$(pick_port); done
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

# A separate compose project and preselected loopback ports keep this smoke test independent of
# another stack while letting the web build point its browser requests at this API. Redis and
# Postgres remain internal.
printf '%s\n' 'services:' > "$override_file"
printf '%s\n' '  postgres:' '    ports: !reset []' '  redis:' '    ports: !reset []' '  worker:' '    command: python -m app.adapters.outbound.rq_jobs.worker' >> "$override_file"
printf '%s\n' '  api:' '    environment:' "      CORS_ORIGINS: http://127.0.0.1:${web_port}" '    ports: !override' "      - \"127.0.0.1:${api_port}:8000\"" >> "$override_file"
printf '%s\n' '  web:' '    build:' '      args:' "        NEXT_PUBLIC_API_URL: http://127.0.0.1:${api_port}/api" '    environment:' "      NEXT_PUBLIC_API_URL: http://127.0.0.1:${api_port}/api" '    ports: !override' "      - \"127.0.0.1:${web_port}:3000\"" >> "$override_file"

printf '%s\n' 'Starting keyless Knowledge-Way stack (EMBEDDING_PROVIDER=none)...'
"${compose[@]}" up --build --wait

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

# This Playwright flow is intentionally against the just-built Compose web artifact, not the
# repository's mock-routed test server. It adds a pinned public fixture through the browser,
# waits for the keyless worker to index the selected three-repository fixture, records its declared
# FastAPI provider dependencies, searches it, and opens returned source evidence.
printf '%s\n' 'Running browser seed/index/search/evidence flow for the selected fastapi-stack...'
node scripts/quickstart_playwright.mjs "http://127.0.0.1:${web_port}" "http://127.0.0.1:${api_port}/api"

printf '%s\n' 'PASS keyless local quickstart smoke test'
if "$keep_running"; then
  printf '%s\n' "Stack remains running (--keep-running). Stop it with: ${compose[*]} down"
fi
