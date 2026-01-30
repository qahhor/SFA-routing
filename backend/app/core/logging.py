"""
Structured logging configuration.

Features:
- JSON logging format for production
- Request ID tracking
- Correlation ID support
- Performance timing
"""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request context if available
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id

        user_id = user_id_var.get()
        if user_id:
            log_data["user_id"] = user_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


class HumanFormatter(logging.Formatter):
    """Human-readable log formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        request_id = request_id_var.get()
        user_id = user_id_var.get()

        context = ""
        if request_id:
            context += f"[{request_id[:8]}]"
        if user_id:
            context += f"[user:{user_id[:8]}]"

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"{timestamp} {record.levelname:8} {context:20} "
            f"{record.name}:{record.funcName}:{record.lineno} - {record.getMessage()}"
        )


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
) -> None:
    """
    Configure application logging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON format (for production)
    """
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Set formatter based on environment
    if json_format or not settings.DEBUG:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(HumanFormatter())

    # Configure root logger
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper()))

    # Configure specific loggers
    loggers_config = {
        "app": level,
        "uvicorn": "INFO",
        "uvicorn.access": "INFO",
        "sqlalchemy.engine": "WARNING" if not settings.DEBUG else "INFO",
        "httpx": "WARNING",
        "celery": "INFO",
    }

    for logger_name, logger_level in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, logger_level.upper()))


class StructuredLogger:
    """Enhanced logger with context support."""

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(
        self,
        level: int,
        msg: str,
        *args,
        extra: Optional[dict[str, Any]] = None,
        **kwargs,
    ):
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "",
            0,
            msg,
            args,
            None,
        )
        if extra:
            record.extra_fields = extra
        self._logger.handle(record)

    def debug(self, msg: str, *args, extra: Optional[dict[str, Any]] = None, **kwargs):
        self._log(logging.DEBUG, msg, *args, extra=extra, **kwargs)

    def info(self, msg: str, *args, extra: Optional[dict[str, Any]] = None, **kwargs):
        self._log(logging.INFO, msg, *args, extra=extra, **kwargs)

    def warning(self, msg: str, *args, extra: Optional[dict[str, Any]] = None, **kwargs):
        self._log(logging.WARNING, msg, *args, extra=extra, **kwargs)

    def error(self, msg: str, *args, extra: Optional[dict[str, Any]] = None, **kwargs):
        self._log(logging.ERROR, msg, *args, extra=extra, **kwargs)

    def exception(self, msg: str, *args, extra: Optional[dict[str, Any]] = None, **kwargs):
        kwargs["exc_info"] = True
        self._log(logging.ERROR, msg, *args, extra=extra, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger."""
    return StructuredLogger(name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request logging and tracking.

    Features:
    - Assigns unique request ID
    - Logs request/response
    - Tracks request timing
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_var.set(request_id)

        # Extract user ID if authenticated
        if hasattr(request.state, "user") and request.state.user:
            user_id_var.set(str(request.state.user.id))

        logger = logging.getLogger("app.requests")

        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
                "client_ip": request.client.host if request.client else None,
            },
        )

        # Process request
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as e:
            logger.exception(
                f"Request failed: {request.method} {request.url.path}",
                extra={"error": str(e)},
            )
            raise

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log response
        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response
