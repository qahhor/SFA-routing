"""
API routes module.
"""

from fastapi import APIRouter

from app.api.routes import (
    field_routing,
    health,
)

# Main API router (mounted at /api/v1)
api_router = APIRouter()

# Include health check
api_router.include_router(health.router)

# Include TSP router at /api/v1 root
api_router.include_router(field_routing.tsp_router)

# VRPC router to be mounted at /vrpc (root level)
vrpc_router = field_routing.vrpc_router
