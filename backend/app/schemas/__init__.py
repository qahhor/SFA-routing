"""
Pydantic schemas for API request/response models.
"""

from app.schemas.agent import AgentCreate, AgentListResponse, AgentResponse, AgentUpdate
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    Token,
    TokenPayload,
    UserCreate,
    UserCreateByAdmin,
    UserListResponse,
    UserResponse,
    UserUpdate,
    UserUpdatePassword,
)
from app.schemas.client import (
    ClientCreate,
    ClientListResponse,
    ClientResponse,
    ClientUpdate,
)
from app.schemas.delivery import (
    DeliveryOptimizeRequest,
    DeliveryOptimizeResponse,
    DeliveryOrderResponse,
    DeliveryRouteResponse,
    DeliveryRouteStopResponse,
)
from app.schemas.planning import (
    DailyPlanResponse,
    VisitPlanResponse,
    VisitPlanUpdate,
    WeeklyPlanRequest,
    WeeklyPlanResponse,
)
from app.schemas.vehicle import (
    VehicleCreate,
    VehicleListResponse,
    VehicleResponse,
    VehicleUpdate,
)

__all__ = [
    # Agent
    "AgentCreate",
    "AgentUpdate",
    "AgentResponse",
    "AgentListResponse",
    # Client
    "ClientCreate",
    "ClientUpdate",
    "ClientResponse",
    "ClientListResponse",
    # Planning
    "WeeklyPlanRequest",
    "WeeklyPlanResponse",
    "DailyPlanResponse",
    "VisitPlanResponse",
    "VisitPlanUpdate",
    # Delivery
    "DeliveryOptimizeRequest",
    "DeliveryOptimizeResponse",
    "DeliveryRouteResponse",
    "DeliveryRouteStopResponse",
    "DeliveryOrderResponse",
    # Vehicle
    "VehicleCreate",
    "VehicleUpdate",
    "VehicleResponse",
    "VehicleListResponse",
    # Auth
    "Token",
    "TokenPayload",
    "RefreshTokenRequest",
    "UserCreate",
    "UserCreateByAdmin",
    "UserUpdate",
    "UserUpdatePassword",
    "UserResponse",
    "UserListResponse",
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "RegisterResponse",
]
