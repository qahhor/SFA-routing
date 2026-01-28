"""
Webhook management endpoints.
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.webhook import WebhookSubscription

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class WebhookCreate(BaseModel):
    name: str
    url: str
    secret: str
    events: List[str]
    description: str = None


class WebhookResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    events: List[str]
    is_active: bool
    created_at: str # ISO format

    class Config:
        from_attributes = True


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    webhook: WebhookCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new webhook."""
    # Validate events? (Optional: check against allowed list)
    
    new_hook = WebhookSubscription(
        name=webhook.name,
        url=webhook.url,
        secret=webhook.secret,
        events=webhook.events,
        description=webhook.description,
        owner_id=current_user.id
    )
    
    db.add(new_hook)
    await db.commit()
    await db.refresh(new_hook)
    
    return new_hook


@router.get("", response_model=List[WebhookResponse])
async def list_webhooks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List my webhooks."""
    query = select(WebhookSubscription).where(
        WebhookSubscription.owner_id == current_user.id
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook."""
    query = select(WebhookSubscription).where(
        WebhookSubscription.id == webhook_id,
        WebhookSubscription.owner_id == current_user.id
    )
    result = await db.execute(query)
    hook = result.scalar_one_or_none()
    
    if not hook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )
        
    await db.delete(hook)
    await db.commit()
    return None
