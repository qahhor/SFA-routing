"""
Delivery route models.
"""
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    String, Date, Numeric, Integer, Enum, ForeignKey,
    DateTime, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.vehicle import Vehicle
    from app.models.delivery_order import DeliveryOrder


class RouteStatus(str, enum.Enum):
    """Delivery route status."""
    DRAFT = "draft"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DeliveryRoute(Base, UUIDMixin, TimestampMixin):
    """
    Optimized delivery route for a vehicle.
    """

    __tablename__ = "delivery_routes"

    # Vehicle assignment
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Route date
    route_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    # Route metrics
    total_distance_km: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0"),
        nullable=False,
    )
    total_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_weight_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0"),
        nullable=False,
    )
    total_stops: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Route geometry (GeoJSON LineString)
    geometry: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Status
    status: Mapped[RouteStatus] = mapped_column(
        Enum(RouteStatus),
        default=RouteStatus.DRAFT,
        nullable=False,
    )

    # Timing
    planned_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    planned_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    vehicle: Mapped["Vehicle"] = relationship(
        "Vehicle",
        back_populates="delivery_routes",
    )
    stops: Mapped[list["DeliveryRouteStop"]] = relationship(
        "DeliveryRouteStop",
        back_populates="route",
        order_by="DeliveryRouteStop.sequence_number",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<DeliveryRoute {self.id} for {self.route_date}>"


class DeliveryRouteStop(Base, UUIDMixin, TimestampMixin):
    """
    Individual stop in a delivery route.
    """

    __tablename__ = "delivery_route_stops"

    # Route reference
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_routes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Order reference
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Sequence in route (1 = first stop)
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Distance and time from previous stop
    distance_from_previous_km: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0"),
        nullable=False,
    )
    duration_from_previous_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Planned arrival time
    planned_arrival: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    planned_departure: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Actual times
    actual_arrival: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_departure: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    route: Mapped["DeliveryRoute"] = relationship(
        "DeliveryRoute",
        back_populates="stops",
    )
    order: Mapped["DeliveryOrder"] = relationship(
        "DeliveryOrder",
        back_populates="route_stop",
    )

    def __repr__(self) -> str:
        return f"<DeliveryRouteStop #{self.sequence_number} in route {self.route_id}>"
