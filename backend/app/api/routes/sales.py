import uuid
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.dependencies import current_user, staff_only
from app.database import get_db
from app.models import PaymentStatus, Product, Retailer, Sale, SaleItem, User, UserRole
from app.schemas import SaleCreate, SaleListRow, SaleOut, StaffHomeOut
from app.services.inventory import stock_totals
from app.services.sales import create_sale
from app.core.time import business_today

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("/options")
def sale_options(actor: User = Depends(staff_only), db: Session = Depends(get_db)):
    totals, _ = stock_totals(db)
    products = db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all()
    retailers = db.scalars(select(Retailer).where(Retailer.active.is_(True)).order_by(Retailer.shop_name).limit(200)).all()
    return {"products": [{"id": str(p.id), "name": p.name, "sku": p.sku, "unit_name": p.unit_name, "selling_price": str(p.selling_price), "available": str(totals[(actor.id, p.id)]["issued"] - totals[(actor.id, p.id)]["sold"] - totals[(actor.id, p.id)]["returned"] + totals[(actor.id, p.id)]["adjustments"])} for p in products], "retailers": [{"id": str(r.id), "shop_name": r.shop_name, "area": r.area, "district": r.district, "phone": r.phone} for r in retailers]}


@router.post("", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
def record_sale(payload: SaleCreate, actor: User = Depends(staff_only), db: Session = Depends(get_db)):
    return create_sale(db, actor, payload)


def _sale_rows(db: Session, stmt):
    sales = db.scalars(stmt.options()).unique().all()
    return [SaleListRow(id=s.id, sale_number=s.sale_number, sale_date=s.sale_date, staff_id=s.staff_id, staff_name=s.staff.full_name, retailer_id=s.retailer_id, retailer_name=s.retailer.shop_name, total_quantity=sum((i.quantity for i in s.items), Decimal("0")), total=s.total, payment_status=s.payment_status, payment_method=s.payment_method, created_at=s.created_at) for s in sales]


@router.get("", response_model=list[SaleListRow])
def sale_history(date_from: date | None = None, date_to: date | None = None, staff_id: uuid.UUID | None = None, retailer_id: uuid.UUID | None = None, product_id: uuid.UUID | None = None, payment_status: PaymentStatus | None = None, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), actor: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Sale).order_by(Sale.created_at.desc())
    if actor.role == UserRole.staff: stmt = stmt.where(Sale.staff_id == actor.id)
    elif staff_id: stmt = stmt.where(Sale.staff_id == staff_id)
    if date_from: stmt = stmt.where(Sale.sale_date >= date_from)
    if date_to: stmt = stmt.where(Sale.sale_date <= date_to)
    if retailer_id: stmt = stmt.where(Sale.retailer_id == retailer_id)
    if payment_status: stmt = stmt.where(Sale.payment_status == payment_status)
    if product_id: stmt = stmt.join(SaleItem).where(SaleItem.product_id == product_id)
    return _sale_rows(db, stmt.offset(offset).limit(limit))


@router.get("/staff-home", response_model=StaffHomeOut)
def staff_home(actor: User = Depends(staff_only), db: Session = Depends(get_db)):
    today = business_today()
    today_sales = db.scalars(select(Sale).where(Sale.staff_id == actor.id, Sale.sale_date == today)).all()
    pending = db.scalars(select(Sale).where(Sale.staff_id == actor.id, Sale.payment_status == PaymentStatus.pending)).all()
    totals, _ = stock_totals(db)
    current_stock = sum((v["issued"] - v["sold"] - v["returned"] + v["adjustments"] for (staff_id, _), v in totals.items() if staff_id == actor.id), Decimal("0"))
    recent = _sale_rows(db, select(Sale).where(Sale.staff_id == actor.id).order_by(Sale.created_at.desc()).limit(5))
    return StaffHomeOut(today_quantity_sold=sum((item.quantity for sale in today_sales for item in sale.items), Decimal("0")), today_sales_value=sum((sale.total for sale in today_sales), Decimal("0.00")), current_total_stock=current_stock, pending_payments_count=len(pending), pending_payments_value=sum((sale.total for sale in pending), Decimal("0.00")), recent_sales=recent)
