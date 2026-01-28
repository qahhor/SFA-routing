"""
Authentication and User schemas.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


# ============== Token Schemas ==============

class Token(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # user_id
    role: UserRole
    exp: Optional[int] = None


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


# ============== User Schemas ==============

class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr = Field(..., description="User email address")
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    role: UserRole = Field(default=UserRole.AGENT, description="User role")


class UserCreate(UserBase):
    """Schema for creating a user (registration)."""
    password: str = Field(..., min_length=8, max_length=100, description="Password")
    agent_id: Optional[UUID] = Field(None, description="Link to Agent if applicable")


class UserCreateByAdmin(UserCreate):
    """Schema for admin creating a user."""
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    agent_id: Optional[UUID] = None


class UserUpdatePassword(BaseModel):
    """Schema for changing password."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


class UserResponse(BaseModel):
    """Schema for user response."""
    id: UUID
    email: EmailStr
    full_name: str
    phone: Optional[str]
    role: UserRole
    is_active: bool
    is_superuser: bool
    agent_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Schema for user list response."""
    items: list[UserResponse]
    total: int
    page: int
    size: int


# ============== Login Schemas ==============

class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


# ============== Registration Schemas ==============

class RegisterRequest(BaseModel):
    """Public registration request (creates agent role by default)."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)


class RegisterResponse(BaseModel):
    """Registration response."""
    user: UserResponse
    message: str = "Registration successful. Please login."
