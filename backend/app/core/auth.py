"""
API Key authentication middleware and dependencies.

Provides:
- API Key validation via X-API-Key header
- Rate limiting per client
- Request logging
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.api_client import APIClient

# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyAuth:
    """API Key authentication handler."""

    @staticmethod
    async def get_client_by_api_key(
        db: AsyncSession,
        api_key: str,
    ) -> Optional[APIClient]:
        """
        Find API client by API key.

        Args:
            db: Database session
            api_key: The API key to lookup

        Returns:
            APIClient if found and active, None otherwise
        """
        key_hash = APIClient.hash_api_key(api_key)

        result = await db.execute(
            select(APIClient).where(
                APIClient.api_key_hash == key_hash,
                APIClient.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_usage(
        db: AsyncSession,
        client: APIClient,
    ) -> None:
        """Update client usage statistics."""
        client.requests_this_month += 1
        client.last_request_at = datetime.now(timezone.utc)
        await db.commit()


async def get_api_client(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> APIClient:
    """
    Dependency to validate API key and get client.

    Raises:
        HTTPException: If API key is missing, invalid, or quota exceeded
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required. Please provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    client = await APIKeyAuth.get_client_by_api_key(db, api_key)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key or client is deactivated.",
        )

    # Check quota
    if client.is_quota_exceeded():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly quota exceeded. Limit: {client.monthly_quota} requests.",
            headers={"Retry-After": "86400"},  # Retry after 1 day
        )

    # Store client in request state for later use
    request.state.api_client = client
    request.state.api_client_id = client.id

    # Update usage (don't await to not slow down request)
    await APIKeyAuth.update_usage(db, client)

    return client


async def get_optional_api_client(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Optional[APIClient]:
    """
    Optional API client dependency for public endpoints.

    Returns None if no API key provided (for public access).
    """
    if not api_key:
        return None

    return await get_api_client(request, api_key, db)


def require_tier(min_tier: str):
    """
    Dependency factory to require minimum subscription tier.

    Usage:
        @router.post("/advanced-feature")
        async def advanced_feature(
            client: APIClient = Depends(require_tier("pro"))
        ):
            ...
    """
    tier_order = {"free": 0, "basic": 1, "pro": 2, "enterprise": 3}

    async def tier_checker(
        client: APIClient = Depends(get_api_client),
    ) -> APIClient:
        client_tier_level = tier_order.get(client.tier, 0)
        required_tier_level = tier_order.get(min_tier, 0)

        if client_tier_level < required_tier_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires '{min_tier}' tier or higher. " f"Your current tier: '{client.tier}'.",
            )
        return client

    return tier_checker


def check_points_limit(points_count: int):
    """
    Dependency factory to check points limit per request.

    Usage:
        @router.post("/optimize")
        async def optimize(
            points: list[Point],
            client: APIClient = Depends(check_points_limit(len(points)))
        ):
            ...
    """

    async def points_checker(
        client: APIClient = Depends(get_api_client),
    ) -> APIClient:
        if points_count > client.max_points_per_request:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Too many points in request. "
                f"Maximum: {client.max_points_per_request}, "
                f"Provided: {points_count}. "
                f"Upgrade your tier for higher limits.",
            )
        return client

    return points_checker
