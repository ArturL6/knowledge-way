#!/usr/bin/env python3
"""Generate bounded Code-Card batches for one pinned local benchmark repository.

One RQ job is active at a time. The state file is atomically checkpointed and
is resumed before any new provider-backed request is submitted.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TERMINAL_FAILURES = {"failed", "stopped", "canceled", "cancelled"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def sql(query: str) -> str:
    return run("docker", "exec", "knowledge-way-postgres-1", "psql", "-U", "knowledgeway", "-d", "knowledgeway", "-Atc", query)


def rq_status(job_id: str) -> dict:
    command = (
        "from redis import Redis; from rq.job import Job; import json; "
        f"j=Job.fetch({job_id!r},connection=Redis.from_url('redis://redis:6379/0')); "
        "print(json.dumps({'status':j.get_status(refresh=True),'error':j.exc_info or ''}))"
    )
    return json.loads(run("docker", "exec", "knowledge-way-worker-1", "python", "-c", command))


def stats(repository_id: str) -> dict:
    raw = sql(
        "SELECT (SELECT count(*) FROM symbols WHERE repository_id={id}), "
        "(SELECT count(*) FROM code_cards WHERE repository_id={id}), "
        "(SELECT coalesce(sum(input_tokens),0) FROM code_cards WHERE repository_id={id}), "
        "(SELECT coalesce(sum(output_tokens),0) FROM code_cards WHERE repository_id={id})".format(id=repr(repository_id))
    )
    symbols, cards, inputs, outputs = map(int, raw.split("|"))
    return {"symbols": symbols, "cards": cards, "input_tokens": inputs, "output_tokens": outputs}


def live_repository(api_base_url: str, repository_id: str) -> dict:
    with urllib.request.urlopen(api_base_url.rstrip("/") + f"/api/repositories/{repository_id}", timeout=30) as response:
        return json.load(response)


def submit(api_base_url: str, repository_id: str, limit: int) -> dict:
    request = urllib.request.Request(
        api_base_url.rstrip("/") + f"/api/repositories/{repository_id}/code-cards",
        method="POST", data=json.dumps({"limit": limit}).encode(), headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def write_state(path: Path, **values: object) -> None:
    values["updated_at"] = now()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(values, indent=2) + "\n")
    os.replace(temporary, path)
    print(json.dumps(values), flush=True)


def poll_job(args, job_id: str) -> int:
    deadline = time.monotonic() + args.poll_deadline_seconds
    while True:
        try:
            job = rq_status(job_id)
        except subprocess.CalledProcessError as error:
            write_state(args.state, phase="failed_job_lookup", repository_id=args.repository_id, job_id=job_id, detail=str(error), **stats(args.repository_id))
            return 1
        current = stats(args.repository_id)
        write_state(args.state, phase="code_cards", repository_id=args.repository_id, job_id=job_id,
                    job_status=job["status"], job_error=job["error"][-1000:], **current,
                    max_input_tokens=args.max_input_tokens, max_output_tokens=args.max_output_tokens)
        if job["status"] == "finished":
            return 0
        if job["status"] in TERMINAL_FAILURES:
            return 1
        if time.monotonic() >= deadline:
            write_state(args.state, phase="stopped_poll_deadline", repository_id=args.repository_id, job_id=job_id,
                        job_status=job["status"], **current, max_input_tokens=args.max_input_tokens,
                        max_output_tokens=args.max_output_tokens)
            return 1
        time.sleep(args.poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-id", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-input-tokens", type=int, required=True)
    parser.add_argument("--max-output-tokens", type=int, required=True)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--poll-deadline-seconds", type=int, default=2100)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 250:
        raise SystemExit("batch-size must be 1..250")
    args.state.parent.mkdir(parents=True, exist_ok=True)
    repository = live_repository(args.api_base_url, args.repository_id)
    if repository.get("indexed_commit_sha") != args.expected_commit or repository.get("indexing_status") != "ready":
        raise SystemExit("repository is not ready at the requested pinned commit")

    saved = json.loads(args.state.read_text()) if args.state.exists() else {}
    saved_job = saved.get("job_id") if saved.get("job_status") not in {"finished", *TERMINAL_FAILURES} else None
    if saved_job and poll_job(args, saved_job):
        return 1

    while True:
        current = stats(args.repository_id)
        if current["input_tokens"] >= args.max_input_tokens or current["output_tokens"] >= args.max_output_tokens:
            write_state(args.state, phase="stopped_budget_cap", repository_id=args.repository_id, **current,
                        max_input_tokens=args.max_input_tokens, max_output_tokens=args.max_output_tokens)
            return 2
        if current["cards"] >= current["symbols"]:
            write_state(args.state, phase="complete", repository_id=args.repository_id, **current,
                        max_input_tokens=args.max_input_tokens, max_output_tokens=args.max_output_tokens)
            return 0
        # Conservative preflight headroom prevents a single bounded batch from
        # crossing the declared cap based on the observed pilot mean.
        estimate_in = current["input_tokens"] / current["cards"] * args.batch_size * 1.5
        estimate_out = current["output_tokens"] / current["cards"] * args.batch_size * 1.5
        if current["input_tokens"] + estimate_in > args.max_input_tokens or current["output_tokens"] + estimate_out > args.max_output_tokens:
            write_state(args.state, phase="stopped_budget_headroom", repository_id=args.repository_id, **current,
                        projected_batch_input_tokens=round(estimate_in), projected_batch_output_tokens=round(estimate_out),
                        max_input_tokens=args.max_input_tokens, max_output_tokens=args.max_output_tokens)
            return 2
        job_id = submit(args.api_base_url, args.repository_id, args.batch_size)["job_id"]
        write_state(args.state, phase="code_cards", repository_id=args.repository_id, job_id=job_id, job_status="queued",
                    **current, max_input_tokens=args.max_input_tokens, max_output_tokens=args.max_output_tokens)
        if poll_job(args, job_id):
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
