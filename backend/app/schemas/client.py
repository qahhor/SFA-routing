"""
Client schemas.
"""
from datetime import time, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.client import ClientCategory
from app.schemas.validators import (
    Latitude,
    Longitude,
    LatitudeOptional,
    LongitudeOptional,
    PhoneNumber,
)


class ClientBase(BaseModel):
    """Base client schema."""
    external_id: str = Field(
        ...,
        description="External system ID (e.g., from ERP)",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "ERP-CLT-001"}
    )
    name: str = Field(
        ...,
        description="Client/store name",
        min_length=1,
        max_length=255,
        json_schema_extra={"example": "Магазин 'Восток'"}
    )
    address: str = Field(
        ...,
        description="Physical address",
        min_length=1,
        max_length=500,
        json_schema_extra={"example": "г. Ташкент, ул. Навои, 15"}
    )
    phone: PhoneNumber = Field(
        default=None,
        json_schema_extra={"example": "+998712345678"}
    )
    contact_person: Optional[str] = Field(
        None,
        description="Contact person name",
        max_length=255,
        json_schema_extra={"example": "Ахмедов Рустам"}
    )
    latitude: Latitude = Field(
        json_schema_extra={"example": 41.299496}
    )
    longitude: Longitude = Field(
        json_schema_extra={"example": 69.240073}
    )
    category: ClientCategory = Field(
        default=ClientCategory.B,
        description="Client category: A (high priority), B (medium), C (low)",
        json_schema_extra={"example": "A"}
    )
    visit_duration_minutes: int = Field(
        default=15,
        ge=5,
        le=120,
        description="Expected visit duration in minutes",
        json_schema_extra={"example": 20}
    )
    time_window_start: time = Field(
        default=time(9, 0),
        description="Client opens at",
        json_schema_extra={"example": "09:00"}
    )
    time_window_end: time = Field(
        default=time(18, 0),
        description="Client closes at",
        json_schema_extra={"example": "18:00"}
    )
    agent_id: Optional[UUID] = Field(
        None,
        description="Assigned agent ID"
    )
    priority: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Visit priority (1-10, higher = more important)",
        json_schema_extra={"example": 5}
    )
    is_active: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_time_window(self):
        """Validate that time_window_start is before time_window_end."""
        if self.time_window_start >= self.time_window_end:
            raise ValueError("time_window_start must be before time_window_end")
        return self


class ClientCreate(ClientBase):
    """Schema for creating a client."""
    pass


class ClientUpdate(BaseModel):
    """Schema for updating a client."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    phone: PhoneNumber = None
    contact_person: Optional[str] = Field(None, max_length=255)
    latitude: LatitudeOptional = None
    longitude: LongitudeOptional = None
    category: Optional[ClientCategory] = None
    visit_duration_minutes: Optional[int] = Field(None, ge=5, le=120)
    time_window_start: Optional[time] = None
    time_window_end: Optional[time] = None
    agent_id: Optional[UUID] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None


class ClientResponse(ClientBase):
    """Schema for client response."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    agent_name: Optional[str] = Field(None, description="Assigned agent name")

    class Config:
        from_attributes = True


class ClientListResponse(BaseModel):
    """Schema for client list response."""
    items: list[ClientResponse]
    total: int
    page: int
    size: int
