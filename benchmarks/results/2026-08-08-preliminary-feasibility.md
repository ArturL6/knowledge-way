# Preliminary benchmark feasibility run — 2026-08-08

> **Not a head-to-head benchmark result.** These runs establish that the three tools can be installed and execute a local code-indexing path. The settings, corpus revisions, file filters, and cold-state definitions were not yet equivalent, so no relative performance or quality claim is valid from these numbers.

## Environment and pins

- Host: Linux (`6.8.0-117-generic`), Python `3.11.15`.
- knowledge-way source: `ef97c5f` (its indexed Click clone reported `00e592cea702e0b2caa0dee42489fdb1c22cd845`).
- CodeGraphContext source: `e367db2488d9a0d112e28c446498a81a59e914f8`; package reports `0.5.6`.
- Graphify source: `3d19463484ebcf773b399ddad9fd3363b2ab3bff`; package reports `0.9.36`.
- Pinned corpus checkout used by CodeGraphContext and Graphify: Click `8.1.7`, resolved to `874ca2bc1c30d93a4ac6e36a15ed685eafe89097`.
- No LLM, embedding provider, SCIP, remote graph database, or private credentials were enabled.

## Installation outcome

| Tool | Outcome | Local backend/path |
| --- | --- | --- |
| knowledge-way | Docker Compose stack started; API health check passed. | Existing PostgreSQL/Redis/API/worker service state. |
| CodeGraphContext | Installed into `/tmp/cgc-venv`; `cgc --help` and `cgc doctor` passed. | Fresh KuzuDB at `/tmp/cgc-click.kuzu`. |
| Graphify | Installed into `/tmp/graphify-venv`; CLI started successfully. | Fresh artifact directory at `/tmp/graphify-click-out`. |

## Observed indexing measurements

### CodeGraphContext — static code graph baseline

Command (fresh KuzuDB path):

```bash
cgc --database kuzudb --path /tmp/cgc-click.kuzu \
  index /tmp/kw-benchmark-corpora/click-small --force --no-progress
```

Observed:

- `94` scanned files; `71` Python files were reported in the scan summary.
- `1,260` function nodes, `108` class nodes, `3,463` `CALLS` edges in the index execution summary.
- `203.43 s` wall clock, `3,533,728 KiB` maximum RSS.
- `97,832,960` bytes KuzuDB directory size.
- It explicitly reported `145` unresolved calls, chiefly ambiguous function/class targets. Those skips are a useful correctness signal, not a failure.

### Graphify — local AST artifact baseline

Command (fresh output directory):

```bash
graphify /tmp/kw-benchmark-corpora/click-small \
  --out /tmp/graphify-click-out --code-only --no-cluster
```

Observed:

- `71` code files; `49` non-code files skipped by the `--code-only` mode.
- `1,398` nodes and `3,322` edges in `graph.json`.
- `1.56 s` wall clock, `71,016 KiB` maximum RSS.
- `3,153,685` bytes output directory size.
- A real local query for `Context` returned the `Context` node at `src/click/core.py:L160`; its default BFS expansion found `459` nodes and was token-budget-truncated to `90` displayed nodes.

### knowledge-way — service integration smoke run

A new repository was added through the live API using the public default-branch URL:

```text
https://github.com/pallets/click.git
```

Observed:

- Repository status reached `ready` in `6.407 s` from API create request through worker completion.
- The repository status reported `163` files and indexed commit `00e592cea702e0b2caa0dee42489fdb1c22cd845`.
- Persisted rows for that repository: `1,945` symbols and `6,936` edges.
- The shared existing PostgreSQL database occupied `90,078,231` bytes after the run; this is **not** a per-repository or cold-index disk measurement.
- Current resident service observations after indexing: API `77.68 MiB`, worker `32.82 MiB`, PostgreSQL `49.9 MiB`; these are steady-service readings, **not** peak index RSS.
- A repository-scoped chat retrieval smoke prompt, `Where is the Context class defined?`, returned no result. This is recorded as a failed retrieval task, not silently converted into a success.

## Why these measurements are not comparable yet

1. **Revision mismatch:** knowledge-way currently clones the configured default branch and does not expose a revision/tag pin in repository ingestion; the two local tools used Click `8.1.7`.
2. **Input/filter mismatch:** Graphify was intentionally code-only (`71` files); CodeGraphContext scanned `94` files; knowledge-way reported `163` default-branch files.
3. **Cold-state mismatch:** CodeGraphContext and Graphify used fresh dedicated state paths, while knowledge-way used the existing service database and volumes. Resetting those shared user data volumes was not performed.
4. **Timing boundary mismatch:** knowledge-way timing includes remote clone/API/queue completion; the other two index pre-cloned local checkout paths.
5. **Retrieval interface mismatch:** CodeGraphContext exposes direct Cypher; Graphify exposes local graph traversal; knowledge-way currently exposes bounded API/MCP retrieval. The common task adapter has not been implemented for all three.

## Required changes before publishing a comparative result

1. Add a `revision`/branch-or-tag pin to knowledge-way repository ingestion and persist the resolved commit in benchmark provenance.
2. Run knowledge-way in a separately named, disposable Compose project/volume set, so a fresh datastore can be measured without touching the normal service.
3. Normalise the source inclusion policy across tools (same commit and the same code-only or all-tracked-files definition).
4. Implement adapters for the checked-in task manifest and execute at least three cold and warm trials per tool.
5. Score exact symbol, caller/callee, natural-language retrieval, graph-edge, update, and MCP tasks; label unsupported items as unsupported.
6. Fix or explicitly scope the repository-filtered retrieval path before crediting knowledge-way with a repository-specific search task.

## Reproducibility artifacts

The neutral protocol, corpus manifest, task manifest, schema, and safe runner are checked in under [`benchmarks/`](../README.md). This report intentionally includes commands, resolved commits, and raw observed counts so later runs can improve it rather than overwrite its limitations.
