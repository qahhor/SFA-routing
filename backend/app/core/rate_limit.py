"""
Rate limiting configuration for API endpoints.

Uses slowapi for request throttling based on client IP or user ID.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from app.core.config import settings


def get_rate_limit_key(request: Request) -> str:
    """
    Get rate limit key from request.

    Uses authenticated user ID if available, otherwise client IP.
    """
    # Check for authenticated user
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"

    # Fall back to IP address
    return get_remote_address(request)


def get_rate_limit_key_ip(request: Request) -> str:
    """Get rate limit key based on IP only."""
    return get_remote_address(request)


# Create limiter instance
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["200/minute"],
    storage_uri=settings.REDIS_URL,
    strategy="fixed-window",
)


# Rate limit presets for different endpoint types
class RateLimits:
    """Rate limit presets for different endpoint types."""

    # Auth endpoints - strict limits to prevent brute force
    AUTH_LOGIN = "5/minute"
    AUTH_REGISTER = "3/minute"
    AUTH_REFRESH = "10/minute"

    # Standard CRUD operations
    CRUD_READ = "100/minute"
    CRUD_WRITE = "30/minute"

    # Optimization endpoints - expensive operations
    OPTIMIZE_ROUTES = "10/minute"
    OPTIMIZE_WEEKLY = "5/minute"

    # Export endpoints
    EXPORT_PDF = "20/minute"

    # Health checks - generous limits
    HEALTH = "60/minute"

    # Default for unspecified endpoints
    DEFAULT = "200/minute"


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.

    Returns a JSON response with retry information.
    """
    # Parse retry-after from the exception
    retry_after = 60  # Default
    if hasattr(exc, "detail") and exc.detail:
        # Try to extract wait time from message
        import re

        match = re.search(r"(\d+)\s*second", str(exc.detail))
        if match:
            retry_after = int(match.group(1))

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "message": str(exc.detail) if exc.detail else "Too many requests",
            "retry_after_seconds": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


def setup_rate_limiting(app):
    """
    Configure rate limiting for the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
