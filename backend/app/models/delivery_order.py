"""
Delivery order model.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.delivery_route import DeliveryRouteStop


class OrderStatus(str, enum.Enum):
    """Delivery order status."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryOrder(Base, UUIDMixin, TimestampMixin):
    """
    Delivery order to be fulfilled.
    """

    __tablename__ = "delivery_orders"

    # External reference
    external_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    # Client reference
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Order details
    weight_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    volume_m3: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )
    items_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Time window for delivery
    time_window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    time_window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Service time (time to unload at destination)
    service_time_minutes: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )

    # Priority (higher = more important)
    priority: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Status
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus),
        default=OrderStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    delivery_instructions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Tracking
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    client: Mapped["Client"] = relationship(
        "Client",
        back_populates="delivery_orders",
    )
    route_stop: Mapped[Optional["DeliveryRouteStop"]] = relationship(
        "DeliveryRouteStop",
        back_populates="order",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<DeliveryOrder {self.external_id}>"
