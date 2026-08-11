import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models import UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    phone: str
    email: EmailStr | None
    role: UserRole
    active: bool
    created_at: datetime


class LoginIn(BaseModel):
    phone: str = Field(min_length=7, max_length=20)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str):
        compact = value.replace(" ", "").replace("-", "")
        if not (compact.lstrip("+").isdigit() and 7 <= len(compact.lstrip("+")) <= 15):
            raise ValueError("phone must contain 7 to 15 digits")
        return compact


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=20)
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.staff

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str):
        return LoginIn.valid_phone(value)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str):
        if not (any(c.islower() for c in value) and any(c.isupper() for c in value) and any(c.isdigit() for c in value) and any(not c.isalnum() for c in value)):
            raise ValueError("password must include upper, lower, number, and symbol")
        return value


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    sku: str = Field(min_length=1, max_length=64)
    unit_name: str = Field(default="packet", min_length=1, max_length=40)
    selling_price: Decimal = Field(ge=0, decimal_places=2)


class ProductOut(ProductIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    active: bool
    created_at: datetime
    updated_at: datetime
