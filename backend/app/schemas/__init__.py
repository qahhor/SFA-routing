"""
Pydantic schemas for API request/response models.
"""
from app.schemas.agent import (
    AgentCreate, AgentUpdate, AgentResponse, AgentListResponse
)
from app.schemas.client import (
    ClientCreate, ClientUpdate, ClientResponse, ClientListResponse
)
from app.schemas.planning import (
    WeeklyPlanRequest, WeeklyPlanResponse, DailyPlanResponse,
    VisitPlanResponse, VisitPlanUpdate
)
from app.schemas.delivery import (
    DeliveryOptimizeRequest, DeliveryOptimizeResponse,
    DeliveryRouteResponse, DeliveryRouteStopResponse,
    DeliveryOrderResponse
)
from app.schemas.vehicle import (
    VehicleCreate, VehicleUpdate, VehicleResponse, VehicleListResponse
)

__all__ = [
    # Agent
    "AgentCreate", "AgentUpdate", "AgentResponse", "AgentListResponse",
    # Client
    "ClientCreate", "ClientUpdate", "ClientResponse", "ClientListResponse",
    # Planning
    "WeeklyPlanRequest", "WeeklyPlanResponse", "DailyPlanResponse",
    "VisitPlanResponse", "VisitPlanUpdate",
    # Delivery
    "DeliveryOptimizeRequest", "DeliveryOptimizeResponse",
    "DeliveryRouteResponse", "DeliveryRouteStopResponse",
    "DeliveryOrderResponse",
    # Vehicle
    "VehicleCreate", "VehicleUpdate", "VehicleResponse", "VehicleListResponse",
]
