"""
API Client management endpoints.

Admin endpoints for managing API clients (external services).
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.api_client import APIClient, ClientTier
from app.schemas.api_client import (
    APIClientCreate,
    APIClientList,
    APIClientResponse,
    APIClientUpdate,
    APIClientUsage,
    APIClientWithKey,
    APIKeyRegenerate,
)

router = APIRouter(prefix="/api-clients", tags=["API Clients"])


@router.post(
    "",
    response_model=APIClientWithKey,
    status_code=status.HTTP_201_CREATED,
    summary="Create new API Client",
    description="Create a new API client for external service access. "
    "**Save the returned API key - it won't be shown again!**",
)
async def create_api_client(
    client_data: APIClientCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new API client and return the API key."""
    # Generate API key
    full_key, key_prefix, key_hash = APIClient.generate_api_key()

    # Get tier limits
    tier = client_data.tier.lower()
    if tier not in [t.value for t in ClientTier]:
        tier = ClientTier.FREE.value

    # Create client
    api_client = APIClient(
        name=client_data.name,
        description=client_data.description,
        api_key_hash=key_hash,
        api_key_prefix=key_prefix,
        tier=tier,
        contact_email=client_data.contact_email,
        webhook_url=client_data.webhook_url,
        allowed_regions=client_data.allowed_regions,
        ip_whitelist=client_data.ip_whitelist,
    )

    # Apply tier limits
    tier_limits = api_client.get_tier_limits()
    api_client.rate_limit_per_minute = tier_limits["rate_limit_per_minute"]
    api_client.max_points_per_request = tier_limits["max_points_per_request"]
    api_client.monthly_quota = tier_limits["monthly_quota"]

    db.add(api_client)
    await db.commit()
    await db.refresh(api_client)

    # Return with full API key
    return APIClientWithKey(
        id=api_client.id,
        name=api_client.name,
        description=api_client.description,
        tier=api_client.tier,
        api_key=full_key,  # Only time full key is shown
        api_key_prefix=api_client.api_key_prefix,
        rate_limit_per_minute=api_client.rate_limit_per_minute,
        max_points_per_request=api_client.max_points_per_request,
        monthly_quota=api_client.monthly_quota,
        requests_this_month=api_client.requests_this_month,
        is_active=api_client.is_active,
        allowed_regions=api_client.allowed_regions,
        contact_email=api_client.contact_email,
        webhook_url=api_client.webhook_url,
        created_at=api_client.created_at,
        updated_at=api_client.updated_at,
        last_request_at=api_client.last_request_at,
    )


@router.get(
    "",
    response_model=APIClientList,
    summary="List API Clients",
)
async def list_api_clients(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    tier: Optional[str] = Query(None, description="Filter by tier"),
    db: AsyncSession = Depends(get_db),
):
    """List all API clients with pagination."""
    query = select(APIClient)

    if is_active is not None:
        query = query.where(APIClient.is_active == is_active)
    if tier:
        query = query.where(APIClient.tier == tier.lower())

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(APIClient.created_at.desc())

    result = await db.execute(query)
    clients = result.scalars().all()

    return APIClientList(
        items=[APIClientResponse.model_validate(c) for c in clients],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get(
    "/{client_id}",
    response_model=APIClientResponse,
    summary="Get API Client",
)
async def get_api_client(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get API client by ID."""
    result = await db.execute(select(APIClient).where(APIClient.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API client with ID {client_id} not found",
        )

    return APIClientResponse.model_validate(client)


@router.patch(
    "/{client_id}",
    response_model=APIClientResponse,
    summary="Update API Client",
)
async def update_api_client(
    client_id: UUID,
    update_data: APIClientUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update API client details."""
    result = await db.execute(select(APIClient).where(APIClient.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API client with ID {client_id} not found",
        )

    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)

    # If tier is being updated, also update limits
    if "tier" in update_dict:
        client.tier = update_dict["tier"].lower()
        tier_limits = client.get_tier_limits()
        client.rate_limit_per_minute = tier_limits["rate_limit_per_minute"]
        client.max_points_per_request = tier_limits["max_points_per_request"]
        client.monthly_quota = tier_limits["monthly_quota"]
        del update_dict["tier"]

    for key, value in update_dict.items():
        setattr(client, key, value)

    await db.commit()
    await db.refresh(client)

    return APIClientResponse.model_validate(client)


@router.post(
    "/{client_id}/regenerate-key",
    response_model=APIKeyRegenerate,
    summary="Regenerate API Key",
    description="Regenerate the API key for a client. **The old key will stop working immediately!**",
)
async def regenerate_api_key(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Regenerate API key for a client."""
    result = await db.execute(select(APIClient).where(APIClient.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API client with ID {client_id} not found",
        )

    # Generate new key
    full_key, key_prefix, key_hash = APIClient.generate_api_key()
    client.api_key_hash = key_hash
    client.api_key_prefix = key_prefix

    await db.commit()

    return APIKeyRegenerate(
        api_key=full_key,
        api_key_prefix=key_prefix,
    )


@router.get(
    "/{client_id}/usage",
    response_model=APIClientUsage,
    summary="Get API Client Usage",
)
async def get_client_usage(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get usage statistics for an API client."""
    result = await db.execute(select(APIClient).where(APIClient.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API client with ID {client_id} not found",
        )

    quota_percentage = 0.0
    if client.monthly_quota > 0:
        quota_percentage = (client.requests_this_month / client.monthly_quota) * 100

    return APIClientUsage(
        client_id=client.id,
        client_name=client.name,
        tier=client.tier,
        requests_this_month=client.requests_this_month,
        monthly_quota=client.monthly_quota,
        quota_percentage=round(quota_percentage, 2),
        rate_limit_per_minute=client.rate_limit_per_minute,
        last_request_at=client.last_request_at,
    )


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete API Client",
)
async def delete_api_client(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete (deactivate) an API client."""
    result = await db.execute(select(APIClient).where(APIClient.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API client with ID {client_id} not found",
        )

    # Soft delete - just deactivate
    client.is_active = False
    await db.commit()
