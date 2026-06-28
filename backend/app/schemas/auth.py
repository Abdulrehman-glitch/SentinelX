from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserPublicResponse


class SignupRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["admin", "engineer", "viewer"] = "viewer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublicResponse


class MessageResponse(BaseModel):
    message: str