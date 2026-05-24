"""API Key authentication middleware."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from core.config import settings


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for docs, health, root, and auth routes
        if (
            request.url.path in ["/", "/docs", "/openapi.json", "/redoc"]
            or request.url.path.startswith("/api/v1/health")
            or request.url.path.startswith("/api/v1/auth")
        ):
            return await call_next(request)

        if request.url.path.startswith("/api/"):
            api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
            if not api_key or api_key != settings.api_key:
                return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

        return await call_next(request)