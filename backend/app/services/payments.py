import io
import re
import uuid
from datetime import datetime, timezone
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models import PaymentMethod, PaymentSettings, PaymentStatus, Sale, User
from app.services.media_storage import get_media_storage

UPI_PATTERN = re.compile(r"^[A-Za-z0-9._-]{2,}@[A-Za-z0-9.-]{2,}$")


class PaymentService:
    """Static company QR service boundary; future providers can implement this contract."""

    def save_settings(self, db: Session, actor: User, display_name: str, upi_id: str | None, bank_reference: str | None, active: bool, upload: bytes | None) -> PaymentSettings:
        if upi_id and not UPI_PATTERN.fullmatch(upi_id):
            raise HTTPException(422, "UPI ID format is invalid")
        settings = db.scalar(select(PaymentSettings).where(PaymentSettings.singleton_key == 1).with_for_update())
        if not settings:
            settings = PaymentSettings(singleton_key=1, display_name=display_name, updated_by=actor.id)
            db.add(settings)
        settings.display_name = display_name.strip(); settings.upi_id = upi_id.strip() if upi_id else None
        settings.bank_reference = bank_reference.strip() if bank_reference else None
        settings.active = active; settings.updated_by = actor.id
        if upload is not None:
            normalized = self._normalize_qr(upload)
            key = f"payment-qr/{uuid.uuid4()}.png"
            get_media_storage().put(key, normalized, "image/png")
            settings.qr_storage_key = key
        if active and not settings.qr_storage_key:
            raise HTTPException(422, "An active payment configuration requires a QR image")
        db.commit(); db.refresh(settings)
        return settings

    def _normalize_qr(self, data: bytes) -> bytes:
        if not data or len(data) > get_settings().max_qr_upload_bytes:
            raise HTTPException(422, "QR image is empty or exceeds the upload limit")
        try:
            image = Image.open(io.BytesIO(data)); image.verify()
            image = Image.open(io.BytesIO(data)); image.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise HTTPException(422, "Uploaded file is not a valid image")
        if image.format not in {"PNG", "JPEG", "WEBP"}:
            raise HTTPException(422, "QR image must be PNG, JPEG, or WebP")
        if min(image.size) < 100 or max(image.size) > 4096:
            raise HTTPException(422, "QR image dimensions must be between 100 and 4096 pixels")
        image = image.convert("RGB")
        output = io.BytesIO(); image.save(output, format="PNG", optimize=True)
        return output.getvalue()

    def mark_received(self, db: Session, sale_id: uuid.UUID, actor: User, method: PaymentMethod) -> Sale:
        sale = db.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
        if not sale: raise HTTPException(404, "Sale not found")
        if sale.staff_id != actor.id: raise HTTPException(403, "Staff may only update payments for their own sales")
        if sale.payment_status == PaymentStatus.paid:
            return sale
        sale.payment_status = PaymentStatus.paid; sale.payment_method = method
        sale.payment_received_by = actor.id; sale.payment_received_at = datetime.now(timezone.utc)
        db.commit(); db.refresh(sale)
        return sale


payment_service = PaymentService()
