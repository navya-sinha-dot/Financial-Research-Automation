"""Shared slowapi rate limiter, keyed by client IP.

Applied to endpoints that trigger real work (a live SEC scrape, a PPTX
render) so a misbehaving client can't hammer the expensive paths.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
