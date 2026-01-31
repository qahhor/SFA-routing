"""
Pydantic schemas for API request/response models.
"""

from app.schemas.agent import (
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentUpdate,
)
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
from app.schemas.field_routing import (
    DayRoute,
    ErrorCode,
    Intensity,
    StartLocation,
    TSPAutoResponse,
    TSPKind,
    TSPLocation,
    TSPRequest,
    TSPSingleResponse,
    VehicleType,
    VRPCDepot,
    VRPCLoop,
    VRPCPoint,
    VRPCRequest,
    VRPCResponse,
    VRPCUrls,
    VRPCVehicle,
    WeekPlan,
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
    # TSP (Traveling Salesperson Problem)
    "TSPKind",
    "Intensity",
    "TSPLocation",
    "StartLocation",
    "TSPRequest",
    "DayRoute",
    "WeekPlan",
    "TSPAutoResponse",
    "TSPSingleResponse",
    # VRPC (Vehicle Routing Problem with Capacity)
    "VehicleType",
    "VRPCDepot",
    "VRPCPoint",
    "VRPCVehicle",
    "VRPCUrls",
    "VRPCRequest",
    "VRPCLoop",
    "VRPCResponse",
    # Error Codes
    "ErrorCode",
]
