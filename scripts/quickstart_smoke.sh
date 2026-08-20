#!/usr/bin/env bash
# Start the documented local stack, prove its HTTP entry points work, then stop it.
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
# The no-variable path is deliberately keyless.  Explicit caller values are injected into the
# disposable Compose project rather than editing a developer's .env in-place.
embedding_provider="${EMBEDDING_PROVIDER:-none}"
vertex_project_id="${VERTEX_PROJECT_ID:-}"
code_cards_enabled="${CODE_CARDS_ENABLED:-false}"
rerank_provider="${RERANK_PROVIDER:-none}"

for setting in "$embedding_provider" "$vertex_project_id" "$code_cards_enabled" "$rerank_provider"; do
  if [[ "$setting" == *$'\n'* || "$setting" == *$'\r'* || "$setting" == *'"'* || "$setting" == *'\\'* ]]; then
    printf '%s\n' 'quickstart settings may not contain quotes, backslashes, or line breaks' >&2
    exit 64
  fi
done

if [[ "$embedding_provider" == "vertex" ]]; then
  adc_path="/home/hermes/.gcloud-kw/application_default_credentials.json"
  if [[ ! -f "$adc_path" ]]; then
    printf 'Vertex quickstart requires ADC at %s; refusing to start a stack without it.\n' "$adc_path" >&2
    exit 2
  fi
  if [[ -z "$vertex_project_id" ]]; then
    printf '%s\n' 'Vertex quickstart requires VERTEX_PROJECT_ID; refusing to start a stack without it.' >&2
    exit 2
  fi
fi
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
    # The project owns its named fixture volume, so remove it with the isolated
    # stack.  Do not use broad Docker pruning: other developer stacks are not
    # quickstart resources.
    "${compose[@]}" down --remove-orphans --volumes --rmi local >/dev/null 2>&1 || true
  fi
  # --keep-running prints a follow-up Compose command that still needs this
  # generated override (and its generated .env, when applicable) to exist.
  # The disposable worktree owner removes both after the project-scoped down.
  if ! "$keep_running"; then
    rm -f "$override_file"
    if "$created_env"; then
      rm -f .env
    fi
  fi
  exit "$status"
}
trap cleanup EXIT

if [[ ! -f .env ]]; then
  cp .env.example .env
  created_env=true
fi

# A separate compose project and preselected loopback ports keep this smoke test independent of
# another stack while letting the web build point its browser requests at this API. Redis,
# Postgres, and the fixture checkout remain internal to this disposable project.
printf '%s\n' 'volumes:' '  quickstart-data:' > "$override_file"
printf '%s\n' 'services:' '  postgres:' '    ports: !reset []' '  redis:' '    ports: !reset []' >> "$override_file"
printf '%s\n' '  api:' '    environment:' "      CORS_ORIGINS: http://127.0.0.1:${web_port}" "      EMBEDDING_PROVIDER: \"${embedding_provider}\"" "      VERTEX_PROJECT_ID: \"${vertex_project_id}\"" "      CODE_CARDS_ENABLED: \"${code_cards_enabled}\"" "      RERANK_PROVIDER: \"${rerank_provider}\"" '    ports: !override' "      - \"127.0.0.1:${api_port}:8000\"" >> "$override_file"
if [[ "$embedding_provider" == "vertex" ]]; then
  # Override Compose's normal developer ADC mount with the owner-designated, read-only ADC home.
  printf '%s\n' '    volumes: !override' '      - "quickstart-data:/data"' '      - "/home/hermes/.gcloud-kw:/root/.config/gcloud:ro"' >> "$override_file"
else
  printf '%s\n' '    volumes: !override' '      - "quickstart-data:/data"' >> "$override_file"
fi
printf '%s\n' '  worker:' '    command: python -m app.adapters.outbound.rq_jobs.worker' '    environment:' "      EMBEDDING_PROVIDER: \"${embedding_provider}\"" "      VERTEX_PROJECT_ID: \"${vertex_project_id}\"" "      CODE_CARDS_ENABLED: \"${code_cards_enabled}\"" "      RERANK_PROVIDER: \"${rerank_provider}\"" >> "$override_file"
if [[ "$embedding_provider" == "vertex" ]]; then
  printf '%s\n' '    volumes: !override' '      - "quickstart-data:/data"' '      - "/home/hermes/.gcloud-kw:/root/.config/gcloud:ro"' >> "$override_file"
else
  printf '%s\n' '    volumes: !override' '      - "quickstart-data:/data"' >> "$override_file"
fi
printf '%s\n' '  web:' '    build:' '      args:' "        NEXT_PUBLIC_API_URL: http://127.0.0.1:${api_port}/api" '    environment:' "      NEXT_PUBLIC_API_URL: http://127.0.0.1:${api_port}/api" '    ports: !override' "      - \"127.0.0.1:${web_port}:3000\"" >> "$override_file"

printf 'Starting Knowledge-Way stack (EMBEDDING_PROVIDER=%s)...\n' "$embedding_provider"
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
# A disposable worktree intentionally does not carry node_modules or browser binaries.  Provision
# the lockfile-pinned Playwright package and Chromium before the real-browser smoke.
(cd apps/web && npm ci && {
  if sudo -n true >/dev/null 2>&1; then
    npx playwright install --with-deps chromium
  else
    # The runner's OS dependencies are pre-provisioned; a non-interactive job must not prompt.
    npx playwright install chromium
  fi
})
node scripts/quickstart_playwright.mjs "http://127.0.0.1:${web_port}" "http://127.0.0.1:${api_port}/api"

printf 'PASS local quickstart smoke test (EMBEDDING_PROVIDER=%s)\n' "$embedding_provider"
if "$keep_running"; then
  printf '%s\n' "Stack remains running (--keep-running). Stop it with: ${compose[*]} down"
fi
