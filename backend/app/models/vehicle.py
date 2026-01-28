"""
Vehicle model for delivery fleet.
"""
import uuid
from decimal import Decimal
from datetime import time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Numeric, Boolean, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.delivery_route import DeliveryRoute


class Vehicle(Base, UUIDMixin, TimestampMixin):
    """
    Delivery vehicle with capacity constraints.
    """

    __tablename__ = "vehicles"

    # Identification
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    license_plate: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )

    # Capacity constraints
    capacity_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    capacity_volume_m3: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Start/end location (depot)
    start_latitude: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )
    start_longitude: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )
    end_latitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )
    end_longitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )

    # Working hours
    work_start: Mapped[time] = mapped_column(
        Time,
        default=time(8, 0),
        nullable=False,
    )
    work_end: Mapped[time] = mapped_column(
        Time,
        default=time(20, 0),
        nullable=False,
    )

    # Cost parameters (for optimization)
    cost_per_km: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        default=Decimal("1.0"),
        nullable=True,
    )
    fixed_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0"),
        nullable=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Driver info (optional)
    driver_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    driver_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    delivery_routes: Mapped[list["DeliveryRoute"]] = relationship(
        "DeliveryRoute",
        back_populates="vehicle",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Vehicle {self.name} ({self.license_plate})>"

    @property
    def start_location(self) -> tuple[float, float]:
        """Get start location as (lat, lon) tuple."""
        return (float(self.start_latitude), float(self.start_longitude))

    @property
    def end_location(self) -> tuple[float, float]:
        """Get end location as (lat, lon) tuple."""
        if self.end_latitude and self.end_longitude:
            return (float(self.end_latitude), float(self.end_longitude))
        return self.start_location
