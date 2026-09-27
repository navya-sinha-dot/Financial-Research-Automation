"""Request correlation ID + structured access logging middleware."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.logging_config import request_id_var

logger = logging.getLogger("fra.access")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assigns a request ID (from X-Request-ID if the caller sent one, else
    a fresh UUID), makes it available to every log line emitted while
    handling the request via a contextvar, echoes it back on the response,
    and logs one structured line per request with status and duration.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = request_id_var.set(request_id)
        start = time.monotonic()
        try:
            response = await call_next(request)
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        finally:
            request_id_var.reset(token)
