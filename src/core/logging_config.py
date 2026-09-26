"""Structured logging with request correlation IDs.

Every log line carries a `request_id` field. Inside a request, that's the
value set by RequestIdMiddleware (from the incoming X-Request-ID header, or
a freshly generated UUID); outside a request (startup, a Celery task, a
script) it defaults to "-". JSON output is the default so logs are easy to
ship to any log aggregator; set LOG_JSON=false for human-readable text logs
during local development.
"""

import contextvars
import logging

from pythonjsonlogger import json as jsonlogger

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())

    if json_logs:
        formatter: logging.Formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
    else:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s [req=%(request_id)s]: %(message)s")

    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
