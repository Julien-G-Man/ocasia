"""
FastAPI Middleware for Internal Request Authentication

Verifies that requests from Django include the correct secret header.
"""
import hmac
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.config import settings

logger = logging.getLogger(__name__)


class InternalAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to verify internal requests from Django.

    Rules:
    - `/health` is public (for uptime probes / warmup pings).
    - All other endpoints require valid `X-Internal-Secret`.
    - Browser requests with `Origin` must come from FASTAPI_ALLOWED_ORIGINS.
    """

    async def dispatch(self, request: Request, call_next):
        # Keep health endpoint publicly accessible.
        if request.url.path == "/health":
            return await call_next(request)

        # If this is a browser-originated request, enforce strict origin allowlist.
        origin = request.headers.get("origin")
        allowed = settings.allowed_origins_set
        if origin and allowed and origin not in allowed:
            logger.warning(
                "Request to %s blocked due to disallowed Origin: %s",
                request.url.path,
                origin,
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Origin not allowed"},
            )

        internal_secret = request.headers.get("X-Internal-Secret")

        if not internal_secret:
            logger.warning("Request to %s missing X-Internal-Secret header", request.url.path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing internal authentication header"},
            )

        if not settings.FASTAPI_SECRET or not hmac.compare_digest(internal_secret, settings.FASTAPI_SECRET):
            logger.warning("Request to %s has invalid internal secret", request.url.path)
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid internal authentication secret"},
            )

        return await call_next(request)
