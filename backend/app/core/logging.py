"""Structured logging (section 44). JSON lines to stdout.

Usage: `logger = get_logger("module.name")` then
`logger.info("event.name", field=value, other_field=value)` -- fields are
attached as structured JSON, not interpolated into the message string.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)  # type: ignore[attr-defined]
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(level)


class StructuredLogger:
    """Thin wrapper so call sites can write `logger.info("event", key=value)`
    without colliding with stdlib logging's reserved keyword arguments."""

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _emit(self, level: int, event: str, **fields: Any) -> None:
        self._logger.log(level, event, extra={"extra_fields": fields})

    def debug(self, event: str, **fields: Any) -> None:
        self._emit(logging.DEBUG, event, **fields)

    def info(self, event: str, **fields: Any) -> None:
        self._emit(logging.INFO, event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._emit(logging.WARNING, event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self._emit(logging.ERROR, event, **fields)


def get_logger(name: str) -> StructuredLogger:
    return StructuredLogger(name)
