"""
Pydantic schemas for API Client management.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class APIClientBase(BaseModel):
    """Base schema for API Client."""
    name: str = Field(..., min_length=3, max_length=255, description="Client name")
    description: Optional[str] = Field(None, max_length=1000, description="Client description")
    contact_email: Optional[EmailStr] = Field(None, description="Contact email")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for notifications")


class APIClientCreate(APIClientBase):
    """Schema for creating a new API Client."""
    tier: str = Field("free", description="Subscription tier: free, basic, pro, enterprise")
    allowed_regions: Optional[list[str]] = Field(None, description="Allowed regions")
    ip_whitelist: Optional[list[str]] = Field(None, description="IP whitelist")


class APIClientUpdate(BaseModel):
    """Schema for updating an API Client."""
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    tier: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    webhook_url: Optional[str] = None
    allowed_regions: Optional[list[str]] = None
    ip_whitelist: Optional[list[str]] = None
    is_active: Optional[bool] = None


class APIClientResponse(APIClientBase):
    """Schema for API Client response (without sensitive data)."""
    id: UUID
    tier: str
    api_key_prefix: str = Field(..., description="First 8 characters of API key")
    rate_limit_per_minute: int
    max_points_per_request: int
    monthly_quota: int
    requests_this_month: int
    is_active: bool
    allowed_regions: Optional[list[str]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_request_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class APIClientWithKey(APIClientResponse):
    """Schema for API Client with full API key (only returned on creation)."""
    api_key: str = Field(..., description="Full API key - save this, it won't be shown again!")


class APIKeyRegenerate(BaseModel):
    """Response schema for API key regeneration."""
    api_key: str = Field(..., description="New API key - save this, it won't be shown again!")
    api_key_prefix: str


class APIClientUsage(BaseModel):
    """Schema for API Client usage statistics."""
    client_id: UUID
    client_name: str
    tier: str
    requests_this_month: int
    monthly_quota: int
    quota_percentage: float
    rate_limit_per_minute: int
    last_request_at: Optional[datetime] = None


class APIClientList(BaseModel):
    """Schema for paginated list of API Clients."""
    items: list[APIClientResponse]
    total: int
    page: int
    page_size: int
    pages: int
