from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    department_code: str
    role: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    department: str
    department_id: int
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserSelfUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=64)


class ChangePasswordResponse(BaseModel):
    message: str


class AdminUserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    is_active: Optional[bool] = None
    department_code: Optional[str] = None
    role: Optional[str] = None


class UserListItem(BaseModel):
    id: int
    name: str
    email: str
    role: str
    department: str
    department_id: int
    is_active: bool

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    total: int
    items: list[UserListItem]
    skip: int
    limit: int
