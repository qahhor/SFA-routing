"""
Health check endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.osrm_client import osrm_client
from app.services.vroom_solver import vroom_solver

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Basic health check."""
    return {"status": "healthy"}


@router.get("/health/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Detailed health check including dependencies."""
    checks = {
        "api": "healthy",
        "database": "unknown",
        "osrm": "unknown",
        "vroom": "unknown",
    }

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"

    # Check OSRM
    try:
        if await osrm_client.health_check():
            checks["osrm"] = "healthy"
        else:
            checks["osrm"] = "unhealthy"
    except Exception as e:
        checks["osrm"] = f"unhealthy: {str(e)}"

    # Check VROOM
    try:
        if await vroom_solver.health_check():
            checks["vroom"] = "healthy"
        else:
            checks["vroom"] = "unhealthy"
    except Exception as e:
        checks["vroom"] = f"unhealthy: {str(e)}"

    overall = "healthy" if all(
        v == "healthy" for v in checks.values()
    ) else "degraded"

    return {
        "status": overall,
        "checks": checks,
    }
