"""API Key authentication middleware — pure ASGI implementation."""

import logging
from typing import Callable

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from core.config import settings

logger = logging.getLogger(__name__)

# Paths that skip auth entirely (no API key needed)
PUBLIC_PATHS = {
    "/",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class ApiKeyAuthMiddleware:
    """
    Pure ASGI auth middleware — replaces BaseHTTPMiddleware.
    BaseHTTPMiddleware doesn't properly handle WebSocket scopes in some
    FastAPI/Starlette version combinations, causing 500 on WS connections.
    This pure ASGI implementation correctly distinguishes HTTP vs WebSocket.
    """

    def __init__(self, app: Callable):
        self.app = app

    async def __call__(self, scope, receive, send):
        """ASGI callable — receives raw scope dict, not a Request object."""
        if scope["type"] == "websocket":
            await self.app(scope, receive, send)
            return

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        headers = Headers(scope=scope)

        # Always-allowed paths
        if path in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        # Health and auth endpoints (no auth required)
        if path.startswith("/api/v1/health") or path.startswith("/api/v1/auth"):
            await self.app(scope, receive, send)
            return

        # API routes — validate API key
        if path.startswith("/api/"):
            api_key = headers.get("X-API-Key")
            query_key = None
            qs = scope.get("query_string", b"").decode()
            for param in qs.split("&"):
                if param.startswith("api_key="):
                    query_key = param.split("=", 1)[1]
                    break

            key = api_key or query_key
            if not key or key != settings.api_key:
                logger.warning(f"Auth failed for {path}: key_present={bool(key)}")
                # Build a 401 response directly as raw ASGI
                await self._send_401(scope, receive, send)
                return

        await self.app(scope, receive, send)

    async def _send_401(self, scope, receive, send):
        """Send a 401 response as raw ASGI."""
        status = "401 Unauthorized"
        headers = [(b"content-type", b"application/json")]
        body = b'{"detail":"Invalid or missing API key"}'

        async def asgi_wrapper(receive, send):
            await send({"type": "http.response.start", "status": 401, "headers": headers})
            await send({"type": "http.response.body", "body": body})

        await asgi_wrapper(receive, send)