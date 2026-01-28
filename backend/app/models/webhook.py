"""
Webhook subscription model.
"""
import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class WebhookSubscription(Base, UUIDMixin, TimestampMixin):
    """
    Subscription for event notifications.
    """
    __tablename__ = "webhook_subscriptions"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(100), nullable=False)  # For HMAC signature
    
    # Events to subscribe to: ["optimization.completed", "optimization.failed"]
    # Storing as comma-separated string for simplicity in minimal DB setup, 
    # or ARRAY if Postgres specific. Let's use ARRAY(String) assuming Postgres.
    events: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    owner_id: Mapped[uuid.UUID] = mapped_column(String(36), index=True) # User who created it

    def __repr__(self):
        return f"<Webhook {self.name} ({self.url})>"
