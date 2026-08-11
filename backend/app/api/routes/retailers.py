import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.api.dependencies import current_user, operations_viewer
from app.core.config import get_settings
from app.database import get_db
from app.models import Retailer, Sale, SaleItem, User, UserRole
from sqlalchemy import func
from app.schemas import RetailerIn, RetailerOut, RetailerUpdate

router = APIRouter(prefix="/retailers", tags=["retailers"])


@router.get("", response_model=list[RetailerOut])
def search_retailers(q: str | None = Query(default=None, max_length=100), area: str | None = None, district: str | None = None, include_inactive: bool = False, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), actor: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Retailer)
    if actor.role == UserRole.staff or not include_inactive:
        stmt = stmt.where(Retailer.active.is_(True))
    if q:
        term = f"%{q}%"
        stmt = stmt.where(or_(Retailer.shop_name.ilike(term), Retailer.contact_name.ilike(term), Retailer.phone.ilike(term), Retailer.area.ilike(term)))
    if area: stmt = stmt.where(Retailer.area.ilike(f"%{area}%"))
    if district: stmt = stmt.where(Retailer.district.ilike(f"%{district}%"))
    return db.scalars(stmt.order_by(Retailer.shop_name).offset(offset).limit(limit)).all()


@router.post("", response_model=RetailerOut, status_code=status.HTTP_201_CREATED)
def create_retailer(payload: RetailerIn, actor: User = Depends(current_user), db: Session = Depends(get_db)):
    if actor.role == UserRole.staff and not get_settings().staff_can_create_retailers:
        raise HTTPException(403, "Staff retailer creation is disabled")
    retailer = Retailer(**payload.model_dump())
    db.add(retailer); db.commit(); db.refresh(retailer)
    return retailer


@router.patch("/{retailer_id}", response_model=RetailerOut)
def update_retailer(retailer_id: uuid.UUID, payload: RetailerUpdate, _: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    retailer = db.get(Retailer, retailer_id)
    if not retailer: raise HTTPException(404, "Retailer not found")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(retailer, key, value)
    db.commit(); db.refresh(retailer)
    return retailer


@router.get("/{retailer_id}")
def retailer_detail(retailer_id: uuid.UUID, _: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    retailer = db.get(Retailer, retailer_id)
    if not retailer: raise HTTPException(404, "Retailer not found")
    value, quantity, last = db.execute(select(func.coalesce(func.sum(Sale.total), 0), func.coalesce(func.sum(SaleItem.quantity), 0), func.max(Sale.sale_date)).outerjoin(SaleItem, SaleItem.sale_id == Sale.id).where(Sale.retailer_id == retailer_id)).one()
    # Sale totals are aggregated separately to avoid multiplying multi-item sales.
    value = db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.retailer_id == retailer_id)) or 0
    staff = db.execute(select(User.id, User.full_name, func.sum(Sale.total)).join(Sale, Sale.staff_id == User.id).where(Sale.retailer_id == retailer_id).group_by(User.id, User.full_name).order_by(func.sum(Sale.total).desc())).all()
    recent = db.scalars(select(Sale).where(Sale.retailer_id == retailer_id).order_by(Sale.created_at.desc()).limit(20)).all()
    return {"id": retailer.id, "shop_name": retailer.shop_name, "contact_name": retailer.contact_name, "phone": retailer.phone, "address": retailer.address, "area": retailer.area, "district": retailer.district, "active": retailer.active, "total_purchase_value": str(value), "total_quantity": str(quantity), "last_purchase_date": last, "staff": [{"id": str(uid), "name": name, "sales_value": str(total)} for uid, name, total in staff], "recent_sales": [{"id": str(s.id), "sale_number": s.sale_number, "sale_date": s.sale_date, "total": str(s.total), "payment_status": s.payment_status.value} for s in recent]}


@router.delete("/{retailer_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_retailer(retailer_id: uuid.UUID, _: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    retailer = db.get(Retailer, retailer_id)
    if not retailer: raise HTTPException(404, "Retailer not found")
    retailer.active = False; db.commit()
