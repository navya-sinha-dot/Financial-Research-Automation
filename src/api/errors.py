"""Consistent JSON error envelope for every error response the API returns.

Without this, a 404 from FastAPI's default HTTPException handler and a 422
from pydantic validation come back in two different shapes, which is an
annoying surprise for any client. Every error here comes back as:

    {"error": {"status_code": int, "message": str, "path": str, "details": [...]?}}
"""

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


def _error_body(status_code: int, message: str, path: str, details: list | None = None) -> dict:
    body: dict = {"error": {"status_code": status_code, "message": message, "path": path}}
    if details:
        body["error"]["details"] = details
    return body


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.status_code, str(exc.detail), request.url.path),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_body(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Request validation failed.",
                request.url.path,
                details=list(exc.errors()),
            ),
        )

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=_error_body(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Rate limit exceeded: {exc.detail}",
                request.url.path,
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "An unexpected error occurred.",
                request.url.path,
            ),
        )
