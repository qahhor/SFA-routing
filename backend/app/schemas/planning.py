"""
Planning schemas for SFA weekly planning.
"""
from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.visit_plan import VisitStatus


class WeeklyPlanRequest(BaseModel):
    """Request for generating weekly plan."""
    agent_id: UUID = Field(..., description="Agent ID")
    week_start_date: date = Field(..., description="Monday of the planning week")
    week_number: int = Field(default=1, ge=1, le=2, description="Week number in cycle")


class PlannedVisitResponse(BaseModel):
    """Planned visit in a daily plan."""
    client_id: UUID
    client_name: str
    client_address: Optional[str] = None
    sequence_number: int
    planned_time: time
    estimated_arrival: time
    estimated_departure: time
    distance_from_previous_km: float
    duration_from_previous_minutes: int
    latitude: float
    longitude: float


class DailyPlanResponse(BaseModel):
    """Daily plan response."""
    date: date
    day_of_week: str
    visits: list[PlannedVisitResponse]
    total_visits: int
    total_distance_km: float
    total_duration_minutes: int
    geometry: Optional[dict] = Field(None, description="Route geometry (GeoJSON)")


class WeeklyPlanResponse(BaseModel):
    """Weekly plan response."""
    agent_id: UUID
    agent_name: str
    week_start: date
    week_end: date
    daily_plans: list[DailyPlanResponse]
    total_visits: int
    total_distance_km: float
    total_duration_minutes: int
    generated_at: datetime


class VisitPlanResponse(BaseModel):
    """Visit plan response."""
    id: UUID
    agent_id: UUID
    client_id: UUID
    client_name: str
    client_address: str
    planned_date: date
    planned_time: time
    sequence_number: int
    status: VisitStatus
    distance_from_previous_km: Optional[float]
    duration_from_previous_minutes: Optional[int]
    actual_arrival_time: Optional[datetime]
    actual_departure_time: Optional[datetime]
    notes: Optional[str]
    skip_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VisitPlanUpdate(BaseModel):
    """Schema for updating a visit plan."""
    planned_date: Optional[date] = None
    planned_time: Optional[time] = None
    status: Optional[VisitStatus] = None
    actual_arrival_time: Optional[datetime] = None
    actual_departure_time: Optional[datetime] = None
    notes: Optional[str] = None
    skip_reason: Optional[str] = None


class VisitPlanListResponse(BaseModel):
    """Visit plan list response."""
    items: list[VisitPlanResponse]
    total: int
    date: date
