"""
Agent (Sales Representative) schemas.
"""
from datetime import time, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    """Base agent schema."""
    external_id: str = Field(..., description="External system ID")
    name: str = Field(..., description="Agent name")
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")
    start_latitude: Decimal = Field(..., description="Start point latitude")
    start_longitude: Decimal = Field(..., description="Start point longitude")
    end_latitude: Optional[Decimal] = Field(None, description="End point latitude")
    end_longitude: Optional[Decimal] = Field(None, description="End point longitude")
    work_start: time = Field(default=time(9, 0), description="Work start time")
    work_end: time = Field(default=time(18, 0), description="Work end time")
    max_visits_per_day: int = Field(default=30, ge=1, le=100)
    is_active: bool = Field(default=True)


class AgentCreate(AgentBase):
    """Schema for creating an agent."""
    pass


class AgentUpdate(BaseModel):
    """Schema for updating an agent."""
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    start_latitude: Optional[Decimal] = None
    start_longitude: Optional[Decimal] = None
    end_latitude: Optional[Decimal] = None
    end_longitude: Optional[Decimal] = None
    work_start: Optional[time] = None
    work_end: Optional[time] = None
    max_visits_per_day: Optional[int] = Field(None, ge=1, le=100)
    is_active: Optional[bool] = None


class AgentResponse(AgentBase):
    """Schema for agent response."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    clients_count: Optional[int] = Field(
        None, description="Number of assigned clients"
    )

    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    """Schema for agent list response."""
    items: list[AgentResponse]
    total: int
    page: int
    size: int
