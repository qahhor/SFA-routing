"""
API routes module.
"""

from fastapi import APIRouter

from app.api.routes import (
    agents,
    api_clients,
    auth,
    bulk,
    clients,
    delivery,
    export,
    health,
    jobs,
    planning,
    realtime,
    vehicles,
    webhooks,
)

api_router = APIRouter()

# Include all route modules
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(api_clients.router)  # API Client management
api_router.include_router(jobs.router)  # Async job tracking
api_router.include_router(agents.router)
api_router.include_router(clients.router)
api_router.include_router(vehicles.router)
api_router.include_router(planning.router)
api_router.include_router(delivery.router)
api_router.include_router(export.router)
api_router.include_router(bulk.router)
api_router.include_router(webhooks.router)
api_router.include_router(realtime.router)
