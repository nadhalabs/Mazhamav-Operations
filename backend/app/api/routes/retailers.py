import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.api.dependencies import current_user, operations_viewer
from app.core.config import get_settings
from app.database import get_db
from app.models import Retailer, User, UserRole
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


@router.delete("/{retailer_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_retailer(retailer_id: uuid.UUID, _: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    retailer = db.get(Retailer, retailer_id)
    if not retailer: raise HTTPException(404, "Retailer not found")
    retailer.active = False; db.commit()
