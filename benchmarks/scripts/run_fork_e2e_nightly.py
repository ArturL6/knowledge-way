#!/usr/bin/env python3
"""Durable, low-cost E2E orchestrator for the pinned fork realism baseline.

Runs against the isolated kw-e2e Compose project only. It parses first with
embeddings disabled, generates bounded Gemini cards, enables Vertex only after
cards are durable, and then embeds each repository once.
"""
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "e2e"
REPOS = ARTIFACTS / "fork-e2e-baseline-repositories.json"
OVERRIDES = Path("/tmp/kw-e2e-overrides.env")
COMPOSE = ["docker", "compose", "-p", "kw-e2e", "-f", "/tmp/kw-e2e-compose.yml"]
API = "http://localhost:8001/api"
CARD_BATCH_SIZE = 250
MAX_CARD_INPUT_TOKENS = 10_000_000
POLL_SECONDS = 15


def now():
    return datetime.now(timezone.utc).isoformat()


def write_state(**values):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    values["updated_at"] = now()
    (ARTIFACTS / "fork-e2e-nightly-state.json").write_text(json.dumps(values, indent=2) + "\n")
    print(json.dumps(values), flush=True)


def api(path, method="GET", body=None):
    request = urllib.request.Request(
        f"{API}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"content-type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def sql(query):
    return subprocess.check_output(COMPOSE + ["exec", "-T", "postgres", "psql", "-U", "knowledgeway", "-d", "knowledgeway", "-tAc", query], text=True).strip()


def wait_repositories(items):
    while True:
        statuses = [api(f"/repositories/{item['repository_id']}") for item in items]
        summary = [{"name": row["name"], "status": row["indexing_status"], "sha": row.get("indexed_commit_sha"), "error": row.get("error_message")} for row in statuses]
        write_state(phase="deterministic_index", repositories=summary)
        if any(row["indexing_status"] == "failed" for row in statuses):
            raise RuntimeError(f"deterministic indexing failed: {summary}")
        if all(row["indexing_status"] == "ready" for row in statuses):
            return statuses
        time.sleep(POLL_SECONDS)


def wait_job(job_id):
    """Wait for the RQ job returned by the API, not the separate audit-row ID."""
    probe = (
        "from redis import Redis; from rq.job import Job; "
        "import json; "
        f"j=Job.fetch('{job_id}', connection=Redis.from_url('redis://redis:6379/0')); "
        "print(json.dumps({'status': j.get_status(refresh=True), 'error': j.exc_info or ''}))"
    )
    while True:
        raw = subprocess.check_output(COMPOSE + ["exec", "-T", "worker", "python", "-c", probe], text=True).strip()
        result = json.loads(raw)
        status, error = result["status"], result["error"]
        write_state(phase="code_cards", job_id=job_id, job_status=status)
        if status == "failed":
            raise RuntimeError(f"code-card job failed: {error}")
        if status == "finished":
            return
        time.sleep(POLL_SECONDS)


def card_stats(repo_id):
    row = sql("SELECT count(*), COALESCE(sum(input_tokens),0), COALESCE(sum(output_tokens),0) "
              f"FROM code_cards WHERE repository_id='{repo_id}'")
    return tuple(map(int, row.split("|")))


def generate_cards(items):
    for item in items:
        while True:
            cards, inputs, outputs = card_stats(item["repository_id"])
            symbols = int(sql(f"SELECT count(*) FROM symbols WHERE repository_id='{item['repository_id']}'"))
            write_state(phase="code_cards", repository=item["fixture_id"], cards=cards, symbols=symbols, input_tokens=inputs, output_tokens=outputs, budget_cap_input_tokens=MAX_CARD_INPUT_TOKENS)
            if cards >= symbols:
                break
            if inputs >= MAX_CARD_INPUT_TOKENS:
                raise RuntimeError(f"card input-token safety cap reached for {item['fixture_id']}: {inputs}")
            result = api(f"/repositories/{item['repository_id']}/code-cards", method="POST", body={"limit": CARD_BATCH_SIZE})
            wait_job(result["job_id"])


def enable_embeddings_once(items):
    text = OVERRIDES.read_text().replace("EMBEDDING_PROVIDER=none", "EMBEDDING_PROVIDER=vertex")
    OVERRIDES.write_text(text)
    subprocess.run(COMPOSE + ["up", "-d", "--force-recreate", "api", "worker"], check=True)
    for item in items:
        write_state(phase="card_enriched_embeddings", repository=item["fixture_id"])
        subprocess.run(COMPOSE + ["exec", "-T", "worker", "python", "-c", f"from app.ingestion import reembed_repository; reembed_repository('{item['repository_id']}')"], check=True, timeout=3600)
        chunks, embeddings = sql("SELECT count(*), count(embedding) FROM code_chunks " f"WHERE repository_id='{item['repository_id']}'").split("|")
        if chunks != embeddings:
            raise RuntimeError(f"embedding coverage mismatch for {item['fixture_id']}: {embeddings}/{chunks}")


def main():
    items = json.loads(REPOS.read_text())
    started = time.monotonic()
    write_state(phase="starting", repositories=[item["fixture_id"] for item in items], card_source_character_cap=4000, budget_cap_input_tokens=MAX_CARD_INPUT_TOKENS)
    statuses = wait_repositories(items)
    (ARTIFACTS / "fork-e2e-baseline-index-status.json").write_text(json.dumps(statuses, indent=2) + "\n")
    generate_cards(items)
    totals = {item["fixture_id"]: dict(zip(("cards", "input_tokens", "output_tokens"), card_stats(item["repository_id"]))) for item in items}
    (ARTIFACTS / "fork-e2e-card-usage.json").write_text(json.dumps(totals, indent=2) + "\n")
    enable_embeddings_once(items)
    write_state(phase="ready_for_evaluation", duration_seconds=round(time.monotonic() - started, 2), card_usage=totals)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        write_state(phase="failed", error=str(error))
        raise
