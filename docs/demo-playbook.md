# Guided demo playbook

This is a repeatable, local acceptance demo for repository admission, indexing, search, graph navigation, and the read-only MCP bridge. It uses the current Docker deployment and APIs—not a mock.

## Scope and prerequisites

Run commands from the repository root. Start with a clean database if repeatability matters:

```bash
cp .env.example .env
docker compose up --build -d
curl --fail http://localhost:8000/health
```

Expected: the last command returns `{"status":"ok"}`. The API will refuse a database that has not received the Alembic migrations; apply [the migration instructions](migrations.md) before starting it against a new database.

**Local resources.** Docker needs PostgreSQL, Redis, API, worker, and Next.js web containers. Reserve roughly 4 GB RAM and 10 GB free disk for the service plus one small clone; actual index time and storage scale with checkout size, number of source files, and embeddings. Start with one worker and one small repository. Do not use production credentials in this demo.

## Part 1: one small repository

Use [pallets/itsdangerous](https://github.com/pallets/itsdangerous), a compact Python repository with ordinary functions/classes and tests. It is a good parser/indexing smoke test without a large download.

### UI: add and index

1. Open [http://localhost:3000](http://localhost:3000).
2. Under **Connect a repository**, enter:
   - **Repository name:** `itsdangerous-demo`
   - **Clone URL:** `https://github.com/pallets/itsdangerous.git`
3. Click **Add repository**. The UI should say the first index was queued.
4. Refresh the dashboard until the card status is `ready`; record its **Current commit** and repository ID from the API command below. If it becomes `failed`, use the error displayed on the card and `docker compose logs worker api` before retrying.

**Pass criteria:** one dashboard card reaches `ready`, shows a non-empty commit SHA, and has no error message. `pending`/`indexing` means the test is still running, not a pass.

### API: prove the indexed data

Set the repository identifier (replace the name only if you chose another one):

```bash
export API=http://localhost:8000
export REPO_ID=$(curl -fsS "$API/api/repositories" | python3 -c 'import json,sys; print(next(r["id"] for r in json.load(sys.stdin) if r["name"] == "itsdangerous-demo"))')
curl -fsS "$API/api/repositories/$REPO_ID/status"
```

Expected: JSON has `"status":"ready"` and a non-empty `indexed_commit_sha`.

Search and retain a result's `file_id` and (for the graph) a result's `symbol_id`:

```bash
curl -fsSG "$API/api/search" --data-urlencode 'q=Signer' --data 'mode=hybrid&limit=10'
curl -fsSG "$API/api/search/symbols" --data-urlencode 'q=Signer'
curl -fsS "$API/api/repositories/$REPO_ID/tree?path=src"
```

**Pass criteria:** search returns one or more results with repository/path/line data; symbol search returns a `Signer`-related symbol; the tree contains source entries. Search is currently global, so confirm the returned `repository` is `itsdangerous-demo` rather than assuming a repository filter.

### Graph: inspect real relationships

The API graph is repository-scoped and requires an actual symbol ID. Copy one from the symbol-search result, then run:

```bash
export SYMBOL_ID='paste-symbol-id-here'
curl -fsS "$API/api/repositories/$REPO_ID/symbols/$SYMBOL_ID"
curl -fsS "$API/api/repositories/$REPO_ID/symbols/$SYMBOL_ID/callees"
curl -fsS "$API/api/repositories/$REPO_ID/symbols/$SYMBOL_ID/subgraph?depth=2&max_nodes=50"
```

Expected: the detail identifies the same repository; the subgraph response has the requested root, at most 50 nodes, and `depth: 2`. An empty caller/callee list is valid for a leaf symbol; it does *not* invalidate indexing. Choose another symbol if you need a non-empty edge demonstration.

The **Code graph** UI at `/graph` accepts the same repository and symbol IDs and a depth of 1–2. Its **Use fixture demo** button is deliberately synthetic and is not evidence of indexed graph data. In the current Docker topology, use the API commands above as the operational graph check: the graph screen requests same-origin `/api/...`, while the compose setup exposes the API separately on port 8000 rather than configuring a web reverse-proxy rewrite.

### MCP: query the same API through a client

Install the MCP bridge into a virtual environment and configure a stdio MCP client with this exact server entry (adjust only the absolute checkout path):

```json
{
  "mcpServers": {
    "knowledge-way": {
      "command": "/absolute/path/to/knowledge-way/.venv/bin/python",
      "args": ["-m", "knowledge_way_mcp.server"],
      "cwd": "/absolute/path/to/knowledge-way/apps/mcp",
      "env": {"KW_API_BASE_URL": "http://localhost:8000"}
    }
  }
}
```

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r apps/mcp/requirements.txt
```

Restart/reload the MCP client, then call:

1. `list_repositories` — find `itsdangerous-demo` and its ID.
2. `search_code` with `query: "Signer"`, `mode: "hybrid"`, `limit: 10` — verify an indexed result for the demo repository.
3. `get_symbol` with `repository_id: REPO_ID`, `symbol_id: SYMBOL_ID`.
4. `get_subgraph` with the same IDs, `depth: 2`, `max_nodes: 50`.

**Pass criteria:** all calls return API-backed JSON; `get_symbol` and `get_subgraph` identify only `REPO_ID`; the bounded subgraph has no more than 50 nodes. This MCP server is read-only: it cannot add, sync, reindex, delete, clone, or read a local checkout. See [MCP setup and client variants](mcp.md) for more clients and optional bearer-token handling.

## Part 2: multi-repository grouping test

Index every repository in a suite individually through the UI form above (or `POST /api/repositories` with `{"name":"…","clone_url":"…"}`), wait for each to be `ready`, and record each ID. Create a workspace and attach the IDs:

```bash
export WORKSPACE_ID=$(curl -fsS -X POST "$API/api/workspaces" -H 'content-type: application/json' \
  -d '{"name":"dependency-demo","description":"Related public repositories"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
curl -fsS -X PUT "$API/api/workspaces/$WORKSPACE_ID/repositories/$REPO_ID"
curl -fsS "$API/api/workspaces/$WORKSPACE_ID/repositories"
```

Expected: the final list contains the added repository. Repeat the `PUT` for the other repository IDs. A repository can belong to only one workspace; a second workspace assignment returns HTTP 409.

### Recommended public suites

Use a pinned commit/branch if reproducibility is essential. These relationships are documented by the projects' package metadata/documentation; the tests exercise Python/TypeScript parser paths and realistic, independently cloned repositories.

- **Small starter (Python):** [pallets/itsdangerous](https://github.com/pallets/itsdangerous) — Part 1.
- **Flask stack (Python, 3 repos):** [Flask](https://github.com/pallets/flask), [Werkzeug](https://github.com/pallets/werkzeug), and [Jinja](https://github.com/pallets/jinja). Flask documents Werkzeug and Jinja as dependencies in its [installation documentation](https://flask.palletsprojects.com/en/stable/installation/). Query `Flask`, `Request`, and `Template`; index all three, then group them as `flask-stack`.
- **FastAPI stack (Python, 3 repos):** [FastAPI](https://github.com/fastapi/fastapi), [Starlette](https://github.com/Kludex/starlette), and [Pydantic](https://github.com/pydantic/pydantic). FastAPI's [deployment dependencies](https://fastapi.tiangolo.com/deployment/versions/) document its Starlette and Pydantic requirements. Query `FastAPI`, `Starlette`, and `BaseModel`; group as `fastapi-stack`.
- **TypeScript tooling (2 repos):** [TypeScript](https://github.com/microsoft/TypeScript) and [typescript-eslint](https://github.com/typescript-eslint/typescript-eslint). typescript-eslint documents TypeScript as a [peer dependency](https://typescript-eslint.io/users/dependency-versions/). Query `Program`, `Parser`, and `typescript`; group as `typescript-eslint-stack`.

**Critical current limitation:** a workspace is an organizational membership list, **not** a unified code graph or dependency resolver. Indexing, symbol IDs, caller/callee/subgraph calls, and graph edges remain repository-scoped. Global text search may return hits from several repositories, but it does not infer that a Flask symbol resolves to Werkzeug, that FastAPI resolves to Starlette/Pydantic, or that typescript-eslint resolves to TypeScript. Treat matching names and package manifests as test observations, not cross-repository edges.

**Future acceptance criterion (not implemented):** after cross-repository resolution exists, repeat the same suites and require explicit, commit-pinned dependency/import edges between the independently indexed repositories, with provenance and an unambiguous workspace-scoped query. Do not claim that result from today's workspace grouping test.

## Private repositories and SSH

The indexer runs in the `worker` container and its checkout storage is mounted at `./data`; credentials are not persisted by knowledge-way. Verify Git access from the *worker context* before adding a private URL. For SSH, provide a deploy key/known-host configuration to that container through your deployment's secret mechanism, use a URL such as `git@github.com:org/private-repo.git`, and ensure the key is read-only. For HTTPS, use an approved credential helper or short-lived token mechanism that the worker can access; never put a token in a repository name, command history, logs, or a committed `.env`.

A private-repo pass requires: the worker can authenticate without an interactive prompt, the dashboard reaches `ready`, search results stay limited to the intended deployment audience, and MCP uses the API's configured authentication (`KW_API_BEARER_TOKEN` when applicable). This project does not yet provide production multi-user authorization; do not expose private content publicly.

## Cleanup

Remove test repositories from the dashboard using **Delete** and confirm the dialog. This removes indexed metadata/files/chunks/graph data but never changes the remote. Remove the workspace after removing its memberships:

```bash
curl -fsS -X DELETE "$API/api/workspaces/$WORKSPACE_ID"
curl -fsS -X DELETE "$API/api/repositories/$REPO_ID"
docker compose down
```

For a complete local reset—including PostgreSQL volume and `./data` checkouts—use this destructive command only after checking the path:

```bash
docker compose down -v
rm -rf ./data
```

Expected cleanup result: `GET /api/repositories` and `GET /api/workspaces` no longer list the test objects. Retain volumes/data instead if you intend to measure incremental sync or reindex behavior.
