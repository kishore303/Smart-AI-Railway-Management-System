from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    username: str = Field(description="username or email")
    password: str


class UserBrief(BaseModel):
    id: int
    name: str
    email: str
    role: str
    department: str
    department_id: int
    is_active: bool

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserBrief
    expires_in: int


class MeResponse(UserBrief):
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ForgotPasswordRequest(BaseModel):
    email: str


class ForgotPasswordResponse(BaseModel):
    message: str
    # In dev we expose reset_token for testing; production would send email
    reset_token: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=64)


class ResetPasswordResponse(BaseModel):
    message: str


class TokenPayload(BaseModel):
    user_id: int
    email: str
    department: str
    department_id: int
    role: str
    iat: int
    exp: int
