"""
User model for authentication and authorization.
"""

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.agent import Agent


class UserRole(str, enum.Enum):
    """User roles for RBAC."""

    ADMIN = "admin"  # Full system access
    DISPATCHER = "dispatcher"  # Manage routes, agents, planning
    AGENT = "agent"  # View own routes and clients
    DRIVER = "driver"  # View own delivery routes


class User(Base, UUIDMixin, TimestampMixin):
    """User model for authentication."""

    __tablename__ = "users"

    # Authentication fields
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Profile fields
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Role and permissions
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.AGENT,
        nullable=False,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Optional link to Agent (for agents who are also users)
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Refresh token storage (for token invalidation)
    refresh_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    agent: Mapped[Optional["Agent"]] = relationship(
        "Agent",
        back_populates="user",
        foreign_keys=[agent_id],
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == UserRole.ADMIN or self.is_superuser

    @property
    def is_dispatcher(self) -> bool:
        """Check if user has dispatcher or higher role."""
        return self.role in (UserRole.ADMIN, UserRole.DISPATCHER) or self.is_superuser

    @property
    def can_manage_routes(self) -> bool:
        """Check if user can manage routes."""
        return self.role in (UserRole.ADMIN, UserRole.DISPATCHER)

    @property
    def can_view_all_agents(self) -> bool:
        """Check if user can view all agents."""
        return self.role in (UserRole.ADMIN, UserRole.DISPATCHER)
