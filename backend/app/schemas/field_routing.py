"""
Schemas for Routing Services.

Based on Google OR-Tools routing specification.
TSP - Traveling Salesperson Problem
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
    MANUAL = "manual"


class VisitIntensity(str, Enum):
    """Intensity of visits at each point."""

    THREE_TIMES_A_WEEK = "THREE_TIMES_A_WEEK"
    TWICE_A_WEEK = "TWICE_A_WEEK"
    ONCE_A_WEEK = "ONCE_A_WEEK"
    TWICE_A_MONTH = "TWICE_A_MONTH"
    ONCE_A_MONTH = "ONCE_A_MONTH"


class VehicleType(str, Enum):
    """Type of vehicle."""

    CAR = "car"
    TRUCK = "truck"
    WALKING = "walking"
    CYCLING = "cycling"


class Profile(str, Enum):
    """Profile for OSRM routing."""

    DRIVING = "driving"
    WALKING = "walking"
    CYCLING = "cycling"


# ============================================================
# TSP (Traveling Salesperson Problem) Schemas
# ============================================================


class TSPLocation(BaseModel):
    """Location for TSP service."""

    lat: str = Field(..., description="Latitude with precision 6")
    lng: str = Field(..., description="Longitude with precision 6")
    visit_duration: int = Field(..., ge=0, description="Visit duration in seconds")
    visit_intensity: VisitIntensity = Field(
        ..., description="Intensity of visits at this point"
    )

    @field_validator("lat", "lng")
    @classmethod
    def validate_coordinate(cls, v: str) -> str:
        """Validate coordinate format."""
        try:
            float(v)
        except ValueError:
            raise ValueError("Coordinate must be a valid number string")
        return v


class TSPData(BaseModel):
    """Data for TSP service (auto and single kinds)."""

    locations: list[TSPLocation] = Field(
        ..., min_length=1, description="List of points to visit"
    )
    map_url: str = Field(..., description="URL of OSRM server for distance matrix")
    profile: Profile = Field(..., description="Vehicle profile for routing")
    max_visit_limit_per_day: int = Field(
        ..., ge=1, le=50, description="Maximum points per day"
    )
    working_seconds_per_day: int = Field(
        ..., ge=3600, le=86400, description="Working hours in seconds"
    )


class TSPRequest(BaseModel):
    """Request for TSP service."""

    kind: TSPKind = Field(..., description="Kind of service: auto, single, or manual")
    data: TSPData = Field(..., description="Data for the service")


class TSPAutoResponse(BaseModel):
    """Response for TSP auto kind."""

    code: int = Field(..., description="Result code. 100 = success")
    plans: Optional[list[list[list[list[int]]]]] = Field(
        None,
        description="List of plans. Each plan contains 4 weeks of daily routes",
    )
    error_text: Optional[str] = Field(
        None, description="Error description if code != 100"
    )


class TSPSingleResponse(BaseModel):
    """Response for TSP single kind."""

    code: int = Field(..., description="Result code. 100 = success")
    routes: Optional[list[list[list[int]]]] = Field(
        None,
        description="Routes for 4 weeks. Each week has daily routes with location indexes",
    )
    ignored_locations: Optional[list[int]] = Field(
        None, description="Indexes of locations that couldn't be scheduled"
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

    depot: VRPCDepot = Field(..., description="Start/end location for vehicles")
    points: list[VRPCPoint] = Field(..., min_length=1, description="Delivery points")
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
        description="Balance between min total distance and min overall time (1-100)",
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
