"""
Async job management endpoints.

Provides API for:
- Submitting optimization jobs
- Checking job status
- Listing jobs for a client
- Cancelling jobs
"""
from datetime import datetime
from typing import Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.celery_app import celery_app
from app.core.auth import get_api_client
from app.models.api_client import APIClient
from app.schemas.job import (
    DeliveryRoutesJobParams,
    JobListResponse,
    JobResponse,
    JobStatus,
    JobStatusResponse,
    JobType,
    WeeklyPlanJobParams,
)
from app.tasks.optimization import (
    generate_weekly_plan_task,
    optimize_delivery_routes_task,
)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def celery_state_to_job_status(state: str) -> JobStatus:
    """Convert Celery task state to JobStatus."""
    state_map = {
        "PENDING": JobStatus.PENDING,
        "STARTED": JobStatus.STARTED,
        "SUCCESS": JobStatus.SUCCESS,
        "FAILURE": JobStatus.FAILURE,
        "REVOKED": JobStatus.REVOKED,
        "RETRY": JobStatus.STARTED,
        "RECEIVED": JobStatus.PENDING,
    }
    return state_map.get(state, JobStatus.PENDING)


@router.post(
    "/weekly-plan",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Weekly Plan Generation Job",
    description="Submit a background job to generate weekly plan for an agent. "
                "Returns job ID for status tracking.",
)
async def submit_weekly_plan_job(
    params: WeeklyPlanJobParams,
    api_client: APIClient = Depends(get_api_client),
):
    """Submit weekly plan generation as background job."""
    # Submit task to Celery
    task = generate_weekly_plan_task.apply_async(
        args=[
            str(params.agent_id),
            params.week_start_date,
            params.week_number,
        ],
        # Store client ID in task metadata for filtering
        headers={"client_id": str(api_client.id)},
    )

    return JobResponse(
        job_id=task.id,
        job_type=JobType.WEEKLY_PLAN,
        status=JobStatus.PENDING,
        message="Weekly plan generation job submitted",
        status_url=f"/api/v1/jobs/{task.id}",
    )


@router.post(
    "/delivery-routes",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Delivery Routes Optimization Job",
    description="Submit a background job to optimize delivery routes. "
                "Returns job ID for status tracking.",
)
async def submit_delivery_routes_job(
    params: DeliveryRoutesJobParams,
    api_client: APIClient = Depends(get_api_client),
):
    """Submit delivery routes optimization as background job."""
    # Check points limit
    total_points = len(params.order_ids)
    if total_points > api_client.max_points_per_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many orders. Maximum: {api_client.max_points_per_request}, "
                   f"Provided: {total_points}. Upgrade your tier for higher limits.",
        )

    # Submit task to Celery
    task = optimize_delivery_routes_task.apply_async(
        args=[
            [str(oid) for oid in params.order_ids],
            [str(vid) for vid in params.vehicle_ids],
            params.route_date,
        ],
        headers={"client_id": str(api_client.id)},
    )

    return JobResponse(
        job_id=task.id,
        job_type=JobType.DELIVERY_ROUTES,
        status=JobStatus.PENDING,
        message="Delivery routes optimization job submitted",
        status_url=f"/api/v1/jobs/{task.id}",
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get Job Status",
    description="Check the status of a submitted job. Poll this endpoint to track progress.",
)
async def get_job_status(
    job_id: str,
    api_client: APIClient = Depends(get_api_client),
):
    """Get status of a job by ID."""
    result = AsyncResult(job_id, app=celery_app)

    # Calculate runtime if task has started
    runtime = None
    started_at = None
    completed_at = None

    if result.date_done:
        completed_at = result.date_done

    # Build response
    response = JobStatusResponse(
        job_id=job_id,
        status=celery_state_to_job_status(result.state),
        started_at=started_at,
        completed_at=completed_at,
        runtime_seconds=runtime,
    )

    if result.state == "SUCCESS":
        response.result = result.result
        response.progress = 100.0
    elif result.state == "FAILURE":
        response.error = str(result.result) if result.result else "Unknown error"
    elif result.state == "STARTED":
        # Get progress from task meta if available
        if hasattr(result, "info") and isinstance(result.info, dict):
            response.progress = result.info.get("progress", 0)

    return response


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel Job",
    description="Attempt to cancel a pending or running job.",
)
async def cancel_job(
    job_id: str,
    api_client: APIClient = Depends(get_api_client),
):
    """Cancel a job by ID."""
    result = AsyncResult(job_id, app=celery_app)

    if result.state in ("SUCCESS", "FAILURE"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed job",
        )

    # Revoke the task
    celery_app.control.revoke(job_id, terminate=True)


@router.get(
    "",
    response_model=JobListResponse,
    summary="List Recent Jobs",
    description="List recent jobs for the authenticated client.",
)
async def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    api_client: APIClient = Depends(get_api_client),
):
    """
    List recent jobs.
    
    Note: This is a simplified implementation. In production,
    you'd store job metadata in a database for better querying.
    """
    # This is a placeholder - in production, store jobs in DB
    # For now, return empty list as Celery doesn't easily support
    # listing all tasks by client
    return JobListResponse(items=[], total=0)
