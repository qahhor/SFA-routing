"""
API routes module.
"""
from fastapi import APIRouter

from app.api.routes import agents, auth, clients, vehicles, planning, delivery, health, export

api_router = APIRouter()

# Include all route modules
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(agents.router)
api_router.include_router(clients.router)
api_router.include_router(vehicles.router)
api_router.include_router(planning.router)
api_router.include_router(delivery.router)
api_router.include_router(export.router)
