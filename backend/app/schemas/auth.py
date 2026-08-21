import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPublicResponse


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["admin", "engineer", "viewer"] = "viewer"


class LoginRequest(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    username: str | None = Field(default=None, min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    # The access token is short-lived and meant to be held in memory only.
    # The refresh token is NOT in this body — it is set as an HttpOnly cookie
    # so JavaScript can never read it.
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=900, description="Access-token lifetime in seconds.")
    user: UserPublicResponse


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class SessionResponse(BaseModel):
    id: uuid.UUID
    issued_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    rotation_counter: int
    user_agent: str | None
    ip_address: str | None

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    message: str
