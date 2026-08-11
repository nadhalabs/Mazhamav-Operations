import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.models import RequestStatus


class StockRequestCreate(BaseModel):
    product_id: uuid.UUID
    requested_quantity: Decimal = Field(gt=0, decimal_places=3)
    notes: str | None = Field(default=None, max_length=1000)


class StockRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    staff_id: uuid.UUID
    product_id: uuid.UUID
    requested_quantity: Decimal
    status: RequestStatus
    requested_at: datetime
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    fulfilled_quantity: Decimal | None
    fulfilled_by: uuid.UUID | None
    fulfilled_at: datetime | None
    notes: str | None
    review_notes: str | None


class StockRequestListRow(StockRequestOut):
    staff_name: str
    product_name: str
    unit_name: str
    current_staff_balance: Decimal
    is_low_stock: bool
    is_old_pending: bool


class RequestDecision(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class RequestFulfil(BaseModel):
    fulfilled_quantity: Decimal | None = Field(default=None, gt=0, decimal_places=3)
