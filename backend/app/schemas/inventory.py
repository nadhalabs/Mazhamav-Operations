import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models import MovementType


class IssueStockIn(BaseModel):
    staff_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0, decimal_places=3)
    note: str | None = Field(default=None, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ReturnStockIn(BaseModel):
    staff_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0, decimal_places=3)
    reason: str = Field(min_length=3, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=128)


class AdjustmentIn(BaseModel):
    product_id: uuid.UUID
    staff_id: uuid.UUID | None = None
    quantity: Decimal = Field(decimal_places=3)
    reason: str = Field(min_length=3, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=128)

    @field_validator("quantity")
    @classmethod
    def nonzero_quantity(cls, value: Decimal):
        if value == 0:
            raise ValueError("quantity must not be zero")
        return value


class WarehouseIn(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0, decimal_places=3)
    note: str | None = Field(default=None, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=128)


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    product_id: uuid.UUID
    staff_id: uuid.UUID | None
    movement_type: MovementType
    quantity: Decimal
    notes: str | None
    created_by: uuid.UUID
    created_at: datetime


class StaffStockRow(BaseModel):
    staff_id: uuid.UUID
    staff_name: str
    product_id: uuid.UUID
    product_name: str
    unit_name: str
    total_issued: Decimal
    total_sold: Decimal
    total_returned: Decimal
    adjustments: Decimal
    current_balance: Decimal


class MyStockRow(BaseModel):
    product_id: uuid.UUID
    product_name: str
    unit_name: str
    stock_received: Decimal
    sold: Decimal
    returned: Decimal
    adjustments: Decimal
    current_stock: Decimal


class WarehouseStockRow(BaseModel):
    product_id: uuid.UUID
    product_name: str
    unit_name: str
    warehouse_in: Decimal
    issued: Decimal
    returned: Decimal
    adjustments: Decimal
    current_balance: Decimal
