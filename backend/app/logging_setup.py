"""Structured JSON logging (Spec 10, NFR-06): stdout + rotating file."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Structured fields we attach via `extra={...}` (Spec 10 log catalog)
_EXTRA_FIELDS = (
    "session_id", "stage", "duration_ms", "error", "step_id", "op",
    "plan_version", "deleted_sessions", "freed_bytes", "recovered",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in _EXTRA_FIELDS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    """Install the JSON formatter on stdout and (optionally) a rotating file."""
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JsonFormatter())
    handlers: list[logging.Handler] = [stdout_handler]

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(JsonFormatter())
        handlers.append(file_handler)

    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers = handlers
