"""
Sentry integration for error tracking and performance monitoring.

Features:
- Automatic exception capture
- Performance tracing
- User context
- Custom tags and breadcrumbs
"""

import logging
from contextvars import ContextVar
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Sentry SDK is optional - gracefully degrade if not installed
try:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.httpx import HttpxIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    sentry_sdk = None

# Context for user tracking
_user_context: ContextVar[Optional[dict]] = ContextVar("sentry_user", default=None)


def init_sentry() -> bool:
    """
    Initialize Sentry SDK.

    Call this once during application startup.

    Returns:
        True if Sentry was initialized, False otherwise.
    """
    if not SENTRY_AVAILABLE:
        logger.info("Sentry SDK not installed, error tracking disabled")
        return False

    dsn = getattr(settings, "SENTRY_DSN", None)
    if not dsn:
        logger.info("SENTRY_DSN not configured, error tracking disabled")
        return False

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=settings.ENVIRONMENT,
            release=f"{settings.APP_NAME}@{settings.APP_VERSION}",
            # Performance monitoring
            traces_sample_rate=0.1 if settings.ENVIRONMENT == "production" else 1.0,
            profiles_sample_rate=0.1 if settings.ENVIRONMENT == "production" else 1.0,
            # Integrations
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
                CeleryIntegration(),
                HttpxIntegration(),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR,
                ),
            ],
            # Data scrubbing
            send_default_pii=False,
            before_send=_before_send,
            before_send_transaction=_before_send_transaction,
            # Breadcrumbs
            max_breadcrumbs=50,
            # Other options
            attach_stacktrace=True,
            request_bodies="small",
            with_locals=settings.ENVIRONMENT != "production",
        )

        logger.info(f"Sentry initialized for {settings.ENVIRONMENT} environment")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
        return False


def _before_send(event: dict, hint: dict) -> Optional[dict]:
    """
    Process event before sending to Sentry.

    Filter out noisy events and add context.
    """
    # Filter out expected errors
    if "exc_info" in hint:
        exc_type, exc_value, _ = hint["exc_info"]

        # Don't report client errors
        if exc_type.__name__ in (
            "HTTPException",
            "ValidationError",
            "RateLimitExceeded",
        ):
            status_code = getattr(exc_value, "status_code", None)
            if status_code and 400 <= status_code < 500:
                return None

    # Add user context
    user = _user_context.get()
    if user:
        event["user"] = user

    return event


def _before_send_transaction(event: dict, hint: dict) -> Optional[dict]:
    """
    Process transaction before sending to Sentry.

    Filter out noisy transactions.
    """
    # Skip health check transactions
    transaction_name = event.get("transaction", "")
    if any(path in transaction_name for path in ["/health", "/metrics", "/docs"]):
        return None

    return event


def set_user_context(
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    username: Optional[str] = None,
    ip_address: Optional[str] = None,
    extra: Optional[dict] = None,
):
    """
    Set user context for error tracking.

    Call this after authentication to attach user info to errors.
    """
    if not SENTRY_AVAILABLE:
        return

    user_data = {}
    if user_id:
        user_data["id"] = user_id
    if email:
        user_data["email"] = email
    if username:
        user_data["username"] = username
    if ip_address:
        user_data["ip_address"] = ip_address
    if extra:
        user_data.update(extra)

    _user_context.set(user_data)

    if sentry_sdk:
        sentry_sdk.set_user(user_data)


def clear_user_context():
    """Clear user context."""
    _user_context.set(None)
    if sentry_sdk:
        sentry_sdk.set_user(None)


def capture_exception(
    error: Exception,
    extra: Optional[dict] = None,
    tags: Optional[dict] = None,
    level: str = "error",
):
    """
    Capture exception and send to Sentry.

    Args:
        error: Exception to capture
        extra: Additional context data
        tags: Tags for filtering
        level: Severity level
    """
    if not SENTRY_AVAILABLE or not sentry_sdk:
        logger.exception("Error (Sentry disabled)", exc_info=error)
        return

    with sentry_sdk.push_scope() as scope:
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)
        if tags:
            for key, value in tags.items():
                scope.set_tag(key, value)
        scope.level = level

        sentry_sdk.capture_exception(error)


def capture_message(
    message: str,
    level: str = "info",
    extra: Optional[dict] = None,
    tags: Optional[dict] = None,
):
    """
    Capture a message and send to Sentry.

    Args:
        message: Message to capture
        level: Severity level (debug, info, warning, error, fatal)
        extra: Additional context data
        tags: Tags for filtering
    """
    if not SENTRY_AVAILABLE or not sentry_sdk:
        logger.log(
            getattr(logging, level.upper(), logging.INFO),
            f"Message (Sentry disabled): {message}",
        )
        return

    with sentry_sdk.push_scope() as scope:
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)
        if tags:
            for key, value in tags.items():
                scope.set_tag(key, value)
        scope.level = level

        sentry_sdk.capture_message(message)


def add_breadcrumb(
    message: str,
    category: str = "custom",
    level: str = "info",
    data: Optional[dict] = None,
):
    """
    Add a breadcrumb to the current scope.

    Breadcrumbs are events leading up to an error.
    """
    if not SENTRY_AVAILABLE or not sentry_sdk:
        return

    sentry_sdk.add_breadcrumb(
        category=category,
        message=message,
        level=level,
        data=data,
    )


def start_transaction(
    name: str,
    op: str = "task",
    description: Optional[str] = None,
):
    """
    Start a new transaction for performance monitoring.

    Usage:
        with start_transaction("process_order", op="task") as transaction:
            # ... do work ...
            transaction.set_status("ok")
    """
    if not SENTRY_AVAILABLE or not sentry_sdk:
        # Return a no-op context manager
        class NoOpTransaction:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def set_status(self, status):
                pass

            def set_tag(self, key, value):
                pass

            def set_data(self, key, value):
                pass

        return NoOpTransaction()

    return sentry_sdk.start_transaction(
        name=name,
        op=op,
        description=description,
    )


def start_span(
    op: str,
    description: Optional[str] = None,
):
    """
    Start a new span within the current transaction.

    Usage:
        with start_span(op="db.query", description="fetch users"):
            # ... do work ...
    """
    if not SENTRY_AVAILABLE or not sentry_sdk:

        class NoOpSpan:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def set_status(self, status):
                pass

            def set_tag(self, key, value):
                pass

            def set_data(self, key, value):
                pass

        return NoOpSpan()

    return sentry_sdk.start_span(
        op=op,
        description=description,
    )


def set_tag(key: str, value: Any):
    """Set a tag on the current scope."""
    if SENTRY_AVAILABLE and sentry_sdk:
        sentry_sdk.set_tag(key, str(value))


def set_context(name: str, data: dict):
    """Set context data on the current scope."""
    if SENTRY_AVAILABLE and sentry_sdk:
        sentry_sdk.set_context(name, data)
