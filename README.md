# Notes MCP Server

A lightweight MCP (Model Context Protocol) server that stores personal notes in SQLite
and exposes them to AI clients over Streamable HTTP at `/mcp`.

## Features
- `add_note`: Create a note with title, content, and optional tags.
- `get_note`: Fetch full note content by ID.
- `search_notes`: Search notes by keyword across title or content with preview.
- `list_recent_notes`: List recent notes newest first with preview.
- `update_note`: Selectively update title, content, or tags.
- `delete_note`: Delete a note and its associated tag relations.
- Resource `notes://tags`: Read all distinct tags and note counts.
- Prompt `summarize_recent_notes`: Template for summarizing notes from the last N days.

## Quick Start
```bash
cp .env.example .env
# Edit .env and set MCP_AUTH_TOKEN (generate with: openssl rand -hex 32)
docker compose up -d
```

## Connect to Claude & Clients
In Claude Desktop or developer IDEs (e.g. Cursor), add to your MCP client configuration:
```json
{
  "mcpServers": {
    "notes": {
      "url": "https://<your-domain>/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_AUTH_TOKEN>"
      }
    }
  }
}
```
*(In web connector UIs, supply `https://<your-domain>/mcp`; if the client requires custom headers, provide the Bearer token. See the Auth note below).*

## Configuration
| Variable | Default | Description |
|---|---|---|
| `MCP_AUTH_TOKEN` | *(required)* | Secret Bearer token for authenticating requests |
| `DB_PATH` | `data/notes.db` | File path to SQLite database |
| `HOST` | `0.0.0.0` | Host interface to bind server |
| `PORT` | `3000` | Port to listen on |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ALLOWED_HOSTS` | `*` | Comma-separated allowed hostnames or `*` to disable host check |

## Auth Note
v1 uses a static bearer token, which is suitable for personal use and testing with Claude Desktop, Cursor, and ChatGPT. Some clients' web connector UIs only support OAuth, so a later upgrade to OAuth through an external provider is planned.

## Deploy
Production deployment uses Docker Compose behind an nginx reverse proxy with SSL termination. See [deploy/nginx.conf.example](deploy/nginx.conf.example) for proxy configuration and `.github/workflows/release.yml` for automated CI/CD builds and VPS deployments.

## Development
```bash
uv sync
uv run pytest
uv run ruff check .
```

## License
MIT
