import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.dependencies import operations_viewer, staff_only
from app.database import get_db
from app.models import Product, RequestStatus, StockRequest, User, UserRole
from app.schemas import RequestDecision, RequestFulfil, StockRequestCreate, StockRequestListRow, StockRequestOut
from app.services.inventory import staff_balance
from app.services.stock_requests import decide_request, fulfil_request

router = APIRouter(prefix="/stock-requests", tags=["stock requests"])


@router.post("", response_model=StockRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(payload: StockRequestCreate, actor: User = Depends(staff_only), db: Session = Depends(get_db)):
    product = db.scalar(select(Product).where(Product.id == payload.product_id, Product.active.is_(True)))
    if not product: raise HTTPException(422, "Active product not found")
    existing = db.scalar(select(StockRequest).where(StockRequest.staff_id == actor.id, StockRequest.product_id == payload.product_id, StockRequest.status.in_([RequestStatus.pending, RequestStatus.approved])))
    if existing: raise HTTPException(409, "An open request already exists for this product")
    request = StockRequest(staff_id=actor.id, product_id=payload.product_id, requested_quantity=payload.requested_quantity, notes=payload.notes)
    db.add(request)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "An open request already exists for this product")
    db.refresh(request); return request


@router.get("/mine", response_model=list[StockRequestListRow])
def my_requests(limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), actor: User = Depends(staff_only), db: Session = Depends(get_db)):
    return _rows(db, select(StockRequest).where(StockRequest.staff_id == actor.id).order_by(StockRequest.requested_at.desc()).offset(offset).limit(limit))


@router.get("", response_model=list[StockRequestListRow])
def all_requests(request_status: RequestStatus | None = None, limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0), _: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    stmt = select(StockRequest).order_by(StockRequest.requested_at.desc())
    if request_status: stmt = stmt.where(StockRequest.status == request_status)
    return _rows(db, stmt.offset(offset).limit(limit))


def _rows(db: Session, stmt):
    requests = db.scalars(stmt).all()
    users = {u.id: u for u in db.scalars(select(User).where(User.role == UserRole.staff)).all()}
    products = {p.id: p for p in db.scalars(select(Product)).all()}
    old_before = datetime.now(timezone.utc) - timedelta(hours=48)
    result = []
    for r in requests:
        balance = staff_balance(db, r.staff_id, r.product_id)
        base = StockRequestOut.model_validate(r).model_dump()
        result.append(StockRequestListRow(**base, staff_name=users[r.staff_id].full_name, product_name=products[r.product_id].name, unit_name=products[r.product_id].unit_name, current_staff_balance=balance, is_low_stock=balance <= Decimal("5"), is_old_pending=r.status == RequestStatus.pending and r.requested_at.replace(tzinfo=r.requested_at.tzinfo or timezone.utc) < old_before))
    return result


@router.post("/{request_id}/approve", response_model=StockRequestOut)
def approve(request_id: uuid.UUID, payload: RequestDecision, actor: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    return decide_request(db, request_id, actor, RequestStatus.approved, payload.note)


@router.post("/{request_id}/reject", response_model=StockRequestOut)
def reject(request_id: uuid.UUID, payload: RequestDecision, actor: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    return decide_request(db, request_id, actor, RequestStatus.rejected, payload.note)


@router.post("/{request_id}/fulfil", response_model=StockRequestOut)
def fulfil(request_id: uuid.UUID, payload: RequestFulfil, actor: User = Depends(operations_viewer), db: Session = Depends(get_db)):
    return fulfil_request(db, request_id, actor, payload.fulfilled_quantity)
