"""
Client model with geolocation.
"""
import enum
import uuid
from datetime import time, date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Time, Numeric, Integer, Enum, ForeignKey, Boolean, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.visit_plan import VisitPlan
    from app.models.delivery_order import DeliveryOrder


class ClientCategory(str, enum.Enum):
    """
    Client category determining visit frequency.

    A: 2 visits per week (key accounts)
    B: 1 visit per week (regular)
    C: 1 visit per 2 weeks (small accounts)
    """
    A = "A"
    B = "B"
    C = "C"


class Client(Base, UUIDMixin, TimestampMixin):
    """
    Client model representing a delivery point or store.
    """

    __tablename__ = "clients"

    # External system integration
    external_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Geolocation
    latitude: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
        index=True,
    )
    longitude: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
        index=True,
    )

    # Category and visit settings
    category: Mapped[ClientCategory] = mapped_column(
        Enum(ClientCategory),
        default=ClientCategory.B,
        nullable=False,
    )
    visit_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=15,
        nullable=False,
    )

    # Time window when client is available
    time_window_start: Mapped[time] = mapped_column(
        Time,
        default=time(9, 0),
        nullable=False,
    )
    time_window_end: Mapped[time] = mapped_column(
        Time,
        default=time(18, 0),
        nullable=False,
    )

    # Assigned agent
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Priority (higher = more important)
    priority: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # FMCG Analytical Fields (Synced from ERP/ML)
    outstanding_debt: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), default=0)
    stock_days_remaining: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    churn_risk_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2), default=0) # 0.00 to 1.00
    last_order_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_new_client: Mapped[bool] = mapped_column(Boolean, default=False)
    has_active_promo: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    agent: Mapped[Optional["Agent"]] = relationship(
        "Agent",
        back_populates="clients",
    )
    visit_plans: Mapped[list["VisitPlan"]] = relationship(
        "VisitPlan",
        back_populates="client",
        lazy="selectin",
    )
    delivery_orders: Mapped[list["DeliveryOrder"]] = relationship(
        "DeliveryOrder",
        back_populates="client",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Client {self.name} ({self.external_id})>"

    @property
    def location(self) -> tuple[float, float]:
        """Get location as (lat, lon) tuple."""
        return (float(self.latitude), float(self.longitude))

    @property
    def visits_per_week(self) -> float:
        """Get required visits per week based on category."""
        frequency_map = {
            ClientCategory.A: 2.0,
            ClientCategory.B: 1.0,
            ClientCategory.C: 0.5,
        }
        return frequency_map[self.category]
