"""
API Client model for external service authentication.

Supports multi-tenant access with:
- API Key authentication
- Rate limiting per client
- Usage quotas
- Region restrictions
"""

import secrets
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class ClientTier(str, Enum):
    """API Client subscription tiers."""

    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class APIClient(Base, UUIDMixin, TimestampMixin):
    """
    API Client for external service access.

    Each external project connecting to the Route Optimization Service
    gets an API Client with its own API key and rate limits.
    """

    __tablename__ = "api_clients"

    # Client identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # API Key (hashed)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    api_key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)  # First 8 chars for identification

    # Subscription tier
    tier: Mapped[str] = mapped_column(String(20), default=ClientTier.FREE.value, nullable=False)

    # Rate limiting
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_points_per_request: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    monthly_quota: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)

    # Usage tracking
    requests_this_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_request_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    quota_reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Restrictions
    allowed_regions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # ["uzbekistan", "kazakhstan"]
    allowed_endpoints: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # ["/planning/*", "/delivery/*"]
    ip_whitelist: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # ["192.168.1.*"]

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Contact info
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    @classmethod
    def generate_api_key(cls) -> tuple[str, str, str]:
        """
        Generate a new API key.

        Returns:
            Tuple of (full_key, key_prefix, key_hash)
        """
        import hashlib

        # Generate 32-byte random key, encode as hex (64 chars)
        full_key = f"roaas_{secrets.token_hex(32)}"
        key_prefix = full_key[:8]
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()

        return full_key, key_prefix, key_hash

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash an API key for comparison."""
        import hashlib

        return hashlib.sha256(api_key.encode()).hexdigest()

    def verify_api_key(self, api_key: str) -> bool:
        """Verify if provided API key matches."""
        return self.api_key_hash == self.hash_api_key(api_key)

    def get_tier_limits(self) -> dict:
        """Get rate limits based on tier."""
        tier_limits = {
            ClientTier.FREE.value: {
                "rate_limit_per_minute": 10,
                "max_points_per_request": 50,
                "monthly_quota": 1000,
            },
            ClientTier.BASIC.value: {
                "rate_limit_per_minute": 60,
                "max_points_per_request": 200,
                "monthly_quota": 10000,
            },
            ClientTier.PRO.value: {
                "rate_limit_per_minute": 300,
                "max_points_per_request": 1000,
                "monthly_quota": 100000,
            },
            ClientTier.ENTERPRISE.value: {
                "rate_limit_per_minute": 1000,
                "max_points_per_request": 5000,
                "monthly_quota": -1,  # Unlimited
            },
        }
        return tier_limits.get(self.tier, tier_limits[ClientTier.FREE.value])

    def is_rate_limited(self) -> bool:
        """Check if client has exceeded rate limit."""
        # This would be checked with Redis in actual implementation
        return False

    def is_quota_exceeded(self) -> bool:
        """Check if monthly quota is exceeded."""
        if self.monthly_quota == -1:  # Unlimited
            return False
        return self.requests_this_month >= self.monthly_quota

    def __repr__(self) -> str:
        return f"<APIClient {self.name} ({self.api_key_prefix}...)>"
