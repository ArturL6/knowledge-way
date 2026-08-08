# Preliminary Click benchmark — 2026-08-08

This is a **single cold-run feasibility result**, not a product ranking. It uses the common code-only baseline: no LLM, no vector provider, no SCIP, and no remote graph database. Runs were sequential on the same Linux host (4 CPU cores, 8.13 GB RAM total), with the Click `8.1.7` source commit `874ca2bc1c30d93a4ac6e36a15ed685eafe89097`.

## Pinned implementations

- knowledge-way: `ef97c5f2f793a8e3b62f6a25b03223baad65cb80`
- CodeGraphContext: `e367db2488d9a0d112e28c446498a81a59e914f8`
- Graphify: `3d19463484ebcf773b399ddad9fd3363b2ab3bff`

## Corpus

- 146 tracked files
- 71 Python files
- Click release/tag: `8.1.7`

## Indexing observations

- **knowledge-way** completed its API/worker index in **6.384 s** (wall clock from repository creation to `ready`) and stored 163 files, 2,022 code chunks, 1,945 symbols, and 6,936 edges. The measurement includes the service queue/API lifecycle and is therefore not directly comparable to a local CLI-only extractor.
- **Graphify** `extract --code-only --no-cluster` completed in **1.83 s**, used a peak RSS of **73,031,680 bytes**, wrote **3,153,701 bytes**, and produced 1,398 nodes / 3,322 edges. It skipped 49 non-code files and 27 unclassified files, so its inclusion set is not identical to knowledge-way's 163 stored files.
- **CodeGraphContext** selected its default local KuzuDB backend but was killed by the host (`exit 137`) after **208.21 s** and **3,461,345,280 bytes** peak RSS; no usable graph/query result was produced. Its local benchmark state occupied 30,448,924 bytes after termination. This is an observed run-specific resource failure, not a general claim about CodeGraphContext.

## Retrieval smoke test

The exact-symbol prompt `Context` was exercised after indexing.

- Graphify's graph query returned `Context` at `src/click/core.py:L160`, but its broad BFS response contained 460 nodes and was truncated to the token budget; a narrower node lookup is needed for a precision score.
- knowledge-way's current unscoped `/api/search` endpoint returned zero results for this prompt in this run; the repository-filtered query requested by the benchmark is not yet supported by that endpoint. This is a concrete product gap, not counted as a quality score.
- CodeGraphContext could not be queried because indexing failed.

## What this result does and does not establish

Graphify was the only tool to complete the direct local-AST cold run under this 8 GB host constraint. It does **not** establish superiority: the tools have materially different persistence, service, filtering, and graph semantics. Before any ranking, repeat each completed run at least three times; then add a manually labeled symbol/call oracle, controlled file filters, warm/update measurements, MCP tool tasks, and the Flask/Werkzeug/Jinja multi-repo suite.
