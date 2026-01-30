"""
Visit plan model for scheduled visits.
"""

import enum
import uuid
from datetime import date, datetime, time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.client import Client


class VisitStatus(str, enum.Enum):
    """Visit status enumeration."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class VisitPlan(Base, UUIDMixin, TimestampMixin):
    """
    Planned visit to a client.

    Links an agent to a client for a specific date and time.
    """

    __tablename__ = "visit_plans"

    # Foreign keys
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Planning details
    planned_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    planned_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )
    estimated_arrival_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    estimated_departure_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )

    # Route sequence (1 = first visit of the day)
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Distance and duration from previous point
    distance_from_previous_km: Mapped[Optional[float]] = mapped_column(
        nullable=True,
    )
    duration_from_previous_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Status tracking
    status: Mapped[VisitStatus] = mapped_column(
        Enum(VisitStatus),
        default=VisitStatus.PLANNED,
        nullable=False,
    )

    # Actual visit times (filled when visit is completed)
    actual_arrival_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_departure_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    skip_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    agent: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="visit_plans",
    )
    client: Mapped["Client"] = relationship(
        "Client",
        back_populates="visit_plans",
    )

    # Constraints
    __table_args__ = (UniqueConstraint("agent_id", "client_id", "planned_date", name="uq_agent_client_date"),)

    def __repr__(self) -> str:
        return f"<VisitPlan {self.agent_id} -> {self.client_id} on {self.planned_date}>"
