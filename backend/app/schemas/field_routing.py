"""
Schemas for Routing Services.

Based on Google OR-Tools routing specification.
TSP - Traveling Salesperson Problem (Salesperson Plan)
VRPC - Vehicle Routing Problem with Capacity Constraints
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================
# Enums
# ============================================================


class TSPKind(str, Enum):
    """Kind of TSP service."""

    AUTO = "auto"
    SINGLE = "single"


class Intensity(str, Enum):
    """Intensity of visits at each point."""

    THREE_TIMES_A_WEEK = "THREE_TIMES_A_WEEK"  # 3 visits/week (Mon, Wed, Fri)
    TWO_TIMES_A_WEEK = "TWO_TIMES_A_WEEK"  # 2 visits/week (Mon, Thu)
    ONCE_A_WEEK = "ONCE_A_WEEK"  # 1 visit/week
    ONCE_IN_TWO_WEEKS = "ONCE_IN_TWO_WEEKS"  # 1 visit per 2 weeks
    ONCE_A_MONTH = "ONCE_A_MONTH"  # 1 visit per month


class VehicleType(str, Enum):
    """Type of vehicle."""

    CAR = "car"
    TRUCK = "truck"
    WALKING = "walking"
    CYCLING = "cycling"


# ============================================================
# TSP (Traveling Salesperson Problem) Schemas
# ============================================================


class TSPLocation(BaseModel):
    """Location for TSP service."""

    id: str = Field(
        ..., min_length=1, description="Unique location identifier"
    )
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    intensity: Intensity = Field(..., description="Visit intensity")
    visitDuration: int = Field(
        ..., ge=0, description="Visit duration in minutes"
    )
    workingDays: list[int] = Field(
        default=[1, 2, 3, 4, 5, 6],
        description="Working days (1=Mon, 6=Sat)",
    )

    @field_validator("workingDays")
    @classmethod
    def validate_working_days(cls, v: list[int]) -> list[int]:
        """Validate working days are 1-6."""
        for day in v:
            if day < 1 or day > 6:
                raise ValueError("Working days must be between 1 and 6")
        return v


class StartLocation(BaseModel):
    """Start location (depot) for TSP."""

    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")


class TSPRequest(BaseModel):
    """Request for TSP service."""

    kind: TSPKind = Field(..., description="Kind of service: auto or single")
    locations: list[TSPLocation] = Field(
        ..., min_length=1, description="Locations to visit"
    )
    startLocation: Optional[StartLocation] = Field(
        None, description="Start location (depot)"
    )


class DayRoute(BaseModel):
    """Route for a single day."""

    dayNumber: int = Field(..., ge=1, le=6, description="Day number (1-6)")
    route: list[str] = Field(
        ..., description="List of location IDs in visit order"
    )
    totalDuration: int = Field(
        ..., ge=0, description="Total duration in minutes"
    )
    totalDistance: float = Field(..., ge=0, description="Total distance in km")


class WeekPlan(BaseModel):
    """Plan for a single week."""

    weekNumber: int = Field(..., ge=1, le=4, description="Week number (1-4)")
    days: list[DayRoute] = Field(..., description="Daily routes")


class TSPSingleResponse(BaseModel):
    """Response for TSP single kind."""

    code: int = Field(..., description="Result code. 100 = success")
    weeks: Optional[list[WeekPlan]] = Field(
        None, description="4-week plan with daily routes"
    )
    error_text: Optional[str] = Field(
        None, description="Error description if code != 100"
    )


class TSPAutoResponse(BaseModel):
    """Response for TSP auto kind (multiple plans from clustering)."""

    code: int = Field(..., description="Result code. 100 = success")
    plans: Optional[list[list[WeekPlan]]] = Field(
        None, description="Multiple plans (one per cluster)"
    )
    error_text: Optional[str] = Field(
        None, description="Error description if code != 100"
    )


# ============================================================
# VRPC (Vehicle Routing Problem with Capacity) Schemas
# ============================================================


class VRPCDepot(BaseModel):
    """Depot location for VRPC service."""

    lat: str = Field(..., description="Latitude with precision 6")
    lng: str = Field(..., description="Longitude with precision 6")

    @field_validator("lat", "lng")
    @classmethod
    def validate_coordinate(cls, v: str) -> str:
        """Validate coordinate format."""
        try:
            float(v)
        except ValueError:
            raise ValueError("Coordinate must be a valid number string")
        return v


class VRPCPoint(BaseModel):
    """Delivery point for VRPC service."""

    lat: str = Field(..., description="Latitude with precision 6")
    lng: str = Field(..., description="Longitude with precision 6")
    weight: float = Field(..., ge=0, description="Weight of cargo")

    @field_validator("lat", "lng")
    @classmethod
    def validate_coordinate(cls, v: str) -> str:
        """Validate coordinate format."""
        try:
            float(v)
        except ValueError:
            raise ValueError("Coordinate must be a valid number string")
        return v


class VRPCVehicle(BaseModel):
    """Vehicle for VRPC service."""

    type: VehicleType = Field(..., description="Type of vehicle")
    capacity: float = Field(..., gt=0, description="Vehicle capacity")


class VRPCUrls(BaseModel):
    """OSRM URLs for different vehicle types."""

    car: Optional[str] = None
    truck: Optional[str] = None
    walking: Optional[str] = None
    cycling: Optional[str] = None


class VRPCRequest(BaseModel):
    """Request for VRPC service."""

    depot: VRPCDepot = Field(
        ..., description="Start/end location for vehicles"
    )
    points: list[VRPCPoint] = Field(
        ..., min_length=1, description="Delivery points"
    )
    vehicles: list[VRPCVehicle] = Field(
        ..., min_length=1, description="Available vehicles"
    )
    max_cycle_distance: Optional[float] = Field(
        None, description="Maximum distance per cycle in meters"
    )
    global_span_coefficient: Optional[int] = Field(
        30,
        ge=1,
        le=100,
        description="Balance distance vs time (1-100)",
    )
    urls: VRPCUrls = Field(..., description="OSRM URLs for vehicle types")


class VRPCLoop(BaseModel):
    """Single loop/trip for a vehicle."""

    route: list[int] = Field(..., description="List of point indexes to visit")
    distance: float = Field(..., description="Distance in meters")
    duration: float = Field(..., description="Duration in seconds")


class VRPCResponse(BaseModel):
    """Response for VRPC service."""

    code: int = Field(..., description="Result code. 100 = success")
    vehicles: Optional[list[list[VRPCLoop]]] = Field(
        None,
        description="Routes per vehicle. Each vehicle may have multiple loops",
    )
    total_distance: Optional[float] = Field(
        None, description="Total distance in meters"
    )
    total_duration: Optional[float] = Field(
        None, description="Total duration in seconds"
    )
    error_text: Optional[str] = Field(
        None, description="Error description if code != 100"
    )


# ============================================================
# Error Codes
# ============================================================


class ErrorCode:
    """Error code definitions."""

    SUCCESS = 100
    INVALID_INPUT_FORMAT = 101
    UNSUPPORTED_VEHICLE_TYPE = 102
    URL_NOT_FOUND_FOR_VEHICLE = 103
    OSRM_CONNECTION_ERROR = 104
    OSRM_MATRIX_ERROR = 105
    WEIGHT_EXCEEDS_CAPACITY = 106
    ARC_COST_NOT_SET = 107
    TIME_LIMIT_REACHED = 108
    NO_SOLUTION_FOUND = 109
    UNEXPECTED_ERROR = 110
    OUT_OF_MEMORY = 111
