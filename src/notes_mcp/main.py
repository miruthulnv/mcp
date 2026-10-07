"""Main entrypoint and HTTP application for notes-mcp."""

import logging
from typing import Any

import uvicorn
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from notes_mcp.auth import BearerAuthMiddleware
from notes_mcp.config import Settings, get_settings
from notes_mcp.server import create_mcp

logger = logging.getLogger(__name__)

_app_instance: Any = None


def create_app(settings: Settings | None = None) -> Any:
    """Build and configure the ASGI application with auth and health check."""
    if settings is None:
        settings = get_settings()

    # Configure logging
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level)

    # Build MCP server
    mcp = create_mcp(settings.db_path)

    # Configure transport security for reverse proxy / allowed hosts
    transport_security: TransportSecuritySettings | None = None
    if settings.allowed_hosts:
        if "*" in settings.allowed_hosts:
            transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
        else:
            hosts: list[str] = []
            for h in settings.allowed_hosts:
                hosts.append(h)
                if not h.endswith("*") and ":" not in h:
                    hosts.append(f"{h}:*")
            transport_security = TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=hosts,
            )

    # Streamable HTTP ASGI app at /mcp
    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        transport_security=transport_security,
        host=settings.host,
    )

    async def health_check(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    # Health check route (no auth)
    mcp_app.add_route("/health", health_check, methods=["GET"])

    # Wrap with Bearer authentication middleware
    return BearerAuthMiddleware(mcp_app, settings.auth_token)


async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    """Module-level ASGI application callable for uvicorn."""
    global _app_instance
    if _app_instance is None:
        _app_instance = create_app()
    await _app_instance(scope, receive, send)


def main() -> None:
    """Run uvicorn server using settings from environment."""
    settings = get_settings()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
