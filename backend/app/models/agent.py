"""
Agent (Sales Representative) model.
"""
import uuid
from datetime import time
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Time, Numeric, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.visit_plan import VisitPlan
    from app.models.user import User


class Agent(Base, UUIDMixin, TimestampMixin):
    """
    Sales representative (торговый представитель) model.

    Each agent has ~300 assigned clients and visits 25-30 per day.
    """

    __tablename__ = "agents"

    # External system integration
    external_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    # Personal info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Start location (office or home)
    start_latitude: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )
    start_longitude: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    # End location (defaults to start if not set)
    end_latitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )
    end_longitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )

    # Real-time Location
    current_latitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )
    current_longitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )
    last_gps_update: Mapped[Optional[time]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Working hours
    work_start: Mapped[time] = mapped_column(
        Time,
        default=time(9, 0),
        nullable=False,
    )
    work_end: Mapped[time] = mapped_column(
        Time,
        default=time(18, 0),
        nullable=False,
    )

    # Planning constraints
    max_visits_per_day: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    clients: Mapped[list["Client"]] = relationship(
        "Client",
        back_populates="agent",
        lazy="selectin",
    )
    visit_plans: Mapped[list["VisitPlan"]] = relationship(
        "VisitPlan",
        back_populates="agent",
        lazy="selectin",
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="agent",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<Agent {self.name} ({self.external_id})>"

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
