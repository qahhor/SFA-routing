"""
Pydantic schemas for async job tracking.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Status of an async job."""
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"


class JobType(str, Enum):
    """Type of optimization job."""
    WEEKLY_PLAN = "weekly_plan"
    DELIVERY_OPTIMIZE = "delivery_optimize"
    DELIVERY_ROUTES = "delivery_routes"
    ROUTE_OPTIMIZATION = "route_optimization"
    BULK_IMPORT = "bulk_import"


class JobCreate(BaseModel):
    """Schema for creating a new job."""
    job_type: JobType
    params: dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    """Schema for job submission response."""
    job_id: str = Field(..., description="Celery task ID")
    job_type: JobType
    status: JobStatus = JobStatus.PENDING
    message: str = "Job submitted successfully"
    status_url: Optional[str] = Field(None, description="URL to check job status")
    check_url: Optional[str] = Field(None, description="URL to check job status")
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Optional[float] = Field(None, ge=0, le=100, description="Progress percentage")
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Schema for job status check."""
    job_id: str
    job_type: Optional[JobType] = None
    status: JobStatus
    progress: Optional[float] = Field(None, ge=0, le=100, description="Progress percentage")
    result: Optional[dict] = Field(None, description="Job result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    runtime_seconds: Optional[float] = None


class JobListResponse(BaseModel):
    """Schema for list of jobs."""
    items: list[JobResponse]
    total: int


class WeeklyPlanJobParams(BaseModel):
    """Parameters for weekly plan generation job."""
    agent_id: UUID
    week_start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="ISO date format")
    week_number: int = Field(1, ge=1, le=2)


class DeliveryOptimizeJobParams(BaseModel):
    """Parameters for delivery optimization job."""
    order_ids: list[UUID]
    vehicle_ids: list[UUID]
    route_date: str = Field(..., description="ISO format date (YYYY-MM-DD)")


class DeliveryRoutesJobParams(BaseModel):
    """Parameters for delivery routes optimization job."""
    order_ids: list[UUID] = Field(..., min_length=1)
    vehicle_ids: list[UUID] = Field(..., min_length=1)
    route_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="ISO date format")


class AsyncJobRequest(BaseModel):
    """Request to start an async optimization job."""
    job_type: JobType
    params: dict[str, Any]


class AsyncJobResponse(BaseModel):
    """Response after starting an async job."""
    job_id: str
    job_type: JobType
    status: JobStatus = JobStatus.PENDING
    message: str = "Job queued successfully"
    check_url: str = Field(..., description="URL to check job status")
