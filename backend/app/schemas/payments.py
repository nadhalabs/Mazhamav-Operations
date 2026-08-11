import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from app.models import PaymentMethod, PaymentStatus


class PaymentSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    display_name: str
    upi_id: str | None
    bank_reference: str | None
    active: bool
    has_qr: bool
    updated_at: datetime


class PaymentReceivedIn(BaseModel):
    payment_method: PaymentMethod


class PaymentReceiptOut(BaseModel):
    id: uuid.UUID
    payment_status: PaymentStatus
    payment_method: PaymentMethod | None
    payment_received_by: uuid.UUID | None
    payment_received_at: datetime | None


class PaymentQrContext(BaseModel):
    display_name: str
    upi_id: str | None
    bank_reference: str | None
    qr_url: str
    sale_id: uuid.UUID | None = None
    sale_number: str | None = None
    amount_due: Decimal | None = None
    retailer: str | None = None
    payment_status: PaymentStatus | None = None
