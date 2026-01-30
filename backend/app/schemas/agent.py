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
    external_id: str = Field(
        ...,
        description="External system ID (e.g., from ERP)",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "ERP-AGT-001"}
    )
    name: str = Field(
        ...,
        description="Agent full name",
        min_length=1,
        max_length=255,
        json_schema_extra={"example": "Иванов Иван Иванович"}
    )
    phone: PhoneNumber = Field(
        default=None,
        json_schema_extra={"example": "+998901234567"}
    )
    email: Optional[str] = Field(
        None,
        description="Email address",
        max_length=255,
        json_schema_extra={"example": "agent@company.uz"}
    )
    start_latitude: Latitude = Field(
        json_schema_extra={"example": 41.311081}
    )
    start_longitude: Longitude = Field(
        json_schema_extra={"example": 69.279737}
    )
    end_latitude: LatitudeOptional = None
    end_longitude: LongitudeOptional = None
    work_start: time = Field(
        default=time(9, 0),
        description="Work start time (HH:MM)",
        json_schema_extra={"example": "09:00"}
    )
    work_end: time = Field(
        default=time(18, 0),
        description="Work end time (HH:MM)",
        json_schema_extra={"example": "18:00"}
    )
    max_visits_per_day: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Maximum visits agent can make per day",
        json_schema_extra={"example": 12}
    )
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
