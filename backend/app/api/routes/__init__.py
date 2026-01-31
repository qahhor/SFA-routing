"""
API routes module.
"""

from fastapi import APIRouter

from app.api.routes import (
    field_routing,
    health,
)

api_router = APIRouter()

# Include route modules
api_router.include_router(health.router)
api_router.include_router(field_routing.router)
