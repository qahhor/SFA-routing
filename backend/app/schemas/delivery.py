"""
Delivery optimization schemas.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.delivery_order import OrderStatus
from app.models.delivery_route import RouteStatus


class DeliveryOrderCreate(BaseModel):
    """Schema for creating a delivery order."""

    external_id: str
    client_id: UUID
    weight_kg: Decimal = Field(..., gt=0)
    volume_m3: Optional[Decimal] = Field(None, gt=0)
    items_count: Optional[int] = Field(None, ge=1)
    time_window_start: datetime
    time_window_end: datetime
    service_time_minutes: int = Field(default=5, ge=1, le=60)
    priority: int = Field(default=1, ge=1, le=10)
    notes: Optional[str] = None
    delivery_instructions: Optional[str] = None


class DeliveryOrderResponse(BaseModel):
    """Delivery order response."""

    id: UUID
    external_id: str
    client_id: UUID
    client_name: Optional[str] = None
    client_address: Optional[str] = None
    weight_kg: Decimal
    volume_m3: Optional[Decimal]
    items_count: Optional[int]
    time_window_start: datetime
    time_window_end: datetime
    service_time_minutes: int
    priority: int
    status: OrderStatus
    notes: Optional[str]
    delivery_instructions: Optional[str]
    delivered_at: Optional[datetime]
    failure_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeliveryOptimizeRequest(BaseModel):
    """Request for delivery route optimization."""

    order_ids: list[UUID] = Field(..., min_length=1)
    vehicle_ids: list[UUID] = Field(..., min_length=1)
    route_date: date


class DeliveryRouteStopResponse(BaseModel):
    """Stop in a delivery route."""

    id: UUID
    order_id: UUID
    order_external_id: Optional[str] = None
    client_id: UUID
    client_name: str
    client_address: str
    sequence_number: int
    distance_from_previous_km: float
    duration_from_previous_minutes: int
    planned_arrival: datetime
    planned_departure: datetime
    actual_arrival: Optional[datetime]
    actual_departure: Optional[datetime]
    latitude: float
    longitude: float
    weight_kg: float

    class Config:
        from_attributes = True


class DeliveryRouteResponse(BaseModel):
    """Delivery route response."""

    id: UUID
    vehicle_id: UUID
    vehicle_name: str
    vehicle_license_plate: str
    route_date: date
    total_distance_km: float
    total_duration_minutes: int
    total_weight_kg: float
    total_stops: int
    status: RouteStatus
    planned_start: Optional[datetime]
    planned_end: Optional[datetime]
    actual_start: Optional[datetime]
    actual_end: Optional[datetime]
    stops: list[DeliveryRouteStopResponse]
    geometry: Optional[dict] = Field(None, description="Route geometry (GeoJSON)")
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeliveryOptimizeResponse(BaseModel):
    """Response for delivery optimization."""

    routes: list[DeliveryRouteResponse]
    unassigned_orders: list[UUID]
    total_distance_km: float
    total_duration_minutes: int
    total_vehicles_used: int
    summary: dict
    optimized_at: datetime


class DeliveryRouteListResponse(BaseModel):
    """Delivery route list response."""

    items: list[DeliveryRouteResponse]
    total: int
    date: date
