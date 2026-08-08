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

`KW_API_BASE_URL` is required and must be an absolute `http` or `https` URL (no query or fragment). `KW_API_BEARER_TOKEN` is optional and, when set, is sent as an `Authorization: Bearer <token>` header. The server writes MCP protocol traffic to stdio, so do not use its terminal output as an interactive prompt.

Available bounded tools:

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
