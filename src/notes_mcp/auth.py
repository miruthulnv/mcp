"""Authentication middleware for notes-mcp."""

import hmac
from collections.abc import Callable
from typing import Any


class BearerAuthMiddleware:
    """ASGI middleware to enforce bearer token authentication.

    Allows GET /health without authentication.
    Requires 'Authorization: Bearer <token>' for all other routes.
    """

    def __init__(self, app: Any, auth_token: str) -> None:
        self.app = app
        self.auth_token = auth_token

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable,
        send: Callable,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()

        # Public health check endpoint
        if path == "/health" and method == "GET":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("latin1").strip()

        authenticated = False
        if auth_header.startswith("Bearer "):
            provided_token = auth_header[7:].strip()
            # Constant-time comparison to prevent timing attacks, never logging the token
            if hmac.compare_digest(provided_token, self.auth_token):
                authenticated = True

        if not authenticated:
            body = b'{"error": "Unauthorized"}'
            response_headers = [
                (b"content-type", b"application/json"),
                (b"www-authenticate", b"Bearer"),
                (b"content-length", str(len(body)).encode("ascii")),
            ]
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": response_headers,
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                }
            )
            return

        await self.app(scope, receive, send)
