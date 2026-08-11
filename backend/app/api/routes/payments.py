import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import current_user, owner_only, staff_only
from app.core.config import get_settings
from app.database import get_db
from app.models import PaymentSettings, Sale, User, UserRole
from app.schemas import PaymentQrContext, PaymentReceiptOut, PaymentReceivedIn, PaymentSettingsOut
from app.services.media_storage import get_media_storage
from app.services.payments import payment_service

router = APIRouter(prefix="/payments", tags=["payments"])


def settings_out(settings: PaymentSettings) -> PaymentSettingsOut:
    return PaymentSettingsOut(display_name=settings.display_name, upi_id=settings.upi_id, bank_reference=settings.bank_reference, active=settings.active, has_qr=bool(settings.qr_storage_key), updated_at=settings.updated_at)


@router.get("/settings", response_model=PaymentSettingsOut)
def get_payment_settings(_: User = Depends(owner_only), db: Session = Depends(get_db)):
    settings = db.scalar(select(PaymentSettings).where(PaymentSettings.singleton_key == 1))
    if not settings: raise HTTPException(404, "Payment settings have not been configured")
    return settings_out(settings)


@router.post("/settings", response_model=PaymentSettingsOut)
async def update_settings(display_name: str = Form(min_length=2, max_length=160), upi_id: str | None = Form(default=None, max_length=160), bank_reference: str | None = Form(default=None, max_length=1000), active: bool = Form(default=True), qr_image: UploadFile | None = File(default=None), actor: User = Depends(owner_only), db: Session = Depends(get_db)):
    upload = None
    if qr_image:
        if qr_image.content_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise HTTPException(422, "QR image must be PNG, JPEG, or WebP")
        upload = await qr_image.read(get_settings().max_qr_upload_bytes + 1)
    settings = payment_service.save_settings(db, actor, display_name, upi_id, bank_reference, active, upload)
    return settings_out(settings)


@router.get("/qr-context", response_model=PaymentQrContext)
def qr_context(sale_id: uuid.UUID | None = None, actor: User = Depends(current_user), db: Session = Depends(get_db)):
    settings = db.scalar(select(PaymentSettings).where(PaymentSettings.singleton_key == 1, PaymentSettings.active.is_(True)))
    if not settings or not settings.qr_storage_key: raise HTTPException(404, "Company payment QR is not currently available")
    context = {"display_name": settings.display_name, "upi_id": settings.upi_id, "bank_reference": settings.bank_reference, "qr_url": f"/api/v1/payments/qr-image?v={int(settings.updated_at.timestamp())}"}
    if sale_id:
        sale = db.get(Sale, sale_id)
        if not sale: raise HTTPException(404, "Sale not found")
        if actor.role == UserRole.staff and sale.staff_id != actor.id: raise HTTPException(403, "Sale is not assigned to this staff account")
        context.update({"sale_id": sale.id, "sale_number": sale.sale_number, "amount_due": sale.total if sale.payment_status.value == "pending" else 0, "retailer": sale.retailer.shop_name, "payment_status": sale.payment_status})
    return PaymentQrContext(**context)


@router.get("/qr-image")
def qr_image(actor: User = Depends(current_user), db: Session = Depends(get_db)):
    settings = db.scalar(select(PaymentSettings).where(PaymentSettings.singleton_key == 1))
    if not settings or not settings.qr_storage_key or (not settings.active and actor.role != UserRole.owner):
        raise HTTPException(404, "Company payment QR is not available")
    try: data, content_type = get_media_storage().get(settings.qr_storage_key)
    except (FileNotFoundError, KeyError): raise HTTPException(404, "Company payment QR image is unavailable")
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})


@router.post("/sales/{sale_id}/received", response_model=PaymentReceiptOut)
def mark_payment_received(sale_id: uuid.UUID, payload: PaymentReceivedIn, actor: User = Depends(staff_only), db: Session = Depends(get_db)):
    sale = payment_service.mark_received(db, sale_id, actor, payload.payment_method)
    return PaymentReceiptOut.model_validate(sale, from_attributes=True)
