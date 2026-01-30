"""
Standardized exception handling for API-first design.

Provides consistent error responses across all endpoints with:
- Unique error codes for client-side handling
- Request tracking via request_id
- Detailed error messages with context
- HTTP status code alignment
"""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Standardized error response format."""
    code: str
    message: str
    status_code: int
    timestamp: str
    request_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    help_url: Optional[str] = None


class ErrorResponse(BaseModel):
    """Wrapper for error responses."""
    error: ErrorDetail


# =============================================================================
# Base Exception Classes
# =============================================================================

class AppException(Exception):
    """Base exception for all application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        self.message = message or self.message
        self.details = details
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)

    def to_response(self, request_id: Optional[str] = None) -> ErrorResponse:
        """Convert exception to standardized error response."""
        return ErrorResponse(
            error=ErrorDetail(
                code=self.error_code,
                message=self.message,
                status_code=self.status_code,
                timestamp=datetime.utcnow().isoformat() + "Z",
                request_id=request_id,
                details=self.details,
            )
        )


# =============================================================================
# Client Errors (4xx)
# =============================================================================

class ValidationException(AppException):
    """Invalid input data."""
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "VALIDATION_ERROR"
    message = "Invalid input data"


class AuthenticationException(AppException):
    """Authentication failed."""
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTHENTICATION_FAILED"
    message = "Authentication required"


class AuthorizationException(AppException):
    """User lacks permission."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "PERMISSION_DENIED"
    message = "You do not have permission to perform this action"


class NotFoundException(AppException):
    """Resource not found."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"
    message = "Resource not found"


class ConflictException(AppException):
    """Resource conflict (duplicate, state conflict)."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"
    message = "Resource conflict"


class RateLimitException(AppException):
    """Rate limit exceeded."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Rate limit exceeded. Please retry later."


# =============================================================================
# Domain-Specific Exceptions
# =============================================================================

class AgentNotFoundException(NotFoundException):
    """Agent not found."""
    error_code = "AGENT_NOT_FOUND"
    message = "Agent not found"

    def __init__(self, agent_id: str):
        super().__init__(
            message=f"Agent with ID '{agent_id}' not found",
            details={"agent_id": agent_id}
        )


class ClientNotFoundException(NotFoundException):
    """Client not found."""
    error_code = "CLIENT_NOT_FOUND"
    message = "Client not found"

    def __init__(self, client_id: str):
        super().__init__(
            message=f"Client with ID '{client_id}' not found",
            details={"client_id": client_id}
        )


class VehicleNotFoundException(NotFoundException):
    """Vehicle not found."""
    error_code = "VEHICLE_NOT_FOUND"
    message = "Vehicle not found"

    def __init__(self, vehicle_id: str):
        super().__init__(
            message=f"Vehicle with ID '{vehicle_id}' not found",
            details={"vehicle_id": vehicle_id}
        )


class OrderNotFoundException(NotFoundException):
    """Delivery order not found."""
    error_code = "ORDER_NOT_FOUND"
    message = "Delivery order not found"

    def __init__(self, order_id: str):
        super().__init__(
            message=f"Delivery order with ID '{order_id}' not found",
            details={"order_id": order_id}
        )


class RouteNotFoundException(NotFoundException):
    """Delivery route not found."""
    error_code = "ROUTE_NOT_FOUND"
    message = "Delivery route not found"

    def __init__(self, route_id: str):
        super().__init__(
            message=f"Delivery route with ID '{route_id}' not found",
            details={"route_id": route_id}
        )


class PlanNotFoundException(NotFoundException):
    """Visit plan not found."""
    error_code = "PLAN_NOT_FOUND"
    message = "Visit plan not found"

    def __init__(self, plan_id: str):
        super().__init__(
            message=f"Visit plan with ID '{plan_id}' not found",
            details={"plan_id": plan_id}
        )


class DuplicateExternalIdException(ConflictException):
    """Duplicate external_id."""
    error_code = "DUPLICATE_EXTERNAL_ID"

    def __init__(self, resource_type: str, external_id: str):
        super().__init__(
            message=f"{resource_type} with external_id '{external_id}' already exists",
            details={"resource_type": resource_type, "external_id": external_id}
        )


class IdempotencyConflictException(ConflictException):
    """Duplicate idempotency key."""
    error_code = "IDEMPOTENCY_CONFLICT"
    message = "Request with this idempotency key was already processed"

    def __init__(self, idempotency_key: str):
        super().__init__(
            message=f"Request with idempotency key '{idempotency_key}' already processed",
            details={"idempotency_key": idempotency_key}
        )


# =============================================================================
# External Service Exceptions (5xx)
# =============================================================================

class ExternalServiceException(AppException):
    """External service error."""
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "EXTERNAL_SERVICE_ERROR"
    message = "External service unavailable"


class OSRMException(ExternalServiceException):
    """OSRM service error."""
    error_code = "OSRM_ERROR"
    message = "OSRM routing service unavailable"


class VROOMException(ExternalServiceException):
    """VROOM service error."""
    error_code = "VROOM_ERROR"
    message = "VROOM optimization service unavailable"


class OptimizationException(AppException):
    """Optimization failed."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "OPTIMIZATION_FAILED"
    message = "Route optimization failed"


class InsufficientDataException(ValidationException):
    """Not enough data for operation."""
    error_code = "INSUFFICIENT_DATA"

    def __init__(self, resource: str, required: int, provided: int):
        super().__init__(
            message=f"Insufficient {resource}: required {required}, provided {provided}",
            details={"resource": resource, "required": required, "provided": provided}
        )


# =============================================================================
# Configuration Exception
# =============================================================================

class ConfigurationException(AppException):
    """Configuration error - should fail at startup."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "CONFIGURATION_ERROR"
    message = "Application configuration error"


# =============================================================================
# Exception Handler Registration
# =============================================================================

def get_request_id(request: Request) -> str:
    """Extract or generate request ID."""
    return getattr(request.state, "request_id", None) or str(uuid4())


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle all application exceptions with standardized format."""
    request_id = get_request_id(request)
    response = exc.to_response(request_id=request_id)

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(),
        headers={"X-Request-ID": request_id},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    request_id = get_request_id(request)

    # Log the exception (would be captured by Sentry in production)
    import logging
    logger = logging.getLogger(__name__)
    logger.exception(f"Unhandled exception: {exc}", extra={"request_id": request_id})

    error = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            status_code=500,
            timestamp=datetime.utcnow().isoformat() + "Z",
            request_id=request_id,
        )
    )

    return JSONResponse(
        status_code=500,
        content=error.model_dump(),
        headers={"X-Request-ID": request_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
