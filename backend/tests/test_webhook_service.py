"""
Tests for webhook service with HMAC signatures.
"""
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.webhook_service import WebhookService, WebhookDeliveryResult


class TestWebhookSignature:
    """Tests for HMAC signature generation and verification."""

    def test_generate_signature(self):
        """Test signature generation."""
        secret = "test-secret-key"
        payload = '{"event": "test", "data": {}}'
        timestamp = 1704067200  # 2024-01-01 00:00:00 UTC

        signature = WebhookService.generate_signature(secret, payload, timestamp)

        # Signature should be a hex string
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in signature)

    def test_signature_deterministic(self):
        """Test that same inputs produce same signature."""
        secret = "test-secret"
        payload = '{"key": "value"}'
        timestamp = 1704067200

        sig1 = WebhookService.generate_signature(secret, payload, timestamp)
        sig2 = WebhookService.generate_signature(secret, payload, timestamp)

        assert sig1 == sig2

    def test_signature_different_secrets(self):
        """Test that different secrets produce different signatures."""
        payload = '{"key": "value"}'
        timestamp = 1704067200

        sig1 = WebhookService.generate_signature("secret1", payload, timestamp)
        sig2 = WebhookService.generate_signature("secret2", payload, timestamp)

        assert sig1 != sig2

    def test_signature_different_payloads(self):
        """Test that different payloads produce different signatures."""
        secret = "test-secret"
        timestamp = 1704067200

        sig1 = WebhookService.generate_signature(secret, '{"a": 1}', timestamp)
        sig2 = WebhookService.generate_signature(secret, '{"b": 2}', timestamp)

        assert sig1 != sig2

    def test_signature_different_timestamps(self):
        """Test that different timestamps produce different signatures."""
        secret = "test-secret"
        payload = '{"key": "value"}'

        sig1 = WebhookService.generate_signature(secret, payload, 1704067200)
        sig2 = WebhookService.generate_signature(secret, payload, 1704067201)

        assert sig1 != sig2

    def test_verify_signature_valid(self):
        """Test verification of valid signature."""
        secret = "test-secret"
        payload = '{"event": "test"}'
        timestamp = int(time.time())

        signature = WebhookService.generate_signature(secret, payload, timestamp)

        assert WebhookService.verify_signature(
            secret, payload, timestamp, signature
        ) is True

    def test_verify_signature_invalid(self):
        """Test verification rejects invalid signature."""
        secret = "test-secret"
        payload = '{"event": "test"}'
        timestamp = int(time.time())

        assert WebhookService.verify_signature(
            secret, payload, timestamp, "invalid-signature"
        ) is False

    def test_verify_signature_wrong_secret(self):
        """Test verification rejects wrong secret."""
        payload = '{"event": "test"}'
        timestamp = int(time.time())

        signature = WebhookService.generate_signature("secret1", payload, timestamp)

        assert WebhookService.verify_signature(
            "secret2", payload, timestamp, signature
        ) is False

    def test_verify_signature_modified_payload(self):
        """Test verification rejects modified payload."""
        secret = "test-secret"
        timestamp = int(time.time())

        signature = WebhookService.generate_signature(
            secret, '{"original": true}', timestamp
        )

        assert WebhookService.verify_signature(
            secret, '{"modified": true}', timestamp, signature
        ) is False

    def test_verify_signature_expired_timestamp(self):
        """Test verification rejects expired timestamp."""
        secret = "test-secret"
        payload = '{"event": "test"}'
        # Timestamp from 10 minutes ago (beyond 5 minute tolerance)
        old_timestamp = int(time.time()) - 600

        signature = WebhookService.generate_signature(secret, payload, old_timestamp)

        assert WebhookService.verify_signature(
            secret, payload, old_timestamp, signature, tolerance_seconds=300
        ) is False

    def test_verify_signature_within_tolerance(self):
        """Test verification accepts timestamp within tolerance."""
        secret = "test-secret"
        payload = '{"event": "test"}'
        # Timestamp from 2 minutes ago (within 5 minute tolerance)
        recent_timestamp = int(time.time()) - 120

        signature = WebhookService.generate_signature(secret, payload, recent_timestamp)

        assert WebhookService.verify_signature(
            secret, payload, recent_timestamp, signature, tolerance_seconds=300
        ) is True

    def test_verify_signature_future_timestamp(self):
        """Test verification rejects future timestamp beyond tolerance."""
        secret = "test-secret"
        payload = '{"event": "test"}'
        # Timestamp 10 minutes in the future
        future_timestamp = int(time.time()) + 600

        signature = WebhookService.generate_signature(secret, payload, future_timestamp)

        assert WebhookService.verify_signature(
            secret, payload, future_timestamp, signature, tolerance_seconds=300
        ) is False


class TestWebhookDeliveryResult:
    """Tests for WebhookDeliveryResult."""

    def test_success_result(self):
        """Test successful delivery result."""
        result = WebhookDeliveryResult(
            subscription_id="sub-123",
            url="https://example.com/webhook",
            success=True,
            status_code=200,
            attempts=1,
            duration_ms=150.5,
        )

        assert result.subscription_id == "sub-123"
        assert result.url == "https://example.com/webhook"
        assert result.success is True
        assert result.status_code == 200
        assert result.attempts == 1
        assert result.duration_ms == 150.5
        assert result.error is None

    def test_failure_result(self):
        """Test failed delivery result."""
        result = WebhookDeliveryResult(
            subscription_id="sub-456",
            url="https://example.com/webhook",
            success=False,
            error="Connection timeout",
            attempts=3,
            duration_ms=10500.0,
        )

        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.attempts == 3
        assert result.status_code is None


class TestWebhookServiceConfiguration:
    """Tests for WebhookService configuration."""

    def test_default_configuration(self):
        """Test default service configuration."""
        service = WebhookService()

        assert service.MAX_RETRIES == 3
        assert service.RETRY_DELAYS == [1, 2, 4]
        assert service.TIMEOUT_SECONDS == 10.0

    def test_retry_delays_match_retries(self):
        """Test retry delays list matches max retries."""
        service = WebhookService()

        assert len(service.RETRY_DELAYS) == service.MAX_RETRIES


class TestWebhookHeaders:
    """Tests for webhook headers construction."""

    def test_header_format(self):
        """Test signature header format matches Stripe-style."""
        secret = "whsec_test123"
        payload = '{"event": "optimization.completed"}'
        timestamp = 1704067200

        signature = WebhookService.generate_signature(secret, payload, timestamp)

        # The header value should be sha256=<hex_signature>
        header_value = f"sha256={signature}"

        assert header_value.startswith("sha256=")
        assert len(header_value) == 71  # "sha256=" (7) + 64 hex chars
