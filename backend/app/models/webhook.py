"""
Webhook subscription model.
"""

import uuid
from typing import Optional

from sqlalchemy import Boolean, String, JSON
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
    # Using JSON for database compatibility (works with both SQLite and PostgreSQL)
    events: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    owner_id: Mapped[uuid.UUID] = mapped_column(String(36), index=True)  # User who created it

    def __repr__(self):
        return f"<Webhook {self.name} ({self.url})>"
