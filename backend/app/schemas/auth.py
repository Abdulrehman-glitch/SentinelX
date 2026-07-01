from typing import Literal

from pydantic import BaseModel, Field

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
    access_token: str
    token_type: str = "bearer"
    user: UserPublicResponse


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str
