# AGENTS.md - Developer & Agent Guide

## Purpose
Notes MCP Server is a lightweight MCP server in Python exposing a personal SQLite notes database
to AI clients (e.g. Claude Desktop, Cursor) over Streamable HTTP at `/mcp`.

## Repository Layout
```
├── .github/workflows/     # CI (lint/test/build) and release (GHCR publish & VPS deploy)
├── deploy/                # Reverse proxy configs (deploy/nginx.conf.example)
├── src/notes_mcp/
│   ├── auth.py            # Constant-time Bearer token ASGI middleware
│   ├── config.py          # Environment settings with defaults & validation
│   ├── db.py              # Parameterized SQLite3 queries & tag management
│   ├── server.py          # FastMCP / MCPServer tools, resource, and prompt
│   └── main.py            # ASGI app assembly (/health + /mcp) and CLI runner
├── tests/                 # Pytest test suite covering auth, config, db, and tools
├── Dockerfile             # Multi-stage non-root container image
└── docker-compose.yml     # Compose spec with persistent SQLite volume
```

## Setup & Common Commands
- Setup: `uv sync`
- Run server: `MCP_AUTH_TOKEN=test uv run notes-mcp`
- Test: `uv run pytest`
- Lint & format: `uv run ruff check .` and `uv run ruff format .`
- Docker build & run: `docker compose up --build -d`

## Code Conventions & Rules
- Strictly typed Python 3.12+; no unnecessary abstractions or heavy ORMs.
- Parameterized SQL only (`?` placeholders). Never format strings into SQL queries.
- Tool errors must be returned as dicts (e.g. `{"error": "Note 12 not found"}`) rather than unhandled exceptions.
- Limit parameters clamped between 1 and 50. Search/list queries truncate content to ~200 chars.
- Never commit secrets or `.env` files. Keep `.env.example` updated.
- Use conventional commit messages (`feat:`, `fix:`, `chore:`, `docs:`, `ci:`).

## How to Add a New Tool
1. Add the database function taking a connection as first argument in `src/notes_mcp/db.py`.
2. Register the tool decorator `@mcp.tool()` inside `create_mcp()` in `src/notes_mcp/server.py`.
3. Add docstrings with clear descriptions of the tool and arguments (used by LLMs).
4. Clamp limits and validate inputs; return dict on error or success.
5. Add test coverage in `tests/test_db.py` and `tests/test_tools.py`.

## Testing with MCP Inspector
Start the server:
`MCP_AUTH_TOKEN=my-token uv run notes-mcp`
Launch Inspector:
`npx @modelcontextprotocol/inspector`
Connect using transport **Streamable HTTP**, URL `http://localhost:3000/mcp`, and header `Authorization: Bearer my-token`.

## API Deviations from Plan
- **FastMCP in `mcp` 2.x**: In `mcp>=2.0`, `FastMCP` was renamed to `MCPServer` (`from mcp.server.mcpserver import MCPServer`). We aliased `FastMCP = MCPServer` for backward compatibility.
- **Prompt string arguments**: MCP JSON-RPC protocol specification expects string values for prompt parameters (`arguments={"days": "7"}`).
