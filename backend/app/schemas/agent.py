"""
Agent (Sales Representative) schemas.
"""
from datetime import time, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.validators import (
    Latitude,
    Longitude,
    LatitudeOptional,
    LongitudeOptional,
    PhoneNumber,
)


class AgentBase(BaseModel):
    """Base agent schema."""
    external_id: str = Field(..., description="External system ID", min_length=1, max_length=100)
    name: str = Field(..., description="Agent name", min_length=1, max_length=255)
    phone: PhoneNumber = None
    email: Optional[str] = Field(None, description="Email address", max_length=255)
    start_latitude: Latitude
    start_longitude: Longitude
    end_latitude: LatitudeOptional = None
    end_longitude: LongitudeOptional = None
    work_start: time = Field(default=time(9, 0), description="Work start time")
    work_end: time = Field(default=time(18, 0), description="Work end time")
    max_visits_per_day: int = Field(default=30, ge=1, le=100)
    is_active: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_end_coordinates(self):
        """Validate that both end coordinates are provided or neither."""
        if (self.end_latitude is None) != (self.end_longitude is None):
            raise ValueError("Both end_latitude and end_longitude must be provided together")
        return self

    @model_validator(mode="after")
    def validate_work_hours(self):
        """Validate that work_start is before work_end."""
        if self.work_start >= self.work_end:
            raise ValueError("work_start must be before work_end")
        return self


class AgentCreate(AgentBase):
    """Schema for creating an agent."""
    pass


class AgentUpdate(BaseModel):
    """Schema for updating an agent."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: PhoneNumber = None
    email: Optional[str] = Field(None, max_length=255)
    start_latitude: LatitudeOptional = None
    start_longitude: LongitudeOptional = None
    end_latitude: LatitudeOptional = None
    end_longitude: LongitudeOptional = None
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
