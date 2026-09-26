"""Unit tests for structured logging: the request-id contextvar/filter and
configure_logging's handler setup.
"""
import logging

from src.core.logging_config import RequestIdFilter, configure_logging, request_id_var


def test_request_id_filter_attaches_current_context_value():
    token = request_id_var.set("abc-123")
    try:
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", None, None)
        result = RequestIdFilter().filter(record)
        assert result is True
        assert record.request_id == "abc-123"
    finally:
        request_id_var.reset(token)


def test_request_id_filter_defaults_to_dash_outside_a_request():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", None, None)
    RequestIdFilter().filter(record)
    assert record.request_id == "-"


def test_configure_logging_installs_a_single_handler_with_the_filter():
    configure_logging(level="DEBUG", json_logs=True)
    root = logging.getLogger()
    assert len(root.handlers) == 1
    handler = root.handlers[0]
    assert any(isinstance(f, RequestIdFilter) for f in handler.filters)
    assert root.level == logging.DEBUG


def test_configure_logging_supports_plain_text_mode():
    configure_logging(level="INFO", json_logs=False)
    root = logging.getLogger()
    handler = root.handlers[0]
    assert "request_id" in handler.formatter._fmt
