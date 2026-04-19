"""Custom middleware for the FinBot API."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from finbot.utils.logger import get_logger

logger = get_logger("finbot.api.middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and latency."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.time()
        response = await call_next(request)
        elapsed_ms = (time.time() - start) * 1000

        # Extract user from state if set by auth dependency
        user_id = getattr(request.state, "user_id", "anonymous") if hasattr(request, "state") else "anonymous"

        logger.info(
            "%s %s → %d (%.0fms) [user=%s]",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            user_id,
        )
        return response
