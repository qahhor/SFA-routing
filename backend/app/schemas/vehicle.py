"""
Vehicle schemas.
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
    PositiveDecimal,
)


class VehicleBase(BaseModel):
    """Base vehicle schema."""
    name: str = Field(..., description="Vehicle name", min_length=1, max_length=100)
    license_plate: str = Field(..., description="License plate number", min_length=1, max_length=20)
    capacity_kg: PositiveDecimal
    capacity_volume_m3: Optional[Decimal] = Field(
        None, gt=0, description="Volume capacity in m3"
    )
    start_latitude: Latitude
    start_longitude: Longitude
    end_latitude: LatitudeOptional = None
    end_longitude: LongitudeOptional = None
    work_start: time = Field(default=time(8, 0))
    work_end: time = Field(default=time(20, 0))
    cost_per_km: Optional[Decimal] = Field(default=Decimal("1.0"), ge=0)
    fixed_cost: Optional[Decimal] = Field(default=Decimal("0"), ge=0)
    driver_name: Optional[str] = Field(None, max_length=255)
    driver_phone: PhoneNumber = None
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


class VehicleCreate(VehicleBase):
    """Schema for creating a vehicle."""
    pass


class VehicleUpdate(BaseModel):
    """Schema for updating a vehicle."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    license_plate: Optional[str] = Field(None, min_length=1, max_length=20)
    capacity_kg: Optional[Decimal] = Field(None, gt=0)
    capacity_volume_m3: Optional[Decimal] = Field(None, gt=0)
    start_latitude: LatitudeOptional = None
    start_longitude: LongitudeOptional = None
    end_latitude: LatitudeOptional = None
    end_longitude: LongitudeOptional = None
    work_start: Optional[time] = None
    work_end: Optional[time] = None
    cost_per_km: Optional[Decimal] = Field(None, ge=0)
    fixed_cost: Optional[Decimal] = Field(None, ge=0)
    driver_name: Optional[str] = Field(None, max_length=255)
    driver_phone: PhoneNumber = None
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
