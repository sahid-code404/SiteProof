import uuid

from pydantic import EmailStr, Field

from app.models.user import UserRole
from app.schemas.base import APIModel


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class AuthUser(APIModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser
