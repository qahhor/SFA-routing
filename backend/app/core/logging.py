"""
Structured logging configuration.
"""
import json
import logging
import sys
from typing import Any

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings after parsing the LogRecord.
    """

    def __init__(self, fmt=None, datefmt=None, style='%', validate=True):
        super().__init__(fmt, datefmt, style, validate)

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)

        log_record: dict[str, Any] = {
            "timestamp": record.asctime,
            "level": record.levelname,
            "message": record.message,
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Add extra fields safely
        if hasattr(record, "extra"):
            log_record.update(record.extra) # type: ignore

        return json.dumps(log_record)


def setup_logging():
    """Configure logging."""
    logger = logging.getLogger()
    logger.setLevel(settings.LOG_LEVEL if hasattr(settings, "LOG_LEVEL") else logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    
    # Remove existing handlers
    logger.handlers = []
    logger.addHandler(handler)
    
    # Set levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
