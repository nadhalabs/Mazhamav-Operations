import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import PaymentStatus, RequestStatus, UserRole
from app.schemas.common import LoginIn, UserCreate


class UserUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=20)
    role: UserRole
    active: bool

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str):
        return LoginIn.valid_phone(value)

    @field_validator("role")
    @classmethod
    def manageable_role(cls, value: UserRole):
        if value == UserRole.owner:
            raise ValueError("owner role cannot be assigned here")
        return value


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str):
        return UserCreate.strong_password(value)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self


class StaffListRow(BaseModel):
    id: uuid.UUID
    full_name: str
    phone: str
    role: UserRole
    active: bool
    current_stock: Decimal
    sales_today: Decimal
    sales_this_month: Decimal
    last_activity: datetime | None
    created_at: datetime


class StaffStockDetail(BaseModel):
    product_id: uuid.UUID
    product: str
    unit_name: str
    total_issued: Decimal
    total_sold: Decimal
    total_returned: Decimal
    adjustments: Decimal
    current_stock: Decimal


class StaffProductPerformance(BaseModel):
    product_id: uuid.UUID
    product: str
    quantity_sold: Decimal
    revenue: Decimal


class StaffRetailerActivity(BaseModel):
    retailer_id: uuid.UUID
    retailer: str
    quantity_sold: Decimal
    sales_value: Decimal
    last_sale_date: date


class StaffRecentSale(BaseModel):
    id: uuid.UUID
    sale_number: str
    retailer: str
    quantity: Decimal
    total: Decimal
    payment_status: PaymentStatus
    sale_date: date
    created_at: datetime


class StaffRequestDetail(BaseModel):
    id: uuid.UUID
    product: str
    requested_quantity: Decimal
    fulfilled_quantity: Decimal | None
    status: RequestStatus
    requested_at: datetime


class StaffPerformance(BaseModel):
    sales_today: Decimal
    sales_this_week: Decimal
    sales_this_month: Decimal
    quantity_sold: Decimal
    sales_value: Decimal
    retailers_served: int
    pending_payment_value: Decimal
    current_stock: Decimal
    pending_stock_requests: int


class StaffDetail(BaseModel):
    id: uuid.UUID
    full_name: str
    phone: str
    role: UserRole
    active: bool
    created_at: datetime
    range: dict[str, str]
    performance: StaffPerformance
    stock: list[StaffStockDetail]
    product_performance: list[StaffProductPerformance]
    retailer_activity: list[StaffRetailerActivity]
    area_performance: list[dict]
    recent_sales: list[StaffRecentSale]
    stock_requests: list[StaffRequestDetail]
