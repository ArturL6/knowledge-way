# Neutral code-intelligence benchmark

This directory is a **scaffold**, not a published comparison or a performance claim. It defines the same pinned public corpora, task identifiers, measurements, output format, and provenance requirements for knowledge-way, CodeGraphContext, Graphify, or another implementation.

No adapter or script installs, invokes, downloads, or assumes any competitor. A maintainer supplies a local adapter configuration for a tool they are authorized to use.

## Layout

- `corpora.json` — public Git sources and pinned release refs. The resolved commit SHA is captured at execution.
- `tasks.json` — curated task IDs and relevance/edge oracles. The initial task set is deliberately small and reviewable; expand it through pull requests with source citations.
- `result.schema.json` — interchange and validation contract for completed runs.
- `scripts/validate.py` — offline manifest/schema consistency validation.
- `scripts/fetch_corpora.py` — opt-in clone/checkout helper for public sources.
- `scripts/run_benchmark.py` — captures provenance and runs a supplied, local adapter.

## Quick start

Validation is offline and has no credentials or network dependency:

```bash
python3 benchmarks/scripts/validate.py
python3 -m unittest discover -s benchmarks/tests -v
```

To obtain public corpora (an explicit network action), choose a directory outside a source checkout if desired:

```bash
python3 benchmarks/scripts/fetch_corpora.py --destination ~/kw-benchmark-corpora
```

The fetch helper only creates or reuses named subdirectories; it rejects an existing non-empty target and never runs `rm`, `clean`, reset, or force checkout. Inspect the upstream repositories and licenses before use.

## Running an implementation

An adapter is a local JSON file, intentionally not checked in. It declares the executable command and placeholder expansion. Start from `adapter.example.json`, copy it outside version control, and replace the command with the implementation's documented interface. The command receives one JSON request on stdin and must write one JSON response on stdout for each request. It must not print logs to stdout.

```bash
cp benchmarks/adapter.example.json /tmp/my-adapter.json
# edit /tmp/my-adapter.json for a locally installed implementation
python3 benchmarks/scripts/run_benchmark.py \
  --tool knowledge-way --adapter-config /tmp/my-adapter.json \
  --corpora-dir ~/kw-benchmark-corpora --output ~/kw-results/run-001.json
python3 benchmarks/scripts/validate.py --result ~/kw-results/run-001.json
```

`run_benchmark.py` refuses to overwrite an output file, redacts common secret-shaped configuration values in captured provenance, and uses no credentials itself. It reports command wall time and optional adapter-provided RSS/disk measurements; tools should document their own measurement method in `measurement_notes`.

## Recorded runs

- [Preliminary feasibility run (2026-08-08)](results/2026-08-08-preliminary-feasibility.md) — installation and smoke-index evidence only; it explicitly documents why it is **not** a comparative performance or quality result.

## Measurement protocol

1. Use the exact same `corpora.json`, `tasks.json`, machine, corpus checkout SHAs, adapter limits, and cold/warm policy for every tool.
2. Run at least three trials per tool/mode. Keep raw JSON files; aggregate separately and report median plus individual values.
3. Measure **index wall time**, peak **RSS**, and resulting **disk bytes** after a cold index. Define cold state without destructive cleanup (for example an implementation-specific fresh, disposable data directory created by its adapter).
4. For retrieval, submit task IDs in manifest order and calculate precision@k and MRR from the checked-in relevance oracle. Do not count empty/failed responses as successes.
5. For graph tasks, calculate edge precision/recall only against tasks with `edge_oracle`; identify unsupported edge types and unscored tasks.
6. For updates, apply only the declared non-destructive fixture patch or adapter operation and report update wall time; preserve the original corpus checkout.
7. For MCP, execute each `mcp_task` against the same corpus and record a pass only when the documented observable assertion holds.

Results must state omitted metrics and unsupported tasks as `null`/`unsupported`, not as zero or success. Comparisons should include tool version, configuration, hardware, and limitations. Never interpret different corpus revisions, task subsets, or hardware as a head-to-head result.
