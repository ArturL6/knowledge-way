# knowledge-way MCP server

`apps/mcp` is a local **stdio**, read-only MCP bridge over knowledge-way's existing public FastAPI endpoints. It never opens the database, executes a shell command, reads local files, or exposes write/index/delete/chat tools.

## Install and launch

Install its small, separate dependency set (prefer a virtual environment):

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r apps/mcp/requirements.txt
KW_API_BASE_URL=http://localhost:8000 \
  PYTHONPATH=apps/mcp python -m knowledge_way_mcp.server
```

`KW_API_BASE_URL` is required and must be an absolute `http` or `https` URL (no query or fragment). It may be the server root (`http://localhost:8000`) or include `/api` (`http://localhost:8000/api`). `KW_API_BEARER_TOKEN` is optional and, when set, is sent as an `Authorization: Bearer` header; it only becomes protection when the deployed API or its reverse proxy validates that header. The server writes MCP protocol traffic to stdio, so do not use its terminal output as an interactive prompt.

## Copy-paste local test

From the repository root, start the application stack and wait for the health check:

```bash
docker compose up -d --build
curl -fsS http://localhost:8000/health
```

Create the separate MCP environment once, then point it at the local API. Do **not** start this command manually when a client such as Claude Code or Cursor is configured below: the client starts it automatically.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r apps/mcp/requirements.txt

KW_API_BASE_URL=http://localhost:8000 \
  PYTHONPATH=apps/mcp python -m knowledge_way_mcp.server
```

To test the bridge directly, use the automated MCP tests:

```bash
PYTHONPATH=apps/mcp pytest -q apps/mcp/tests
```

### Connection model

```text
Your MCP-capable agent
  -- stdio/MCP --> knowledge_way_mcp.server (local subprocess)
  -- HTTP GET --> KW_API_BASE_URL (knowledge-way API)
  -- SQL/RQ --> PostgreSQL and worker services
```

For the standard local Docker deployment, use `http://localhost:8000`. For an agent in the same Kubernetes cluster, use the API Service DNS name; for an external agent, expose the API through a TLS-protected, authenticated ingress or VPN. The current local stack has no mandatory API authentication, so do not expose port 8000 publicly; when API auth is deployed, provide its token to the MCP process as `KW_API_BEARER_TOKEN` through the agent's secret mechanism.

## Available tools

- `list_repositories`
- `search_code(query, mode, limit)` — query up to 1,000 chars, limit 1–50
- `get_symbol(repository_id, symbol_id)`
- `get_callers(repository_id, symbol_id)`
- `get_callees(repository_id, symbol_id)`
- `get_subgraph(repository_id, symbol_id, depth, max_nodes)` — depth 1–2, nodes 1–100

Repository and symbol identifiers are capped at 256 characters. Internally every API operation is an HTTP `GET` under `/api/`.

## Client configuration

Use absolute paths in client configuration. Replace `/absolute/path/to/knowledge-way` and the API URL as appropriate. Add `KW_API_BEARER_TOKEN` only if your API deployment requires it.

### Claude Code

```json
{
  "mcpServers": {
    "knowledge-way": {
      "command": "/absolute/path/to/knowledge-way/.venv/bin/python",
      "args": ["-m", "knowledge_way_mcp.server"],
      "cwd": "/absolute/path/to/knowledge-way/apps/mcp",
      "env": {
        "KW_API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Cursor

Add this server object to Cursor's MCP configuration (usually `~/.cursor/mcp.json`):

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

### Hermes / generic stdio MCP client

Configure the same command, working directory, and environment in the client's generic stdio-MCP server entry:

```json
{
  "command": "/absolute/path/to/knowledge-way/.venv/bin/python",
  "args": ["-m", "knowledge_way_mcp.server"],
  "cwd": "/absolute/path/to/knowledge-way/apps/mcp",
  "env": {
    "KW_API_BASE_URL": "http://localhost:8000",
    "KW_API_BEARER_TOKEN": "optional-token"
  }
}
```

For Hermes-specific current configuration syntax, consult the Hermes Agent MCP documentation; this bridge itself is standard stdio MCP.

## Test

```bash
PYTHONPATH=apps/mcp pytest -q apps/mcp/tests
```
