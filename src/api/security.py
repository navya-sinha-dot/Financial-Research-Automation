"""API key authentication for mutating endpoints.

Read (GET) endpoints stay open so the app is easy to demo/browse. Anything
that triggers work with a real cost -- scraping, report rendering, writing
data -- requires `X-API-Key` when `settings.API_KEY` is configured. Leaving
`API_KEY` empty (the default) disables auth entirely for local development.
"""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.core.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(provided_key: str | None = Security(_api_key_header)) -> None:
    if not settings.API_KEY:
        return  # Auth disabled -- no key configured.
    if provided_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
        )
