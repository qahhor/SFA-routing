"""
Vehicle schemas.
"""
from datetime import time, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VehicleBase(BaseModel):
    """Base vehicle schema."""
    name: str = Field(..., description="Vehicle name")
    license_plate: str = Field(..., description="License plate number")
    capacity_kg: Decimal = Field(..., gt=0, description="Weight capacity in kg")
    capacity_volume_m3: Optional[Decimal] = Field(
        None, gt=0, description="Volume capacity in m3"
    )
    start_latitude: Decimal = Field(..., description="Depot latitude")
    start_longitude: Decimal = Field(..., description="Depot longitude")
    end_latitude: Optional[Decimal] = Field(None, description="Return point latitude")
    end_longitude: Optional[Decimal] = Field(None, description="Return point longitude")
    work_start: time = Field(default=time(8, 0))
    work_end: time = Field(default=time(20, 0))
    cost_per_km: Optional[Decimal] = Field(default=Decimal("1.0"))
    fixed_cost: Optional[Decimal] = Field(default=Decimal("0"))
    driver_name: Optional[str] = Field(None)
    driver_phone: Optional[str] = Field(None)
    is_active: bool = Field(default=True)


class VehicleCreate(VehicleBase):
    """Schema for creating a vehicle."""
    pass


class VehicleUpdate(BaseModel):
    """Schema for updating a vehicle."""
    name: Optional[str] = None
    license_plate: Optional[str] = None
    capacity_kg: Optional[Decimal] = Field(None, gt=0)
    capacity_volume_m3: Optional[Decimal] = Field(None, gt=0)
    start_latitude: Optional[Decimal] = None
    start_longitude: Optional[Decimal] = None
    end_latitude: Optional[Decimal] = None
    end_longitude: Optional[Decimal] = None
    work_start: Optional[time] = None
    work_end: Optional[time] = None
    cost_per_km: Optional[Decimal] = None
    fixed_cost: Optional[Decimal] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    is_active: Optional[bool] = None


class VehicleResponse(VehicleBase):
    """Schema for vehicle response."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VehicleListResponse(BaseModel):
    """Schema for vehicle list response."""
    items: list[VehicleResponse]
    total: int
    page: int
    size: int
