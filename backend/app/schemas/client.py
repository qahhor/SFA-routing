"""
Client schemas.
"""
from datetime import time, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.client import ClientCategory


class ClientBase(BaseModel):
    """Base client schema."""
    external_id: str = Field(..., description="External system ID")
    name: str = Field(..., description="Client name")
    address: str = Field(..., description="Physical address")
    phone: Optional[str] = Field(None, description="Phone number")
    contact_person: Optional[str] = Field(None, description="Contact person name")
    latitude: Decimal = Field(..., description="Latitude")
    longitude: Decimal = Field(..., description="Longitude")
    category: ClientCategory = Field(
        default=ClientCategory.B,
        description="Client category (A, B, C)"
    )
    visit_duration_minutes: int = Field(default=15, ge=5, le=120)
    time_window_start: time = Field(default=time(9, 0))
    time_window_end: time = Field(default=time(18, 0))
    agent_id: Optional[UUID] = Field(None, description="Assigned agent ID")
    priority: int = Field(default=1, ge=1, le=10)
    is_active: bool = Field(default=True)


class ClientCreate(ClientBase):
    """Schema for creating a client."""
    pass


class ClientUpdate(BaseModel):
    """Schema for updating a client."""
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    contact_person: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
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
