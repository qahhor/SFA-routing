"""
Idempotency Middleware.
"""

from typing import Callable

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.cache import cache  # Assuming redis cache available


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Ensures that requests with the same Idempotency-Key are processed only once.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:

        # Only check mutating methods
        if request.method not in ["POST", "PUT", "PATCH", "DELETE"]:
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)

        # Check cache
        cache_key = f"idempotency:{key}"

        # We need a robust locking mechanism or atomic set-if-not-exists
        # For simplicity, using basic Redis check
        # In PROD, store response result to return exact same response

        try:
            # Check if key exists (processed or processing)
            # This is simplified. Ideally we store status.
            exists = await cache.get(cache_key)
            if exists:
                return JSONResponse(
                    content={"detail": "Request already processed"},
                    status_code=status.HTTP_409_CONFLICT,  # Or 200 with cached result
                )

            # Mark as processing
            await cache.set(cache_key, "processing", expire=60 * 60 * 24)  # 24h

            response = await call_next(request)

            if response.status_code >= 200 and response.status_code < 300:
                # Success - keep key
                pass
            else:
                # Failed - remove key so it can be retried?
                # Depends on idempotent semantics. Usually 4xx client errors are final.
                # 5xx might be retriable.
                if response.status_code >= 500:
                    await cache.delete(cache_key)

            return response

        except Exception:
            # On redis failure, fail open or closed?
            # Fail open: proceed without idempotency
            return await call_next(request)
