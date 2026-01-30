"""
Tests for exception handling and error responses.
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.core.exceptions import (
    AppException,
    ValidationException,
    NotFoundException,
    AuthenticationException,
    AuthorizationException,
    ConflictException,
    RateLimitException,
    AgentNotFoundException,
    ClientNotFoundException,
    VehicleNotFoundException,
    OrderNotFoundException,
    RouteNotFoundException,
    PlanNotFoundException,
    DuplicateExternalIdException,
    IdempotencyConflictException,
    ExternalServiceException,
    OSRMException,
    VROOMException,
    OptimizationException,
    InsufficientDataException,
    ConfigurationException,
    register_exception_handlers,
)


class TestAppException:
    """Tests for base AppException class."""

    def test_default_values(self):
        """Test default exception values."""
        exc = AppException()
        assert exc.status_code == 500
        assert exc.error_code == "INTERNAL_ERROR"
        assert exc.message == "An unexpected error occurred"
        assert exc.details is None

    def test_custom_message(self):
        """Test exception with custom message."""
        exc = AppException(message="Custom error message")
        assert exc.message == "Custom error message"

    def test_custom_details(self):
        """Test exception with details."""
        details = {"field": "value", "count": 42}
        exc = AppException(details=details)
        assert exc.details == details

    def test_to_response(self):
        """Test conversion to error response."""
        exc = AppException(message="Test error", details={"key": "value"})
        response = exc.to_response(request_id="test-req-123")

        assert response.error.code == "INTERNAL_ERROR"
        assert response.error.message == "Test error"
        assert response.error.status_code == 500
        assert response.error.request_id == "test-req-123"
        assert response.error.details == {"key": "value"}
        assert "Z" in response.error.timestamp  # ISO format with Z suffix


class TestValidationException:
    """Tests for ValidationException."""

    def test_default_values(self):
        """Test default validation exception."""
        exc = ValidationException()
        assert exc.status_code == 400
        assert exc.error_code == "VALIDATION_ERROR"

    def test_custom_message(self):
        """Test validation exception with custom message."""
        exc = ValidationException(message="Invalid email format")
        assert exc.message == "Invalid email format"


class TestNotFoundException:
    """Tests for NotFoundException and its subclasses."""

    def test_base_not_found(self):
        """Test base NotFoundException."""
        exc = NotFoundException()
        assert exc.status_code == 404
        assert exc.error_code == "NOT_FOUND"

    def test_agent_not_found(self):
        """Test AgentNotFoundException."""
        exc = AgentNotFoundException("agent-123")
        assert exc.status_code == 404
        assert exc.error_code == "AGENT_NOT_FOUND"
        assert "agent-123" in exc.message
        assert exc.details == {"agent_id": "agent-123"}

    def test_client_not_found(self):
        """Test ClientNotFoundException."""
        exc = ClientNotFoundException("client-456")
        assert exc.status_code == 404
        assert exc.error_code == "CLIENT_NOT_FOUND"
        assert "client-456" in exc.message
        assert exc.details == {"client_id": "client-456"}

    def test_vehicle_not_found(self):
        """Test VehicleNotFoundException."""
        exc = VehicleNotFoundException("vehicle-789")
        assert exc.status_code == 404
        assert exc.error_code == "VEHICLE_NOT_FOUND"
        assert "vehicle-789" in exc.message

    def test_order_not_found(self):
        """Test OrderNotFoundException."""
        exc = OrderNotFoundException("order-abc")
        assert exc.status_code == 404
        assert exc.error_code == "ORDER_NOT_FOUND"
        assert "order-abc" in exc.message

    def test_route_not_found(self):
        """Test RouteNotFoundException."""
        exc = RouteNotFoundException("route-xyz")
        assert exc.status_code == 404
        assert exc.error_code == "ROUTE_NOT_FOUND"
        assert "route-xyz" in exc.message

    def test_plan_not_found(self):
        """Test PlanNotFoundException."""
        exc = PlanNotFoundException("plan-001")
        assert exc.status_code == 404
        assert exc.error_code == "PLAN_NOT_FOUND"
        assert "plan-001" in exc.message


class TestConflictException:
    """Tests for ConflictException and its subclasses."""

    def test_base_conflict(self):
        """Test base ConflictException."""
        exc = ConflictException()
        assert exc.status_code == 409
        assert exc.error_code == "CONFLICT"

    def test_duplicate_external_id(self):
        """Test DuplicateExternalIdException."""
        exc = DuplicateExternalIdException("Agent", "ERP-001")
        assert exc.status_code == 409
        assert exc.error_code == "DUPLICATE_EXTERNAL_ID"
        assert "Agent" in exc.message
        assert "ERP-001" in exc.message
        assert exc.details == {"resource_type": "Agent", "external_id": "ERP-001"}

    def test_idempotency_conflict(self):
        """Test IdempotencyConflictException."""
        exc = IdempotencyConflictException("idem-key-123")
        assert exc.status_code == 409
        assert exc.error_code == "IDEMPOTENCY_CONFLICT"
        assert "idem-key-123" in exc.message


class TestAuthExceptions:
    """Tests for authentication and authorization exceptions."""

    def test_authentication_exception(self):
        """Test AuthenticationException."""
        exc = AuthenticationException()
        assert exc.status_code == 401
        assert exc.error_code == "AUTHENTICATION_FAILED"

    def test_authorization_exception(self):
        """Test AuthorizationException."""
        exc = AuthorizationException()
        assert exc.status_code == 403
        assert exc.error_code == "PERMISSION_DENIED"


class TestRateLimitException:
    """Tests for RateLimitException."""

    def test_rate_limit_exception(self):
        """Test RateLimitException."""
        exc = RateLimitException()
        assert exc.status_code == 429
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"


class TestExternalServiceExceptions:
    """Tests for external service exceptions."""

    def test_external_service_exception(self):
        """Test base ExternalServiceException."""
        exc = ExternalServiceException()
        assert exc.status_code == 502
        assert exc.error_code == "EXTERNAL_SERVICE_ERROR"

    def test_osrm_exception(self):
        """Test OSRMException."""
        exc = OSRMException(message="OSRM connection timeout")
        assert exc.status_code == 502
        assert exc.error_code == "OSRM_ERROR"
        assert "timeout" in exc.message

    def test_vroom_exception(self):
        """Test VROOMException."""
        exc = VROOMException(message="VROOM solver failed")
        assert exc.status_code == 502
        assert exc.error_code == "VROOM_ERROR"


class TestOptimizationException:
    """Tests for OptimizationException."""

    def test_optimization_exception(self):
        """Test OptimizationException."""
        exc = OptimizationException(
            message="No feasible solution found",
            details={"vehicles": 2, "orders": 100}
        )
        assert exc.status_code == 422
        assert exc.error_code == "OPTIMIZATION_FAILED"
        assert exc.details == {"vehicles": 2, "orders": 100}


class TestInsufficientDataException:
    """Tests for InsufficientDataException."""

    def test_insufficient_data(self):
        """Test InsufficientDataException."""
        exc = InsufficientDataException("orders", required=10, provided=3)
        assert exc.status_code == 400
        assert exc.error_code == "INSUFFICIENT_DATA"
        assert "10" in exc.message
        assert "3" in exc.message
        assert exc.details == {"resource": "orders", "required": 10, "provided": 3}


class TestConfigurationException:
    """Tests for ConfigurationException."""

    def test_configuration_exception(self):
        """Test ConfigurationException."""
        exc = ConfigurationException(message="Missing SECRET_KEY")
        assert exc.status_code == 500
        assert exc.error_code == "CONFIGURATION_ERROR"
        assert "SECRET_KEY" in exc.message


class TestExceptionHandlerRegistration:
    """Tests for exception handler registration."""

    def test_register_handlers(self):
        """Test that handlers are registered correctly."""
        app = FastAPI()
        register_exception_handlers(app)

        # Verify handlers are registered
        assert AppException in app.exception_handlers
        assert Exception in app.exception_handlers
