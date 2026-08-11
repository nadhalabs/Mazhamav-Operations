import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models import PaymentMethod, PaymentStatus


class RetailerIn(BaseModel):
    shop_name: str = Field(min_length=2, max_length=160)
    contact_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    area: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=1000)

    @field_validator("city", "area", "district", mode="before")
    @classmethod
    def normalize_location(cls, value):
        if value is None: return None
        normalized = " ".join(str(value).split()).title()
        return normalized or None


class RetailerOut(RetailerIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    active: bool


class RetailerUpdate(BaseModel):
    shop_name: str | None = Field(default=None, min_length=2, max_length=160)
    contact_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    area: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=1000)
    active: bool | None = None

    @field_validator("city", "area", "district", mode="before")
    @classmethod
    def normalize_location(cls, value):
        if value is None: return None
        normalized = " ".join(str(value).split()).title()
        return normalized or None

    @model_validator(mode="after")
    def shop_name_cannot_be_null(self):
        if "shop_name" in self.model_fields_set and self.shop_name is None:
            raise ValueError("shop_name cannot be null")
        return self


class SaleItemIn(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0, decimal_places=3)


class SaleCreate(BaseModel):
    retailer_id: uuid.UUID | None = None
    new_retailer: RetailerIn | None = None
    items: list[SaleItemIn] = Field(min_length=1, max_length=50)
    payment_status: PaymentStatus
    payment_method: PaymentMethod | None = None
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_sale(self):
        if bool(self.retailer_id) == bool(self.new_retailer):
            raise ValueError("provide exactly one of retailer_id or new_retailer")
        if self.payment_status == PaymentStatus.paid and not self.payment_method:
            raise ValueError("payment_method is required for a paid sale")
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("combine duplicate products into one sale item")
        return self


class SaleItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal
    unit_price_snapshot: Decimal
    line_total: Decimal


class SaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sale_number: str
    staff_id: uuid.UUID
    retailer_id: uuid.UUID
    sale_date: date
    subtotal: Decimal
    total: Decimal
    payment_status: PaymentStatus
    payment_method: PaymentMethod | None
    notes: str | None
    created_at: datetime
    items: list[SaleItemOut]


class SaleListRow(BaseModel):
    id: uuid.UUID
    sale_number: str
    sale_date: date
    staff_id: uuid.UUID
    staff_name: str
    retailer_id: uuid.UUID
    retailer_name: str
    total_quantity: Decimal
    total: Decimal
    payment_status: PaymentStatus
    payment_method: PaymentMethod | None
    created_at: datetime


class StaffHomeOut(BaseModel):
    today_quantity_sold: Decimal
    today_sales_value: Decimal
    current_total_stock: Decimal
    pending_payments_count: int
    pending_payments_value: Decimal
    recent_sales: list[SaleListRow]
